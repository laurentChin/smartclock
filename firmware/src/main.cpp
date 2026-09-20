// smartclock-audio : décodeur MP3 alimenté par le port série (Pi -> ESP32), sortie I2S vers un MAX98357A.
//
// Pi -> ESP32 : trames binaires  0xA5 | type | longueur (2 octets, petit-boutiste) | charge utile | somme de contrôle
//   1 AUDIO   octets MP3 (1024 max par trame)
//   2 START   nouvelle lecture : vide le tampon, préremplit puis démarre le décodage
//   3 STOP    arrête la lecture
//   4 VOLUME  1 octet, 0-100
//   5 PING    répond PONG
// ESP32 -> Pi : lignes de texte
//   BUF <octets libres> <octets audio reçus>   toutes les 100 ms pendant une lecture (contrôle de débit)
//   STATE idle|prebuffer|playing, EVT <...>, OK <...>, PONG <...>, BOOT <...>
//
// La somme de contrôle est celle de type + longueur + charge utile, modulo 256.

#include <Arduino.h>
#include "AudioFileSource.h"
#include "AudioGeneratorMP3.h"
#include "AudioOutputI2S.h"

static const int I2S_BCLK = 26;
static const int I2S_LRC  = 25;
static const int I2S_DOUT = 22;

static const uint32_t SERIAL_BAUD        = 921600;
static const size_t   RING_BYTES         = 24 * 1024;
static const size_t   PREBUFFER_BYTES    = 12 * 1024;   // ~0,75 s de MP3 à 128 kb/s
static const uint32_t UNDERRUN_WAIT_MS   = 300;
static const uint32_t BUF_REPORT_MS      = 100;
static const float    MAX_GAIN           = 1.0f;        // volume 100 = gain 1.0
static const size_t   MAX_PAYLOAD        = 1024;

enum : uint8_t { FRAME_MAGIC = 0xA5, T_AUDIO = 1, T_START = 2, T_STOP = 3, T_VOLUME = 4, T_PING = 5 };

// ---- Tampon circulaire ----
static uint8_t ring[RING_BYTES];
static size_t ringHead = 0, ringTail = 0, ringCount = 0;
static uint32_t audioBytesReceived = 0;

static size_t ringFree() { return RING_BYTES - ringCount; }

static bool ringPush(const uint8_t *data, size_t n) {
  if (n > ringFree()) return false;
  for (size_t i = 0; i < n; i++) { ring[ringHead] = data[i]; ringHead = (ringHead + 1) % RING_BYTES; }
  ringCount += n;
  return true;
}

static size_t ringPop(uint8_t *dst, size_t n) {
  if (n > ringCount) n = ringCount;
  for (size_t i = 0; i < n; i++) { dst[i] = ring[ringTail]; ringTail = (ringTail + 1) % RING_BYTES; }
  ringCount -= n;
  return n;
}

static void ringClear() { ringHead = ringTail = ringCount = 0; audioBytesReceived = 0; }

// ---- État ----
static AudioOutputI2S *out = nullptr;
static AudioGeneratorMP3 *mp3 = nullptr;
static bool streaming = false;
static bool prebuffering = false;
static int volume = 30;
static uint32_t overflowFrames = 0, badFrames = 0, underruns = 0;
static uint32_t maxDecodeUs = 0;   // plus longue durée d'un appel à mp3->loop() (diagnostic)
static unsigned long lastBufReport = 0;

static void applyVolume() { out->SetGain(MAX_GAIN * volume / 100.0f); }

static void sendBufReport() {
  Serial.printf("BUF %u %u\n", (unsigned)ringFree(), (unsigned)audioBytesReceived);
  lastBufReport = millis();
}

static void stopDecoder() {
  if (mp3) { mp3->stop(); delete mp3; mp3 = nullptr; }
}

// ---- Analyse des trames reçues ----
static void pumpSerial();

static void handleFrame(uint8_t type, const uint8_t *payload, uint16_t len) {
  switch (type) {
    case T_AUDIO:
      if (!streaming) return;
      if (ringPush(payload, len)) audioBytesReceived += len; else overflowFrames++;
      break;
    case T_START:
      maxDecodeUs = 0;
      stopDecoder();
      ringClear();
      streaming = true;
      prebuffering = true;
      Serial.println("STATE prebuffer");
      sendBufReport();
      break;
    case T_STOP:
      streaming = false;
      prebuffering = false;
      stopDecoder();
      ringClear();
      Serial.println("STATE idle");
      break;
    case T_VOLUME:
      if (len >= 1) {
        volume = payload[0] > 100 ? 100 : payload[0];
        applyVolume();
        Serial.printf("OK vol=%d\n", volume);
      }
      break;
    case T_PING:
      Serial.printf("PONG smartclock-audio 0.2 heap=%u overflow=%u bad=%u underrun=%u maxdec_us=%u\n",
                    (unsigned)ESP.getFreeHeap(), overflowFrames, badFrames, underruns, maxDecodeUs);
      break;
  }
}

static uint8_t fType, fSum;
static uint16_t fLen, fPos;
static uint8_t fBuf[MAX_PAYLOAD];
static enum { S_MAGIC, S_TYPE, S_LEN0, S_LEN1, S_PAYLOAD, S_SUM } fState = S_MAGIC;

static void feedByte(uint8_t b) {
  switch (fState) {
    case S_MAGIC:   if (b == FRAME_MAGIC) fState = S_TYPE; break;
    case S_TYPE:    fType = b; fSum = b; fState = S_LEN0; break;
    case S_LEN0:    fLen = b; fSum += b; fState = S_LEN1; break;
    case S_LEN1:
      fLen |= (uint16_t)b << 8; fSum += b; fPos = 0;
      if (fLen > MAX_PAYLOAD) { badFrames++; fState = S_MAGIC; }
      else fState = fLen ? S_PAYLOAD : S_SUM;
      break;
    case S_PAYLOAD:
      fBuf[fPos++] = b; fSum += b;
      if (fPos == fLen) fState = S_SUM;
      break;
    case S_SUM:
      fState = S_MAGIC;
      if (b == fSum) handleFrame(fType, fBuf, fLen); else badFrames++;
      break;
  }
}

static void pumpSerial() {
  int budget = 2048;
  while (budget-- > 0 && Serial.available()) feedByte((uint8_t)Serial.read());
}

// ---- Source de données du décodeur : le tampon circulaire ----
class RingSource : public AudioFileSource {
public:
  uint32_t read(void *data, uint32_t len) override {
    // Le décodeur s'arrête si on lui renvoie 0 octet : on attend brièvement l'arrivée de données.
    unsigned long t0 = millis();
    while (ringCount == 0 && streaming && millis() - t0 < UNDERRUN_WAIT_MS) {
      pumpSerial();
      if (ringCount == 0) delay(1);
    }
    size_t n = ringPop((uint8_t *)data, len);
    consumed += n;
    return n;
  }
  bool seek(int32_t, int) override { return false; }
  bool close() override { return true; }
  bool isOpen() override { return streaming; }
  uint32_t getSize() override { return 0; }
  uint32_t getPos() override { return consumed; }
  uint32_t consumed = 0;
};

static RingSource source;

static void startDecoder() {
  stopDecoder();
  source.consumed = 0;
  mp3 = new AudioGeneratorMP3();
  if (mp3->begin(&source, out)) {
    prebuffering = false;
    Serial.println("STATE playing");
  } else {
    stopDecoder();
    Serial.println("EVT decoder_start_failed");
  }
}

void setup() {
  Serial.setRxBufferSize(8192);
  Serial.begin(SERIAL_BAUD);
  Serial.println();
  Serial.printf("BOOT smartclock-audio 0.2 baud=%u\n", (unsigned)SERIAL_BAUD);

  out = new AudioOutputI2S(0, AudioOutputI2S::EXTERNAL_I2S, 48);
  out->SetPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);
  out->SetOutputModeMono(true);
  applyVolume();
}

void loop() {
  pumpSerial();
  if (!streaming) return;

  if (prebuffering && ringCount >= PREBUFFER_BYTES) startDecoder();

  if (mp3 && mp3->isRunning()) {
    uint32_t t0 = micros();
    bool ok = mp3->loop();
    uint32_t dt = micros() - t0;
    if (dt > maxDecodeUs) maxDecodeUs = dt;
    if (!ok) {
      underruns++;
      stopDecoder();
      prebuffering = true;
      Serial.println("EVT underrun");
      Serial.println("STATE prebuffer");
    }
  }

  if (millis() - lastBufReport >= BUF_REPORT_MS) sendBufReport();
}
