// temperature.js — connexion à Netatmo et choix de la pièce dont la température est affichée

let status = null;

function ago(epoch) {
  const minutes = Math.round((Date.now() / 1000 - epoch) / 60);
  if (minutes < 1) return "à l'instant";
  return minutes < 60 ? `il y a ${minutes} min` : `il y a ${Math.round(minutes / 60)} h`;
}

function showError(id, message) {
  $(id).textContent = message || "";
  $(id).hidden = !message;
}

function renderStatus() {
  const s = status;
  $("temp-value").textContent = s.fresh && s.temperature !== null ? `${s.temperature.toFixed(1).replace(".", ",")} °C` : "--";
  if (!s.configured) {
    $("temp-room").textContent = "Netatmo n'est pas configuré";
  } else if (!s.room) {
    $("temp-room").textContent = "Choisis une pièce ci-dessous";
  } else {
    $("temp-room").textContent = s.room.name;
  }
  $("temp-updated").textContent = s.updated_at ? `Dernière mesure ${ago(s.updated_at)}` : "";
  showError("temp-error", s.error);
  $("connect-title").textContent = s.configured ? "Connexion à Netatmo (modifier)" : "Connexion à Netatmo";
  $("connect-save").textContent = s.configured ? "Mettre à jour" : "Se connecter";
  $("disconnect").hidden = !s.configured;
  $("room-form").hidden = !s.configured;
}

async function loadRooms() {
  const select = $("room-select");
  select.replaceChildren();
  try {
    const rooms = await api("GET", "/api/netatmo/rooms");
    const multiple = new Set(rooms.map((r) => r.home_id)).size > 1;
    rooms.forEach((r) => {
      const label = multiple ? `${r.home_name} · ${r.room_name}` : r.room_name;
      const option = new Option(label, JSON.stringify([r.home_id, r.room_id]));
      if (status.room && status.room.room_id === r.room_id && status.room.home_id === r.home_id) option.selected = true;
      select.append(option);
    });
    if (!rooms.length) showError("temp-error", "Netatmo ne renvoie aucune pièce pour ce compte");
  } catch (error) {
    showError("temp-error", error.message);
  }
}

async function refresh() {
  status = await api("GET", "/api/netatmo");
  renderStatus();
  if (status.configured) await loadRooms();
}

$("connect-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = {
    client_id: $("n-client-id").value.trim(),
    client_secret: $("n-client-secret").value.trim(),
    refresh_token: $("n-refresh-token").value.trim(),
  };
  if (!body.client_id || !body.client_secret || !body.refresh_token) {
    return showError("connect-error", "Renseigne les trois champs");
  }
  const save = $("connect-save");
  save.disabled = true;
  save.textContent = "Vérification…";
  showError("connect-error", "");
  try {
    status = await api("PUT", "/api/netatmo/credentials", body);
    ["n-client-id", "n-client-secret", "n-refresh-token"].forEach((id) => { $(id).value = ""; });
    toast("Compte Netatmo connecté");
    await refresh();
  } catch (error) {
    showError("connect-error", error.message);
  } finally {
    save.disabled = false;
    renderStatus();
  }
});

$("room-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!$("room-select").value) return;
  const [homeId, roomId] = JSON.parse($("room-select").value);
  const save = $("room-save");
  save.disabled = true;
  try {
    status = await api("PUT", "/api/netatmo/room", { home_id: homeId, room_id: roomId });
    toast("Pièce enregistrée");
    renderStatus();
    // la première mesure arrive quelques secondes après le choix
    setTimeout(refresh, 4000);
  } catch (error) {
    showError("temp-error", error.message);
  } finally {
    save.disabled = false;
  }
});

$("disconnect").addEventListener("click", async () => {
  if (!confirm("Déconnecter Netatmo ? Les identifiants enregistrés sur le Pi seront supprimés.")) return;
  try {
    await api("DELETE", "/api/netatmo");
    toast("Netatmo déconnecté");
    await refresh();
  } catch (error) {
    showError("connect-error", error.message);
  }
});

refresh().catch((error) => showError("temp-error", error.message));
setInterval(() => api("GET", "/api/netatmo").then((s) => { status = s; renderStatus(); }).catch(() => {}), 30000);
