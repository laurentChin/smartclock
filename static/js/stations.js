// stations.js — gestion des stations

let stations = JSON.parse($("initial-data").textContent).stations;
const list = $("station-list");
const dialog = $("station-dialog");
const form = $("station-form");
let editing = null;     // station en cours de modification, null pour un ajout

function hostOf(url) {
  try { return new URL(url).hostname; } catch { return url; }
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
    edit.className = "edit";
    edit.setAttribute("aria-label", `Modifier la station ${station.name}`);
    const name = document.createElement("div");
    name.className = "station-name";
    name.textContent = station.name;
    const meta = document.createElement("div");
    meta.className = "meta";
    const parts = [hostOf(station.url)];
    if (station.genre) parts.unshift(station.genre);
    if (station.alarm_count) parts.push(`${station.alarm_count} alarme${station.alarm_count > 1 ? "s" : ""}`);
    meta.textContent = parts.join(" · ");
    edit.append(name, meta);
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
  showError("");
  dialog.showModal();
}

$("add-station").addEventListener("click", () => openDialog(null));
$("cancel-station").addEventListener("click", () => dialog.close());

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = { name: $("s-name").value.trim(), url: $("s-url").value.trim(), genre: $("s-genre").value.trim() };
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
