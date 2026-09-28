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

test("the second prefix carries four reads and only the nine approved writes",()=>{
  assert.equal(validate(fixture()),true);
  const reads=second.filter(c=>c.method === "GET"), writes=second.filter(c=>c.method !== "GET");
  assert.equal(reads.length,4);
  assert.ok(reads.every(c=>c.operation === "read" && c.input === null));
  assert.equal(writes.length,9);
  assert.ok(writes.every(c=>typeof c.input === "string" && ["register","probe","renew","resume","pause","revise","retire","amend"].includes(String(c.operation))));
});
const actions=arr(obj(document.console).actions).map(obj);
const at6=(/** @type {string} */ label)=>actions.findIndex(a=>a.label === label);
const register=at6("Novo datasource"), revise=at6("Editar conexão e limites"), retire=at6("Remover"), amend=at6("Editar política");
function findSecret() {return arr(obj(actions[register]).fields).map(obj).findIndex(f=>f.kind === "secret");}
const probeCall=calls.findIndex(c=>c.operation === "probe"), readCall=calls.findIndex(c=>c.path === "/admin/v2/datasources/{datasource_id}" && c.method === "GET");
const v1Write=calls.findIndex(c=>c.path === "/admin/v1/database");
if([register,revise,retire,amend,probeCall,readCall,v1Write].some(i=>i < 0)) throw new Error("Fixture actions required.");

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
  // Presentation-only groups, tones and title never hide, duplicate or invent a value.
  ["group hides an entry",["console","detail","tabs",0,"groups",0,"members"],arr(obj(arr(obj(arr(obj(obj(document.console).detail).tabs)[0]).groups)[0]).members).slice(0,1)],
  ["entry in two groups",["console","detail","tabs",0,"groups",1,"members",0],String(arr(obj(arr(obj(arr(obj(obj(document.console).detail).tabs)[0]).groups)[0]).members)[0])],
  ["unknown group member",["console","detail","tabs",0,"groups",0,"members",0],"r999999"],
  ["unknown group key",["console","detail","tabs",0,"groups",0,"script"],"x"],
  ["unknown tone",["console","summary","figures",7,"wording",0,"tone"],"danger"],
  ["unknown display",["console","detail","tabs",0,"entries",0,"show"],"html"],
  ["title on a number",["console","detail","title"],["datasource","revision"]],
  ["title outside model",["console","detail","title"],["datasource","nowhere"]],
  // Phase 9, Stage 6: writes only through the approved operation, method and fields.
  ["write operation with another method",["calls",writeIndex,"method"],"GET"],
  ["second-prefix write with the wrong method",["calls",calls.findIndex(c=>c.operation === "retire"),"method"],"POST"],
  ["second-prefix operation on the first prefix",["calls",v1Write,"operation"],"revise"],
  ["action on a read",["console","actions",revise,"call"],String(calls[readCall]?.id)],
  ["action field outside the input",["console","actions",revise,"fields",0,"path"],["nowhere"]],
  ["action source outside the base",["console","actions",revise,"fields",0,"source"],["datasource","nowhere"]],
  ["secret read back into a form",["console","actions",register,"fields",findSecret(),"source"],["catalog_revision"]],
  ["records without items",["console","actions",amend,"fields",0,"items"],[]],
  ["typed confirmation that is not text",["console","actions",retire,"typed","kind"],"secret"],
  ["version stamp without origin",["console","actions",revise,"origin"],null],
  ["version stamp on text",["console","actions",revise,"stamp"],["display_name"]],
  ["opening without identity path",["console","actions",register,"lands"],null],
  ["probe that writes",["console","actions",register,"probe"],String(calls.find(c=>c.operation === "register")?.id)],
  ["wizard step with a foreign field",["console","guide","steps",0,"fields",0],"y999999"],
  ["unknown place",["console","actions",revise,"place"],"root"],
  // Política v1 pages only arrange approved readings: nothing omitted, nothing added.
  ["page for unknown view",["console","pages",0,"view"],"v99"],
  ["page omits a read field",["console","pages",0,"sections",0,"entries"],arr(obj(arr(obj(arr(obj(document.console).pages)[0]).sections)[0]).entries).slice(0,1)],
  ["page shows a field outside the view",["console","pages",4,"sections",1,"entries"],(()=>{const kept=arr(obj(arr(obj(arr(obj(document.console).pages)[4]).sections)[1]).entries);return [...kept,{...obj(kept[0]),id:"w99999",path:["config","masking"],kind:"tree"}];})()],
  ["two pages for one view",["console","pages",1,"view"],String(obj(arr(obj(document.console).pages)[0]).view)],
  ["page path through a list index",["console","pages",2,"sections",1,"entries",0,"path"],["rules",0,"match"]],
  ["page path outside model",["console","pages",0,"sections",0,"entries",0,"path"],["nowhere"]],
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
  // Test-only markers: a lost answer and a slow answer.
  if(reply.body === "LOST") throw new TypeError("Failed to fetch");
  if(reply.body === "SLOW") { await new Promise(resolve=>setTimeout(resolve,80)); return new Response(JSON.stringify({catalog_revision:4,datasource_id:key,datasource_revision:3,changed:true}),{status:200,headers:{"Content-Type":"application/json"}}); }
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

test("only the declared write function can send to the second prefix with a body",()=>{
  const code=readFileSync(new URL("../../src/maskgw/admin/ui/assets/ui.js",import.meta.url),"utf8");
  assert.match(code,/second && method !== "GET" && !mutating/);
  assert.equal(code.split("destination(path,false,call.method,true)").length-1,1);
  assert.equal(code.split("false,extra,true,true)").length-1,1);
});

// ---- second-prefix writes (Phase 9, Stage 6) ---------------------------------
/** @param {string} operation */
const writeOf=operation=>String(calls.find(c=>c.operation === operation)?.id);
const draftBody={
  expected_catalog_revision:3,alias:"novo-demo",display_name:"Novo",enabled:true,
  connection:{host:"db-novo.example.internal",port:5432,database:"app",username:"gw",tls:{mode:"verify-full"}},
  credential:{password:"senha-local-de-teste"},limits:{statement_timeout_ms:30000,max_rows:1000,max_sessions:8},
  destination_policy:{allow_public:false,allow_loopback:false,allowed_hosts:[]},
  policy:{masking:[{match:"cpf",mode:"contains",case_sensitive:false,transformer:"fixed",config:{value:"x"}}],exceptions:[],database:{statement_timeout_ms:30000,max_rows:1000},sql:{denied_functions:[]}},
};
const written={catalog_revision:4,datasource_id:key,datasource_revision:1,changed:true};

test("a write is one checked request with the declared method, path and body",async()=>{
  const client=await open(token);seen=[];
  replies={"/admin/v2/datasources":{status:200,body:written}};
  const result=await client.submit(writeOf("register"),draftBody);
  assert.deepEqual(result,{kind:"done",value:written});
  assert.equal(seen.length,1);
  assert.equal(seen[0]?.init.method,"POST");assert.equal(seen[0]?.url.pathname,"/admin/v2/datasources");
  assert.deepEqual(JSON.parse(String(seen[0]?.init.body)),draftBody);
  assert.equal(new Headers(seen[0]?.init.headers).get("Content-Type"),"application/json");
  client.close();
});

test("a malformed body or one carrying the token never leaves the page",async()=>{
  const client=await open(token);seen=[];
  const {alias,...missing}=draftBody;void alias;
  await assert.rejects(()=>client.submit(writeOf("register"),missing));
  await assert.rejects(()=>client.submit(writeOf("register"),{...draftBody,dsn:"postgresql://x"}));
  await assert.rejects(()=>client.submit(writeOf("register"),{...draftBody,connection:{...draftBody.connection,port:"5432"}}));
  await assert.rejects(()=>client.submit(writeOf("register"),{...draftBody,credential:{password:token}}));
  await assert.rejects(()=>client.submit(writeOf("revise"),{expected_revision:2,alias:"outro"},key));
  assert.equal(seen.length,0);
  client.close();
});

test("an item write substitutes exactly the validated key, action suffix included",async()=>{
  const client=await open(token);seen=[];
  replies={["/admin/v2/datasources/"+key+":rotate-credential"]:{status:200,body:{...written,datasource_revision:3}}};
  const result=await client.submit(writeOf("renew"),{expected_revision:2,credential:{password:"nova-senha-local"}},key);
  assert.equal(result.kind,"done");
  assert.equal(seen.at(-1)?.url.pathname,"/admin/v2/datasources/"+key+":rotate-credential");
  for(const hostileKey of ["../status","dso_x",key+"/policy","%2e%2e","",key+":enable"]) {
    await assert.rejects(()=>client.submit(writeOf("renew"),{expected_revision:2,credential:{password:"x"}},hostileKey));
  }
  await assert.rejects(()=>client.submit(writeOf("register"),draftBody,key));
  assert.equal(seen.length,1);
  client.close();
});

test("closed error envelopes give category and stamp; anything else is unknown",async()=>{
  const client=await open(token);
  replies={["/admin/v2/datasources/"+key]:{status:409,body:{error:"REVISION_CONFLICT",detail:"x",current_revision:7}}};
  const conflict=await client.submit(writeOf("retire"),{expected_revision:2,confirm_alias:"crm"},key);
  assert.equal(conflict.kind,"refused");
  if(conflict.kind === "refused") {assert.equal(conflict.category,"REVISION_CONFLICT");assert.equal(obj(conflict.value).current_revision,7);assert.equal(conflict.status,409);}
  replies={"/admin/v2/datasources":{status:422,body:{error:"SCHEMA_INVALID",detail:"x",fields:[{path:"body.connection.port",reason:"out_of_range"}]}}};
  const schema=await client.submit(writeOf("register"),draftBody);
  assert.equal(schema.kind,"refused");
  if(schema.kind === "refused") assert.deepEqual(schema.fields,[{path:"body.connection.port",reason:"out_of_range"}]);
  replies={"/admin/v2/datasources":{status:409,body:{error:"MADE_UP",detail:"x"}}};
  assert.deepEqual(await client.submit(writeOf("register"),draftBody),{kind:"unknown"});
  replies={"/admin/v2/datasources":{status:500,body:{error:"CATALOG_OUTCOME_UNCERTAIN",detail:"x",extra:1}}};
  assert.deepEqual(await client.submit(writeOf("register"),draftBody),{kind:"unknown"});
  replies={"/admin/v2/datasources":{status:200,body:{...written,changed:"yes"}}};
  assert.deepEqual(await client.submit(writeOf("register"),draftBody),{kind:"unknown"});
  replies={"/admin/v2/datasources":{status:200,body:"LOST"}};
  assert.deepEqual(await client.submit(writeOf("register"),draftBody),{kind:"unknown"});
  client.close();
});

test("one write at a time, shared with the first prefix",async()=>{
  const client=await open(token);
  replies={["/admin/v2/datasources/"+key+":disable"]:{status:200,body:"SLOW"}};
  const first=client.submit(writeOf("pause"),{expected_revision:2},key);
  assert.equal(client.busy(),true);
  await assert.rejects(()=>client.submit(writeOf("pause"),{expected_revision:2},key),e=>e instanceof Error && "kind" in e && e.kind === "incompatible");
  assert.equal((await first).kind,"done");assert.equal(client.busy(),false);
  client.close();
});

test("reads and checks never reach a write, and a test is the only quiet write",async()=>{
  const client=await open(token);seen=[];
  await assert.rejects(()=>client.read(writeOf("retire"),undefined,key));
  await assert.rejects(()=>client.check(writeOf("probe"),{}));
  assert.equal(seen.length,0);
  assert.deepEqual(["register","probe","renew","resume","pause","revise","retire","amend"].filter(op=>client.quiet(writeOf(op))),["probe"]);
  client.close();
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
