(() => {
  'use strict';
  const logic = globalThis.TwoPickDashboardLogic;
  const root = document.querySelector('#main-dashboard');
  if (!logic || !root) return;

  const ui = {
    greeting: root.querySelector('#dashboard-greeting'),
    refresh: root.querySelector('#dashboard-refresh'),
    active: root.querySelector('#dashboard-active-list'),
    confirmed: root.querySelector('#dashboard-confirmed-list'),
    schedules: root.querySelector('#dashboard-schedule-list'),
    pet: root.querySelector('#dashboard-pet-connection'),
  };
  const mockScheduleSeed = [
    { id: 'seed-1', title: '우리의 첫 만남 기념일', date: '2026-11-26', type: 'anniversary' },
    { id: 'seed-2', title: '겨울 전시회 데이트', date: '2026-11-29', type: 'date' },
    { id: 'seed-3', title: '함께 장보기', date: '2026-12-05', type: 'todo' },
  ];
  let busy = false;

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  }

  function readSchedules() {
    try {
      const stored = JSON.parse(localStorage.getItem('tow_pick_mock_schedules') || 'null');
      return Array.isArray(stored) ? stored : mockScheduleSeed;
    } catch (_) {
      return mockScheduleSeed;
    }
  }

  function renderEmpty(target, message) {
    target.innerHTML = `<p class="dashboard-empty">${escapeHtml(message)}</p>`;
  }

  function renderSchedules() {
    const items = logic.upcomingSchedules(readSchedules(), new Date());
    if (!items.length) return renderEmpty(ui.schedules, '다가오는 테스트 일정이 없어요.');
    ui.schedules.innerHTML = items.map((item) => `<div class="dashboard-item"><time datetime="${item.date}">${item.date.slice(5).replace('-', '.')}</time><div><strong>${escapeHtml(item.title)}</strong><small>${item.type === 'anniversary' ? '기념일' : item.type === 'date' ? '데이트' : '함께 할 일'}</small></div></div>`).join('');
  }

  function renderDecisions(decisions, confirmations) {
    const summary = logic.summarizeDecisions(decisions, confirmations);
    if (!summary.active.length) renderEmpty(ui.active, '진행 중인 공동결정이 없어요. 새로운 결정을 시작해 보세요.');
    else ui.active.innerHTML = summary.active.map((item) => `<a class="dashboard-item" href="#decision-workspace"><span class="dashboard-dot"></span><div><strong>${escapeHtml(item.title)}</strong><small>진행 중 · 이어서 조건이나 승인을 확인하세요.</small></div><span>→</span></a>`).join('');

    if (!summary.confirmed.length) renderEmpty(ui.confirmed, '최근 확정된 결정이 아직 없어요.');
    else ui.confirmed.innerHTML = summary.confirmed.map((item) => `<div class="dashboard-item"><span class="dashboard-check">✓</span><div><strong>${escapeHtml(item.confirmation?.content_snapshot || item.title)}</strong><small>${item.confirmation?.confirmed_at ? new Date(item.confirmation.confirmed_at).toLocaleDateString('ko-KR') : '확정 완료'}</small></div></div>`).join('');
  }

  async function refresh() {
    const active = Boolean(state.user && state.token && state.couple?.members?.length === 2);
    root.classList.toggle('hidden', !active);
    if (!active || busy) return;
    busy = true;
    ui.refresh.disabled = true;
    ui.refresh.textContent = '불러오는 중…';
    ui.greeting.textContent = `${state.user.nickname}님의 오늘`;
    renderSchedules();
    try {
      const [decisions, confirmations] = await Promise.all([
        api('/decisions'),
        api('/decision-confirmations').catch(() => []),
      ]);
      renderDecisions(decisions, confirmations);
    } catch (error) {
      renderEmpty(ui.active, error.message);
      renderEmpty(ui.confirmed, '결정 기록을 불러오지 못했어요.');
    } finally {
      busy = false;
      ui.refresh.disabled = false;
      ui.refresh.textContent = '대시보드 새로고침';
    }
  }

  ui.refresh.addEventListener('click', refresh);
  window.addEventListener('twopick:session-changed', refresh);
  window.addEventListener('twopick:decisions-changed', refresh);
  window.addEventListener('twopick:schedules-changed', renderSchedules);
  window.addEventListener('twopick:pet-state', (event) => {
    const labels = [event.detail.usb && 'USB', event.detail.ble && 'BLE'].filter(Boolean);
    ui.pet.textContent = labels.length ? `PET DOCK ${labels.join(' + ')} 연결됨` : 'PET DOCK 연결 대기';
  });
  refresh();
})();
