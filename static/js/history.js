// Lógica da página de histórico do parceiro (gráfico + tabela).

let chart = null;
let currentDays = 30;

const chipEls = document.querySelectorAll(".range-chip");
const startInput = document.getElementById("dateStart");
const endInput = document.getElementById("dateEnd");
const applyBtn = document.getElementById("applyRange");
const historyBody = document.getElementById("historyBody");

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

async function loadHistory({ days, start, end } = {}) {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (!start && !end && days) params.set("days", days);

  const res = await fetch(`/api/partner/${window.PARTNER_SLUG}/history?${params.toString()}`);
  const data = await res.json();
  renderChart(data.history);
  renderTable(data.history);
}

function renderChart(history) {
  const ctx = document.getElementById("historyChart").getContext("2d");

  const points = history.map((h) => ({ x: h.captured_at, y: h.points }));
  const clubePoints = history
    .filter((h) => h.points_clube !== null && h.points_clube !== undefined)
    .map((h) => ({ x: h.captured_at, y: h.points_clube }));

  const promoBackground = {
    id: "promoBackground",
    beforeDraw(c) {
      const { ctx, chartArea, scales } = c;
      if (!chartArea) return;
      ctx.save();
      history.forEach((h, i) => {
        if (!h.is_promo) return;
        const next = history[i + 1];
        const x1 = scales.x.getPixelForValue(new Date(h.captured_at).getTime());
        const x2 = next ? scales.x.getPixelForValue(new Date(next.captured_at).getTime()) : chartArea.right;
        ctx.fillStyle = "rgba(227, 179, 65, 0.08)";
        ctx.fillRect(x1, chartArea.top, x2 - x1, chartArea.bottom - chartArea.top);
      });
      ctx.restore();
    },
  };

  const datasets = [
    {
      label: "Pontos padrão",
      data: points,
      borderColor: "#e3b341",
      backgroundColor: "rgba(227, 179, 65, 0.12)",
      pointRadius: 2.5,
      pointHoverRadius: 5,
      borderWidth: 2,
      tension: 0.15,
      fill: true,
    },
  ];

  if (clubePoints.length > 0) {
    datasets.push({
      label: "Pontos Clube Livelo",
      data: clubePoints,
      borderColor: "#4fd1c5",
      backgroundColor: "transparent",
      pointRadius: 2,
      pointHoverRadius: 4,
      borderWidth: 1.5,
      borderDash: [4, 3],
      tension: 0.15,
    });
  }

  if (chart) chart.destroy();

  chart = new Chart(ctx, {
    type: "line",
    data: { datasets },
    plugins: [promoBackground],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          type: "time",
          time: { unit: currentDays && currentDays <= 30 ? "day" : "week" },
          grid: { color: "#21252e" },
          ticks: { color: "#9096a3", font: { family: "IBM Plex Mono", size: 11 } },
        },
        y: {
          grid: { color: "#21252e" },
          ticks: { color: "#9096a3", font: { family: "IBM Plex Mono", size: 11 } },
          title: { display: true, text: "pontos por unidade de moeda", color: "#5c6270", font: { size: 11 } },
        },
      },
      plugins: {
        legend: { labels: { color: "#e8e6e1", font: { family: "Inter", size: 12 } } },
        tooltip: {
          backgroundColor: "#171a21",
          borderColor: "#2a2e38",
          borderWidth: 1,
          titleFont: { family: "IBM Plex Mono", size: 12 },
          bodyFont: { family: "IBM Plex Mono", size: 12 },
        },
      },
    },
  });
}

function renderTable(history) {
  if (history.length === 0) {
    historyBody.innerHTML = `<tr><td colspan="3" class="empty-state">Sem registros no período selecionado.</td></tr>`;
    return;
  }
  historyBody.innerHTML = [...history]
    .reverse()
    .map(
      (h) => `
      <tr>
        <td class="updated-cell">${fmtDate(h.captured_at)}</td>
        <td class="points-cell">${h.points_is_up_to ? "até " : ""}${fmtPoints(h.points)} pts</td>
        <td>${h.is_promo ? '<span class="badge promo">Promoção</span>' : '<span class="variation flat">padrão</span>'}</td>
      </tr>`
    )
    .join("");
}

chipEls.forEach((chip) => {
  chip.addEventListener("click", () => {
    chipEls.forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    startInput.value = "";
    endInput.value = "";
    const days = parseInt(chip.dataset.days, 10);
    currentDays = days === 0 ? null : days;
    loadHistory(days === 0 ? {} : { days });
  });
});

applyBtn.addEventListener("click", () => {
  chipEls.forEach((c) => c.classList.remove("active"));
  const start = startInput.value ? `${startInput.value}T00:00:00` : null;
  const end = endInput.value ? `${endInput.value}T23:59:59` : null;
  currentDays = null;
  loadHistory({ start, end });
});

loadHistory({ days: currentDays });
