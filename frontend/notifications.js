(() => {
  'use strict';
  const logic = globalThis.TwoPickNotificationLogic;
  const root = document.querySelector('#notification-center');
  const openButton = document.querySelector('#notification-button');
  if (!logic || !root || !openButton) return;
  const ui = {
    badge: document.querySelector('#notification-badge'), list: root.querySelector('#notification-list'),
    close: root.querySelector('#notification-close'), backdrop: root.querySelector('#notification-backdrop'),
    readAll: root.querySelector('#notification-read-all'),
  };
  const items = [
    { id: 'condition', type: 'condition', title: '상대방이 조건을 제출했어요', message: '공동결정 화면에서 후보 추천을 이어갈 수 있어요.', created_at: '2026-11-25T09:30:00', route: 'decision' },
    { id: 'approval', type: 'approval', title: '후보 승인을 기다리고 있어요', message: '최신 후보를 확인하고 내 계정에서 직접 승인해 주세요.', created_at: '2026-11-25T08:40:00', route: 'decision' },
    { id: 'confirmed', type: 'confirmed', title: '두 사람의 결정이 확정됐어요', message: '확정된 선택은 기록 화면에서 다시 볼 수 있어요.', created_at: '2026-11-24T20:15:00', route: 'history' },
    { id: 'schedule', type: 'schedule', title: '내일은 첫 만남 기념일이에요', message: '등록된 일정과 준비할 내용을 확인해 보세요.', created_at: '2026-11-24T09:00:00', route: 'schedule' },
  ];
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
    if (!authenticated) return root.classList.add('hidden');
    readIds = loadReads();
    const count = logic.unreadCount(items, readIds);
    ui.badge.textContent = count > 9 ? '9+' : String(count);
    ui.badge.classList.toggle('hidden', count === 0);
    openButton.setAttribute('aria-label', `알림 센터 열기${count ? `, 읽지 않은 알림 ${count}개` : ''}`);
    ui.list.innerHTML = logic.sortNotifications(items).map((item) => {
      const unread = !readIds.includes(String(item.id));
      return `<button type="button" class="notification-item ${unread ? 'unread' : ''}" data-notification-id="${item.id}" data-route="${item.route}"><span class="notification-type ${item.type}" aria-hidden="true"></span><span><strong>${item.title}</strong><small>${item.message}</small><time>${new Date(item.created_at).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</time></span>${unread ? '<i aria-label="읽지 않음"></i>' : ''}</button>`;
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
