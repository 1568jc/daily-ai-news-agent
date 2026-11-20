(() => {
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-brief-target]");
    if (!button) return;
    const history = button.closest("#history");
    if (!history) return;
    const target = button.dataset.briefTarget;
    history.querySelectorAll("[data-brief-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.briefPanel !== target;
    });
    history.querySelectorAll("[data-brief-target]").forEach((tab) => {
      const active = tab.dataset.briefTarget === target;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    });
  });

  const workbench = document.getElementById("workbench");
  const divider = document.getElementById("split-divider");
  if (!workbench || !divider) return;

  const storageKey = "ainews.settingsWidth";
  const minimumLeft = 320;
  const minimumRight = 380;
  let dragging = false;

  function currentWidth() {
    return Number.parseFloat(workbench.style.getPropertyValue("--settings-width")) || 400;
  }

  function applyWidth(width, persist = false) {
    const bounds = workbench.getBoundingClientRect();
    const maximum = Math.max(minimumLeft, bounds.width - minimumRight - divider.offsetWidth);
    const clamped = Math.round(Math.min(Math.max(width, minimumLeft), maximum));
    workbench.style.setProperty("--settings-width", `${clamped}px`);
    divider.setAttribute("aria-valuemin", String(minimumLeft));
    divider.setAttribute("aria-valuemax", String(Math.round(maximum)));
    divider.setAttribute("aria-valuenow", String(clamped));
    if (persist) {
      try {
        localStorage.setItem(storageKey, String(clamped));
      } catch (error) {
        return;
      }
    }
  }

  try {
    const saved = Number(localStorage.getItem(storageKey));
    if (saved) applyWidth(saved);
  } catch (error) {
    applyWidth(400);
  }

  divider.addEventListener("pointerdown", (event) => {
    if (window.innerWidth <= 1050) return;
    event.preventDefault();
    dragging = true;
    divider.setPointerCapture(event.pointerId);
    document.body.classList.add("is-resizing");
  });

  divider.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    applyWidth(event.clientX - workbench.getBoundingClientRect().left);
  });

  function stopDragging(event) {
    if (!dragging) return;
    dragging = false;
    if (divider.hasPointerCapture(event.pointerId)) divider.releasePointerCapture(event.pointerId);
    document.body.classList.remove("is-resizing");
    applyWidth(currentWidth(), true);
  }

  divider.addEventListener("pointerup", stopDragging);
  divider.addEventListener("pointercancel", stopDragging);
  divider.addEventListener("dblclick", () => applyWidth(400, true));
  divider.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? minimumLeft : currentWidth() + (event.key === "ArrowLeft" ? -24 : 24);
    applyWidth(next, true);
  });
  window.addEventListener("resize", () => applyWidth(currentWidth()));
})();
