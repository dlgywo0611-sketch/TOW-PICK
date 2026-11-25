(function exposeScheduleApiLogic(root) {
  const pad = (value) => String(value).padStart(2, '0');
  const isoDate = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  function parseDate(value) { const [y, m, d] = String(value).split('-').map(Number); const date = new Date(y, m - 1, d); return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d ? date : null; }
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
    const start = parseDate(schedule.local_date); if (!start) return []; const end = new Date(year, month + 1, 0); const dates = []; const rule = schedule.repeat_rule || 'none';
    if (rule === 'none') { if (start.getFullYear() === year && start.getMonth() === month) dates.push(start); }
    else if (rule === 'weekly') { const cursor = new Date(start); while (cursor < new Date(year, month, 1)) cursor.setDate(cursor.getDate() + 7); while (cursor <= end) { if (cursor.getMonth() === month) dates.push(new Date(cursor)); cursor.setDate(cursor.getDate() + 7); } }
    else if (rule === 'monthly') { const date = new Date(year, month, start.getDate()); if (date.getMonth() === month && date >= start) dates.push(date); }
    else if (rule === 'yearly' && start.getMonth() === month) { const date = new Date(year, month, start.getDate()); if (date.getMonth() === month && date >= start) dates.push(date); }
    return dates.map((date) => ({ ...schedule, date: isoDate(date), type: schedule.kind }));
  }
  function calendarEvents(schedules, year, month) { return schedules.flatMap((item) => occurrencesForMonth(item, year, month)); }
  function upcomingOccurrences(schedules, from = new Date(), limit = 3) {
    const start = new Date(from.getFullYear(), from.getMonth(), from.getDate()); const found = [];
    for (let offset = 0; offset < 13; offset += 1) { const monthDate = new Date(start.getFullYear(), start.getMonth() + offset, 1); found.push(...calendarEvents(schedules, monthDate.getFullYear(), monthDate.getMonth()).filter((item) => parseDate(item.date) >= start)); }
    return found.sort((a, b) => a.date.localeCompare(b.date)).filter((item, index, all) => all.findIndex((other) => other.id === item.id && other.date === item.date) === index).slice(0, limit);
  }
  root.TwoPickScheduleApiLogic = { validateInput, occurrencesForMonth, calendarEvents, upcomingOccurrences };
}(typeof window !== 'undefined' ? window : globalThis));
