const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = { globalThis: {}, Date };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'frontend', 'dashboard-logic.js'), 'utf8'), context);
const logic = context.globalThis.TwoPickDashboardLogic;

const decisions = [
  { id: 3, title: '진행', status: 'open' },
  { id: 2, title: '확정', status: 'confirmed' },
  { id: 1, title: '이전 확정', status: 'confirmed' },
];
const summary = logic.summarizeDecisions(decisions, [{ decision_id: 2, content_snapshot: '초밥' }]);
assert.equal(summary.active.length, 1);
assert.equal(summary.confirmed.length, 2);
assert.equal(summary.confirmed[0].confirmation.content_snapshot, '초밥');

const upcoming = logic.upcomingSchedules([
  { date: '2026-11-24', title: '과거' },
  { date: '2026-11-26', title: '내일' },
  { date: 'bad', title: '오류' },
], new Date(2026, 10, 25));
assert.equal(upcoming.length, 1);
assert.equal(upcoming[0].title, '내일');
console.log('PASS: dashboard decision summaries and upcoming schedules');
