// system.js — redémarrage et arrêt du Pi

const ACTIONS = {
  reboot: {
    title: "Redémarrer le Pi ?",
    text: "La radio et l'écran s'arrêtent le temps du redémarrage.",
    ok: "Redémarrer",
    done: "Redémarrage en cours…",
  },
  shutdown: {
    title: "Éteindre le Pi ?",
    text: "Il faudra le débrancher puis le rebrancher pour le rallumer. Les alarmes ne sonneront pas tant qu'il est éteint.",
    ok: "Éteindre",
    done: "Le Pi s'éteint. Tu peux fermer cette page.",
  },
};

const dialog = $("confirm-dialog");
let pending = null;

document.querySelectorAll("[data-action]").forEach((button) =>
  button.addEventListener("click", () => {
    pending = button.dataset.action;
    const action = ACTIONS[pending];
    $("confirm-title").textContent = action.title;
    $("confirm-text").textContent = action.text;
    $("confirm-ok").textContent = action.ok;
    dialog.showModal();
  }));

$("confirm-cancel").addEventListener("click", () => dialog.close());

function setStatus(message) {
  $("system-status").textContent = message;
  $("system-status").hidden = false;
}

async function waitForServer() {
  await new Promise((resolve) => setTimeout(resolve, 15000));     // le temps que le Pi s'arrête
  for (;;) {
    try {
      const response = await fetch("/api/stations", { cache: "no-store" });
      if (response.ok) return;
    } catch { /* serveur encore arrêté */ }
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
}

$("confirm-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = pending;
  dialog.close();
  try {
    await api("POST", `/api/system/${name}`, {});
  } catch (error) {
    toast(error.message);
    return;
  }
  document.querySelectorAll("[data-action]").forEach((b) => { b.disabled = true; });
  setStatus(ACTIONS[name].done);
  if (name === "reboot") {
    await waitForServer();
    setStatus("Le Pi a redémarré.");
    document.querySelectorAll("[data-action]").forEach((b) => { b.disabled = false; });
  }
});
