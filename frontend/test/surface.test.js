import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { check as validate, open } from "../../src/maskgw/admin/ui/assets/ui.js";
import { inspectPublic } from "../tools/inspect.js";

// Phase 9, Stage 5: read-only second prefix in the closed presentation.
/** @param {unknown} value @returns {Record<string,unknown>} */
function obj(value) { if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Fixture object required."); return /** @type {Record<string,unknown>} */ (value); }
/** @param {unknown} value @returns {unknown[]} */
function arr(value) { if (!Array.isArray(value)) throw new Error("Fixture list required."); return value; }
const bytes=readFileSync(new URL("../private/presentation.json",import.meta.url));
/** @returns {Record<string,unknown>} */
function fixture() { return obj(JSON.parse(bytes.toString("utf8"))); }
/** @param {unknown} root @param {Array<string|number>} path @param {unknown} value */
function change(root,path,value) {
  let current=root;
  for (const part of path.slice(0,-1)) current=typeof part === "number" ? arr(current)[part] : obj(current)[part];
  const last=path.at(-1);
  if (typeof last === "number") arr(current)[last]=value; else if (typeof last === "string") obj(current)[last]=value; else throw new Error("Empty path.");
}
const document=fixture();
const calls=arr(document.calls).map(obj);
const second=calls.filter(c=>String(c.path).startsWith("/admin/v2/"));
const first=calls.findIndex(c=>String(c.path).startsWith("/admin/v2/"));
const listCall=second.find(c=>c.path === "/admin/v2/datasources");
const itemCall=second.find(c=>c.path === "/admin/v2/datasources/{datasource_id}");
const statusCall=second.find(c=>c.path === "/admin/v2/status");
const writeIndex=calls.findIndex(c=>c.method === "PUT");
if (!listCall || !itemCall || !statusCall || first < 0 || writeIndex < 0) throw new Error("Fixture calls required.");

test("the second prefix only carries four authenticated reads",()=>{
  assert.equal(validate(fixture()),true);
  assert.equal(second.length,4);
  assert.ok(second.every(c=>c.method === "GET" && c.operation === "read" && c.input === null));
});

/** @type {Array<[string,Array<string|number>,unknown]>} */
const hostile=[
  ["write under second prefix",["calls",first,"method"],"POST"],
  ["delete under second prefix",["calls",first,"method"],"DELETE"],
  ["non-read operation under second prefix",["calls",first,"operation"],"create"],
  ["first-prefix write moved to second prefix",["calls",writeIndex,"path"],"/admin/v2/datasources"],
  ["third prefix",["calls",first,"path"],"/admin/v3/status"],
  ["console absent",["console"],undefined],
  ["unknown console key",["console","script"],"x"],
  ["summary on first-prefix read",["console","summary","call"],String(calls[0]?.id)],
  ["summary on item read",["console","summary","call"],String(itemCall.id)],
  ["list on item read",["console","collection","call"],String(itemCall.id)],
  ["item read without identity",["console","detail","call"],String(listCall.id)],
  ["unknown figure path",["console","summary","figures",0,"path"],["nowhere"]],
  ["prototype figure path",["console","summary","figures",0,"path"],["__proto__"]],
  ["rows are not a list",["console","collection","items"],["catalog_revision"]],
  ["key is not text",["console","collection","key"],["revision"]],
  ["search on number",["console","collection","searchable"],[["revision"]]],
  ["unknown column kind",["console","collection","columns",0,"kind"],"html"],
  ["unknown tab source",["console","detail","tabs",0,"source"],"url"],
  ["tab path outside model",["console","detail","tabs",0,"entries",0,"path"],["nowhere"]],
  ["duplicate console id",["console","guide","id"],String(obj(obj(document.console).summary).id)],
  ["non opaque console id",["console","guide","id"],"guide"],
  ["guide with one step",["console","guide","steps"],[obj(arr(obj(obj(document.console).guide).steps)[0])]],
  ["guide control smuggled",["console","guide","steps",0,"control"],"password"],
];
for (const [name,path,value] of hostile) test("console refused: "+name,()=>{
  const p=fixture();
  if(value === undefined) delete p.console; else change(p,path,value);
  assert.equal(validate(p),false);
});

// ---- transport of the second prefix ----------------------------------------
const token="surface-test-marker-private-credential";
const origin="http://127.0.0.1:8765";
const key="dso_"+"a".repeat(32);
/** @type {{url:URL, init:RequestInit}[]} */ let seen=[];
/** @type {Record<string,{status:number,body:unknown}>} */ let replies={};
Object.defineProperty(globalThis,"window",{value:{location:{origin}},configurable:true});
/** @param {RequestInfo | URL} input @param {RequestInit | undefined} init */
globalThis.fetch=async(input,init)=>{
  assert.ok(input instanceof URL && init);
  seen.push({url:input,init});
  if(input.pathname.endsWith("presentation.json")) return new Response(bytes,{headers:{"Content-Type":"application/json"}});
  const reply=replies[input.pathname] ?? {status:404,body:{error:"NOT_FOUND",detail:"x"}};
  return new Response(JSON.stringify(reply.body),{status:reply.status,headers:{"Content-Type":"application/json"}});
};
test.beforeEach(()=>{seen=[];replies={};});
const summary={
  catalog_available:true,catalog_revision:3,datasources:{total:1,enabled:1,published:1},
  registry:{published:1,sessions:0,retired_open:0,candidates:0,closing:false},
  limits:{max_sessions:32,max_retired:4,max_candidates:2},writes_blocked:false,dns_timeout_ms:5000,
};
const row={id:key,alias:"crm",display_name:"CRM",enabled:true,revision:2,last_test:{status:"never",checked_at:null},runtime:{published:true,generation:4,sessions:0}};

test("list and item reads use GET, only the checked key and the second prefix",async()=>{
  replies={"/admin/v2/status":{status:200,body:summary},"/admin/v2/datasources":{status:200,body:{catalog_revision:3,datasources:[row]}}};
  const client=await open(token);
  await client.read(String(statusCall.id));
  const list=await client.read(String(listCall.id));
  assert.deepEqual(list,{catalog_revision:3,datasources:[row]});
  for(const {init} of seen) assert.equal(init.method,"GET");
  await assert.rejects(()=>client.read(String(itemCall.id)),/Request unsuccessful/);
  for(const hostileKey of ["../status","dso_x","a/b",key+"/policy","%2e%2e","dso_"+"A".repeat(32),"",key+"?x=1"]) {
    await assert.rejects(()=>client.read(String(itemCall.id),undefined,hostileKey));
  }
  await assert.rejects(()=>client.read(String(listCall.id),undefined,key));
  assert.equal(seen.filter(s=>s.url.pathname.includes("/datasources/")).length,0);
  client.close();
});

test("an absent catalog and a blocked catalog are told apart by HTTP status only",async()=>{
  const client=await open(token);
  await assert.rejects(()=>client.read(String(statusCall.id)),e=>e instanceof Error && "kind" in e && e.kind === "absent");
  replies={"/admin/v2/status":{status:503,body:{error:"CATALOG_BLOCKED",detail:"x"}}};
  await assert.rejects(()=>client.read(String(statusCall.id)),e=>e instanceof Error && "kind" in e && e.kind === "unavailable");
  replies={"/admin/v2/status":{status:500,body:{error:"INTERNAL_ERROR",detail:"x"}}};
  await assert.rejects(()=>client.read(String(statusCall.id)),e=>e instanceof Error && "kind" in e && e.kind === "unknown");
  replies={"/admin/v2/status":{status:200,body:{...summary,extra:token}}};
  await assert.rejects(()=>client.read(String(statusCall.id)));
  client.close();
});

test("an item read substitutes exactly the validated key",async()=>{
  const client=await open(token);
  replies={["/admin/v2/datasources/"+key]:{status:404,body:{error:"NOT_FOUND",detail:"x"}}};
  await assert.rejects(()=>client.read(String(itemCall.id),undefined,key),e=>e instanceof Error && "kind" in e && e.kind === "absent");
  assert.equal(seen.at(-1)?.url.pathname,"/admin/v2/datasources/"+key);
  assert.equal(seen.at(-1)?.init.method,"GET");
  assert.equal(new Headers(seen.at(-1)?.init.headers).get("Authorization"),"Bearer "+token);
  client.close();
});

test("no public surface can send to the second prefix with a body",()=>{
  const code=readFileSync(new URL("../../src/maskgw/admin/ui/assets/ui.js",import.meta.url),"utf8");
  assert.match(code,/second && method !== "GET"/);
});

test("second-prefix vocabulary is checked on token boundaries",()=>{
  const tokens=["alias","enabled","verify-full"];
  assert.doesNotThrow(()=>inspectPublic("const disabled=true; const aliasing=1;",[],true,tokens));
  assert.throws(()=>inspectPublic("const alias=1;",[],true,tokens));
  assert.throws(()=>inspectPublic("x={a:'enabled'}",[],true,tokens));
  assert.throws(()=>inspectPublic("/* verify-full */",[],true,tokens));
  assert.throws(()=>inspectPublic("x='ena'+'bled'",[],true,tokens));
  assert.throws(()=>inspectPublic("<b>&#97;lias</b>",[],false,tokens));
});
