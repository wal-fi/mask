import { test, chromium, firefox, webkit } from "@playwright/test";
import { spawn } from "node:child_process";
import { randomBytes, createHash } from "node:crypto";
import { once } from "node:events";
import { createServer } from "node:http";
import { readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const engines = {chromium, firefox, webkit};
const expected = {chromium:"153.0.8010.12",firefox:"155.0",webkit:"26.6"};
/** @param {unknown} condition @param {string} label */
function requireTrue(condition, label="assertion") {
  if (!condition) { test.info().annotations.push({type:"check",description:label}); throw new Error("Browser assertion failed."); }
}

/** No reporter receives captured requests, token or administrative values.
 * @param {keyof typeof engines} name
 * @param {(page:import("@playwright/test").Page, origin:string, token:string) => Promise<void>} action
 * @param {Record<string,string>} extra
 */
async function scenario(name, action, extra={}) {
  if (!process.env.MASKGW_TEST_DSN) throw new Error("PostgreSQL gate requires DSN.");
  const token = randomBytes(32).toString("hex");
  const browser = await engines[name].launch();
  const child = spawn(join(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python"),
    ["-u", "-m", "tests.browser_server"], {cwd:root, env:{...process.env,...extra,MASKGW_BROWSER_TOKEN:token}, stdio:["pipe","pipe","pipe"]});
  let stderrText = "";
  child.stderr.on("data", data => { stderrText += String(data); });
  let failed = false;
  let stage = "port";
  try {
    const port = await new Promise((resolve, reject) => {
      child.stdout.once("data", data => { const value=String(data).trim(); if (/^[0-9]+$/.test(value)) resolve(value); else reject(new Error("Harness failed.")); });
      child.once("exit", () => reject(new Error("Harness exited.")));
    });
    stage = "version";
    requireTrue(browser.version() === expected[name]);
    writeFileSync(join(tmpdir(), "maskgw-browser-version-"+name+".json"), JSON.stringify({name,version:browser.version()}));
    const context = await browser.newContext();
    const page = await context.newPage();
    stage = "action";
    await action(page, "http://127.0.0.1:"+port, token);
  } catch { failed = true; }
  finally {
    // Close all contexts before the runner's automatic failure snapshots.
    await browser.close();
    const finished = child.exitCode === null ? once(child,"exit") : Promise.resolve([child.exitCode]);
    child.stdin.end("stop\n");
    const result = await finished;
    if (result[0] !== 0) { failed = true; stage = "exit"; }
    if (stderrText) {

      failed = true;
      stage = ["Browser harness failed."].filter(v=>stderrText.includes(v)).join("|") || "other";
    }
  }
  if (failed) test.info().annotations.push({type:"gate",description:stage});
  requireTrue(!failed);
}

test.describe("transport", () => {
    test("exact fetch and no effects", async ({}, info) => {
      const name = info.project.name;
      if (name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");
      await scenario(name, async (page, origin, token) => {
        /** @type {{path:string,method:string,auth:boolean,origin:string|null,referer:boolean}[]} */ const seen=[];
        let leaked=false;
        /** @type {Promise<void>[]} */ const observations=[];
        page.on("request", request => {
          observations.push((async()=>{
          const url = new URL(request.url()); const headers=await request.allHeaders();
          if (url.href.includes(token) || (request.postData() ?? "").includes(token)) leaked=true;
          if (headers.authorization && (url.origin !== origin || headers.authorization !== "Bearer "+token)) leaked=true;
          seen.push({path:url.pathname,method:request.method(),auth:headers.authorization === "Bearer "+token,origin:headers.origin ?? null,referer:!!headers.referer});
          })());
        });
        page.on("console", message => {if(message.text().includes(token)) leaked=true;});
        await page.goto(origin+"/admin/ui");
        requireTrue(!seen.some(r=>r.path.startsWith("/admin/v1/") || r.auth));
        const ok = await page.evaluate(async secret => {
          try {
            const api = await import("/admin/ui/assets/ui.js");
            const client = await api.open(secret);
            await client.read("c0");
            await client.check("c8", {masking:[],exceptions:[]});
            try { await client.check("c9", {}); return false; } catch {}
            return localStorage.length === 0 && sessionStorage.length === 0 && document.cookie === "";
          } catch { return false; }
        }, token);
        await Promise.all(observations);
        requireTrue(ok && !leaked,"roundtrip");
        const calls=seen.filter(r=>r.auth);
        requireTrue(calls.length===3 && calls[0]?.path === "/admin/ui/presentation.json" && calls[1]?.method === "GET","three-calls");
        requireTrue(calls[2]?.path === "/admin/v1/config:validate" && calls[2]?.origin === origin && !calls[2]?.referer,"post-origin");
        requireTrue(!seen.some(r=>r.method === "OPTIONS"));
      });
    });

    for (const target of ["same", "external"]) test("real redirect refuses bearer forwarding "+target, async ({}, info) => {
      const name=info.project.name;
      if(name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");
      let received=0;
      const sink=createServer((_request,response)=>{received++;response.end();});
      await new Promise(resolve=>sink.listen(0,"127.0.0.1",()=>resolve(undefined)));
      const address=sink.address();
      if(!address || typeof address === "string") throw new Error("Harness failed.");
      const endpoint="http://127.0.0.1:"+address.port+"/sink";
      try {
        await fetch(endpoint);requireTrue(received===1,"sink-control");received=0;
        await scenario(name,async(page,origin,token)=>{
          let forwarded=false;
          page.on("request",r=>{if(new URL(r.url()).pathname === "/sink") forwarded=true;});
          await page.goto(origin+"/admin/ui");
          const refused=await page.evaluate(async secret=>{try{await(await import("/admin/ui/assets/ui.js")).open(secret);return false;}catch{return true;}},token);
          requireTrue(refused && !forwarded && received===0,"redirect");
        },{MASKGW_BROWSER_REDIRECT:target === "same" ? "/sink" : endpoint});
      } finally {await new Promise(resolve=>sink.close(()=>resolve(undefined)));}
    });

    for (const damage of ["hash","metadata"]) test("bad "+damage+" blocks business", async ({}, info) => {
      const name = info.project.name;
      if (name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");
      await scenario(name, async (page, origin, token) => {
        let business=0, presentation=0;
        page.on("request", r=>{const path=new URL(r.url()).pathname;if(path.startsWith("/admin/v1/")) business++;if(path === "/admin/ui/presentation.json") presentation++;});
        const original=readFileSync(join(root,"src/maskgw/admin/ui/assets/presentation.json"));
        const bad=Buffer.from('{"format":2}');
        await page.route("**/admin/ui/presentation.json", route=>route.fulfill({status:200,contentType:"application/json",body:bad}));
        if(damage === "metadata") {
          const js=readFileSync(join(root,"src/maskgw/admin/ui/assets/ui.js"),"utf8")
            .replace(createHash("sha256").update(original).digest("hex"),createHash("sha256").update(bad).digest("hex"));
          await page.route("**/admin/ui/assets/ui.js", route=>route.fulfill({status:200,contentType:"text/javascript",body:js}));
        }
        await page.goto(origin+"/admin/ui");
        const refused=await page.evaluate(async secret=>{try{const c=await(await import("/admin/ui/assets/ui.js")).open(secret);await c.read("c0");return false;}catch{return true;}},token);
        requireTrue(refused && business===0 && presentation===1);
      });
    });

    test("external browser CSRF cannot send bearer or mutate", async ({}, info) => {
      const name=info.project.name;
      if(name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");
      const foreign=createServer((_request,response)=>{response.setHeader("Content-Type","text/html");response.end("<!doctype html><title>Harness</title>");});
      await new Promise(resolve=>foreign.listen(0,"127.0.0.1",()=>resolve(undefined)));
      const address=foreign.address();
      if(!address || typeof address === "string") throw new Error("Harness failed.");
      try {
        await scenario(name,async(page,origin,token)=>{
          await page.goto("http://127.0.0.1:"+address.port);
          const refused=await page.evaluate(async ({origin,token})=>{
            try {await fetch(origin+"/admin/v1/config:validate",{method:"POST",mode:"cors",credentials:"omit",headers:{Authorization:"Bearer "+token,"Content-Type":"application/json"},body:JSON.stringify({masking:[],exceptions:[]})});return false;}catch{return true;}
          },{origin,token});
          requireTrue(refused,"csrf-cors");
          // Form-compatible media type: no ambient credential and no mutation.
          const status=await page.evaluate(async origin=>{
            try {const response=await fetch(origin+"/admin/v1/config:validate",{method:"POST",mode:"no-cors",credentials:"omit",body:"x=1"});return response.type;}catch{return "blocked";}
          },origin);
          requireTrue(status === "opaque" || status === "blocked","csrf-form");
        },{MASKGW_BROWSER_CSRF:"1"});
      } finally {await new Promise(resolve=>foreign.close(()=>resolve(undefined)));}
    });

    test("CSP blocks inline execution with positive detector control", async ({}, info) => {
      const name=info.project.name;
      if(name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");
      await scenario(name,async(page,origin)=>{
        await page.route("**/control",route=>route.fulfill({contentType:"text/html",body:"<!doctype html><title>Control</title>"}));
        /** @returns {boolean} */
        function inject() {
          const script=document.createElement("script");
          script.textContent="document.documentElement.dataset.executed='yes'";
          document.head.append(script);
          return document.documentElement.dataset.executed === "yes";
        }
        await page.goto(origin+"/control");requireTrue(await page.evaluate(inject));
        await page.goto(origin+"/admin/ui");requireTrue(!await page.evaluate(inject));
      });
    });
});
