import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { check as validate, digest } from "../../src/maskgw/admin/ui/assets/ui.js";
import { allowed, full } from "./contracts.js";
import { inspectPublic } from "../tools/inspect.js";
/** @param {unknown} value @returns {value is Record<string,unknown>} */
function isObject(value) { return typeof value === "object" && value !== null && !Array.isArray(value); }
/** @param {unknown} value @returns {Record<string,unknown>} */
function obj(value) {
  if (!isObject(value)) throw new Error("Fixture object required.");
  return value;
}
/** @param {unknown} value @returns {unknown[]} */
function arr(value) { if (!Array.isArray(value)) throw new Error("Fixture list required."); return value; }
/** @returns {Record<string,unknown>} */
function fixture() { /** @type {unknown} */ const value=JSON.parse(readFileSync(new URL("../private/presentation.json",import.meta.url),"utf8")); return obj(value); }
/** @param {Record<string,unknown>} root @param {Array<string|number>} path @param {unknown} value */
function set(root,path,value) {
  let current=root;
  for (const part of path.slice(0,-1)) current=obj(typeof part === "number" ? arr(current)[part] : current[part]);
  const last=path.at(-1);
  if (typeof last !== "string") throw new Error("Fixture leaf required.");
  current[last]=value;
}
// Traverse arrays without assigning an unchecked JSON value to a DTO.
/** @param {unknown} root @param {Array<string|number>} path @param {unknown} value */
function change(root,path,value) {
  let current=root;
  for (const part of path.slice(0,-1)) current=typeof part === "number" ? arr(current)[part] : obj(current)[part];
  const last=path.at(-1);
  if (typeof last === "number") arr(current)[last]=value;
  else if (typeof last === "string") obj(current)[last]=value;
  else throw new Error("Empty fixture path.");
}

test("static presentation and digest agree",()=> {
  assert.equal(validate(fixture()),true);
  const bytes=readFileSync(new URL("../private/presentation.json",import.meta.url));
  assert.equal(createHash("sha256").update(bytes).digest("hex"),digest);
});
/** @type {Array<[string,Array<string|number>,unknown]>} */
const hostile=[
  ["unknown root key",["extra"],true], ["format boolean",["format"],true], ["format number",["format"],2],
  ["remote path",["calls",0,"path"],"https://evil.invalid/admin/v1/status"],
  ["authority",["calls",0,"path"],"//evil.invalid/admin/v1/status"],
  ["query",["calls",0,"path"],"/admin/v1/status?x=1"],
  ["fragment",["calls",0,"path"],"/admin/v1/status#x"],
  ["encoded",["calls",0,"path"],"/admin/v1/%73tatus"],
  ["traversal",["calls",0,"path"],"/admin/v1/../status"],
  ["backslash",["calls",0,"path"],"/admin/v1/\\status"],
  ["two slots",["calls",3,"path"],"/admin/v1/{rule_id}/{rule_id}"],
  ["invalid method",["calls",0,"method"],"PATCH"],
  ["missing output",["calls",0,"output"],"m999"],
  ["read with input",["calls",0,"input"],"m0"],
  ["invalid action",["calls",0,"operation"],"execute"],
  ["unknown call property",["calls",0,"callback"],"alert(1)"],
  ["duplicate identity",["calls",0,"id"],"m0"],
  ["non opaque identity",["calls",0,"id"],"status"],
  ["missing view reference",["views",0,"call"],"c999"],
  ["missing action reference",["views",0,"actions"],["c999"]],
  ["bad path",["views",0,"controls",0,"path"],["absent"]],
  ["prototype segment",["views",0,"controls",0,"path"],["__proto__"]],
  ["constructor segment",["views",0,"controls",0,"path"],["constructor"]],
  ["prototype segment 2",["views",0,"controls",0,"path"],["prototype"]],
  ["negative segment",["views",0,"controls",0,"path"],[-1]],
  ["token projection",["views",0,"controls",0,"projections"],[{type:"copy",source:"token",paths:[],target:[]}]],
  ["prototype projection",["views",0,"controls",0,"projections"],[{type:"copy",source:"base",paths:[],target:["constructor"]}]],
  ["unknown control",["views",0,"controls",0,"type"],"html"],
  ["unsafe integer",["models",0,"shape","max"],9007199254740992],
  ["unknown shape",["models",0,"shape","type"],"javascript"],
  ["missing editor model",["editors",0,"model"],"m999"],
  ["invalid binding role",["bindings",0,"role"],"token"],
  ["unsafe default",["views",0,"controls",0,"default"],{}],
  ["unknown message state",["messages",0,"state"],"execute"],
];
for (const [name,path,value] of hostile) test(name,()=>{const p=fixture();change(p,path,value);assert.equal(validate(p),false);});
for (const key of ["__proto__","constructor","prototype"]) test("poison key "+key,()=>{
  const p=fixture();Object.defineProperty(p,key,{value:{polluted:true},enumerable:true});assert.equal(validate(p),false);assert.equal(Object.hasOwn({},"polluted"),false);
});
test("text containing dangerous names remains text",()=>{const p=fixture();change(p,["messages",0,"text"],"__proto__ constructor prototype <img src=x onerror=alert(1)>");assert.equal(validate(p),true);});
test("foreign object prototype refused",()=>{const p=fixture();Object.setPrototypeOf(p,{polluted:true});assert.equal(validate(p),false);});
test("object cycle refused",()=>{const p=fixture();p.extra=p;assert.equal(validate(p),false);});
test("reference cycle refused",()=>{const p=fixture();change(p,["models",0,"shape"],{type:"nullable",item:"m0"});assert.equal(validate(p),false);});
test("missing reference refused",()=>{const p=fixture();change(p,["models",0,"shape"],{type:"nullable",item:"m999"});assert.equal(validate(p),false);});
test("128 models inclusive",()=>{
  const p=fixture(),models=arr(p.models);
  while(models.length<128) models.push({id:"m"+models.length,shape:{type:"boolean"}});
  assert.equal(validate(p),true);models.push({id:"m128",shape:{type:"boolean"}});assert.equal(validate(p),false);
});
test("512 controls inclusive",()=>{
  const p=fixture();const view=obj(arr(p.views)[0]);const list=arr(view.controls);
  let all=0;
  for(const owner of [...arr(p.views),...arr(p.editors)]) all+=arr(obj(owner).controls).length;
  for(let i=0;i<512-all;i++) list.push({...obj(list[0]),id:"k"+(1000+i)});
  assert.equal(validate(p),true);list.push({...obj(list[0]),id:"k9999"});assert.equal(validate(p),false);
});
test("reference depth 16 inclusive",()=>{
  const p=fixture(),models=arr(p.models);
  for(let i=0;i<16;i++) models.push({id:"m"+(200+i),shape:i===15?{type:"boolean"}:{type:"nullable",item:"m"+(201+i)}});
  assert.equal(validate(p),true);models.push({id:"m199",shape:{type:"nullable",item:"m200"}});assert.equal(validate(p),false);
});
for(const [name,text,js] of [
  ["literal","revision",false], ["HTML entity","rev&#105;sion",false],
  ["CSS escape","rev\\69 sion",false], ["JS escape","const x='rev\\u0069sion';",true],
  ["concat","const x='rev'+'ision';",true], ["base64 reconstruction","atob('cmV2aXNpb24=');",true],
]) test("public negative "+name,()=>assert.throws(()=>inspectPublic(String(text),["revision"],Boolean(js))));
test("public benign bytes pass",()=>inspectPublic("export const value=1;",["revision"],true));

const negative=[
  '/** @type {import("../private/contracts.js").WriteOutcome} */ const value={type:"uncertain",value:{revision:2,applied:true}};',
  '/** @type {import("../private/contracts.js").WriteOutcome} */ const value={type:"rejected",value:{error:"CONFIG_DURABILITY_ERROR",detail:"x",applied:true}};',

  '/** @type {import("../private/contracts.js").UiWriteContract} */ const value={method:"PUT",path:"/admin/v1/config",request:{},response:{revision:1,applied:true}};',
  '/** @type {import("../private/contracts.js").AdoptRequest} */ const value={expected_revision:0,confirm_comment_loss:false};',
  '/** @type {import("../private/contracts.js").DatabaseWriteRequest} */ const value={expected_revision:0,statement_timeout_ms:"100",max_rows:1};',
  '/** @type {import("../private/contracts.js").ViewState} */ const value={type:"uncertain"};',
  '/** @type {import("../private/contracts.js").UiRuleContent} */ const value={match:"x",transformer:"random",config:{strategy:"digits",preserve_length:true,length:10}};',
  '/** @type {import("../private/contracts.js").UiSqlRequest} */ const value={expected_revision:0,allowed_pg_functions:[]};',
];
for(const [index,source] of negative.entries()) test("typing counterexample "+index,()=>{
  mkdirSync(new URL("../.type-negative/",import.meta.url),{recursive:true});
  const file=new URL("../.type-negative/case"+index+".js",import.meta.url);
  writeFileSync(file,source+"\nexport {};\n");
  const result=spawnSync(process.execPath,["node_modules/typescript/bin/tsc","--allowJs","--checkJs","--strict","--noEmit","--noUncheckedIndexedAccess","--exactOptionalPropertyTypes","--skipLibCheck","false","--target","ES2022","--module","NodeNext",".type-negative/case"+index+".js"],{encoding:"utf8"});
  assert.equal(result.status,2);assert.match(result.stdout,/TS(2322|2741|2353)/);assert.doesNotMatch(result.stdout,/TS2307/);
});

test("ten allowed write types and the separate eleventh contract",()=>{
  const p=fixture();
  const writes=arr(p.calls).map(obj).filter(c=>c.method !== "GET" && c.operation !== "check");
  assert.deepEqual(new Set(allowed.map(c=>c.method+" "+c.path)),new Set(writes.map(c=>String(c.method)+" "+String(c.path))));
  assert.equal(allowed.length,10);assert.equal(full.path,"/admin/v1/config");
});
test("closed discriminator union rejects changed tag",()=>{
  const p=fixture();const item=arr(p.models).map(obj).find(m=>obj(m.shape).type === "union");
  assert.ok(item);obj(arr(obj(item.shape).variants)[0]).value="UNAPPROVED";assert.equal(validate(p),false);
});
for (const name of ["index.html","ui.js","ui.css"]) test("private marker in each public artifact "+name,()=>{
  const text=readFileSync(new URL("../../src/maskgw/admin/ui/assets/"+name,import.meta.url),"utf8");
  assert.throws(()=>inspectPublic(text+"\n/* expected_revision */",["expected_revision"],name === "ui.js"));
});

for(const key of ["__proto__","constructor","prototype"]) test("template identity is structural "+key,()=>{
  const p=fixture();change(p,["calls",3,"path"],"/admin/v1/rules/{"+key+"}");change(p,["calls",3,"identity"],key);assert.equal(validate(p),false);
});


test("generated resources and anchors preserve LF across checkout",()=>{
  const names=[
    ...["calls.json","contracts.d.ts","model-names.json","presentation.json","protocol-schema.json","vocabulary.json","wire-schemas.json"].map(name=>"frontend/private/"+name),
    ...["index.html","ui.js","ui.css","presentation.json","manifest.json"].map(name=>"src/maskgw/admin/ui/assets/"+name),
    "src/maskgw/admin/ui/_anchor.py","src/maskgw/admin/ui/_catalog.py","frontend/src/protocol.js",
  ];
  for (const name of names) assert.equal(readFileSync(new URL("../../"+name,import.meta.url)).includes(Buffer.from("\r\n")),false,name);
});
