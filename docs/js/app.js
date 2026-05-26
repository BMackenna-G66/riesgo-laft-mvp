// app.js — router principal
const App = (() => {
  const PAGES = {
    dashboard: { title: 'Dashboard',          render: () => Dashboard.render() },
    clients:   { title: 'Clientes',           render: () => Clients.render() },
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

  async function reload() {
    document.getElementById('global-loader').style.display = 'flex';
    try {
      await Data.load();
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

    // Tabs en detalle (si aplica)
    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const group = tab.closest('.tabs');
        group.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const pane = tab.dataset.tab;
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        document.getElementById('tab-' + pane)?.classList.add('active');
      });
    });

    await reload();
  }

  return { navigate, reload, toast, init };
})();

document.addEventListener('DOMContentLoaded', App.init);
