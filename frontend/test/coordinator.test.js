import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { open, coordinate, entry, capture } from "../../src/maskgw/admin/ui/assets/ui.js";
import { responseFor } from "./samples.js";
const bytes=readFileSync(new URL("../../src/maskgw/admin/ui/assets/presentation.json",import.meta.url));
const token="private-test-key-not-for-storage";
Object.defineProperty(globalThis,"window",{value:{location:{origin:"http://127.0.0.1:8765"}},configurable:true});
/** @param {number} version */
function current(version) {
  const value=responseFor("c1");if(!entry(value) || !entry(value.config)) throw new Error("Fixture failed.");
  value.revision=version;value.adopted=version > 0;value.config.revision=version;return value;
}
/** @param {unknown} value @param {number} status */
function json(value,status=200) {return new Response(JSON.stringify(value),{status,headers:{"Content-Type":"application/json"}});}
/** @type {{url:URL,init:RequestInit}[]} */ let requests=[];
/** @type {() => Promise<Response>} */ let answer;
let version=1,failRead=false;
test.beforeEach(()=>{
  requests=[];version=1;failRead=false;answer=async()=>{version=2;return json({revision:2,applied:true});};
  globalThis.fetch=async(input,init)=>{
    assert.ok(input instanceof URL && init);requests.push({url:input,init});
    if(input.pathname.endsWith("presentation.json")) return new Response(bytes,{headers:{"Content-Type":"application/json"}});
    if(init.method === "GET") {if(failRead) throw new Error("private failure");return json(current(version));}
    return answer();
  };
});
async function start() {const client=await open(token), flow=coordinate(client,"c1");assert.equal(await flow.load(),true);assert.equal(flow.begin("c17",{statement_timeout_ms:100,max_rows:1}),true);return {flow,client};}
function count() {return requests.filter(r=>r.init.method !== "GET").length;}
function held() {let release=()=>{};const promise=new Promise(resolve=>{release=()=>resolve(undefined);});return {promise,release};}

test("one pending command, no queue, no polling rebase and verified readback",async()=>{
  const {flow}=await start(), gate=held();answer=async()=>{await gate.promise;version=2;return json({revision:2,applied:true});};
  const draft=flow.getState();assert.equal(flow.poll(current(5)),true);assert.deepEqual(flow.getState(),draft);assert.equal(flow.getObservation()?.version,5);
  const pending=flow.confirm();assert.equal(flow.getState().tag,"pending");
  assert.equal(await flow.confirm(),false);assert.equal(flow.begin("c17",{}),false);assert.equal(flow.poll(current(6)),false);assert.equal(count(),1);
  const body=JSON.parse(String(requests.find(r=>r.init.method === "PUT")?.init.body));assert.equal(body.expected_revision,1);
  gate.release();await pending;const state=flow.getState();assert.equal(state.tag,"success");
  if(state.tag !== "success") throw new Error("Fixture failed.");assert.equal(state.newBase?.version,2);assert.equal(flow.finish(),true);assert.equal(flow.getState().tag,"reading");flow.close();
});
test("conflict preserves the exact draft and requires explicit review of separate base",async()=>{
  const {flow}=await start();answer=async()=>{version=4;return json({error:"REVISION_CONFLICT",detail:"private",current_revision:4},409);};
  const original=flow.getState();assert.equal(original.tag,"draft");await flow.confirm();const state=flow.getState();
  assert.equal(state.tag,"conflict");if(state.tag !== "conflict" || original.tag !== "draft") throw new Error("Fixture failed.");
  assert.deepEqual(state.edit,original.edit);assert.equal(state.newBase?.version,4);assert.equal(count(),1);assert.equal(await flow.confirm(),false);
  assert.equal(flow.review({statement_timeout_ms:200,max_rows:2}),true);const revised=flow.getState();if(revised.tag !== "draft") throw new Error("Fixture failed.");assert.equal(revised.edit.command.version,4);assert.equal(count(),1);flow.close();
});
test("busy remains a draft until a manual attempt and never queues",async()=>{
  const {flow}=await start();answer=async()=>json({error:"RELOAD_BUSY",detail:"x",current_revision:1},409);
  await flow.confirm();assert.equal(flow.getState().tag,"busy");assert.equal(count(),1);assert.equal(await flow.reconcile(),false);await Promise.resolve();assert.equal(count(),1);
  await flow.confirm();assert.equal(count(),2);flow.close();
});
for(const kind of ["uncertain","unknown","incompatible"]) test("blocking outcome "+kind,async()=>{
  const {flow}=await start();answer=async()=>{
    version=5;
    return kind === "uncertain" ? json({error:"CONFIG_DURABILITY_ERROR",detail:"x",current_revision:2,applied:true},500) : kind === "unknown" ? json({error:"INTERNAL_ERROR",detail:"x"},500) : json({error:"CONFIG_OUT_OF_SYNC",detail:"x",current_revision:1},409);
  };
  await flow.confirm();const state=flow.getState();assert.equal(state.tag,kind);assert.equal(count(),1);assert.equal(await flow.confirm(),false);assert.equal(flow.finish(),false);assert.equal(flow.review({}),false);
  if(state.tag === "uncertain" || state.tag === "unknown") {assert.equal(state.newBase?.version,5);await flow.reconcile();assert.equal(flow.getState().tag,kind);assert.equal(count(),1);}
  flow.close();
});
for(const kind of ["network","timeout","json","mime","envelope","500"]) test("ambiguous write "+kind,async()=>{
  const {flow}=await start();answer=async()=>{
    version=3;
    if(kind === "network") throw new Error(token);
    if(kind === "timeout") throw new DOMException("private","TimeoutError");
    if(kind === "json") return new Response("{",{headers:{"Content-Type":"application/json"}});
    if(kind === "mime") return new Response("{}",{headers:{"Content-Type":"text/html"}});
    if(kind === "envelope") return json({revision:2,applied:false});
    return new Response(token,{status:500});
  };
  await flow.confirm();assert.equal(flow.getState().tag,"unknown");assert.equal(count(),1);assert.equal(await flow.confirm(),false);assert.ok(!JSON.stringify(flow.getState()).includes(token));flow.close();
});
test("acknowledgment with failed readback is saved but not up to date",async()=>{
  const {flow}=await start();answer=async()=>{failRead=true;return json({revision:2,applied:true});};await flow.confirm();
  const state=flow.getState();if(state.tag !== "success") throw new Error("Fixture failed.");assert.equal(state.newBase,undefined);assert.equal(state.message,"Salva; visualização ainda não atualizada.");assert.equal(flow.finish(),false);
  failRead=false;version=2;await flow.reconcile();assert.equal(flow.finish(),true);assert.equal(count(),1);flow.close();
});
for(const action of ["cancel","close","401"]) test("late acknowledgment after "+action+" cannot restore state",async()=>{
  const {flow,client}=await start(), gate=held();answer=async()=>{await gate.promise;return json({revision:2,applied:true});};
  const pending=flow.confirm();
  if(action === "cancel") {assert.equal(flow.cancel(),true);assert.equal(flow.getState().tag,"unknown");}
  if(action === "close") client.close();
  if(action === "401") {const previous=globalThis.fetch;globalThis.fetch=async()=>new Response(token,{status:401});await assert.rejects(()=>client.read("c1"));globalThis.fetch=previous;}
  const stopped=flow.getState();gate.release();await pending;assert.deepEqual(flow.getState(),stopped);assert.equal(count(),1);flow.close();
});
test("invalid projection, credential and pre-aborted command perform zero writes",async()=>{
  const client=await open(token);const flow=coordinate(client,"c1");await flow.load();
  const before=requests.length;
  for(const draft of [{expected_revision:1},{statement_timeout_ms:100,max_rows:1,unknown:token},{statement_timeout_ms:true,max_rows:1}]) assert.throws(()=>flow.begin("c17",draft));
  assert.throws(()=>flow.begin("c11",{rule:{match:token+'"\\',transformer:"fixed"}}));
  const stop=new AbortController();stop.abort();await assert.rejects(()=>client.mutate({id:"c17",version:1,draft:{statement_timeout_ms:100,max_rows:1},identity:undefined},stop.signal));
  assert.equal(requests.length,before);flow.close();
});
test("DELETE JSON body, safe template and all normative fetch options",async()=>{
  const client=await open(token);await client.mutate({id:"c13",version:1,draft:{},identity:"rul_"+"1".repeat(32)});
  const request=requests[1];assert.ok(request);assert.equal(request.init.method,"DELETE");assert.equal(request.init.body,'{"expected_revision":1}');assert.equal(new Headers(request.init.headers).get("Content-Type"),"application/json");
  assert.equal(request.init.mode,"cors");assert.equal(request.init.credentials,"omit");assert.equal(request.init.redirect,"error");assert.equal(request.init.cache,"no-store");assert.equal(request.init.referrerPolicy,"no-referrer");client.close();
});
test("two sessions are independent and server versions arbitrate",async()=>{
  const a=await start(), b=await start();await a.flow.confirm();assert.equal(b.flow.getState().tag,"draft");
  answer=async()=>json({error:"REVISION_CONFLICT",detail:"x",current_revision:2},409);await b.flow.confirm();assert.equal(b.flow.getState().tag,"conflict");assert.equal(a.flow.getState().tag,"success");a.flow.close();assert.equal(b.flow.getState().tag,"conflict");b.flow.close();
});
test("polling refuses unsafe, divergent and backwards snapshots",async()=>{
  const {flow}=await start();const old=flow.getState();
  assert.equal(flow.poll(current(0)),false);const bad=current(1);bad.revision=2;assert.throws(()=>flow.poll(bad));
  const changed=current(1);if(!entry(changed.config))throw new Error("Fixture failed.");changed.config.database={statement_timeout_ms:200,max_rows:1};assert.throws(()=>flow.poll(changed));assert.deepEqual(flow.getState(),old);flow.close();
});
test("read responses out of order cannot replace newer state",async()=>{
  const client=await open(token),flow=coordinate(client,"c1"), gate=held();const previous=globalThis.fetch;let n=0;
  globalThis.fetch=async()=>{if(++n === 1) {await gate.promise;return json(current(1));}return json(current(2));};
  const first=flow.load(), second=flow.load();await second;gate.release();await first;const state=flow.getState();assert.equal(state.tag,"reading");if(state.tag === "reading") assert.equal(state.snapshot.version,2);
  flow.close();globalThis.fetch=previous;
});
test("immutable snapshot values cannot be changed via state references",async()=>{
  const {flow}=await start();const state=flow.getState();assert.ok(Object.isFrozen(state));if(state.tag !== "draft")throw new Error("Fixture failed.");assert.ok(Object.isFrozen(state.edit));assert.ok(Object.isFrozen(state.edit.base.value));assert.deepEqual(capture(state.edit.draft),state.edit.draft);flow.close();
});
test("failed repeat readback revokes the older base before human review",async()=>{
  const {flow}=await start();answer=async()=>{version=2;return json({error:"REVISION_CONFLICT",detail:"x",current_revision:2},409);};
  await flow.confirm();let state=flow.getState();assert.equal(state.tag,"conflict");if(state.tag !== "conflict")throw new Error("Fixture failed.");assert.equal(state.newBase?.version,2);
  failRead=true;assert.equal(await flow.reconcile(),false);state=flow.getState();if(state.tag !== "conflict")throw new Error("Fixture failed.");assert.equal(state.newBase,undefined);assert.equal(flow.review({statement_timeout_ms:200,max_rows:1}),false);assert.equal(count(),1);flow.close();
});
