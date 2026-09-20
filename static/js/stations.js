// stations.js — gestion des stations et éditeur de logo

const initial = JSON.parse($("initial-data").textContent);
let stations = initial.stations;
const list = $("station-list");
const dialog = $("station-dialog");
const form = $("station-form");
let editing = null;     // station en cours de modification, null pour un ajout

const SIZE = initial.logo_size;     // côté de la grille du logo (défini dans config.py)
// Logo affiché par le panneau quand la station n'en a pas (défini dans config.py)
const DEFAULT_LOGO = initial.default_logo;
const QUICK_COLORS = ["#ffffff", "#ff3b30", "#ffcc00", "#34c759", "#0a84ff", "#e2007a"];

function hostOf(url) {
  try { return new URL(url).hostname; } catch { return url; }
}

const blankLogo = () => Array.from({ length: SIZE }, () => Array(SIZE).fill(null));
const cloneLogo = (logo) => logo.map((row) => row.slice());
const hasPixels = (logo) => logo.some((row) => row.some(Boolean));

// ---------- miniature dans la liste ----------

function logoThumb(logo) {
  const thumb = document.createElement("span");
  thumb.className = "logo-thumb";
  thumb.style.setProperty("--n", SIZE);
  thumb.setAttribute("aria-hidden", "true");
  for (const row of logo || DEFAULT_LOGO) {
    for (const color of row) {
      const cell = document.createElement("i");
      cell.style.background = color || "#000";
      thumb.append(cell);
    }
  }
  return thumb;
}

async function reload() {
  stations = await api("GET", "/api/stations");
  render();
}

function render() {
  list.replaceChildren();
  for (const station of stations) {
    const item = document.createElement("li");
    item.className = "alarm";

    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "edit station-edit";
    edit.setAttribute("aria-label", `Modifier la station ${station.name}`);
    const text = document.createElement("span");
    const name = document.createElement("div");
    name.className = "station-name";
    name.textContent = station.name;
    const meta = document.createElement("div");
    meta.className = "meta";
    const parts = [hostOf(station.url)];
    if (station.genre) parts.unshift(station.genre);
    if (station.alarm_count) parts.push(`${station.alarm_count} alarme${station.alarm_count > 1 ? "s" : ""}`);
    meta.textContent = parts.join(" · ");
    text.append(name, meta);
    edit.append(logoThumb(station.logo), text);
    edit.addEventListener("click", () => openDialog(station));
    item.append(edit);

    if (station.is_default) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = "Par défaut";
      item.append(badge);
    }
    list.append(item);
  }
}

// ---------- éditeur de logo ----------

let logo = blankLogo();
let savedLogo = blankLogo();
let brush = "#ffffff";
let erasing = false;
let painting = false;
let sourceImage = null;     // image envoyée, gardée pour recalculer quand on change les réglages
const gridEl = $("logo-grid");
gridEl.style.setProperty("--n", SIZE);
const cells = [];

for (let y = 0; y < SIZE; y++) {
  for (let x = 0; x < SIZE; x++) {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "logo-cell";
    cell.dataset.x = x;
    cell.dataset.y = y;
    gridEl.append(cell);
    cells.push(cell);
  }
}

function drawLogo() {
  cells.forEach((cell) => {
    const color = logo[cell.dataset.y][cell.dataset.x];
    cell.style.background = color || "#000";
    cell.setAttribute("aria-label",
      `Ligne ${Number(cell.dataset.y) + 1}, colonne ${Number(cell.dataset.x) + 1} : ${color || "éteint"}`);
  });
  drawSwatches();
}

function drawSwatches() {
  const used = [...new Set(logo.flat().filter(Boolean))];
  const colors = [...used, ...QUICK_COLORS.filter((c) => !used.includes(c))];
  $("logo-swatches").replaceChildren(...colors.map((color) => {
    const swatch = document.createElement("button");
    swatch.type = "button";
    swatch.className = "swatch";
    swatch.style.background = color;
    swatch.setAttribute("aria-label", `Couleur ${color}`);
    swatch.setAttribute("aria-pressed", String(!erasing && color === brush));
    swatch.addEventListener("click", () => chooseBrush(color));
    return swatch;
  }));
}

function chooseBrush(color) {
  brush = color;
  $("logo-color").value = color;
  setErasing(false);
}

function setErasing(value) {
  erasing = value;
  $("logo-erase").setAttribute("aria-pressed", String(value));
  drawSwatches();
}

function paint(cell) {
  const color = erasing ? null : brush;
  if (logo[cell.dataset.y][cell.dataset.x] === color) return;
  logo[cell.dataset.y][cell.dataset.x] = color;
  drawLogo();
}

let lastPoint = null;     // dernière position du pointeur pendant un glissé

function paintAt(x, y) {
  const cell = document.elementFromPoint(x, y);
  if (cell && cell.classList.contains("logo-cell")) paint(cell);
}

gridEl.addEventListener("pointerdown", (event) => {
  const cell = event.target.closest(".logo-cell");
  if (!cell) return;
  event.preventDefault();
  painting = true;
  lastPoint = [event.clientX, event.clientY];
  paint(cell);
});
gridEl.addEventListener("pointermove", (event) => {
  if (!painting) return;
  // un glissé rapide saute des cases : on peint tout le trajet entre les deux positions
  const [x0, y0] = lastPoint;
  const steps = Math.max(1, Math.ceil(Math.hypot(event.clientX - x0, event.clientY - y0) / 8));
  for (let i = 1; i <= steps; i++) {
    paintAt(x0 + (event.clientX - x0) * i / steps, y0 + (event.clientY - y0) * i / steps);
  }
  lastPoint = [event.clientX, event.clientY];
});
["pointerup", "pointercancel", "pointerleave"].forEach((type) =>
  gridEl.addEventListener(type, () => { painting = false; lastPoint = null; }));
gridEl.addEventListener("keydown", (event) => {      // Entrée / Espace : peindre la case au clavier
  if ((event.key === "Enter" || event.key === " ") && event.target.classList.contains("logo-cell")) {
    event.preventDefault();
    paint(event.target);
  }
});

$("logo-color").addEventListener("input", (event) => chooseBrush(event.target.value));
$("logo-erase").addEventListener("click", () => setErasing(!erasing));
$("logo-clear").addEventListener("click", () => { logo = blankLogo(); sourceImage = null; hideImportOptions(); drawLogo(); });
$("logo-reset").addEventListener("click", () => {
  logo = cloneLogo(savedLogo);
  sourceImage = null;
  hideImportOptions();
  drawLogo();
});

// ---------- réduction d'une image en grille ----------

const WORK = SIZE * 20;      // taille de travail : 20 pixels par case
const MERGE_DISTANCE = 70;   // deux teintes plus proches que cela sont regroupées

const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const toHex = (c) => "#" + c.map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");

function lighten(color, floor = 110) {
  const peak = Math.max(...color);
  if (peak >= floor || peak === 0) return color;
  return color.map((v) => Math.min(255, v * floor / peak));
}

/** Réduit une image en grille SIZE x SIZE : couleurs franches, la couleur de fond sauf si un motif couvre assez la case. */
function reduceImage(image, { fit, threshold, light, zoom = 0 }) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = WORK;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.imageSmoothingQuality = "high";
  const w = image.naturalWidth || image.width;
  const h = image.naturalHeight || image.height;
  // zoom : fraction rognée sur chaque bord, pour agrandir un motif entouré de marge
  const scale = (fit === "cover" ? WORK / Math.min(w, h) : WORK / Math.max(w, h)) / (1 - 2 * zoom);
  ctx.drawImage(image, (WORK - w * scale) / 2, (WORK - h * scale) / 2, w * scale, h * scale);
  const data = ctx.getImageData(0, 0, WORK, WORK).data;

  // 1. teintes : on regroupe les pixels par teinte approchée, puis on fusionne les teintes voisines
  const buckets = new Map();
  const off = [];      // pixels transparents = LED éteinte
  for (let i = 0; i < WORK * WORK; i++) {
    const [r, g, b, a] = [data[i * 4], data[i * 4 + 1], data[i * 4 + 2], data[i * 4 + 3]];
    if (a < 128) { off.push(i); continue; }
    const key = (r >> 5) * 64 + (g >> 5) * 8 + (b >> 5);
    const bucket = buckets.get(key) || { n: 0, sum: [0, 0, 0] };
    bucket.n++;
    bucket.sum[0] += r; bucket.sum[1] += g; bucket.sum[2] += b;
    buckets.set(key, bucket);
  }
  const palette = [];
  [...buckets.values()].sort((p, q) => q.n - p.n).forEach((bucket) => {
    const mean = bucket.sum.map((v) => v / bucket.n);
    if (palette.length < 6 && palette.every((p) => dist(p.color, mean) > MERGE_DISTANCE)) {
      palette.push({ color: mean, n: 0, sum: [0, 0, 0] });
    }
  });
  if (off.length) palette.push({ color: [0, 0, 0], n: 0, sum: [0, 0, 0], off: true });

  // 2. chaque pixel prend la teinte la plus proche ; on garde la couleur moyenne réelle de chaque teinte
  const owner = new Int16Array(WORK * WORK);
  const offIndex = palette.findIndex((p) => p.off);
  for (let i = 0; i < WORK * WORK; i++) {
    let best = -1;
    if (data[i * 4 + 3] < 128) {
      best = offIndex;
    } else {
      const px = [data[i * 4], data[i * 4 + 1], data[i * 4 + 2]];
      let bestDistance = Infinity;
      palette.forEach((p, k) => {
        if (p.off) return;
        const d = dist(p.color, px);
        if (d < bestDistance) { bestDistance = d; best = k; }
      });
      palette[best].sum[0] += px[0]; palette[best].sum[1] += px[1]; palette[best].sum[2] += px[2];
    }
    owner[i] = best;
    palette[best].n++;
  }
  palette.forEach((p) => { if (!p.off && p.n) p.color = p.sum.map((v) => v / p.n); });

  // 3. fond = teinte la plus fréquente ; une case prend la teinte de premier plan qui la couvre assez
  const background = palette.reduce((best, p, k) => (p.n > palette[best].n ? k : best), 0);
  const step = WORK / SIZE;
  const result = blankLogo();
  for (let cy = 0; cy < SIZE; cy++) {
    for (let cx = 0; cx < SIZE; cx++) {
      const counts = new Map();
      for (let y = cy * step; y < (cy + 1) * step; y++) {
        for (let x = cx * step; x < (cx + 1) * step; x++) {
          const k = owner[y * WORK + x];
          counts.set(k, (counts.get(k) || 0) + 1);
        }
      }
      let choice = background;
      let top = 0;
      counts.forEach((n, k) => { if (k !== background && n > top) { top = n; choice = k; } });
      if (top < threshold * step * step) choice = background;
      let color = palette[choice].color;
      if (light) color = lighten(color);
      result[cy][cx] = Math.max(...color) < 24 ? null : toHex(color);
    }
  }
  return result;
}

function hideImportOptions() {
  $("logo-options").hidden = true;
  $("logo-file").value = "";
}

function applyImport() {
  if (!sourceImage) return;
  logo = reduceImage(sourceImage, {
    fit: $("logo-fit").value,
    threshold: Number($("logo-detail").value) / 100,
    zoom: Number($("logo-zoom").value) / 100,
    light: $("logo-light").checked,
  });
  drawLogo();
}

$("logo-file").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  const image = new Image();
  image.onload = () => {
    sourceImage = image;
    $("logo-options").hidden = false;
    applyImport();
    URL.revokeObjectURL(url);
  };
  image.onerror = () => { showError("Image illisible : essaie un PNG, JPEG ou SVG"); URL.revokeObjectURL(url); };
  image.src = url;
});
["logo-fit", "logo-zoom", "logo-detail", "logo-light"].forEach((id) => $(id).addEventListener("input", applyImport));

// ---------- formulaire ----------

function showError(message) {
  $("station-error").textContent = message || "";
  $("station-error").hidden = !message;
}

function openDialog(station) {
  editing = station;
  $("station-dialog-title").textContent = station ? "Modifier la station" : "Nouvelle station";
  $("s-name").value = station ? station.name : "";
  $("s-url").value = station ? station.url : "";
  $("s-genre").value = station ? station.genre : "";
  $("s-default").checked = station ? !!station.is_default : false;
  $("s-default").disabled = !!(station && station.is_default);   // on change de défaut en en choisissant une autre
  $("delete-station").hidden = !station || !!station.is_default;
  savedLogo = station && station.logo ? cloneLogo(station.logo) : blankLogo();
  logo = cloneLogo(savedLogo);
  sourceImage = null;
  hideImportOptions();
  setErasing(false);
  chooseBrush("#ffffff");
  drawLogo();
  showError("");
  dialog.showModal();
}

$("add-station").addEventListener("click", () => openDialog(null));
$("cancel-station").addEventListener("click", () => dialog.close());

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = {
    name: $("s-name").value.trim(),
    url: $("s-url").value.trim(),
    genre: $("s-genre").value.trim(),
    logo: hasPixels(logo) ? logo : null,      // grille vide : le panneau affiche le logo par défaut
  };
  if (!body.name) return showError("Donne un nom à la station");
  if (!body.url) return showError("Indique l'adresse du flux");

  const save = $("save-station");
  save.disabled = true;
  save.textContent = "Vérification…";    // le serveur teste le flux, cela peut prendre quelques secondes
  showError("");
  try {
    let id = editing ? editing.id : null;
    if (editing) {
      await api("PUT", `/api/stations/${editing.id}`, body);
    } else {
      await api("POST", "/api/stations", body);
    }
    if ($("s-default").checked && !$("s-default").disabled) {
      if (id === null) {     // nouvelle station : on retrouve son identifiant
        await reload();
        id = stations.find((s) => s.url === body.url && s.name === body.name).id;
      }
      await api("POST", `/api/stations/${id}/default`);
    }
    dialog.close();
    toast(editing ? "Station modifiée" : "Station ajoutée");
    await reload();
  } catch (error) {
    showError(error.message);
  } finally {
    save.disabled = false;
    save.textContent = "Enregistrer";
  }
});

$("delete-station").addEventListener("click", async () => {
  const fallback = stations.find((s) => s.is_default);
  const count = editing.alarm_count;
  const note = count
    ? `\n${count} alarme${count > 1 ? "s passeront" : " passera"} sur ${fallback ? fallback.name : "la station par défaut"}.`
    : "";
  if (!confirm(`Supprimer la station ${editing.name} ?${note}`)) return;
  try {
    await api("DELETE", `/api/stations/${editing.id}`);
    dialog.close();
    toast("Station supprimée");
    await reload();
  } catch (error) {
    showError(error.message);
  }
});

render();
