'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const htmlPath = path.join(__dirname, '..', 'Passenger', 'backend', 'admin', 'index.html');
const html = fs.readFileSync(htmlPath, 'utf8');
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(match => match[1]);
assert.equal(scripts.length, 6, 'six Admin scripts must ship');
scripts.forEach((source, index) => new vm.Script(source, {filename: `admin-inline-${index + 1}.js`}));

for (const label of ['Dashboard', 'Rides', 'Drivers / Fleet', 'Support', 'Finance',
                     'Staff & Access', 'Audit Logs', 'BUILD 42', 'ADMIN v0.9.0']) {
  assert.ok(html.includes(label), `missing ${label}`);
}
for (const id of ['staff-workspace', 'audit-workspace', 'staff-create-form', 'staff-login',
                  'rides', 'fleet-rows', 'support-rows', 'staff-rows', 'audit-rows']) {
  assert.match(html, new RegExp(`id=["']${id}["']`), `missing #${id}`);
}
assert.ok(html.includes('window.loadPagedRides=async function'), 'ride paginator must be global across inline scripts');
assert.ok(html.includes("if(staffWorkspace)"), 'Staff workspace initialization must be null-safe');
assert.ok(!html.toUpperCase().includes('BUILD 35 · ADMIN'), 'stale Admin release label');
console.log('PASS: current Admin source structure, navigation, release labels and all inline JavaScript syntax.');
const paginator = html.match(/window\.loadPagedRides=async function\(\)\{[^\n]+/)[0];
const compliance = {window: {}, currentRole: 'COMPLIANCE', ridePage: {stale: true},
  $: () => ({value: 'test-token'}), fetch: () => {throw Error('Compliance must not fetch rides');}};
vm.createContext(compliance);
vm.runInContext(paginator, compliance);
compliance.window.loadPagedRides().then(() => {
  assert.equal(compliance.ridePage, null);
  console.log('PASS: Compliance paginator clears stale ride data without requesting a forbidden endpoint.');
}).catch(error => {console.error(error); process.exitCode = 1;});
