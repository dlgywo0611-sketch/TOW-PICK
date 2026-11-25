(function exposeScheduleApiLogic(root) {
  'use strict';
  const SEOUL_TIME_ZONE = 'Asia/Seoul';
  const pad = (value) => String(value).padStart(2, '0');
  const dateKey = (year, month, day) => `${year}-${pad(month + 1)}-${pad(day)}`;
  const daysInMonth = (year, month) => new Date(Date.UTC(year, month + 1, 0)).getUTCDate();

  function parseDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
    if (!match) return null;
    const year = Number(match[1]); const month = Number(match[2]) - 1; const day = Number(match[3]);
    if (month < 0 || month > 11 || day < 1 || day > daysInMonth(year, month)) return null;
    return { year, month, day, key: dateKey(year, month, day) };
  }

  function seoulDateParts(value = new Date()) {
    if (typeof value === 'string' && parseDate(value)) return parseDate(value);
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: SEOUL_TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(value).reduce((result, part) => ({ ...result, [part.type]: part.value }), {});
    return parseDate(`${parts.year}-${parts.month}-${parts.day}`);
  }

  function addDays(parts, count) {
    const value = new Date(Date.UTC(parts.year, parts.month, parts.day + count));
    return parseDate(dateKey(value.getUTCFullYear(), value.getUTCMonth(), value.getUTCDate()));
  }

  function validateInput(input) {
    const title = String(input?.title || '').trim(); const local_date = String(input?.local_date || ''); const kind = input?.kind === 'anniversary' ? 'anniversary' : 'schedule';
    const repeat_rule = ['none', 'weekly', 'monthly', 'yearly'].includes(input?.repeat_rule) ? input.repeat_rule : (kind === 'anniversary' ? 'yearly' : 'none'); const local_time = String(input?.local_time || '').trim() || null;
    if (!title || title.length > 200) return { valid: false, error: '일정 이름을 1~200자로 입력해 주세요.' };
    if (!parseDate(local_date)) return { valid: false, error: '올바른 날짜를 선택해 주세요.' };
    if (local_time && !/^([01]\d|2[0-3]):[0-5]\d$/.test(local_time)) return { valid: false, error: '올바른 시간을 선택해 주세요.' };
    if (kind === 'anniversary' && !['none', 'yearly'].includes(repeat_rule)) return { valid: false, error: '기념일은 반복 없음 또는 매년 반복만 선택할 수 있어요.' };
    return { valid: true, value: { title, kind, local_date, local_time, repeat_rule } };
  }

  function occurrencesForMonth(schedule, year, month) {
    const anchor = parseDate(schedule.local_date); if (!anchor) return [];
    const first = parseDate(dateKey(year, month, 1)); const lastKey = dateKey(year, month, daysInMonth(year, month));
    const dates = []; const rule = schedule.repeat_rule || 'none';
    if (rule === 'none') {
      if (anchor.year === year && anchor.month === month) dates.push(anchor.key);
    } else if (rule === 'weekly') {
      let cursor = anchor;
      while (cursor.key < first.key) cursor = addDays(cursor, 7);
      while (cursor.key <= lastKey) { dates.push(cursor.key); cursor = addDays(cursor, 7); }
    } else if (rule === 'monthly') {
      const candidate = dateKey(year, month, Math.min(anchor.day, daysInMonth(year, month)));
      if (candidate >= anchor.key) dates.push(candidate);
    } else if (rule === 'yearly' && anchor.month === month) {
      const candidate = dateKey(year, month, Math.min(anchor.day, daysInMonth(year, month)));
      if (candidate >= anchor.key) dates.push(candidate);
    }
    return dates.map((date) => ({ ...schedule, date, type: schedule.kind }));
  }

  function calendarEvents(schedules, year, month) { return schedules.flatMap((item) => occurrencesForMonth(item, year, month)); }

  function buildCalendarDays(year, month, events = []) {
    const firstWeekday = new Date(Date.UTC(year, month, 1)).getUTCDay();
    const gridStart = new Date(Date.UTC(year, month, 1 - firstWeekday));
    return Array.from({ length: 42 }, (_, index) => {
      const current = new Date(gridStart.getTime() + index * 86400000);
      const currentYear = current.getUTCFullYear(); const currentMonth = current.getUTCMonth(); const day = current.getUTCDate();
      const key = dateKey(currentYear, currentMonth, day);
      return { date: key, day, inMonth: currentYear === year && currentMonth === month, events: events.filter((event) => event.date === key) };
    });
  }

  function upcomingOccurrences(schedules, from = new Date(), limit = 3) {
    const start = seoulDateParts(from); const found = [];
    for (let offset = 0; offset < 13; offset += 1) {
      const index = start.year * 12 + start.month + offset; const year = Math.floor(index / 12); const month = index % 12;
      found.push(...calendarEvents(schedules, year, month).filter((item) => item.date >= start.key));
    }
    return found.sort((a, b) => a.date.localeCompare(b.date)).filter((item, index, all) => all.findIndex((other) => other.id === item.id && other.date === item.date) === index).slice(0, limit);
  }

  root.TwoPickScheduleApiLogic = { SEOUL_TIME_ZONE, parseDate, seoulDateParts, validateInput, occurrencesForMonth, calendarEvents, buildCalendarDays, upcomingOccurrences };
}(typeof window !== 'undefined' ? window : globalThis));
