const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const frontend = path.join(__dirname, '..', 'frontend');
const files = fs.readdirSync(frontend).filter((name) => name.endsWith('.js')).sort();
for (const file of files) {
  const result = spawnSync(process.execPath, ['--check', path.join(frontend, file)], { stdio: 'inherit' });
  if (result.status !== 0) process.exit(result.status || 1);
}
console.log(`PASS: ${files.length} frontend scripts are valid JavaScript`);
