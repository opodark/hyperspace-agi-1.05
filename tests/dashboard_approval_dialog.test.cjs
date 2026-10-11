// SPDX-License-Identifier: Apache-2.0
// Review in-page dialog: all existing review flows use one dialog and keep
// their original authenticated endpoints.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'control-plane', 'dashboard.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);

assert.match(html, /id="approvalDialog" role="dialog" aria-modal="true"/);
assert.match(html, /id="approvalDialogRationale" class="inp" rows="3" maxlength="2000"/);
assert.match(html, /onclick="closeApprovalDialog\(false\)"/);
assert.match(html, /onclick="closeApprovalDialog\(true\)"/);
assert.match(script, /function requestApprovalRationale\(action,detail\)/);
assert.match(script, /accepted&&!rationale/); // non si può confermare senza motivazione
assert.match(script, /event\.key==='Escape'.*closeApprovalDialog\(false\)/);

for (const name of ['reviewDream', 'reviewDevelopmentDream', 'reviewMission']) {
  assert.match(script, new RegExp(`async function ${name}\\([\\s\\S]*?requestApprovalRationale\\(`));
}
assert.match(script, /fetch\('\/dreams\/'.*\/review/);
assert.match(script, /fetch\('\/development-dreams\/'.*\/review/);
assert.match(script, /fetch\('\/missions\/'.*\/review/);

console.log('dashboard approval dialog tests passed');
