(() => {
  const logic = window.MockFeaturesLogic;
  if (!logic) return;

  const history = [
    { id: 'dinner-1', category: 'meal', icon: '🍝', title: '금요일 저녁 메뉴', date: '2026. 11. 20.', result: '동네 파스타 식당', summary: '퇴근 후 가까운 곳에서 천천히 저녁을 먹기로 했어요.' },
    { id: 'weekend-1', category: 'date', icon: '🌿', title: '주말 데이트', date: '2026. 11. 15.', result: '서울숲 산책', summary: '사람이 적은 오전 시간에 만나 따뜻한 음료와 함께 산책했어요.' },
    { id: 'movie-1', category: 'home', icon: '🎬', title: '오늘 볼 영화', date: '2026. 11. 8.', result: '어바웃 타임', summary: '집에서 간단한 간식과 함께 다시 보고 싶던 영화를 골랐어요.' },
  ];
  const ratingKey = 'tow_pick_mock_satisfaction';
  const elements = {
    filter: document.querySelector('#history-filter'), list: document.querySelector('#history-list'),
    title: document.querySelector('#history-detail-title'), meta: document.querySelector('#history-detail-meta'),
    result: document.querySelector('#history-detail-result'), summary: document.querySelector('#history-detail-summary'),
    buttons: document.querySelector('#satisfaction-buttons'), status: document.querySelector('#satisfaction-status'),
  };
  if (!elements.list) return;

  let selectedId = history[0].id;
  const ratings = JSON.parse(localStorage.getItem(ratingKey) || '{}');

  function selectedItem() {
    return history.find((item) => item.id === selectedId) || history[0];
  }

  function saveRating(itemId, value) {
    const rating = logic.normalizeRating(value);
    if (!rating) return;
    ratings[itemId] = rating;
    localStorage.setItem(ratingKey, JSON.stringify(ratings));
    renderDetail();
  }

  function renderList() {
    const items = logic.filterHistory(history, elements.filter.value);
    elements.list.innerHTML = items.length ? items.map((item) => `
      <button type="button" class="history-item" data-history-id="${item.id}" aria-pressed="${item.id === selectedId}">
        <span class="history-icon" aria-hidden="true">${item.icon}</span>
        <span><strong>${item.title}</strong><small>${item.date} · ${item.result}</small></span>
        <span aria-hidden="true">→</span>
      </button>`).join('') : '<p class="decision-empty">이 분류의 기록이 아직 없어요.</p>';
    if (items.length && !items.some((item) => item.id === selectedId)) selectedId = items[0].id;
    renderDetail();
  }

  function renderDetail() {
    const item = selectedItem();
    const currentRating = logic.normalizeRating(ratings[item.id]);
    elements.title.textContent = item.title;
    elements.meta.textContent = `${item.date} · 두 사람 모두 승인`;
    elements.result.textContent = item.result;
    elements.summary.textContent = item.summary;
    elements.buttons.innerHTML = [1, 2, 3, 4, 5].map((rating) => `
      <button type="button" data-rating="${rating}" aria-label="만족도 ${rating}점" aria-pressed="${currentRating === rating}">${rating}<span>♥</span></button>`).join('');
    elements.status.textContent = currentRating
      ? `${currentRating}점 · ${logic.getSatisfactionLabel(currentRating)} (이 브라우저의 테스트 데이터에 저장됨)`
      : logic.getSatisfactionLabel(null);
  }

  elements.filter.addEventListener('change', renderList);
  elements.list.addEventListener('click', (event) => {
    const button = event.target.closest('[data-history-id]');
    if (!button) return;
    selectedId = button.dataset.historyId;
    renderList();
  });
  elements.buttons.addEventListener('click', (event) => {
    const button = event.target.closest('[data-rating]');
    if (button) saveRating(selectedItem().id, button.dataset.rating);
  });
  renderList();
})();

(() => {
  const logic = window.MockFeaturesLogic;
  const form = document.querySelector('#schedule-form');
  if (!logic || !form) return;

  const storageKey = 'tow_pick_mock_schedules';
  const seedEvents = [
    { id: 'seed-1', title: '우리의 첫 만남 기념일', date: '2026-11-26', type: 'anniversary' },
    { id: 'seed-2', title: '겨울 전시회 데이트', date: '2026-11-29', type: 'date' },
    { id: 'seed-3', title: '함께 장보기', date: '2026-12-05', type: 'todo' },
  ];
  const elements = {
    month: document.querySelector('#calendar-month'), grid: document.querySelector('#calendar-grid'),
    prev: document.querySelector('#calendar-prev'), next: document.querySelector('#calendar-next'),
    list: document.querySelector('#schedule-list'), status: document.querySelector('#schedule-form-status'),
    date: document.querySelector('#schedule-date-input'),
  };
  const typeLabels = { anniversary: '기념일', date: '데이트', todo: '함께 할 일' };
  const pad = (value) => String(value).padStart(2, '0');
  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const today = new Date();
  let viewDate = new Date(today.getFullYear(), today.getMonth(), 1);
  let schedules;
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) || 'null');
    schedules = Array.isArray(stored) ? stored : seedEvents.slice();
  } catch (_) {
    schedules = seedEvents.slice();
  }
  elements.date.value = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;

  function persist() {
    localStorage.setItem(storageKey, JSON.stringify(schedules));
  }

  function renderCalendar() {
    const year = viewDate.getFullYear();
    const month = viewDate.getMonth();
    elements.month.textContent = `${year}년 ${month + 1}월`;
    elements.grid.innerHTML = logic.buildCalendarDays(year, month, schedules).map((day) => {
      const eventLabels = day.events.slice(0, 2).map((event) => `<small class="calendar-event ${event.type}">${escapeHtml(event.title)}</small>`).join('');
      const extra = day.events.length > 2 ? `<small class="calendar-extra">+${day.events.length - 2}</small>` : '';
      return `<button type="button" class="calendar-day${day.inMonth ? '' : ' muted'}" data-calendar-date="${day.date}" aria-label="${day.date}, 일정 ${day.events.length}개"><span>${day.day}</span>${eventLabels}${extra}</button>`;
    }).join('');
  }

  function renderList() {
    const sorted = schedules.slice().sort((a, b) => a.date.localeCompare(b.date));
    elements.list.innerHTML = sorted.length ? sorted.map((event) => `
      <article class="schedule-item">
        <time datetime="${event.date}"><strong>${event.date.slice(5).replace('-', '.')}</strong><span>${event.date.slice(0, 4)}</span></time>
        <div><span class="schedule-type ${event.type}">${typeLabels[event.type]}</span><strong>${escapeHtml(event.title)}</strong></div>
        <button type="button" data-delete-schedule="${event.id}" aria-label="${escapeHtml(event.title)} 삭제">삭제</button>
      </article>`).join('') : '<p class="decision-empty">등록된 일정이 없어요.</p>';
  }

  function renderAll() {
    renderCalendar();
    renderList();
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form));
    const validation = logic.validateSchedule(values);
    if (!validation.valid) {
      elements.status.textContent = validation.error;
      return;
    }
    schedules.push({ id: `local-${Date.now()}`, ...validation.value });
    persist();
    const [year, month] = validation.value.date.split('-').map(Number);
    viewDate = new Date(year, month - 1, 1);
    form.reset();
    elements.date.value = validation.value.date;
    elements.status.textContent = '테스트 일정으로 등록했습니다. 실제 API 연동 전까지 이 브라우저에만 저장됩니다.';
    renderAll();
  });

  elements.prev.addEventListener('click', () => { viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1); renderCalendar(); });
  elements.next.addEventListener('click', () => { viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1); renderCalendar(); });
  elements.grid.addEventListener('click', (event) => {
    const day = event.target.closest('[data-calendar-date]');
    if (day) elements.date.value = day.dataset.calendarDate;
  });
  elements.list.addEventListener('click', (event) => {
    const button = event.target.closest('[data-delete-schedule]');
    if (!button) return;
    schedules = schedules.filter((item) => item.id !== button.dataset.deleteSchedule);
    persist();
    elements.status.textContent = '테스트 일정을 삭제했습니다.';
    renderAll();
  });
  renderAll();
})();
