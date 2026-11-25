const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = { globalThis: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'frontend', 'service-shell-logic.js'), 'utf8'), context);
const logic = context.globalThis.TwoPickServiceShellLogic;

assert.equal(logic.normalizeRoute('#decision'), 'decision');
assert.equal(logic.normalizeRoute(' HISTORY '), 'history');
assert.equal(logic.normalizeRoute('#unknown'), 'home');
assert.equal(logic.normalizeRoute(''), 'home');
assert.equal(logic.routeTitle('#pet'), '펫');
assert.equal(new Set(logic.routes).size, 6);
console.log('PASS: service route normalization and menu definitions');
