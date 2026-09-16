import test from "node:test";
import assert from "node:assert/strict";
import { author } from "../src/author.js";
import { commands } from "../src/commands.js";
import { entry } from "../src/reader.js";
import { book, responseFor } from "./samples.js";
const plan=author(book), transport=commands(book);
function base() {
  const v=responseFor("c1");if(!entry(v) || !entry(v.config)) throw new Error("Fixture refused.");
  v.revision=1;v.adopted=true;v.config.revision=1;v.config.database={statement_timeout_ms:30000,max_rows:1000};
  v.config.masking=[1,2,3].map(n=>({id:"rul_"+String(n).repeat(32),match:"same",mode:"contains",case_sensitive:false,transformer:"fixed",config:{value:String(n)}}));
  v.config.exceptions=[{id:"exc_"+"a".repeat(32),match:"keep",mode:"exact",case_sensitive:false}];
  v.config.sql={denied_functions:["UPPER"],allowed_pg_functions:["lower"]};return v;
}
const ids=[1,2,3].map(n=>"rul_"+String(n).repeat(32));
test("exact three batch profiles, no exception reorder or config PUT",()=>{
  assert.deepEqual(plan.batches.map(p=>[p.id,p.call,p.operation]),[["v2","c10","move"],["v4","c17","replace"],["v5","c18","append"]]);
  for(const id of ["v0","v1","v3"]) assert.throws(()=>plan.batch(id));
});
for(const value of [[],ids.slice(1),[...ids,ids[0]],[ids[0],ids[0],ids[2]],[...ids.slice(0,2),"rul_"+"4".repeat(32)], [null,...ids.slice(1)],["bad",...ids.slice(1)],ids.join(","),null,true]) test("malformed or non-base permutation rejected "+JSON.stringify(value),()=>{
  assert.throws(()=>plan.checkedBatch("v2",base(),{rule_ids:value}));
});
test("full permutation preserves exact source, content and all protected fields",()=>{
  const source=base(), before=JSON.stringify(source), draft={rule_ids:[...ids].reverse()};
  const next=plan.batchCandidate("v2",source,draft);assert.ok(entry(next)&&entry(source.config));
  const prior=plan.candidate(source);assert.ok(entry(prior));
  assert.deepEqual(next,{...prior,masking:Array.isArray(prior.masking)?[...prior.masking].reverse():[]});
  assert.equal(JSON.stringify(source),before);assert.ok(Object.isFrozen(next));
  assert.deepEqual(plan.initial("v2",source),{rule_ids:ids});
  const newer=structuredClone(source);assert.ok(entry(newer.config)&&Array.isArray(newer.config.masking));newer.config.masking.pop();
  assert.throws(()=>plan.checkedBatch("v2",newer,draft));
});
for(const [key,min,max] of [["statement_timeout_ms",100,600000],["max_rows",1,1000000]]) {
  for(const value of [Number(min)-1,Number(max)+1,true,false,1.5,"100","01"," 100",null,Number.MAX_SAFE_INTEGER+1,NaN,Infinity]) test("database refuses type/range "+key+":"+String(value),()=>{
    assert.throws(()=>plan.checkedBatch("v4",base(),{statement_timeout_ms:30000,max_rows:1000,[String(key)]:value}));
  });
  for(const value of [min,max]) test("database accepts boundary "+key+":"+value,()=>{
    const body={statement_timeout_ms:30000,max_rows:1000,[String(key)]:value};assert.deepEqual(plan.checkedBatch("v4",base(),body),body);
  });
}
test("database body always complete and extra fields never projected away",()=>{
  for(const value of [{statement_timeout_ms:100},{max_rows:1},{statement_timeout_ms:100,max_rows:1,extra:0},{statement_timeout_ms:100,max_rows:1,expected_revision:1}]) assert.throws(()=>plan.checkedBatch("v4",base(),value));
  const body=plan.checkedBatch("v4",base(),{statement_timeout_ms:100,max_rows:1});
  const source=base(), prior=plan.candidate(source), next=plan.batchCandidate("v4",source,body);assert.ok(entry(prior));assert.deepEqual(next,{...prior,database:body});
  assert.ok(transport.prepare({id:"c17",version:1,draft:body,identity:undefined}));
});
test("SQL sends only additions verbatim; candidate retains protected values",()=>{
  const source=base(), additions={denied_functions:["LOWER","lower"," UPPER ","Straße","STRASSE"]};
  assert.deepEqual(plan.initial("v5",source),{denied_functions:[]});
  assert.deepEqual(plan.checkedBatch("v5",source,additions),additions);
  const candidate=plan.batchCandidate("v5",source,additions), prior=plan.candidate(source);assert.ok(entry(prior)&&entry(prior.sql));
  assert.deepEqual(candidate,{...prior,sql:{...prior.sql,denied_functions:["UPPER",...additions.denied_functions]}});
  assert.ok(!JSON.stringify(plan.checkedBatch("v5",source,additions)).includes("allowed_pg_functions"));
  for(const extra of [null,[],["lower"]]) assert.throws(()=>plan.checkedBatch("v5",source,{...additions,allowed_pg_functions:extra}));
  for(const value of [[],null,true,[1],"lower"]) assert.throws(()=>plan.checkedBatch("v5",source,{denied_functions:value}));
});
test("batch drafts refuse prototypes, accessors, IDs, versions and non-adopted base",()=>{
  let seen=0;const accessor=Object.defineProperty({},"rule_ids",{enumerable:true,get(){seen++;return ids;}});
  for(const value of [accessor,Object.create({rule_ids:ids}),JSON.parse('{"__proto__":{}}'),{rule_ids:ids,id:"x"},{rule_ids:ids,revision:1}]) assert.throws(()=>plan.checkedBatch("v2",base(),value));
  const source=base();source.adopted=false;assert.throws(()=>plan.checkedBatch("v2",source,{rule_ids:ids}));assert.equal(seen,0);
});
test("display positions are one based without changing authoritative DTO",()=>{
  const value={revision:1,adopted:true,rules:ids.map((id,position)=>({id,position,match:"x",mode:"contains",case_sensitive:false,transformer:"fixed",config:{value:"x"}}))};
  const shown=plan.displayed("c2",value);assert.ok(entry(shown)&&Array.isArray(shown.rules));assert.deepEqual(shown.rules.map(x=>x.position),[1,2,3]);assert.deepEqual(value.rules.map(x=>x.position),[0,1,2]);
});
