document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
    button.addEventListener("click", () => sidebar?.classList.toggle("open"));
  });

  document.addEventListener("click", (event) => {
    if (window.innerWidth <= 767 && sidebar?.classList.contains("open")
        && !sidebar.contains(event.target) && !event.target.closest("[data-sidebar-toggle]")) {
      sidebar.classList.remove("open");
    }
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll("form.needs-validation").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });
});

window.renderDashboardCharts = (data) => {
  if (!window.Chart) return;
  Chart.defaults.font.family = "'DM Sans', sans-serif";
  Chart.defaults.font.size = 10;
  Chart.defaults.color = "#78869a";
  const palette = ["#3867d6", "#37a77a", "#f0ac45", "#8766d4", "#e36c76", "#45aabe", "#94a4bd"];
  const drawBars = (id, rows, horizontal = false) => {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: rows.map((row) => row.label),
        datasets: [{ data: rows.map((row) => row.value), backgroundColor: rows.map((_, index) => palette[index % palette.length]), borderRadius: 5, maxBarThickness: 30 }],
      },
      options: {
        indexAxis: horizontal ? "y" : "x",
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: !horizontal }, border: { display: false }, ticks: { precision: 0 } },
          y: { grid: { display: horizontal }, border: { display: false }, beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  };
  const drawDoughnut = (id, rows) => {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: rows.map((row) => row.label),
        datasets: [{ data: rows.map((row) => row.value), backgroundColor: palette, borderWidth: 3, borderColor: "#fff" }],
      },
      options: { maintainAspectRatio: false, cutout: "66%", plugins: { legend: { position: "bottom", labels: { usePointStyle: true, padding: 14 } } } },
    });
  };
  drawBars("accessChart", data.access, true);
  drawDoughnut("bookingChart", data.booking);
  drawBars("staffChart", data.staff);
  drawBars("facilityChart", data.facility);
};
