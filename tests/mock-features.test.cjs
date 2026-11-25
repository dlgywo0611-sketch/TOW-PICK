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

console.log('PASS: mock history filtering and satisfaction validation');
