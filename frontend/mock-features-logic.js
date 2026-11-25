(function exposeMockFeaturesLogic(root) {
  function normalizeRating(value) {
    const rating = Number(value);
    return Number.isInteger(rating) && rating >= 1 && rating <= 5 ? rating : null;
  }

  function filterHistory(items, category = 'all') {
    if (!Array.isArray(items)) return [];
    return category === 'all' ? items.slice() : items.filter((item) => item.category === category);
  }

  function getSatisfactionLabel(value) {
    const labels = ['아쉬워요', '조금 아쉬워요', '괜찮았어요', '만족해요', '정말 좋았어요'];
    const rating = normalizeRating(value);
    return rating ? labels[rating - 1] : '아직 평가하지 않았어요';
  }

  function validateSchedule(input) {
    const title = String(input?.title || '').trim();
    const date = String(input?.date || '');
    const allowedTypes = ['anniversary', 'date', 'todo'];
    if (!title || title.length > 40) return { valid: false, error: '일정 이름을 1~40자로 입력해 주세요.' };
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return { valid: false, error: '올바른 날짜를 선택해 주세요.' };
    const [year, month, day] = date.split('-').map(Number);
    const parsed = new Date(year, month - 1, day);
    if (parsed.getFullYear() !== year || parsed.getMonth() !== month - 1 || parsed.getDate() !== day) {
      return { valid: false, error: '존재하는 날짜를 선택해 주세요.' };
    }
    const type = allowedTypes.includes(input?.type) ? input.type : 'todo';
    return { valid: true, value: { title, date, type } };
  }

  function buildCalendarDays(year, month, events = []) {
    const firstWeekday = new Date(year, month, 1).getDay();
    const gridStart = new Date(year, month, 1 - firstWeekday);
    const pad = (value) => String(value).padStart(2, '0');
    return Array.from({ length: 42 }, (_, index) => {
      const current = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index);
      const iso = `${current.getFullYear()}-${pad(current.getMonth() + 1)}-${pad(current.getDate())}`;
      return { date: iso, day: current.getDate(), inMonth: current.getMonth() === month, events: events.filter((event) => event.date === iso) };
    });
  }

  root.MockFeaturesLogic = { normalizeRating, filterHistory, getSatisfactionLabel, validateSchedule, buildCalendarDays };
}(typeof window !== 'undefined' ? window : globalThis));
