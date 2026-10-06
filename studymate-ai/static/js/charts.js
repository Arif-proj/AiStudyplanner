/* Progress page charts (Chart.js). Data comes from window.CHART_DATA. */
const d = window.CHART_DATA;
const palette = ["#4f6df5", "#7c4dff", "#20c997", "#ffb020", "#ef476f", "#38bdf8", "#a78bfa"];

new Chart(document.getElementById("subjectChart"), {
  type: "doughnut",
  data: { labels: d.subjects.labels, datasets: [{ data: d.subjects.values, backgroundColor: palette, borderWidth: 0 }] },
  options: { maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
});

new Chart(document.getElementById("weeklyChart"), {
  type: "bar",
  data: { labels: d.weekly.labels, datasets: [{ label: "Hours studied", data: d.weekly.values, backgroundColor: "#7c4dff", borderRadius: 8 }] },
  options: { maintainAspectRatio: false, scales: { y: { beginAtZero: true } }, plugins: { legend: { display: false } } },
});

new Chart(document.getElementById("taskChart"), {
  type: "doughnut",
  data: { labels: d.tasks.labels, datasets: [{ data: d.tasks.values, backgroundColor: ["#20c997", "#c7cdf0"], borderWidth: 0 }] },
  options: { maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
});
