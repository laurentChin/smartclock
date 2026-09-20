# audio_link.py — liaison série avec l'ESP32 audio (protocole décrit dans firmware/src/main.cpp)
#
# Le Pi télécharge le flux radio (HTTP ou HTTPS), retire les métadonnées ICY et envoie les octets MP3
# à l'ESP32 par le port série, en respectant le contrôle de débit annoncé par ses messages "BUF".

import queue
import threading
import time

import requests
import serial

MAGIC = 0xA5
T_AUDIO, T_START, T_STOP, T_VOLUME, T_PING = 1, 2, 3, 4, 5

CHUNK_BYTES = 512
RESERVE_BYTES = 2048            # marge laissée libre dans le tampon de l'ESP32
MAX_IN_FLIGHT = 8192            # octets envoyés non encore comptés reçus : reste sous le tampon série de l'ESP32 (16 Ko)
RECONNECT_DELAY_S = 3.0
USER_AGENT = "smartclock/0.1"


def make_frame(frame_type, payload=b""):
    low, high = len(payload) & 0xFF, len(payload) >> 8
    checksum = (frame_type + low + high + sum(payload)) & 0xFF
    return bytes([MAGIC, frame_type, low, high]) + payload + bytes([checksum])


def parse_icy_title(block):
    """b"StreamTitle='Artiste - Titre';..." -> "Artiste - Titre" (None si absent)."""
    text = block.rstrip(b"\0").decode("utf-8", errors="replace")
    marker = "StreamTitle='"
    start = text.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = text.find("';", start)
    return text[start:end] if end >= 0 else text[start:]


def _read_exact(raw, n):
    buf = bytearray()
    while len(buf) < n:
        part = raw.read(n - len(buf))
        if not part:
            raise EOFError("flux interrompu")
        buf += part
    return bytes(buf)


class AudioLink:
    def __init__(self, port="/dev/ttyUSB0", baud=921600, on_metadata=None, on_event=None, on_input=None):
        self._port = port
        self._baud = baud
        self._on_metadata = on_metadata or (lambda title: None)
        self._on_event = on_event or (lambda line: None)
        self._on_input = on_input or (lambda line: None)   # "BTN main"…
        self._inputs = queue.Queue()
        self._serial = None
        self._write_lock = threading.Lock()
        self._cv = threading.Condition()
        self._free = 0              # octets libres annoncés par l'ESP32
        self._rx = 0                # octets audio reçus par l'ESP32 depuis START
        self._sent = 0              # octets audio envoyés depuis START
        self._awaiting_start = False
        self._pong = threading.Event()
        self._stream_stop = None
        self._stream_thread = None
        self.state = "idle"

    # ---- ouverture / fermeture ----

    def open(self, timeout=8.0):
        self._serial = serial.Serial(self._port, self._baud, timeout=0.2)
        threading.Thread(target=self._read_loop, daemon=True).start()
        threading.Thread(target=self._input_loop, daemon=True).start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:      # l'ouverture du port redémarre souvent l'ESP32
            self._write(make_frame(T_PING))
            if self._pong.wait(0.6):
                return
        raise TimeoutError("l'ESP32 audio ne répond pas")

    def close(self):
        self.stop()
        if self._serial:
            self._serial.close()
            self._serial = None

    # ---- commandes ----

    def play(self, url):
        self.stop()
        stop_event = threading.Event()
        self._stream_stop = stop_event
        self._stream_thread = threading.Thread(target=self._stream, args=(url, stop_event), daemon=True)
        self._stream_thread.start()

    def stop(self):
        if self._stream_stop:
            self._stream_stop.set()
            with self._cv:
                self._cv.notify_all()
        thread = self._stream_thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        self._stream_stop = self._stream_thread = None
        if self._serial:
            self._write(make_frame(T_STOP))

    def set_volume(self, percent):
        self._write(make_frame(T_VOLUME, bytes([max(0, min(100, int(percent)))])))

    # ---- lecture des messages de l'ESP32 ----

    def _read_loop(self):
        while self._serial:
            try:
                line = self._serial.readline().decode("utf-8", errors="replace").strip()
            except (serial.SerialException, OSError, AttributeError):
                return
            if not line:
                continue
            if line.startswith("BUF "):
                try:
                    _, free, rx = line.split()
                    with self._cv:
                        if not self._awaiting_start:
                            self._free, self._rx = int(free), int(rx)
                            self._cv.notify_all()
                except ValueError:
                    pass
            elif line.startswith("STATE "):
                self.state = line[6:]
                with self._cv:
                    if self.state == "prebuffer":
                        self._awaiting_start = False
                        self._cv.notify_all()
                self._on_event(line)
            elif line.startswith("BTN "):
                self._inputs.put(line)
            elif line.startswith("PONG"):
                self._pong.set()
                self._on_event(line)
            else:
                self._on_event(line)

    def _input_loop(self):
        # Thread à part : un gestionnaire lent (play() attend la fin du relais) ne doit pas bloquer la lecture série.
        while self._serial:
            try:
                line = self._inputs.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._on_input(line)
            except Exception as exc:
                self._on_event(f"EVT entrée : {exc}")

    # ---- relais du flux ----

    def _write(self, data):
        with self._write_lock:
            self._serial.write(data)

    def _stream(self, url, stop):
        while not stop.is_set():
            try:
                self._stream_once(url, stop)
            except Exception as exc:
                if not stop.is_set():
                    self._on_event(f"EVT relais : {exc}")
            if stop.wait(RECONNECT_DELAY_S):
                break

    def _stream_once(self, url, stop):
        headers = {"Icy-MetaData": "1", "User-Agent": USER_AGENT}
        with requests.get(url, stream=True, timeout=(5, 15), headers=headers) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "mpeg" not in content_type and "mp3" not in content_type:
                self._on_event(f"EVT relais : type de flux non pris en charge ({content_type})")
            with self._cv:
                self._sent = self._free = self._rx = 0
                self._awaiting_start = True
            self._write(make_frame(T_START))
            for data in self._audio_chunks(resp, stop):
                self._send_audio(data, stop)
                if stop.is_set():
                    return

    def _audio_chunks(self, resp, stop):
        metaint = int(resp.headers.get("icy-metaint") or 0)
        if not metaint:
            yield from resp.iter_content(chunk_size=4096)
            return
        raw = resp.raw
        while not stop.is_set():
            yield _read_exact(raw, metaint)
            length = _read_exact(raw, 1)[0] * 16
            if length:
                title = parse_icy_title(_read_exact(raw, length))
                if title:
                    self._on_metadata(title)

    def _send_audio(self, data, stop):
        for i in range(0, len(data), CHUNK_BYTES):
            chunk = data[i:i + CHUNK_BYTES]
            with self._cv:
                while not stop.is_set():
                    in_flight = self._sent - self._rx
                    if (in_flight + len(chunk) <= MAX_IN_FLIGHT
                            and self._free - in_flight - RESERVE_BYTES >= len(chunk)):
                        break
                    self._cv.wait(0.2)
                if stop.is_set():
                    return
            self._write(make_frame(T_AUDIO, chunk))
            with self._cv:
                self._sent += len(chunk)
