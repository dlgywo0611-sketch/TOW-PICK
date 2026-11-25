const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const read = (file) => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const html = read('frontend/index.html');
const app = read('frontend/app.js');
const decisions = read('frontend/decision-flow.js');
const styles = read('frontend/styles.css');

for (const id of ['login-form', 'signup-form', 'join-form', 'create-couple-button']) {
  assert.match(html, new RegExp(`id=["']${id}["']`), `missing account/couple control: ${id}`);
}
for (const endpoint of ['/token', '/users', '/couples', '/couples/join', '/couples/me']) {
  assert.ok(app.includes(`'${endpoint}'`), `missing account/couple endpoint: ${endpoint}`);
}
assert.ok(app.includes("'/couples/invite-code'"), 'missing invite code reissue endpoint');
assert.match(app, /Invite code expired or inactive/);
assert.match(html, /id="reissue-invite-button"/);
for (const page of ['home', 'decision', 'history', 'schedule', 'pet', 'settings']) {
  assert.match(html, new RegExp(`data-service-page=["']${page}["']`), `missing service page: ${page}`);
}
for (const endpoint of ['/decisions', '/conditions', '/recommendations', '/candidates', '/approve']) {
  assert.ok(decisions.includes(endpoint), `missing decision flow endpoint fragment: ${endpoint}`);
}
assert.match(html, /name="viewport"/);
assert.match(styles, /@media\s*\(max-width:\s*650px\)/);
assert.match(styles, /@media\s*\(max-width:\s*820px\)/);
assert.doesNotMatch(decisions, /petDock|connectUsb|connectBluetooth/, 'hardware must not approve decisions');
assert.match(app, /requestState\.mutations/, 'duplicate mutation guard must stay enabled');
assert.match(html, /aria-label="알림 센터 열기"/);
console.log('PASS: account, couple, decision, navigation, mobile and hardware separation contracts');
