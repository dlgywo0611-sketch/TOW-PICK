const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');
const html = read('frontend/index.html');
const app = read('frontend/app.js');
const decisions = read('frontend/decision-flow.js');
const mocks = read('frontend/mock-features.js');
const styles = read('frontend/styles.css');

for (const [name, source] of Object.entries({ html, app, decisions, mocks, styles })) {
  assert.doesNotMatch(source, /^(<<<<<<<|=======|>>>>>>>)/m, `${name} contains a merge marker`);
}

const ids = [...html.matchAll(/\bid=["']([^"']+)["']/g)].map((match) => match[1]);
assert.equal(new Set(ids).size, ids.length, 'HTML contains duplicate IDs');

const scripts = [...html.matchAll(/<script\s+[^>]*src=["']([^"']+)["']/g)].map((match) => match[1]);
assert.equal(new Set(scripts).size, scripts.length, 'HTML loads a script more than once');

for (const id of [
  'decision-workspace', 'decision-progress', 'decision-manual-form',
  'history-list', 'satisfaction-buttons',
  'schedule-form', 'calendar-grid', 'schedule-list',
  'connect-usb', 'connect-ble', 'petdock-error',
]) {
  assert.ok(ids.includes(id), `missing merged feature control: ${id}`);
}

const count = (source, fragment) => source.split(fragment).length - 1;
for (const [source, signature] of [
  [app, "elements.connectUsb.addEventListener('click'"],
  [app, "elements.disconnectUsb.addEventListener('click'"],
  [app, "elements.connectBle.addEventListener('click'"],
  [app, "elements.disconnectBle.addEventListener('click'"],
  [decisions, "ui.createForm.addEventListener('submit'"],
  [decisions, "ui.conditionForm.addEventListener('submit'"],
  [decisions, "ui.recommendForm.addEventListener('submit'"],
  [decisions, "ui.manualForm.addEventListener('submit'"],
  [mocks, "elements.filter.addEventListener('change'"],
  [mocks, "elements.buttons.addEventListener('click'"],
  [mocks, "form.addEventListener('submit'"],
  [mocks, "elements.prev.addEventListener('click'"],
  [mocks, "elements.next.addEventListener('click'"],
  [mocks, "elements.grid.addEventListener('click'"],
]) {
  assert.equal(count(source, signature), 1, `event registration is missing or duplicated: ${signature}`);
}

let depth = 0;
for (const character of styles.replace(/\/\*[\s\S]*?\*\//g, '')) {
  if (character === '{') depth += 1;
  if (character === '}') depth -= 1;
  assert.ok(depth >= 0, 'CSS closes a block before it opens');
}
assert.equal(depth, 0, 'CSS contains an unclosed block');

console.log('PASS: merged HTML, event bindings, feature controls and CSS structure are intact');
