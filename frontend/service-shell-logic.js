(function exposeServiceShellLogic(root) {
  const routes = ['home', 'decision', 'history', 'schedule', 'pet', 'settings'];

  function normalizeRoute(hash) {
    const route = String(hash || '').replace(/^#/, '').trim().toLowerCase();
    return routes.includes(route) ? route : 'home';
  }

  function routeTitle(route) {
    return ({ home: '홈', decision: '공동결정', history: '기록', schedule: '일정', pet: '펫', settings: '설정' })[normalizeRoute(route)];
  }

  root.TwoPickServiceShellLogic = { routes, normalizeRoute, routeTitle };
}(typeof window !== 'undefined' ? window : globalThis));
