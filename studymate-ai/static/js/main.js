/* Shared behaviour: mobile sidebar, alerts, confirm dialogs, edit modals. */
document.addEventListener("DOMContentLoaded", () => {
  // Mobile sidebar
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("backdrop");
  const toggle = (open) => {
    sidebar.classList.toggle("open", open);
    backdrop.classList.toggle("show", open);
  };
  const menuBtn = document.getElementById("menuBtn");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", () => toggle(!sidebar.classList.contains("open")));
    backdrop.addEventListener("click", () => toggle(false));
  }

  // Flash messages disappear after a few seconds
  document.querySelectorAll(".auto-dismiss").forEach((el) => {
    setTimeout(() => bootstrap.Alert.getOrCreateInstance(el).close(), 5000);
  });

  // Ask before deleting
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // Generic edit modal: button data-* attributes fill the form fields.
  const modal = document.getElementById("editModal");
  if (modal) {
    modal.addEventListener("show.bs.modal", (event) => {
      const btn = event.relatedTarget;
      const form = modal.querySelector("form");
      form.action = btn.dataset.action;
      Object.entries(btn.dataset).forEach(([key, value]) => {
        if (form.elements[key]) form.elements[key].value = value;
      });
      // Tasks page: show either the "edit" or the "reschedule" fields
      const editGrp = document.getElementById("grpEdit");
      const reschedGrp = document.getElementById("grpResched");
      if (editGrp && reschedGrp) {
        const reschedule = btn.dataset.mode === "reschedule";
        editGrp.classList.toggle("d-none", reschedule);
        reschedGrp.classList.toggle("d-none", !reschedule);
        editGrp.querySelectorAll("input,select").forEach((i) => (i.disabled = reschedule));
        reschedGrp.querySelectorAll("input").forEach((i) => (i.disabled = !reschedule));
        document.getElementById("taskModalTitle").textContent = reschedule ? "Reschedule Task" : "Edit Task";
      }
    });
  }

  // Topics form: suggest study minutes from difficulty (30 / 45 / 60)
  const diff = document.getElementById("difficulty");
  const mins = document.getElementById("minutes");
  if (diff && mins) {
    const defaults = { Easy: 30, Medium: 45, Hard: 60 };
    diff.addEventListener("change", () => (mins.value = defaults[diff.value]));
  }
});
