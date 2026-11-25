const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = { globalThis: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'frontend', 'onboarding-logic.js'), 'utf8'), context);
const getState = context.globalThis.TwoPickOnboardingLogic.getOnboardingState;

assert.equal(getState().action, 'login');
assert.equal(getState({ authenticated: true }).action, 'connect');
assert.equal(getState({ authenticated: true, hasCouple: true }).action, 'wait');
assert.equal(getState({ authenticated: true, hasCouple: true, connected: true }).action, 'decision');
console.log('PASS: onboarding guides account, couple, wait and first decision states');
