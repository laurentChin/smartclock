// app.js — gestion des alarmes

const DAY_CODES = ["LU", "MA", "ME", "JE", "VE", "SA", "DI"];
const DAY_NAMES = { LU: "lundi", MA: "mardi", ME: "mercredi", JE: "jeudi", VE: "vendredi", SA: "samedi", DI: "dimanche" };

const initial = JSON.parse(document.getElementById("initial-data").textContent);
let alarms = initial.alarms;
const stations = initial.stations;

const $ = (id) => document.getElementById(id);
const list = $("alarm-list");
const dialog = $("alarm-dialog");
const form = $("alarm-form");
let editingId = null;
let toastTimer = null;

// ---------- utilitaires ----------

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3500);
}

async function api(method, url, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Erreur du serveur");
  return data;
}

async function reload() {
  alarms = await api("GET", "/api/alarms");
  render();
}

function describeDays(days) {
  const key = DAY_CODES.filter((d) => days.includes(d)).join();
  if (key === DAY_CODES.join()) return "Tous les jours";
  if (key === "LU,MA,ME,JE,VE") return "En semaine";
  if (key === "SA,DI") return "Week-end";
  return DAY_CODES.filter((d) => days.includes(d)).map((d) => DAY_NAMES[d].slice(0, 3) + ".").join(" ");
}

// ---------- liste ----------

function render() {
  list.replaceChildren();
  $("alarm-empty").hidden = alarms.length > 0;

  for (const alarm of alarms) {
    const item = document.createElement("li");
    item.className = "alarm" + (alarm.enabled ? "" : " off");

    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "edit";
    edit.setAttribute("aria-label", `Modifier l'alarme de ${alarm.time}`);
    const time = document.createElement("div");
    time.className = "time";
    time.textContent = alarm.time;
    const meta = document.createElement("div");
    meta.className = "meta";
    const parts = [describeDays(alarm.days), alarm.station_name || "Station supprimée"];
    if (alarm.label) parts.unshift(alarm.label);
    meta.textContent = parts.join(" · ");
    edit.append(time, meta);
    edit.addEventListener("click", () => openDialog(alarm));

    const toggle = document.createElement("label");
    toggle.className = "switch";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = !!alarm.enabled;
    input.setAttribute("role", "switch");
    input.setAttribute("aria-label", `Alarme de ${alarm.time} activée`);
    input.addEventListener("change", async () => {
      try {
        await api("POST", `/api/alarms/${alarm.id}/toggle`, { enabled: input.checked });
      } catch (error) {
        toast(error.message);
      }
      reload();
    });
    toggle.append(input, document.createElement("span"));

    item.append(edit, toggle);
    list.append(item);
  }
}

// ---------- formulaire ----------

function selectedDays() {
  return [...document.querySelectorAll("#f-days input:checked")].map((i) => i.value);
}

function setDays(days) {
  document.querySelectorAll("#f-days input").forEach((i) => { i.checked = days.includes(i.value); });
}

function showError(message) {
  $("form-error").textContent = message || "";
  $("form-error").hidden = !message;
}

function openDialog(alarm) {
  editingId = alarm ? alarm.id : null;
  $("dialog-title").textContent = alarm ? "Modifier l'alarme" : "Nouvelle alarme";
  $("delete-alarm").hidden = !alarm;
  $("f-time").value = alarm ? alarm.time : "07:00";
  setDays(alarm ? alarm.days : ["LU", "MA", "ME", "JE", "VE"]);
  $("f-label").value = alarm ? alarm.label : "";
  const select = $("f-station");
  select.replaceChildren(...stations.map((s) => new Option(s.name, s.id)));
  const wanted = alarm ? alarm.station_id : (stations.find((s) => s.is_default) || stations[0] || {}).id;
  if (wanted !== undefined) select.value = wanted;
  showError("");
  dialog.showModal();
}

$("add-alarm").addEventListener("click", () => openDialog(null));
$("cancel-alarm").addEventListener("click", () => dialog.close());

document.querySelectorAll("[data-preset]").forEach((button) =>
  button.addEventListener("click", () => setDays(button.dataset.preset.split(","))));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = {
    time: $("f-time").value,
    days: selectedDays(),
    station_id: Number($("f-station").value),
    label: $("f-label").value.trim(),
  };
  if (!body.time) return showError("Choisis une heure");
  if (!body.days.length) return showError("Choisis au moins un jour");
  try {
    if (editingId === null) await api("POST", "/api/alarms", body);
    else await api("PUT", `/api/alarms/${editingId}`, body);
    dialog.close();
    toast(editingId === null ? "Alarme ajoutée" : "Alarme modifiée");
    await reload();
  } catch (error) {
    showError(error.message);
  }
});

$("delete-alarm").addEventListener("click", async () => {
  if (!confirm("Supprimer cette alarme ?")) return;
  try {
    await api("DELETE", `/api/alarms/${editingId}`);
    dialog.close();
    toast("Alarme supprimée");
    await reload();
  } catch (error) {
    showError(error.message);
  }
});

render();
