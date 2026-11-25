(() => {
  'use strict';
  const logic = globalThis.TwoPickDashboardLogic;
  const data = globalThis.TwoPickFeatureData;
  const scheduleLogic = globalThis.TwoPickScheduleApiLogic;
  const root = document.querySelector('#main-dashboard');
  if (!logic || !data || !scheduleLogic || !root) return;

  const ui = {
    greeting: root.querySelector('#dashboard-greeting'),
    refresh: root.querySelector('#dashboard-refresh'),
    active: root.querySelector('#dashboard-active-list'),
    confirmed: root.querySelector('#dashboard-confirmed-list'),
    schedules: root.querySelector('#dashboard-schedule-list'),
    pet: root.querySelector('#dashboard-pet-connection'),
    couple: root.querySelector('#dashboard-couple-summary'), notifications: root.querySelector('#dashboard-notification-summary'),
  };
  let busy = false;

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  }

  function renderEmpty(target, message) {
    target.innerHTML = `<p class="dashboard-empty">${escapeHtml(message)}</p>`;
  }

  function renderSchedules(schedules = []) {
    const items = scheduleLogic.upcomingOccurrences(schedules, new Date(), 3);
    if (!items.length) return renderEmpty(ui.schedules, '다가오는 일정이 없어요.');
    ui.schedules.innerHTML = items.map((item) => `<div class="dashboard-item"><time datetime="${item.date}">${item.date.slice(5).replace('-', '.')}</time><div><strong>${escapeHtml(item.title)}</strong><small>${item.kind === 'anniversary' ? '기념일' : '일반 일정'} · ${item.local_time ? item.local_time.slice(0, 5) : '종일'}</small></div></div>`).join('');
  }

  function renderCouple() {
    const members = state.couple?.members || [];
    ui.couple.innerHTML = `<div class="dashboard-item"><span class="dashboard-check">${members.length >= 2 ? '✓' : '…'}</span><div><strong>${members.length >= 2 ? '두 사람 연결됨' : '상대방 연결 대기'}</strong><small>${members.map((item) => escapeHtml(item.nickname)).join(' · ') || '커플 연결 정보 없음'}</small></div></div>`;
  }
  function renderNotificationSetting(setting) {
    ui.notifications.innerHTML = `<div class="dashboard-item"><span class="dashboard-check">${setting.consent ? '✓' : '–'}</span><div><strong>${setting.consent ? '알림 수신 동의' : '알림 미동의'}</strong><small>${setting.consent ? `${setting.d1_enabled ? 'D-1 ' : ''}${setting.day_of_enabled ? '당일 ' : ''}· ${String(setting.send_time).slice(0, 5)} · 실제 발송 준비 중` : '설정에서 본인 동의를 변경할 수 있어요.'}</small></div></div>`;
  }

  function renderDecisions(decisions, confirmations) {
    const summary = logic.summarizeDecisions(decisions, confirmations);
    if (!summary.active.length) renderEmpty(ui.active, '진행 중인 공동결정이 없어요. 새로운 결정을 시작해 보세요.');
    else ui.active.innerHTML = summary.active.map((item) => `<a class="dashboard-item" href="#decision"><span class="dashboard-dot"></span><div><strong>${escapeHtml(item.title)}</strong><small>진행 중 · 이어서 조건이나 승인을 확인하세요.</small></div><span>→</span></a>`).join('');

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
    renderCouple();
    try {
      const [decisions, confirmations, schedules, notificationSetting] = await Promise.all([
        api('/decisions'),
        api('/decision-confirmations'), api('/schedules'), api('/notifications/settings/me'),
      ]);
      renderDecisions(decisions, confirmations);
      renderSchedules(schedules); renderNotificationSetting(notificationSetting);
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
  window.addEventListener('twopick:schedules-changed', (event) => renderSchedules(event.detail.schedules));
  window.addEventListener('twopick:notification-settings-changed', (event) => renderNotificationSetting(event.detail));
  window.addEventListener('twopick:pet-state', (event) => {
    const labels = [event.detail.usb && 'USB', event.detail.ble && 'BLE'].filter(Boolean);
    ui.pet.textContent = labels.length ? `PET DOCK ${labels.join(' + ')} 연결됨` : 'PET DOCK 연결 대기';
  });
  refresh();
})();
