import test from "node:test";
import assert from "node:assert/strict";
import { reader } from "../src/reader.js";
import { book, responseFor } from "./samples.js";
const lens=reader(book);
for(let n=0;n<8;n++) test("closed reader accepts real descriptor "+n,()=>{assert.equal(lens.inspectDataFor("c"+n,responseFor("c"+n)),0);});
for(const bad of [-1,1.5,"0",false,Number.MAX_SAFE_INTEGER+1,NaN,Infinity,null]) test("unsafe envelope version "+String(bad),()=>{
  const value=responseFor("c0");assert.ok(value && typeof value === "object");
  assert.throws(()=>lens.inspectDataFor("c0",{...value,revision:bad}));
});
test("closed model and coherent envelope",()=>{
  const value=responseFor("c0");assert.ok(value && typeof value === "object");
  for(const bad of [{...value,extra:1},{...value,runtime:{revision:1,retired_runtimes_open:0}},{...value,adopted:true},{revision:0},[],null]) assert.throws(()=>lens.inspectDataFor("c0",bad));
  assert.throws(()=>lens.inspectDataFor("c0",JSON.parse('{"__proto__":{},"revision":0}')));
});
test("rows preserve identifiers and positions; hostile text remains data",()=>{
  const row={id:"rul_"+"0".repeat(32),match:'<img src=x onerror="alert(1)">',mode:"contains",case_sensitive:false,transformer:"fixed",config:{value:"</script>"},position:0};
  const one={revision:1,adopted:true,rules:[row]};
  assert.equal(lens.inspectDataFor("c2",one),1);
  assert.throws(()=>lens.inspectDataFor("c2",{...one,rules:[row,{...row,position:1}]}));
  assert.throws(()=>lens.inspectDataFor("c2",{...one,rules:[{...row,position:2}]}));
});
