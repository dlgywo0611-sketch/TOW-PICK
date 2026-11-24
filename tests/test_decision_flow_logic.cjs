'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const logic = require('../frontend/decision-flow-logic.js');

let passed = 0;
function test(name, callback) {
  callback();
  passed++;
  console.log(`PASS ${String(passed).padStart(2, '0')}: ${name}`);
}
function option(title, cost, time, tags = '') {
  return { title, estimated_total_cost_krw: cost, time_slot: time, tags };
}
function decision(current = null, status = 'open', confirmed = false) {
  return { status, confirmed, current_candidate: current };
}
const both = { member_conditions: [{ user_id: 1, submitted: true }, { user_id: 2, submitted: true }] };

test('comma, semicolon and newline splitting with whitespace', () => {
  assert.deepEqual(logic.splitTags('한식, 조용한 곳; 산책\n 전시'), ['한식', '조용한 곳', '산책', '전시']);
});
test('duplicate and oversize tags rejected', () => {
  assert.throws(() => logic.splitTags('한식, 한식'), /중복/);
  assert.throws(() => logic.splitTags('a'.repeat(61)), /60자/);
  assert.throws(() => logic.splitTags(Array.from({ length: 13 }, (_, i) => `t${i}`).join(',')), /12개/);
});
test('two valid public options convert to API request schema', () => {
  assert.deepEqual(logic.makeOptions([
    option('한식', '18000', '토 18:00-20:00', '조용한 곳, 한식'),
    option('전시', '14000', '토 18:00-20:00', '미술관'),
  ]), [
    { title: '한식', estimated_total_cost_krw: 18000, time_slot: '토 18:00-20:00', tags: ['조용한 곳', '한식'] },
    { title: '전시', estimated_total_cost_krw: 14000, time_slot: '토 18:00-20:00', tags: ['미술관'] },
  ]);
});
test('invalid option quantity, price and duplicates rejected', () => {
  const good = option('A', '10000', '토 18:00-20:00');
  assert.throws(() => logic.makeOptions([good]), /2~8/);
  assert.throws(() => logic.makeOptions(Array.from({ length: 9 }, (_, i) => option(String(i), '10000', '토'))), /2~8/);
  assert.throws(() => logic.makeOptions([good, option('a', '10000', '토')]), /중복/);
  assert.throws(() => logic.makeOptions([good, option('B', '', '토')]), /정수/);
  assert.throws(() => logic.makeOptions([good, option('B', '-10', '토')]), /정수/);
  assert.throws(() => logic.makeOptions([good, option('B', '1000000001', '토')]), /10억/);
});
test('no recommendations before both submit', () => {
  assert.equal(logic.conditionsReady({ member_conditions: [{ user_id: 1, submitted: true }, { user_id: 2, submitted: false }] }), false);
  assert.equal(logic.canRecommend(decision(), { member_conditions: [] }), false);
});
test('recommendation available only with two submissions and no candidate', () => {
  assert.equal(logic.canRecommend(decision(), both), true);
  assert.equal(logic.canRecommend(decision(), both, true), false);
  assert.equal(logic.canRecommend(decision({ id: 1 }), both), false);
  assert.equal(logic.canRecommend(decision(null, 'confirmed', true), both), false);
});
test('cannot edit private conditions after a candidate exists', () => {
  assert.equal(logic.canEditConditions(decision()), true);
  assert.equal(logic.canEditConditions(decision({ id: 2 })), false);
  assert.equal(logic.canEditConditions(decision(null, 'confirmed')), false);
});
test('approval belongs only to logged-in member and latest candidate', () => {
  const c = { id: 8, member_approvals: [{ user_id: 1, approved: true }, { user_id: 2, approved: false }] };
  assert.equal(logic.canApprove(decision(c), 1), false);
  assert.equal(logic.canApprove(decision(c), 2), true);
  assert.equal(logic.canApprove(decision(c), 99), false);
  assert.equal(logic.canApprove(decision(c, 'confirmed', true), 2), false);
  assert.equal(logic.canApprove(decision(), 2), false);
});
test('status view contains only safe status flags', () => {
  const status = logic.getMemberStates([{ id: 1, nickname: 'A' }, { id: 2, nickname: 'B' }], both);
  assert.deepEqual(status, [{ id: 1, nickname: 'A', submitted: true }, { id: 2, nickname: 'B', submitted: true }]);
  assert.equal(JSON.stringify(status).includes('preferences'), false);
});
test('web script uses existing auth and decision endpoints, not PET DOCK approval', () => {
  const js = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'decision-flow.js'), 'utf8');
  for (const endpoint of ["'/decisions'", '/conditions/me', '/conditions/status', '/recommendations', '/candidates/', '/approve']) {
    assert.ok(js.includes(endpoint), `Missing flow endpoint ${endpoint}`);
  }
  assert.equal(/petDock|BLE_SERVICE|serialPort|addEventListener\(['"]button['"]/.test(js), false);
  assert.ok(js.includes('textContent'));
  assert.ok(js.includes('twopick:session-changed'));
});
console.log(`\nDecision UI logic tests: ${passed}/${passed} PASS`);
