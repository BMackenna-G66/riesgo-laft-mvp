// dashboard.js — KPIs y gráficos del Dashboard
const Dashboard = (() => {
  let _charts = {};

  function _destroyChart(id) {
    if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
  }

  function _riskColor(nivel) {
    return { Alto: '#c0392b', Medio: '#c87a00', Bajo: '#1a7a3e' }[nivel] || '#5a6880';
  }

  function render() {
    const s = Data.summary();
    const segs = Data.segments();

    // KPIs
    const total = s.total_clients || 0;
    const alto  = s.alto  || 0;
    const medio = s.medio || 0;
    const bajo  = s.bajo  || 0;

    document.getElementById('kpi-grid').innerHTML = `
      <div class="kpi-card azul">
        <div class="kpi-label">Total clientes</div>
        <div class="kpi-value">${total.toLocaleString('es-CL')}</div>
        <div class="kpi-sub">evaluados en este ciclo</div>
      </div>
      <div class="kpi-card critico">
        <div class="kpi-label">Riesgo Alto</div>
        <div class="kpi-value">${alto.toLocaleString('es-CL')}</div>
        <div class="kpi-sub">${total ? ((alto/total)*100).toFixed(1) : 0}% del total</div>
      </div>
      <div class="kpi-card alto">
        <div class="kpi-label">Riesgo Medio</div>
        <div class="kpi-value">${medio.toLocaleString('es-CL')}</div>
        <div class="kpi-sub">${total ? ((medio/total)*100).toFixed(1) : 0}% del total</div>
      </div>
      <div class="kpi-card verde">
        <div class="kpi-label">Riesgo Bajo</div>
        <div class="kpi-value">${bajo.toLocaleString('es-CL')}</div>
        <div class="kpi-sub">${total ? ((bajo/total)*100).toFixed(1) : 0}% del total</div>
      </div>
      <div class="kpi-card azul">
        <div class="kpi-label">Score Final Prom.</div>
        <div class="kpi-value">${(s.score_final_avg||0).toFixed(4)}</div>
        <div class="kpi-sub">escala 0 – 1</div>
      </div>
      <div class="kpi-card azul">
        <div class="kpi-label">Score Clientes Prom.</div>
        <div class="kpi-value">${(s.score_cliente_avg||0).toFixed(4)}</div>
        <div class="kpi-sub">Factor 1 — peso 40%</div>
      </div>
    `;

    // Gráfico 1: Distribución de riesgo (doughnut)
    _destroyChart('chart-dist');
    const ctx1 = document.getElementById('chart-dist').getContext('2d');
    _charts['chart-dist'] = new Chart(ctx1, {
      type: 'doughnut',
      data: {
        labels: segs.map(s => s.nivel),
        datasets: [{
          data: segs.map(s => s.total),
          backgroundColor: segs.map(s => _riskColor(s.nivel)),
          borderWidth: 2, borderColor: '#fff',
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 14 } },
          tooltip: {
            callbacks: {
              label: ctx => ` ${ctx.label}: ${ctx.raw.toLocaleString('es-CL')} clientes (${((ctx.raw/total)*100).toFixed(1)}%)`
            }
          }
        }
      }
    });

    // Gráfico 2: Score promedio por factor (bar horizontal)
    _destroyChart('chart-factors');
    const ctx2 = document.getElementById('chart-factors').getContext('2d');
    const weights = s.weights || {};
    _charts['chart-factors'] = new Chart(ctx2, {
      type: 'bar',
      data: {
        labels: [
          `Clientes (${((weights.clientes||0)*100).toFixed(0)}%)`,
          `Jurisdicciones (${((weights.jurisdicciones||0)*100).toFixed(0)}%)`,
          `Productos (${((weights.productos||0)*100).toFixed(0)}%)`,
          `Canales (${((weights.canales||0)*100).toFixed(0)}%)`
        ],
        datasets: [{
          label: 'Score promedio',
          data: [
            s.score_cliente_avg || 0,
            s.score_jurisdiccion_avg || 0,
            s.score_producto_avg || 0,
            s.score_canal_avg || 0,
          ],
          backgroundColor: ['#1e5fbc','#2d7ae8','#6aabff','#93c5fd'],
          borderRadius: 4,
        }]
      },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { min: 0, max: 1, ticks: { stepSize: 0.2 }, grid: { color: '#dde3ec' } },
          y: { grid: { display: false } }
        }
      }
    });

    // Gráfico 3: Top países por clientes de riesgo (bar)
    const countries = Data.countryRisk().slice(0, 10);
    _destroyChart('chart-countries');
    const ctx3 = document.getElementById('chart-countries').getContext('2d');
    _charts['chart-countries'] = new Chart(ctx3, {
      type: 'bar',
      data: {
        labels: countries.map(c => c.country_name || c.country_code),
        datasets: [{
          label: 'Score promedio',
          data: countries.map(c => c.avg_score),
          backgroundColor: countries.map(c => c.avg_score >= 0.67 ? '#c0392b' : c.avg_score >= 0.34 ? '#c87a00' : '#1a7a3e'),
          borderRadius: 4,
        }]
      },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { min: 0, max: 1, ticks: { stepSize: 0.2 } },
          y: { grid: { display: false } }
        }
      }
    });
  }

  return { render };
})();
