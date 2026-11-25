const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = { globalThis: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'frontend', 'mock-features-logic.js'), 'utf8'), context);
const logic = context.globalThis.MockFeaturesLogic;

assert.equal(logic.normalizeRating(1), 1);
assert.equal(logic.normalizeRating('5'), 5);
assert.equal(logic.normalizeRating(0), null);
assert.equal(logic.normalizeRating(3.5), null);
assert.equal(logic.getSatisfactionLabel(5), '정말 좋았어요');
assert.equal(logic.getSatisfactionLabel('bad'), '아직 평가하지 않았어요');

const items = [{ category: 'meal' }, { category: 'home' }, { category: 'meal' }];
assert.equal(logic.filterHistory(items, 'meal').length, 2);
assert.equal(logic.filterHistory(items, 'all').length, 3);
assert.equal(logic.filterHistory(null, 'all').length, 0);

assert.equal(logic.validateSchedule({ title: ' 100일 ', date: '2026-11-30', type: 'anniversary' }).value.title, '100일');
assert.equal(logic.validateSchedule({ title: '', date: '2026-11-30' }).valid, false);
assert.equal(logic.validateSchedule({ title: '잘못된 날짜', date: '2026-02-30' }).valid, false);
assert.equal(logic.validateSchedule({ title: '일정', date: '2026-11-30', type: 'unknown' }).value.type, 'todo');

const days = logic.buildCalendarDays(2026, 10, [{ date: '2026-11-25', title: '기념일' }]);
assert.equal(days.length, 42);
assert.equal(days[0].date, '2026-11-01');
assert.equal(days.find(day => day.date === '2026-11-25').events.length, 1);
assert.equal(days.filter(day => day.inMonth).length, 30);

console.log('PASS: mock history, satisfaction, schedule validation and calendar grid');
