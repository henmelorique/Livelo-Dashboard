// Compartilhado entre todas as páginas: preenche o "ticker tape" do topo
// com os parceiros em promoção e atualiza o indicador de status.

function fmtPoints(n) {
  if (n === null || n === undefined) return "—";
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function timeAgo(isoString) {
  if (!isoString) return "sem dados ainda";
  const then = new Date(isoString);
  const diffMs = Date.now() - then.getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "agora mesmo";
  if (mins < 60) return `há ${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `há ${hours}h`;
  const days = Math.round(hours / 24);
  return `há ${days}d`;
}

async function loadTickerAndStatus() {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  try {
    const res = await fetch("/api/partners?sort=variation&order=desc");
    const data = await res.json();

    const promos = data.partners.filter((p) => p.is_promo).slice(0, 24);
    const tape = document.getElementById("tickerTape");
    if (tape) {
      if (promos.length === 0) {
        tape.innerHTML = '<div class="ticker-track"><span class="ticker-item">Nenhuma promoção detectada na última coleta.</span></div>';
      } else {
        const items = promos
          .map((p) => {
            const variation = p.variation_pct !== null ? `<span class="tk-up">+${p.variation_pct}%</span>` : "";
            return `<a class="ticker-item" href="/parceiro/${p.slug}"><span class="tk-name">${p.name}</span><span>${fmtPoints(p.current_points)} pts</span>${variation}</a>`;
          })
          .join("");
        // duplica a lista para permitir loop contínuo do CSS
        tape.innerHTML = `<div class="ticker-track">${items}${items}</div>`;
      }
    }

    if (dot && text) {
      dot.className = "dot ok";
      text.textContent = `${data.count} parceiros · ${data.promo_count} em promoção · atualizado ${timeAgo(data.last_updated)}`;
    }
  } catch (err) {
    if (dot && text) {
      dot.className = "dot err";
      text.textContent = "não foi possível carregar o status";
    }
    console.error(err);
  }
}

document.addEventListener("DOMContentLoaded", loadTickerAndStatus);
