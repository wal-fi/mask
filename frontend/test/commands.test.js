import test from "node:test";
import assert from "node:assert/strict";
import { commands, capture, safeVersion, reader } from "../../src/maskgw/admin/ui/assets/ui.js";
import { book, responseFor } from "./samples.js";
import { allowed } from "./contracts.js";
const plans=commands(book);
/** @param {number} index */
export function commandFor(index) {
  const item=allowed[index];if(!item) throw new Error("Fixture failed.");
  const {expected_revision,...draft}=item.request;
  return {id:"c"+(9+index),version:expected_revision,draft,identity:item.path.includes("{") ? (item.path.includes("rules") ? "rul_" : "exc_")+"1".repeat(32) : undefined};
}
for(const [index,item] of allowed.entries()) test("closed projection and destination "+index,()=>{
  const command=commandFor(index), result=plans.prepare(command);
  assert.deepEqual(result.body,item.request);assert.equal(result.call.method,item.method);
  assert.equal(result.path,item.path.replace(/\{[^}]+\}/,command.identity ?? ""));
  assert.deepEqual(plans.outcome(result.call,{revision:command.version+1,applied:true},200,command.version).kind,"success");
});
const wrong=[-1,1.5,true,"1",NaN,Infinity,-Infinity,Number.MAX_SAFE_INTEGER+1,undefined,null];
for(const [i,value] of wrong.entries()) test("unsafe revision at every boundary "+i,()=>{
  assert.throws(()=>safeVersion(value));
  const data={revision:value,adopted:true,config:{revision:value,database:{statement_timeout_ms:100,max_rows:1},masking:[],exceptions:[],sql:{denied_functions:[]}}};
  assert.throws(()=>reader(book).inspectDataFor("c1",data));
  const call=plans.lookup("c17");
  assert.throws(()=>plans.outcome(call,{revision:value,applied:true},200,1));
  assert.throws(()=>plans.outcome(call,{error:"REVISION_CONFLICT",detail:"safe",current_revision:value},409,1));
  assert.throws(()=>plans.outcome(call,{error:"CONFIG_DURABILITY_ERROR",detail:"safe",current_revision:value,applied:true},500,1));
});
test("overflow next revision and non-adopted writes refused",()=>{
  for(const version of [0,Number.MAX_SAFE_INTEGER]) assert.throws(()=>plans.prepare({...commandFor(8),version}));
  assert.doesNotThrow(()=>plans.prepare({...commandFor(8),version:Number.MAX_SAFE_INTEGER-1}));
});
for(const identity of ["", "..","../x","x/y","x\\y","%2f","?x=1","x#y","//external/x","http:foo","constructor","__proto__","prototype","rul_"+"A".repeat(32),"exc_"+"1".repeat(32),"rul_"+"1".repeat(33)]) test("hostile identity "+identity.length+" "+identity,()=>{
  assert.throws(()=>plans.prepare({...commandFor(4),identity}));
});
for(const field of ["expected_revision","revision","id","position","allowed_pg_functions","unknown","__proto__","constructor","prototype"]) test("unapproved projection property "+field,()=>{
  const draft={...commandFor(8).draft};Object.defineProperty(draft,field,{value:2,enumerable:true});
  assert.throws(()=>plans.prepare({...commandFor(8),draft}));
});
test("nested protected fields and data capabilities refused before projection",()=>{
  for(const field of ["id","position","revision","unknown"]) assert.throws(()=>plans.prepare({...commandFor(2),draft:{rule:{match:"x",transformer:"fixed",config:{value:"x"},[field]:"bad"}}}));
  let accessed=false;
  const getter={get value(){accessed=true;return 1;}};
  for(const value of [getter,new Date(),new Map(),{x:undefined},{x:()=>1},Object.create({x:1}),[1,,2],{[Symbol()]:1}]) assert.throws(()=>capture(value));
  assert.equal(accessed,false);
  const cyclic={};Object.defineProperty(cyclic,"x",{value:cyclic,enumerable:true});assert.throws(()=>capture(cyclic));
  assert.equal(Object.hasOwn({},"polluted"),false);
});
test("captured commands and snapshots have no mutable source alias",()=>{
  const draft={statement_timeout_ms:100,max_rows:1};const result=plans.prepare({...commandFor(8),draft});draft.max_rows=999;
  assert.deepEqual(result.body,{statement_timeout_ms:100,max_rows:1,expected_revision:1});assert.ok(Object.isFrozen(result.body));
});
test("all error mappings come from private presentation and remote detail is discarded",()=>{
  const cases=[
    ["REVISION_CONFLICT",409,"conflict"],["RELOAD_BUSY",409,"busy"],["CONFIG_OUT_OF_SYNC",409,"incompatible"],
    ["CONFIG_NOT_ADOPTED",409,"incompatible"],["CONFIG_ALREADY_ADOPTED",409,"conflict"],["NOT_FOUND",404,"conflict"],
    ["CONFIG_WRITE_ERROR",500,"incompatible"],["CONFIG_RELOAD_ERROR",422,"incompatible"],["INTERNAL_ERROR",500,"unknown"],
    ["CONFIG_DURABILITY_ERROR",500,"uncertain"],
  ];
  for(const [error,status,kind] of cases) {
    if(typeof status !== "number") throw new Error("Fixture failed.");
    const data={error,detail:"<script>hostile</script>",current_revision:2,...(kind === "uncertain" ? {applied:true} : {})};
    const result=plans.outcome(plans.lookup("c17"),data,status,1);assert.equal(result.kind,kind);assert.equal(result.version,2);assert.ok(!result.message.includes("hostile"));
  }
});
test("malformed and contradictory outcomes are not acknowledgments",()=>{
  for(const value of [{revision:2,applied:false},{revision:3,applied:true},{revision:2,applied:true,current_revision:3},{revision:2},responseFor("c0")]) assert.throws(()=>plans.outcome(plans.lookup("c17"),value,200,1));
  for(const value of [{error:"CONFIG_DURABILITY_ERROR",detail:"x",current_revision:2},{error:"CONFIG_DURABILITY_ERROR",detail:"x",current_revision:2,applied:false},{error:"CONFIG_DURABILITY_ERROR",detail:"x",current_revision:4,applied:true},{error:"UNKNOWN",detail:"x"}]) assert.throws(()=>plans.outcome(plans.lookup("c17"),value,500,1));
  assert.throws(()=>plans.outcome(plans.lookup("c17"),{error:"RELOAD_BUSY",detail:"x"},200,1));
});
