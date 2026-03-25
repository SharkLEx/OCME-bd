/**
 * live-data.js — Carrega dados ao vivo do card_server e atualiza o DOM
 *
 * Uso: <script src="live-data.js" data-card="token-bd"></script>
 *
 * Elementos com data-live="campo" têm seu textContent atualizado.
 * Elementos com data-live="campo" + data-live-prop="style.width"
 * têm a propriedade CSS atualizada.
 *
 * Graceful degradation: se a API falhar, o conteúdo estático permanece.
 */
(function () {
  const script  = document.currentScript;
  const cardName = script && script.getAttribute('data-card');
  if (!cardName) return;

  function applyData(data) {
    document.querySelectorAll('[data-live]').forEach(function (el) {
      const field = el.getAttribute('data-live');
      const prop  = el.getAttribute('data-live-prop') || 'textContent';
      if (data[field] === undefined || data[field] === null) return;
      if (prop === 'textContent') {
        el.textContent = data[field];
      } else if (prop.startsWith('style.')) {
        el.style[prop.slice(6)] = data[field];
      } else {
        el.setAttribute(prop, data[field]);
      }
    });
  }

  function load() {
    fetch('/api/data/' + cardName)
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (data) { applyData(data); })
      .catch(function () { /* silently fail — static content permanece */ });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
