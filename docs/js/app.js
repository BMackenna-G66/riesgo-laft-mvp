// app.js — router principal
const App = (() => {
  const PAGES = {
    dashboard: { title: 'Dashboard',          render: () => Dashboard.render() },
    clients:   { title: 'Clientes',           render: () => Clients.render() },
    cluster:   { title: 'Cluster Redshift',   render: () => Cluster.render() },
    export:    { title: 'Exportar',           render: () => Export.updatePreview() },
  };

  function navigate(page) {
    if (!PAGES[page]) page = 'dashboard';
    document.querySelectorAll('.nav-link').forEach(a => {
      a.classList.toggle('active', a.dataset.page === page);
    });
    document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
    const el = document.getElementById('page-' + page);
    if (el) el.style.display = 'block';
    document.getElementById('page-title').textContent = PAGES[page].title;
    window.location.hash = page;
    PAGES[page].render();
  }

  async function _updateClusterPill() {
    try {
      const r = await fetch('data/cluster_status.json?v=' + Date.now());
      const s = await r.json();
      const pill = document.getElementById('cluster-status-pill');
      if (!pill) return;
      const colors = {
        available: { bg: '#1a7a3e', text: '#fff' },
        paused:    { bg: 'rgba(255,255,255,.15)', text: 'rgba(255,255,255,.65)' },
        resuming:  { bg: '#c87a00', text: '#fff' },
        pausing:   { bg: '#c87a00', text: '#fff' },
      };
      const c = colors[s.status_raw] || colors.paused;
      pill.textContent = s.status_label || s.status_raw;
      pill.style.background = c.bg;
      pill.style.color = c.text;
    } catch { /* silencioso */ }
  }

  async function reload() {
    document.getElementById('global-loader').style.display = 'flex';
    try {
      await Data.load();
      _updateClusterPill();
      const cur = (window.location.hash || '#dashboard').slice(1);
      navigate(cur in PAGES ? cur : 'dashboard');
    } catch(e) {
      toast('Error cargando datos: ' + e.message, 'error');
    } finally {
      document.getElementById('global-loader').style.display = 'none';
    }
  }

  function toast(msg, type = 'info') {
    const div = document.createElement('div');
    div.className = `toast toast-${type}`;
    div.textContent = msg;
    document.getElementById('toast-container').appendChild(div);
    setTimeout(() => div.remove(), 3500);
  }

  async function init() {
    document.querySelectorAll('.nav-link').forEach(a => {
      a.addEventListener('click', e => { e.preventDefault(); navigate(a.dataset.page); });
    });
    window.addEventListener('hashchange', () => {
      const p = window.location.hash.slice(1);
      if (p in PAGES) navigate(p);
    });
    await reload();
    // Refresca el pill del cluster cada 2 minutos sin recargar toda la página
    setInterval(_updateClusterPill, 120_000);
  }

  return { navigate, reload, toast, init };
})();

document.addEventListener('DOMContentLoaded', App.init);
