(() => {
  'use strict';
  const logic = globalThis.TwoPickNotificationLogic;
  const data = globalThis.TwoPickFeatureData;
  const root = document.querySelector('#notification-center');
  const openButton = document.querySelector('#notification-button');
  if (!logic || !data || !root || !openButton) return;
  const ui = {
    badge: document.querySelector('#notification-badge'), list: root.querySelector('#notification-list'),
    close: root.querySelector('#notification-close'), backdrop: root.querySelector('#notification-backdrop'),
    readAll: root.querySelector('#notification-read-all'),
  };
  const items = data.getMockData('notifications');
  let readIds = [];

  function storageKey() { return state.user ? `tow_pick_mock_notification_reads_${state.user.id}` : ''; }
  function loadReads() {
    try { const value = JSON.parse(localStorage.getItem(storageKey()) || '[]'); return Array.isArray(value) ? value.map(String) : []; }
    catch (_) { return []; }
  }
  function persist() { if (storageKey()) localStorage.setItem(storageKey(), JSON.stringify(readIds)); }

  function render() {
    const authenticated = Boolean(state.user);
    openButton.classList.toggle('hidden', !authenticated);
    if (!authenticated) { readIds = []; ui.list.innerHTML = ''; ui.badge.textContent = '0'; ui.badge.classList.add('hidden'); return root.classList.add('hidden'); }
    readIds = loadReads();
    const count = logic.unreadCount(items, readIds);
    ui.badge.textContent = count > 9 ? '9+' : String(count);
    ui.badge.classList.toggle('hidden', count === 0);
    openButton.setAttribute('aria-label', `알림 센터 열기${count ? `, 읽지 않은 알림 ${count}개` : ''}`);
    ui.list.innerHTML = logic.sortNotifications(items).map((item) => {
      const unread = !readIds.includes(String(item.id));
      return `<button type="button" class="notification-item ${unread ? 'unread' : ''}" data-notification-id="${item.id}" data-route="${item.route}"><span class="notification-type ${item.type}" aria-hidden="true"></span><span><strong>${item.title}</strong><small>${item.message}</small><time>${new Date(item.created_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</time></span>${unread ? '<i aria-label="읽지 않음"></i>' : ''}</button>`;
    }).join('');
  }

  function open() { render(); root.classList.remove('hidden'); document.body.classList.add('overlay-open'); queueMicrotask(() => ui.close.focus()); }
  function close() { root.classList.add('hidden'); document.body.classList.remove('overlay-open'); openButton.focus(); }
  openButton.addEventListener('click', open);
  ui.close.addEventListener('click', close);
  ui.backdrop.addEventListener('click', close);
  ui.readAll.addEventListener('click', () => { readIds = items.map((item) => String(item.id)); persist(); render(); });
  ui.list.addEventListener('click', (event) => {
    const button = event.target.closest('[data-notification-id]');
    if (!button) return;
    readIds = logic.markRead(readIds, button.dataset.notificationId);
    persist();
    close();
    location.hash = button.dataset.route;
  });
  root.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });
  window.addEventListener('twopick:session-changed', render);
  render();
})();
