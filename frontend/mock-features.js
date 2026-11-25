(() => {
  const logic = window.MockFeaturesLogic;
  const data = window.TwoPickFeatureData;
  const form = document.querySelector('#schedule-form');
  if (!logic || !data || !form) return;

  const storageKey = 'tow_pick_mock_schedules';
  const seedEvents = data.getMockData('schedules');
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
    window.dispatchEvent(new CustomEvent('twopick:schedules-changed', { detail: { schedules: schedules.slice() } }));
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
