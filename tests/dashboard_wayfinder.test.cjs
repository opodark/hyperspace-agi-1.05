// SPDX-License-Identifier: Apache-2.0
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const {test}=require('node:test');
const js=fs.readFileSync('control-plane/dashboard.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
class Element {
  constructor(){this.value='';this.children=[];this.textContent='';this.selectedOptions=[];}
  appendChild(node){this.children.push(node);}
  replaceChildren(){this.children=[];}
}
function setup(){
  const elements={},requests=[],answers=[];
  const context={document:{getElementById(id){return elements[id]||(elements[id]=new Element());},createElement(){return new Element();}},
    missionHeaders:()=>({Authorization:'Bearer test'}),loadMissions:async()=>{},
    prompt:()=>answers.shift(),confirm:()=>false,
    fetch:async(path,opts)=>{requests.push({path,opts});return {ok:true,json:async()=>({maps:[]})};}};
  vm.createContext(context);
  vm.runInContext(js.slice(js.indexOf('var wfMaps='),js.indexOf('function missionToken()')),context);
  context.wfCurrent={id:'map-test',revision:3,destination:'<img onerror=evil()>',notes:'',fog:['open'],out_of_scope:[],frontier:['a'],ready:false,
    tickets:[{key:'a',title:'<script>evil()</script>',question:'Choose',mode:'hitl',status:'open',owner:'',answer:'',dependencies:[]}]};
  return {context,elements,requests,answers};
}
test('map renders text safely and blocks handoff until ready',()=>{
  const {context:c,elements:e}=setup();c.wfRender();
  assert.equal(e.wfHandoff.disabled,true);
  assert.equal(e.wfTickets.children[0].children[0].textContent,'<script>evil()</script> — open · disponibile');
  assert.equal(e.wfTickets.children[0].children[2].disabled,false);
  c.wfCurrent.frontier=[];c.wfRender();assert.equal(e.wfTickets.children[0].children[2].disabled,true);
  c.wfCurrent.ready=true;c.wfCurrent.mission_id='mission-test';c.wfRender();
  assert.equal(e.wfHandoff.disabled,false); // failed handoff may be retried
});
test('human resolution cancellation sends no mutation',async()=>{
  const {context:c,requests,answers}=setup();answers.push('operator','A proposed answer');
  await c.wfAction(c.wfCurrent.tickets[0],'resolve');assert.equal(requests.length,0);
});
test('claim includes the current revision and operator token',async()=>{
  const {context:c,requests,answers}=setup();answers.push('worker-one');
  c.fetch=async(path,opts)=>{requests.push({path,opts});return {ok:false,json:async()=>({error:'map changed; reload before saving'})};};
  await c.wfAction(c.wfCurrent.tickets[0],'claim');
  assert.equal(requests.length,1);assert.equal(requests[0].opts.headers.Authorization,'Bearer test');
  assert.deepEqual(JSON.parse(requests[0].opts.body),{revision:3,owner:'worker-one'});
});
