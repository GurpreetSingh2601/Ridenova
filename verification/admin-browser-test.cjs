/* Browser regression using synthetic fixtures only. No live credentials or service access. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
let playwright;
try { playwright = require('playwright'); } catch (error) {
  if (!process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES) throw error;
  playwright = require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, 'playwright'));
}
const html = fs.readFileSync(path.join(__dirname, '../Passenger/backend/admin/index.html'), 'utf8');
const evidence = path.join(__dirname, 'ui-evidence');
fs.mkdirSync(evidence, {recursive:true});
const at = Date.UTC(2026, 9, 3, 9, 30);
const ride = {id:'rn_test_1042',status:'CANCELLED_NO_SHOW',driverId:'drv_test',driverName:'Alex Morgan',category:'Economy',pickup:'100 West Georgia Street, Vancouver',destination:'BC Place, Vancouver',fareCents:2450,updatedAtEpochMs:at,pickupNotes:'Main entrance <script>not HTML</script>',cancellationReason:'RIDER_NOT_AT_PICKUP',waiting:{verifiedArrival:true,eligibleAtEpochMs:at+300000}};
const driver = {id:'drv_test',name:'Alex Morgan',username:'alex.test',vehicle:'2024 Toyota Prius',plate:'TEST 42',category:'ECONOMY',eligibleCategories:['ECONOMY','COMFORT'],status:'APPROVED',documentsReady:true,online:true,dispatchReason:'READY',lastLocation:{ageSeconds:4},ratingCount:32,serviceRating:4.9};
const overview = {passengerCount:128,rideCount:364,activeCount:7,completedCount:342,experience:{ratingCount:296,averageRating:4.9,openCases:3,inReviewCases:2},fleetDrivers:[driver],rides:[ride],ledger:[{rideId:ride.id,subtotalCents:2333,gstCents:117,totalCents:2450,commissionCents:583,driverGrossBeforeCostsCents:1750}],totals:{totalCents:832140,commissionCents:198100,driverGrossBeforeCostsCents:594310}};
const roles = {OWNER:['dashboard','operations','rides','drivers','finance','support','feedback','staff','audit'],OPERATIONS:['dashboard','operations','rides','drivers','support','feedback'],SUPPORT:['dashboard','operations','rides','support','feedback'],FINANCE:['dashboard','rides','finance'],COMPLIANCE:['dashboard','drivers','audit']};
(async()=>{
 const browser=await playwright.chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1050},reducedMotion:'reduce'});
  page.setDefaultTimeout(10000);
  const pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
  let role='OWNER',failOverview=false,expired=false,delay=0,overviewCalls=0;
  const requests=[];
  await page.route('http://ridenova.test/**',async route=>{
   const url=new URL(route.request().url()),p=url.pathname;requests.push(p);
   const json=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
   if(p.startsWith('/admin/assets/'))return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(__dirname,'../Passenger/backend',p),'utf8')});
   if(p==='/map-config')return json({browserKey:'fixture-key'});
   if(p==='/admin')return route.fulfill({contentType:'text/html',body:html});
   if(p==='/v1/staff/login')return json({accessToken:'fixture-'+role,staff:{username:'owner.test',role}});
   if(p==='/v1/staff/logout')return json({ok:true});
   if(expired)return json({message:'Sign in to continue'},401);
   if(p==='/v3/operations/admin/live')return json({rides:[{id:ride.id,status:'DRIVER_ASSIGNED',pickup:{address:ride.pickup,latitude:49.28,longitude:-123.12},destination:{address:ride.destination,latitude:49.27,longitude:-123.11},driverPosition:{latitude:49.29,longitude:-123.13,accuracyMeters:8,observedAtEpochMs:Date.now()-3000},monitor:{state:'CHECK_IN'}}]});
   if(p.endsWith('/evidence'))return json({rideId:ride.id,driverId:driver.id,status:'DRIVER_ASSIGNED',pickup:{address:ride.pickup,latitude:49.28,longitude:-123.12},destination:{address:ride.destination,latitude:49.27,longitude:-123.11},events:[],evidence:[0,1,2].map((n)=>({id:'gps'+n,actor:driver.id,kind:'GPS_DRIVER',observedAtEpochMs:at+n*4000,receivedAtEpochMs:at+n*4000,data:{latitude:49.29-n*.001,longitude:-123.13,accuracyMeters:8,quality:'RELIABLE'}})),nextCursor:null});
   if(p==='/v3/operations/admin/document-policy')return json({availableKinds:['LICENCE','INSURANCE','REGISTRATION','INSPECTION','DRIVING_RECORD'],requiredKinds:['LICENCE','INSURANCE','REGISTRATION','INSPECTION']});
   if(p==='/v1/admin/overview'){
    overviewCalls++;if(delay)await new Promise(r=>setTimeout(r,delay));
    if(failOverview)return json({message:'Synthetic temporary outage'},503);
    const result=structuredClone(overview);
    if(['SUPPORT','FINANCE'].includes(role))result.fleetDrivers=[];
    if(!['OWNER','FINANCE'].includes(role)){delete result.totals;result.ledger=[];}
    if(role==='COMPLIANCE')result.rides=[];
    return json(result);
   }
   if(p==='/v1/admin/rides')return json({rides:url.searchParams.get('q')?[]:[ride],page:1,pages:1,total:url.searchParams.get('q')?0:1});
   if(p.endsWith('/events'))return json({events:[{atEpochMs:at,type:'FLEET_NO_SHOW'}]});
   if(p==='/v2/fleet/admin/drivers')return json({drivers:[driver],page:1,pages:1,total:1});
   if(p==='/v1/admin/support-cases')return json({cases:[{id:'support_test',status:'OPEN',reporterRole:'PASSENGER',reporterId:'passenger_test',category:'FARE',rideId:ride.id,description:'Please review the trip receipt.',updatedAtEpochMs:at}],page:1,pages:1,total:1});
   if(p==='/v1/admin/feedback')return json({feedback:[{rideId:ride.id,authorRole:'PASSENGER',stars:5,tags:['Friendly'],comment:'A smooth trip, thank you.',updatedAtEpochMs:at}]});
   if(p==='/v1/staff/accounts')return json({staff:[{id:'staff_test',username:'support.test',role:'SUPPORT',active:true}]});
   if(p==='/v1/staff/audit')return json({events:[{actor:'owner.test',action:'STAFF_CREATED',subject:'support.test',atEpochMs:at}]});
   if(p==='/v1/admin/finance/summary')return json({payments:[{rideId:ride.id,amountCents:2450,status:'requires_capture'}],refunds:[],entries:[],provisionalDriverBalances:[{driverId:driver.id,grossBeforeCostsCents:1750}]});
   if(p==='/v4/trips/admin/earnings')return json({period:'2026-10-16',engagedMs:4200000,meters:69200,reviewRequired:true,baseEarningsCents:3583,bonusCents:200,tipsCents:0,distanceAllowanceCents:3114,topUpCents:0,totalCents:6897,platformNetBeforeOtherCostsCents:-1778,entries:[{id:'eng45',rideId:ride.id,driverId:driver.id,engagedMs:4200000,meters:69200,reviewRequired:true,active:false,issues:['DISTANCE_VERIFICATION_REQUIRED'],estimated:{engagedMeters:69200,engagedSeconds:4200}}]});
   if(p==='/v4/trips/admin/policy')return json({policies:[{effectiveDate:'2026-06-01',hourlyCents:2189,kmCents:45}]});
   if(p==='/v4/trips/admin/review')return json({reviewed:true});
   if(p==='/v1/admin/finance/zones')return json({zones:[]});
   return json({message:'Unmocked test endpoint: '+p},404);
  });
  async function login(as){role=as;await page.locator('#staff-username').fill('owner.test');await page.locator('#staff-username').press('Enter');assert.equal(await page.evaluate(()=>document.activeElement.id),'staff-password');await page.locator('#staff-password').fill('synthetic-password-only');await page.locator('#staff-password').press('Enter');await page.waitForFunction(()=>document.body.classList.contains('signed-in')&&document.querySelector('#workspace-status').textContent.startsWith('Updated'));}
  async function open(workspace){await page.locator('[data-page="'+workspace+'"]').click();await page.locator('#workspace-'+workspace).waitFor({state:'visible'});await page.waitForFunction(()=>!document.querySelector('#workspace-refresh').disabled);assert.equal(await page.locator('#workspace-status').getAttribute('data-error'),'false',workspace+' refresh failed');}
  async function shot(name){await page.screenshot({path:path.join(evidence,name+'.png'),fullPage:true});}
  await page.route('https://maps.googleapis.com/**',route=>route.fulfill({contentType:'text/javascript',body:`window.google={maps:{Map:class{constructor(el){this.zoom=11;el.textContent='Synthetic map fixture';}setCenter(){}setZoom(z){this.zoom=z}getZoom(){return this.zoom}fitBounds(){}},Marker:class{setMap(){}addListener(){}},Polyline:class{setMap(){}},InfoWindow:class{open(){}},LatLngBounds:class{extend(){}},SymbolPath:{CIRCLE:0},event:{trigger(){},addListenerOnce(m,e,f){f()}}}};window.rnMapsReady44();`}));
  await page.goto('http://ridenova.test/admin');
  assert.equal(await page.locator('#ops-pages').isVisible(),false);
  await shot('admin-sign-in-desktop');
  await login('OWNER');assert.equal(await page.locator('#metrics .tile').count(),11);
  await shot('admin-dashboard-desktop');
  for(const workspace of roles.OWNER){await open(workspace);if(['rides','drivers','finance','staff'].includes(workspace))await shot('admin-'+workspace+'-desktop');}
  await open('operations');await page.locator('#m44-trips').selectOption(ride.id);await page.waitForFunction(()=>document.querySelector('#m44-info').textContent.includes('CHECK_IN'));assert.equal(await page.locator('#m44-slider').getAttribute('max'),'2');await page.locator('#m44-slider').fill('0');await page.locator('#m44-slider').dispatchEvent('input');assert.match(await page.locator('#m44-time').textContent(),/RELIABLE/);await shot('admin-live-operations-build44');await open('drivers');await page.locator('#d44-load').click();await page.waitForFunction(()=>document.querySelectorAll('#d44-kinds input').length===5);
  await open('finance');assert.match(await page.locator('#c45-summary').textContent(),/69.2 recorded km/);assert.match(await page.locator('#c45-entries').textContent(),/Needs review/);assert.equal(await page.locator('#c45-entries button').count(),1);await page.locator('#c45-policy-load').click();await page.waitForFunction(()=>document.querySelector('#c45-policies').textContent.includes('21.89'));assert.match(await page.locator('#finance42-payments').textContent(),/Authorized · awaiting capture/);assert.match(await page.locator('#finance42-events').textContent(),/No refunds or money events yet/);await open('rides');await page.locator('#rides tr').first().focus();await page.keyboard.press('Enter');await page.locator('#ride-details').waitFor({state:'visible'});await page.waitForFunction(()=>document.querySelector('#ride-events').textContent.includes('FLEET_NO_SHOW'));assert.match(await page.locator('#ride-details-content').textContent(),/Main entrance <script>not HTML<\/script>/);assert.equal(await page.locator('#ride-details-content script').count(),0);assert.match(await page.locator('#ride-details-content').textContent(),/RIDER NOT AT PICKUP/);await shot('admin-pickup-details-build43');
  await page.locator('#ride-search').fill('no-match');await page.waitForFunction(()=>document.querySelector('#rides').textContent.includes('No rides found'));assert.equal(await page.locator('#rides .empty-cell').count(),1);await page.locator('#ride-search').fill('');await page.waitForFunction(()=>document.querySelector('#rides').textContent.includes('rn_test_1042'));
  await open('dashboard');failOverview=true;await page.locator('#workspace-refresh').click();await page.waitForFunction(()=>document.querySelector('#workspace-status').dataset.error==='true');assert.equal(await page.locator('#metrics .tile').count(),11);failOverview=false;
  const before=overviewCalls;await page.evaluate(()=>Promise.all([window.refreshWorkspace(),window.refreshWorkspace()]));assert.equal(overviewCalls-before,1,'Duplicate refreshes should coalesce');
  await page.setViewportSize({width:390,height:844});await shot('admin-dashboard-mobile');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Mobile page overflows');await page.locator('#mobile-nav-toggle').click();await page.locator('[data-page="rides"]').click();await page.locator('#workspace-rides').waitFor({state:'visible'});assert.equal(await page.locator('#mobile-nav-toggle').getAttribute('aria-expanded'),'false');await shot('admin-rides-mobile');
  await page.setViewportSize({width:1440,height:1050});
  for(const r of Object.keys(roles).filter(r=>r!=='OWNER')){
   await page.locator('#staff-logout').click();await login(r);
   const visible=await page.locator('#ops-nav button[data-page]:visible').evaluateAll(bs=>bs.map(b=>b.dataset.page));assert.deepEqual(visible,roles[r],r+' navigation');
   for(const w of roles[r])await open(w);
   await page.evaluate(()=>location.hash='staff');await page.waitForFunction(()=>location.hash==='#dashboard');assert.equal(await page.locator('#workspace-staff').isVisible(),false);
  }
  await page.locator('#staff-logout').click();await login('OWNER');await open('finance');await open('dashboard');delay=400;const started=overviewCalls;await page.evaluate(()=>{window.refreshWorkspace()});await page.waitForFunction(()=>document.querySelector('#workspace-refresh').disabled);await page.locator('#staff-logout').click();await page.waitForTimeout(600);assert.ok(overviewCalls>started);assert.equal(await page.locator('#metrics').textContent(),'');assert.equal(await page.locator('#finance42-payments').textContent(),'');assert.equal(await page.locator('#ops-pages').isVisible(),false);delay=0;
  await login('OWNER');expired=true;await page.locator('#workspace-refresh').click();await page.waitForFunction(()=>document.body.classList.contains('signed-out'));assert.match(await page.locator('#staff-identity').textContent(),/expired/);assert.equal(await page.locator('#metrics').textContent(),'');
  assert.deepEqual(pageErrors,[],'Unexpected browser JavaScript error');
  console.log('PASS: 9 Admin workspaces; Owner + 4 restricted roles; GPS timeline replay and document policy; keyboard sign-in and ride details; empty search; failed refresh retains data; duplicate refresh coalescing; 390px navigation and overflow; delayed response after logout; HTTP 401 session clearing.');
  console.log('Screenshots: verification/ui-evidence/ (synthetic fixtures, not a live backend or production data).');
  console.log('Browser: '+browser.version()+'. Total fixture requests: '+requests.length);
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
