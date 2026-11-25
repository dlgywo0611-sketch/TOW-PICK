const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const excluded = new Set(['run-frontend-tests.cjs', 'check-frontend-syntax.cjs']);
const files = fs.readdirSync(__dirname).filter((name) => name.endsWith('.cjs') && !excluded.has(name)).sort();
for (const file of files) {
  const result = spawnSync(process.execPath, [path.join(__dirname, file)], { cwd: root, stdio: 'inherit' });
  if (result.status !== 0) process.exit(result.status || 1);
}
console.log(`\nPASS: ${files.length} frontend regression suites`);
