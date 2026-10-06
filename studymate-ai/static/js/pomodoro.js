/* Pomodoro timer - runs fully in the browser. Finished study sessions are logged. */
const MODES = { study: { minutes: 25, label: "Focus" }, break: { minutes: 5, label: "Break" } };
let mode = "study", remaining = MODES.study.minutes * 60, timer = null;

const text = document.getElementById("timerText");
const face = document.getElementById("timerFace");
const label = document.getElementById("modeLabel");
const msg = document.getElementById("timerMsg");
const studyBtn = document.getElementById("studyMode");
const breakBtn = document.getElementById("breakMode");

function draw() {
  const m = String(Math.floor(remaining / 60)).padStart(2, "0");
  const s = String(remaining % 60).padStart(2, "0");
  text.textContent = `${m}:${s}`;
  document.title = `${m}:${s} – StudyMate AI`;
}
function stop() { clearInterval(timer); timer = null; face.classList.remove("running"); }
function setMode(newMode) {
  stop();
  mode = newMode;
  remaining = MODES[mode].minutes * 60;
  label.textContent = MODES[mode].label;
  face.classList.toggle("break", mode === "break");
  studyBtn.className = "btn " + (mode === "study" ? "btn-brand" : "btn-outline-brand");
  breakBtn.className = "btn " + (mode === "break" ? "btn-brand" : "btn-outline-brand");
  draw();
}
function start() {
  if (timer) return;
  msg.classList.add("d-none");
  face.classList.add("running");
  timer = setInterval(() => {
    remaining--;
    draw();
    if (remaining <= 0) finish();
  }, 1000);
}
async function finish() {
  stop();
  if (mode === "study") {
    msg.textContent = "🎉 Study session completed! Take a 5-minute break.";
    try {
      await fetch("/pomodoro/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duration: MODES.study.minutes, topic_id: document.getElementById("topicSelect").value }),
      });
    } catch (e) { /* the timer keeps working even if logging fails */ }
    msg.classList.remove("d-none");
    setMode("break");
  } else {
    msg.textContent = "Break over. Ready for the next focus session?";
    msg.classList.remove("d-none");
    setMode("study");
  }
}

document.getElementById("startBtn").addEventListener("click", start);
document.getElementById("pauseBtn").addEventListener("click", stop);
document.getElementById("resetBtn").addEventListener("click", () => setMode(mode));
studyBtn.addEventListener("click", () => setMode("study"));
breakBtn.addEventListener("click", () => setMode("break"));
draw();
