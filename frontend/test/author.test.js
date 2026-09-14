import test from "node:test";
import assert from "node:assert/strict";
import { author } from "../src/author.js";
import { entry } from "../src/reader.js";
import { book, responseFor } from "./samples.js";
const plan=author(book);
/** @param {number} version */
function base(version=1) {const value=responseFor("c1");if(!entry(value) || !entry(value.config)) throw new Error("Fixture failed.");value.revision=version;value.adopted=version>0;value.config.revision=version;value.config.database={statement_timeout_ms:30000,max_rows:1000};return value;}
const registry={revision:1,transformers:[
  {name:"fixed",required_parameters:["value"],optional_parameters:[]},
  ...["md5","sha256","sha512","hmac_sha256"].map(name=>({name,required_parameters:[],optional_parameters:[]})),
  {name:"truncate",required_parameters:["length"],optional_parameters:[]},
  {name:"regex",required_parameters:["pattern","replacement"],optional_parameters:[]},
  {name:"random",required_parameters:[],optional_parameters:["strategy","preserve_length","length"]},
]};
test("only two CRUD profiles; protected views cannot gain editing",()=>{
  assert.deepEqual(plan.profiles.map(p=>p.id),["v2","v3"]);
  for(const id of ["v0","v1","v4","v5"]) assert.throws(()=>plan.profile(id));
  assert.deepEqual(plan.defaults("v2"),{mode:"contains",case_sensitive:false});
  assert.deepEqual(plan.defaults("v3"),{mode:"exact",case_sensitive:false});
  assert.equal(plan.consented(base()),true);assert.equal(plan.consented(base(0)),false);
});
test("transient root candidate preserves protection without IDs or version",()=>{
  const source=base();assert.ok(entry(source.config));
  source.config.masking=[{id:"rul_"+"1".repeat(32),match:" old ",mode:"contains",case_sensitive:false,transformer:"fixed",config:{value:"x"}}];
  source.config.exceptions=[{id:"exc_"+"2".repeat(32),match:"keep",mode:"exact",case_sensitive:false}];
  const prior=JSON.stringify(source), next=plan.candidate(source,{page:"v2",operation:"create",identity:undefined,value:{match:"  exact text  ",mode:"contains",case_sensitive:false,transformer:"fixed",config:{value:"x"}}});
  assert.ok(entry(next) && Array.isArray(next.masking));
  assert.equal(JSON.stringify(source),prior);assert.ok(!Object.hasOwn(next,"revision") && !Object.hasOwn(next,"expected_revision") && !Object.hasOwn(next,"config"));
  assert.deepEqual(next.sql,source.config.sql);assert.deepEqual(next.database,source.config.database);
  assert.ok(next.masking.every(v=>entry(v) && !Object.hasOwn(v,"id")));
  assert.equal(next.masking[1]?.match,"  exact text  ");assert.ok(Object.isFrozen(next));
});
for(const [name,parameters] of Object.entries({fixed:{value:"<img src=x>"},md5:{},sha256:{},sha512:{},hmac_sha256:{},truncate:{length:0},regex:{pattern:"[",replacement:"</script>"},random:{strategy:"digits",preserve_length:true}})) test("private editor accepts declared parameters "+name,()=>{
  assert.equal(plan.available(registry).length,8);
  const value={match:" CPF ",mode:"contains",case_sensitive:false,transformer:name,config:parameters};
  assert.deepEqual(plan.checkedContent("v2",value,registry),value);
  assert.throws(()=>plan.checkedContent("v2",{...value,config:{...parameters,secret:"x"}},registry));
});
for(const parameters of [{strategy:"digits",preserve_length:true,length:1},{strategy:"digits",preserve_length:false},{strategy:"digits",preserve_length:false,length:true},{strategy:"other",preserve_length:true}]) test("dependent parameters rejected before transport "+JSON.stringify(parameters),()=>{
  assert.throws(()=>plan.checkedContent("v2",{match:"x",mode:"contains",case_sensitive:false,transformer:"random",config:parameters},registry));
});
test("unknown editor and mismatched registry are blocked without changing source",()=>{
  const value={match:"x",mode:"contains",case_sensitive:false,transformer:"future",config:{value:"kept"}}, before=JSON.stringify(value);
  assert.throws(()=>plan.checkedContent("v2",value,registry));assert.equal(JSON.stringify(value),before);
  assert.throws(()=>plan.checkedContent("v2",{...value,transformer:"fixed"},{revision:1,transformers:[]}));
});
test("validation success is exactly the four normative booleans",()=>{
  const value={valid:true,schema_validated:true,policy_compiled:true,database_checks_performed:false};plan.inspectCheck(value);
  for(const key of Object.keys(value)) {assert.throws(()=>plan.inspectCheck({...value,[key]:!Reflect.get(value,key)}));assert.throws(()=>plan.inspectCheck(Object.fromEntries(Object.entries(value).filter(([k])=>k!==key))));}
  assert.throws(()=>plan.inspectCheck({...value,revision:1}));
});
test("reasons are associated only to exact known controls with local text",()=>{
  const error={error:"SCHEMA_INVALID",detail:"<script>secret</script>",fields:[{path:"masking.0.match",reason:"missing"},{path:"filesystem.secret",reason:"missing"}]};
  const issues=plan.reasons(error,[{path:"masking.0.match",label:"match"}]);assert.equal(issues.length,1);assert.ok(!JSON.stringify(issues).includes("secret"));
  assert.throws(()=>plan.reasons({...error,fields:[{path:"masking.0.match",reason:"hostile"}]},[]));
});

test("replacement and deletion preserve positions, unrelated items and protected base",()=>{
  const source=base();assert.ok(entry(source.config));
  const items=[1,2,3].map(n=>({id:"exc_"+String(n).repeat(32),match:"item-"+n,mode:"exact",case_sensitive:false}));source.config.exceptions=items;
  const identity=items[1]?.id, value={match:" changed ",mode:"exact",case_sensitive:false}, before=JSON.stringify(source);
  const next=plan.candidate(source,{page:"v3",operation:"replace",identity,value});assert.ok(entry(next) && Array.isArray(next.exceptions));
  assert.deepEqual(next.exceptions.map(x=>x.match),["item-1"," changed ","item-3"]);
  const removed=plan.candidate(source,{page:"v3",operation:"delete",identity,value:{}});assert.ok(entry(removed) && Array.isArray(removed.exceptions));
  assert.deepEqual(removed.exceptions.map(x=>x.match),["item-1","item-3"]);assert.equal(JSON.stringify(source),before);
  assert.throws(()=>plan.candidate(source,{page:"v3",operation:"create",identity:undefined,value:{...value,id:"exc_"+"9".repeat(32)}}));
});
test("draft getters, custom prototypes and structural keys are refused without execution",()=>{
  let accessed=0;const getter=Object.defineProperty({},"match",{enumerable:true,get(){accessed++;return "x";}});
  for(const value of [getter,Object.create({match:"x"}),JSON.parse('{"__proto__":{"polluted":true}}')]) {
    assert.throws(()=>plan.defaults("v2",value));assert.throws(()=>plan.checkedContent("v2",value,registry));
    assert.throws(()=>plan.candidate(base(),{page:"v2",operation:"create",identity:undefined,value}));
  }
  assert.equal(accessed,0);assert.equal(Reflect.get(Object.prototype,"polluted"),undefined);
});
