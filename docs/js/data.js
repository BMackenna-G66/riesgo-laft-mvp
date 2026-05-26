// data.js — carga y expone results.json
const Data = (() => {
  let _results = null;

  async function load() {
    const r = await fetch('data/results.json?v=' + Date.now());
    _results = await r.json();
    const el = document.getElementById('last-updated');
    if (el) {
      const label = _results.demo ? ' (datos demo)' : '';
      el.textContent = 'Corrida: ' + _results.run_date + label;
    }
    return _results;
  }

  function get()      { return _results; }
  function summary()  { return _results?.summary  || {}; }
  function segments() { return _results?.segment_summary || []; }
  function clients(filters = {}) {
    let list = _results?.top_clients || [];
    if (filters.nivel)  list = list.filter(c => c.nivel_riesgo_final === filters.nivel);
    if (filters.search) {
      const q = filters.search.toLowerCase();
      list = list.filter(c => String(c.customer_id).toLowerCase().includes(q) || (c.country_code||'').toLowerCase().includes(q));
    }
    return list;
  }
  function countryRisk() { return _results?.country_risk_summary || []; }

  return { load, get, summary, segments, clients, countryRisk };
})();
