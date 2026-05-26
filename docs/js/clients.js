// clients.js — tabla de clientes con filtros
const Clients = (() => {
  function _badge(nivel) {
    const map = { Alto: 'critico', Medio: 'alto', Bajo: 'bajo' };
    return `<span class="badge badge-${map[nivel]||'bajo'}">${nivel}</span>`;
  }

  function _scoreBar(score) {
    const pct = Math.round(score * 100);
    const color = score >= 0.67 ? 'var(--critico)' : score >= 0.34 ? 'var(--alto)' : 'var(--bajo)';
    return `
      <span style="font-variant-numeric:tabular-nums;font-weight:600;">${score.toFixed(4)}</span>
      <div class="score-bar" style="width:80px;display:inline-block;vertical-align:middle;margin-left:6px;">
        <div class="score-fill" style="width:${pct}%;background:${color};"></div>
      </div>`;
  }

  function render() {
    const nivel  = document.getElementById('filter-nivel')?.value || '';
    const search = document.getElementById('filter-search-c')?.value || '';
    const list   = Data.clients({ nivel, search });

    const count = document.getElementById('clients-count');
    if (count) count.textContent = `${list.length} clientes`;

    const tbody = document.getElementById('clients-tbody');
    if (!tbody) return;

    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="empty-state"><div class="icon">—</div><p>Sin resultados</p></td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(c => `
      <tr>
        <td style="font-weight:600;font-size:.78rem;">${c.customer_id}</td>
        <td>${c.country_code || '—'}</td>
        <td>${_scoreBar(c.score_final)}</td>
        <td>${_badge(c.nivel_riesgo_final)}</td>
        <td><span style="font-variant-numeric:tabular-nums;">${c.score_cliente.toFixed(4)}</span></td>
        <td><span style="font-variant-numeric:tabular-nums;">${c.score_jurisdiccion.toFixed(4)}</span></td>
        <td><span style="font-variant-numeric:tabular-nums;">${c.score_producto.toFixed(4)}</span></td>
        <td style="font-size:.75rem;color:var(--muted);">${c.principales_drivers || '—'}</td>
      </tr>
    `).join('');
  }

  return { render };
})();
