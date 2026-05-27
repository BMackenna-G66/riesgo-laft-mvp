// cluster.js — control del cluster Redshift desde el dashboard
const Cluster = (() => {

  const REPO   = 'BMackenna-G66/riesgo-laft-mvp';
  const GH_API = 'https://api.github.com';

  // Colores y textos por estado
  const STATUS_CONFIG = {
    available:  { color: '#1a7a3e', bg: '#e0f5e8', label: 'Disponible',  icon: '●' },
    paused:     { color: '#5a6880', bg: '#f0f3f7', label: 'Pausado',     icon: '◌' },
    resuming:   { color: '#c87a00', bg: '#fef3d0', label: 'Reanudando…', icon: '◑' },
    pausing:    { color: '#c87a00', bg: '#fef3d0', label: 'Pausando…',   icon: '◑' },
    error:      { color: '#c0392b', bg: '#fde8e8', label: 'Error',       icon: '✕' },
    unknown:    { color: '#5a6880', bg: '#f0f3f7', label: 'Desconocido', icon: '?' },
  };

  function _cfg(raw) {
    return STATUS_CONFIG[raw] || STATUS_CONFIG.unknown;
  }

  function _token() {
    return localStorage.getItem('gh_dispatch_token') || '';
  }

  function _saveToken(t) {
    if (t) localStorage.setItem('gh_dispatch_token', t.trim());
  }

  async function _dispatch(workflow, inputs = {}) {
    const token = _token();
    if (!token) {
      _showTokenModal();
      return false;
    }
    const res = await fetch(
      `${GH_API}/repos/${REPO}/actions/workflows/${workflow}/dispatches`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ref: 'main', inputs }),
      }
    );
    return res.status === 204;
  }

  async function _loadStatus() {
    try {
      const r = await fetch('data/cluster_status.json?v=' + Date.now());
      return await r.json();
    } catch { return null; }
  }

  async function render() {
    const status = await _loadStatus();
    const el = document.getElementById('cluster-content');
    if (!el) return;

    if (!status) {
      el.innerHTML = '<p style="color:var(--muted);">No se pudo cargar el estado del cluster.</p>';
      return;
    }

    const cfg = _cfg(status.status_raw);
    const isAvailable = status.status_raw === 'available';
    const isPaused    = status.status_raw === 'paused';
    const isTransient = ['resuming','pausing'].includes(status.status_raw);
    const checkedAt   = status.checked_at
      ? new Date(status.checked_at).toLocaleString('es-CL', { timeZone: 'America/Santiago' })
      : '—';

    const hasToken = !!_token();

    el.innerHTML = `
      <!-- Estado actual -->
      <div class="kpi-grid" style="margin-bottom:24px;">
        <div class="kpi-card" style="border-top-color:${cfg.color};">
          <div class="kpi-label">Estado del Cluster</div>
          <div class="kpi-value" style="font-size:1.4rem;color:${cfg.color};">${cfg.icon} ${cfg.label}</div>
          <div class="kpi-sub">Actualizado: ${checkedAt}</div>
        </div>
        <div class="kpi-card azul">
          <div class="kpi-label">Nodo</div>
          <div class="kpi-value" style="font-size:1.1rem;">${status.node_type || '—'}</div>
          <div class="kpi-sub">${status.number_of_nodes || 1} nodo · ${status.availability_zone || '—'}</div>
        </div>
        <div class="kpi-card azul">
          <div class="kpi-label">Base de datos</div>
          <div class="kpi-value" style="font-size:1.1rem;">${status.database_name || '—'}</div>
          <div class="kpi-sub">${(status.endpoint || '').split('.')[0] || '—'}</div>
        </div>
      </div>

      <!-- Controles -->
      <div class="detail-card" style="max-width:600px;margin-bottom:18px;">
        <h3 style="margin-bottom:16px;">Control del Cluster</h3>

        ${isTransient ? `
          <div style="padding:12px;background:#fef3d0;border-radius:6px;margin-bottom:16px;font-size:.84rem;color:#7a5800;">
            ⏳ Operación en curso — el cluster está en transición. Actualiza en 1–2 minutos.
          </div>` : ''}

        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;">
          <button
            class="btn btn-primary"
            onclick="Cluster.resume()"
            ${!isPaused || isTransient ? 'disabled' : ''}
            style="${!isPaused ? 'opacity:.45;cursor:not-allowed;' : ''}">
            ▶ Reanudar cluster
          </button>
          <button
            class="btn btn-secondary"
            onclick="Cluster.pause()"
            ${!isAvailable || isTransient ? 'disabled' : ''}
            style="${!isAvailable ? 'opacity:.45;cursor:not-allowed;' : ''}">
            ⏸ Pausar cluster
          </button>
          <button class="btn btn-secondary" onclick="Cluster.checkStatus()">
            ↻ Verificar estado
          </button>
        </div>

        <div style="font-size:.78rem;color:var(--muted);line-height:1.7;">
          Los botones disparan workflows en GitHub Actions.<br>
          <strong>Reanudar</strong> tarda ~2–3 minutos. <strong>Pausar</strong> se ejecuta al instante.<br>
          La pausa automática ocurre todos los días a las <strong>19:00 hora Chile</strong>.
        </div>
      </div>

      <!-- Token GitHub -->
      <div class="detail-card" style="max-width:600px;">
        <h3 style="margin-bottom:12px;">Autenticación GitHub</h3>
        ${hasToken
          ? `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
               <span style="font-size:.84rem;color:var(--bajo);">● Token configurado</span>
               <button class="btn btn-secondary btn-sm" onclick="Cluster.clearToken()">Cambiar token</button>
             </div>`
          : `<p style="font-size:.82rem;color:var(--muted);margin-bottom:12px;">
               Necesitas un <a href="https://github.com/settings/tokens/new?scopes=workflow&description=riesgo-laft-dispatch" target="_blank" style="color:var(--blue);">GitHub PAT</a>
               con permiso <code>workflow</code> para controlar el cluster desde aquí.
             </p>
             <div style="display:flex;gap:8px;">
               <input type="password" id="gh-token-input" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                 style="flex:1;padding:8px 11px;border:1px solid var(--border);border-radius:5px;font-size:.84rem;" />
               <button class="btn btn-primary btn-sm" onclick="Cluster.saveToken()">Guardar</button>
             </div>`
        }
        <p style="margin-top:10px;font-size:.72rem;color:var(--muted);">
          El token se guarda solo en tu navegador (localStorage). Nunca se envía al servidor.
          Permisos necesarios: <code>workflow</code> únicamente.
        </p>
      </div>
    `;
  }

  async function resume() {
    App.toast('Enviando solicitud de reanudación…', 'info');
    const ok = await _dispatch('resume_cluster.yml', { motivo: 'Manual desde dashboard' });
    if (ok) {
      App.toast('Reanudación iniciada. El estado se actualizará en ~1 minuto.', 'success');
      setTimeout(render, 4000);
    } else {
      App.toast('Error al disparar el workflow. Verifica el token GitHub.', 'error');
    }
  }

  async function pause() {
    if (!confirm('¿Pausar el cluster ahora? Las conexiones activas serán terminadas.')) return;
    App.toast('Enviando solicitud de pausa…', 'info');
    const ok = await _dispatch('pause_cluster.yml', { motivo: 'Manual desde dashboard' });
    if (ok) {
      App.toast('Pausa iniciada correctamente.', 'success');
      setTimeout(render, 4000);
    } else {
      App.toast('Error al disparar el workflow. Verifica el token GitHub.', 'error');
    }
  }

  async function checkStatus() {
    App.toast('Verificando estado…', 'info');
    const ok = await _dispatch('check_cluster_status.yml');
    if (ok) {
      App.toast('Verificación en curso. El estado se actualizará en ~30 segundos.', 'success');
      setTimeout(render, 35000);
    } else {
      App.toast('Error al disparar el workflow. Verifica el token GitHub.', 'error');
    }
  }

  function saveToken() {
    const val = document.getElementById('gh-token-input')?.value.trim();
    if (!val || !val.startsWith('ghp_')) {
      App.toast('Token inválido — debe comenzar con ghp_', 'error');
      return;
    }
    _saveToken(val);
    App.toast('Token guardado en tu navegador.', 'success');
    render();
  }

  function clearToken() {
    localStorage.removeItem('gh_dispatch_token');
    App.toast('Token eliminado.', 'info');
    render();
  }

  return { render, resume, pause, checkStatus, saveToken, clearToken };
})();
