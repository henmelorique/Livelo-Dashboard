// Lógica da página principal (tabela de parceiros).

const state = {
  sort: "name",
  order: "asc",
  promoOnly: false,
  q: "",
};

const els = {
  body: document.getElementById("partnersBody"),
  search: document.getElementById("searchInput"),
  promoOnly: document.getElementById("promoOnly"),
  promoChip: document.getElementById("promoChip"),
  sortSelect: document.getElementById("sortSelect"),
  orderSelect: document.getElementById("orderSelect"),
  refreshBtn: document.getElementById("refreshBtn"),
  statTotal: document.getElementById("statTotal"),
  statPromo: document.getElementById("statPromo"),
  statTop: document.getElementById("statTop"),
  statUpdated: document.getElementById("statUpdated"),
};

function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function renderRows(partners) {
  if (partners.length === 0) {
    els.body.innerHTML = `<tr><td colspan="4" class="empty-state">Nenhum parceiro encontrado com esse filtro.</td></tr>`;
    return;
  }

  els.body.innerHTML = partners
    .map((p) => {
      const pointsLabel = `${p.current_points_is_up_to ? "até " : ""}${fmtPoints(p.current_points)} pts / ${p.currency} 1`;
      const prevLabel = p.current_points_previous
        ? `<span class="prev">eram ${fmtPoints(p.current_points_previous)}</span>`
        : "";
      const clubeLabel = p.current_points_clube
        ? `<div style="font-size:11px;color:var(--text-faint);margin-top:2px;">clube: ${fmtPoints(p.current_points_clube)} pts</div>`
        : "";

      let variationHtml = '<span class="variation flat">—</span>';
      if (p.variation_pct !== null && p.variation_pct !== undefined) {
        variationHtml = `<span class="variation up">+${p.variation_pct}%</span>`;
      }

      const badges = [
        p.is_promo ? '<span class="badge promo">Promoção</span>' : "",
        p.is_new_partner ? '<span class="badge new">Nova</span>' : "",
      ].join(" ");

      return `
        <tr class="${p.is_promo ? "is-promo" : ""}" onclick="window.location.href='/parceiro/${p.slug}'">
          <td>
            <div class="partner-name-cell">
              <span class="partner-name">${p.name}</span>
              ${badges}
            </div>
          </td>
          <td class="points-cell">${pointsLabel} ${prevLabel}${clubeLabel}</td>
          <td>${variationHtml}</td>
          <td class="updated-cell">${fmtDateTime(p.last_checked_at)}</td>
        </tr>`;
    })
    .join("");
}

async function loadPartners() {
  const params = new URLSearchParams({
    sort: state.sort,
    order: state.order,
    promo_only: state.promoOnly,
    q: state.q,
  });
  const res = await fetch(`/api/partners?${params.toString()}`);
  const data = await res.json();

  renderRows(data.partners);

  els.statTotal.textContent = data.count;
  els.statPromo.textContent = data.promo_count;
  const top = data.partners.reduce((max, p) => ((p.current_points || 0) > (max?.current_points || 0) ? p : max), null);
  els.statTop.textContent = top ? `${fmtPoints(top.current_points)} · ${top.name}` : "—";
  els.statUpdated.textContent = timeAgo(data.last_updated);

  // No modo "readonly" (produção), o botão sincroniza a partir do GitHub
  // em vez de fazer scraping direto — muda só o texto, mesmo botão.
  if (data.mode === "readonly" && !els.refreshBtn.dataset.labeled) {
    els.refreshBtn.textContent = "↻ Sincronizar do GitHub";
    els.refreshBtn.title = "Busca o snapshot mais recente publicado pelo GitHub Actions (não acessa a Livelo diretamente).";
    els.refreshBtn.dataset.labeled = "1";
  }
}

function debounce(fn, wait) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

els.search.addEventListener("input", debounce((e) => {
  state.q = e.target.value;
  loadPartners();
}, 250));

els.promoOnly.addEventListener("change", (e) => {
  state.promoOnly = e.target.checked;
  els.promoChip.classList.toggle("active", state.promoOnly);
  loadPartners();
});

els.sortSelect.addEventListener("change", (e) => {
  state.sort = e.target.value;
  loadPartners();
});

els.orderSelect.addEventListener("change", (e) => {
  state.order = e.target.value;
  loadPartners();
});

document.querySelectorAll("th.sortable").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (state.sort === key) {
      state.order = state.order === "asc" ? "desc" : "asc";
    } else {
      state.sort = key;
      state.order = "asc";
    }
    els.sortSelect.value = state.sort;
    els.orderSelect.value = state.order;
    loadPartners();
  });
});

els.refreshBtn.addEventListener("click", async () => {
  const originalLabel = els.refreshBtn.textContent;
  els.refreshBtn.disabled = true;
  els.refreshBtn.textContent = "↻ Atualizando…";
  try {
    const res = await fetch("/api/refresh", { method: "POST" });
    const data = await res.json();
    if (data.status === "success") {
      els.refreshBtn.textContent =
        data.mode === "readonly"
          ? `✓ +${data.history_inserted || 0} registros`
          : `✓ ${data.partners_found} parceiros`;
    } else {
      els.refreshBtn.textContent = "✗ falhou — veja o console";
      console.error(data.error);
    }
  } catch (err) {
    els.refreshBtn.textContent = "✗ erro de rede";
    console.error(err);
  } finally {
    await loadPartners();
    await loadTickerAndStatus();
    setTimeout(() => {
      els.refreshBtn.disabled = false;
      els.refreshBtn.textContent = originalLabel;
    }, 2500);
  }
});

loadPartners();
