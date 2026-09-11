import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { open } from "../../src/maskgw/admin/ui/assets/ui.js";
import { inspectPublic } from "../tools/inspect.js";

const bytes=readFileSync(new URL("../../src/maskgw/admin/ui/assets/presentation.json",import.meta.url));
const token="transport-test-marker-private-credential";
/** @type {{url: URL, init: RequestInit}[]} */ let calls=[];
let broken=false;
Object.defineProperty(globalThis,"window",{value:{location:{origin:"http://127.0.0.1:8765"}}, configurable:true});
/** @param {RequestInfo | URL} input @param {RequestInit | undefined} init */
globalThis.fetch=async (input, init) => {
  assert.ok(input instanceof URL && init);
  calls.push({url:input,init});
  return new Response(input.pathname.endsWith("presentation.json") ? (broken ? "{}" : bytes) : "{}",{headers:{"Content-Type":"application/json"}});
};
test.beforeEach(()=>{calls=[];broken=false;});

test("explicit token precedes metadata and all fetch options are normative",async()=>{
  assert.equal(calls.length,0);
  await assert.rejects(()=>open(""));assert.equal(calls.length,0);
  const client=await open(token);
  assert.equal(calls.length,1);
  assert.equal(calls[0]?.url.pathname,"/admin/ui/presentation.json");
  await client.read("c0");await client.check("c8",{masking:[],exceptions:[]});
  for(const {url,init} of calls) {
    assert.equal(url.origin,"http://127.0.0.1:8765");assert.equal(url.search,"");
    assert.equal(init.mode,"cors");assert.equal(init.credentials,"omit");assert.equal(init.redirect,"error");
    assert.equal(init.cache,"no-store");assert.equal(init.referrerPolicy,"no-referrer");
    assert.ok(new Headers(init.headers).get("Authorization") === "Bearer "+token);
  }
  assert.equal(calls[2]?.init.method,"POST");
  assert.equal(new Headers(calls[2]?.init.headers).get("Content-Type"),"application/json");
});
test("no capability or business request after wrong hash",async()=>{
  broken=true;await assert.rejects(()=>open(token),/^Error: Request failed\.$/);
  assert.equal(calls.length,1);
});
test("stage four refuses all writes and templates before fetch",async()=>{
  const client=await open(token);
  for(let n=9;n<19;n++) await assert.rejects(()=>client.check("c"+n,{}));
  for(const id of ["c3","c5","unknown","/admin/v1/config"]) await assert.rejects(()=>client.read(id));
  await assert.rejects(()=>client.check("c0",{}));
  await assert.rejects(()=>client.check("c8",{value:token}));
  assert.equal(calls.length,1);
});
test("approved fetch does not weaken private vocabulary or reconstruction guard",()=>{
  /** @type {unknown} */ const words=JSON.parse(readFileSync(new URL("../private/vocabulary.json",import.meta.url),"utf8"));
  assert.ok(Array.isArray(words));assert.equal(words.length,193);
  inspectPublic('fetch(new URL("/admin/ui/presentation.json",window.location.origin));',["revision"],true);
  for(const source of ['fetch("/admin/v1/config");','const x="rev"+"ision";','atob("eA==")','localStorage.x=1','document.write("x")']) {
    assert.throws(()=>inspectPublic(source,["revision","/admin/v1/config"],true));
  }
});

test("origin equality gate runs before Authorization or network",async()=>{
  let reads=0;
  Object.defineProperty(window.location,"origin",{configurable:true,get:()=>++reads === 1 ? "http://127.0.0.1:8765" : "http://localhost:8765"});
  try {await assert.rejects(()=>open(token));assert.equal(calls.length,0);}
  finally {Object.defineProperty(window.location,"origin",{configurable:true,value:"http://127.0.0.1:8765"});}
});
