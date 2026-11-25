(() => {
  'use strict';
  const logic = globalThis.TwoPickServiceShellLogic;
  const nav = document.querySelector('#service-nav');
  if (!logic || !nav) return;
  const pages = Array.from(document.querySelectorAll('[data-service-page]'));
  const links = Array.from(nav.querySelectorAll('[data-service-route]'));

  function isReady() {
    return Boolean(state.user && state.couple?.members?.length === 2);
  }

  function renderRoute(options = {}) {
    const ready = isReady();
    const route = logic.normalizeRoute(location.hash);
    nav.classList.toggle('hidden', !ready);
    for (const page of pages) {
      page.classList.toggle('service-page-hidden', !ready || page.dataset.servicePage !== route);
    }
    for (const link of links) {
      const current = link.dataset.serviceRoute === route;
      link.classList.toggle('active', current);
      if (current) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
    document.body.dataset.serviceRoute = ready ? route : '';
    if (ready && options.focus) {
      const heading = pages.find((page) => page.dataset.servicePage === route)?.querySelector('h2, h3');
      if (heading) {
        heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: false });
      }
    }
  }

  window.addEventListener('hashchange', () => renderRoute({ focus: true }));
  window.addEventListener('twopick:session-changed', () => {
    if (isReady() && !location.hash) history.replaceState(null, '', '#home');
    renderRoute();
  });
  renderRoute();
})();
