/* AI Study Planner page: send the form to /planner/generate and draw the timetable. */
const form = document.getElementById("plannerForm");
const subjectSel = document.getElementById("subject_id");
const examInput = document.getElementById("exam_date");
const alertBox = document.getElementById("plannerAlert");
const resultWrap = document.getElementById("resultWrap");

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const icon = { High: "🔴", Medium: "🟡", Low: "🟢" };

function t12(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return `${String(((h + 11) % 12) + 1).padStart(2, "0")}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}
function showAlert(type, text) {
  alertBox.innerHTML = `<div class="alert alert-${type}">${esc(text)}</div>`;
}

// The exam-date override only makes sense for one subject
subjectSel.addEventListener("change", () => {
  const opt = subjectSel.selectedOptions[0];
  const single = subjectSel.value !== "all";
  examInput.disabled = !single;
  examInput.value = single ? opt.dataset.exam : "";
});

async function generate() {
  const btn = document.getElementById("generateBtn");
  btn.disabled = true;
  alertBox.innerHTML = "";
  try {
    const body = Object.fromEntries(new FormData(form).entries());
    if (examInput.disabled) delete body.exam_date;
    const res = await fetch("/planner/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!data.ok) {
      resultWrap.classList.add("d-none");
      return showAlert("danger", data.message || "Unable to generate study plan.");
    }
    render(data);
    if (data.unscheduled > 0) {
      showAlert("warning", `${data.unscheduled} topic(s) did not fit in the next 14 days. Increase your daily hours or generate again later.`);
    }
  } catch (err) {
    showAlert("danger", "Unable to generate study plan.");
  } finally {
    btn.disabled = false;
  }
}

function render(data) {
  document.getElementById("timetable").innerHTML = data.plan.map((day) => `
    <div class="day-block">
      <div class="day-title">${esc(day.day.toUpperCase())}<small>${esc(day.label)}</small></div>
      ${day.tasks.map((t) => `
        <div class="slot prio-${t.priority.toLowerCase()}">
          <div class="fw-bold text-primary">${t12(t.start)} – ${t12(t.end)}</div>
          <div>${icon[t.priority]} ${esc(t.subject)} – ${esc(t.topic)}</div>
          <div class="small text-secondary">Priority: ${t.priority.toUpperCase()} · ${t.duration} min</div>
        </div>`).join("")}
    </div>`).join("");

  document.getElementById("recs").innerHTML = data.recommendations.map((r) => `
    <div class="col-md-4"><div class="card rec-card h-100"><div class="card-body">
      <div class="fw-bold mb-1">${r.icon} ${esc(r.title)}</div>
      <div class="text-secondary">${esc(r.text)}</div>
    </div></div></div>`).join("");

  resultWrap.classList.remove("d-none");
  resultWrap.scrollIntoView({ behavior: "smooth", block: "start" });
}

form.addEventListener("submit", (e) => { e.preventDefault(); generate(); });
document.getElementById("regenBtn").addEventListener("click", generate);
// The plan is already stored in MongoDB when it is generated; "Save Plan" confirms it.
document.getElementById("saveBtn").addEventListener("click", () => {
  showAlert("success", "Plan saved! Find every task on the My Tasks page.");
});
