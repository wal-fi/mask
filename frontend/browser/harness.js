import { test, chromium, firefox, webkit } from "@playwright/test";
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { once } from "node:events";
import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export const root = fileURLToPath(new URL("../../", import.meta.url));
const engines = {chromium, firefox, webkit};
const expected = {chromium:"153.0.8010.12",firefox:"155.0",webkit:"26.6"};
/** @param {unknown} condition @param {string} label */
export function requireTrue(condition, label="assertion") {
  if (!condition) { test.info().annotations.push({type:"check",description:label}); throw new Error("Browser assertion failed."); }
}

/** No reporter receives captured requests, token or administrative values.
 * @param {keyof typeof engines} name
 * @param {(page:import("@playwright/test").Page, origin:string, token:string, command:(value:string)=>Promise<void>) => Promise<void>} action
 * @param {Record<string,string>} extra
 */
export async function scenario(name, action, extra={}) {
  if (!process.env.MASKGW_TEST_DSN) throw new Error("PostgreSQL gate requires DSN.");
  const token = randomBytes(32).toString("hex");
  const browser = await engines[name].launch(name === "chromium" && extra.MASKGW_BROWSER_BFCACHE === "1" ? {channel:"chromium",ignoreDefaultArgs:["--disable-back-forward-cache"]} : {});
  const child = spawn(join(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python"),
    ["-u", "-m", extra.MASKGW_BROWSER_EDIT === "1" ? "tests.browser_edit_server" : "tests.browser_server"], {cwd:root, env:{...process.env,...extra,MASKGW_BROWSER_TOKEN:token}, stdio:["pipe","pipe","pipe"]});
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
    /** @param {string} value */
    async function command(value) {
      const answer=new Promise((resolve,reject)=>{
        /** @param {Buffer} data */ const got=data=>{cleanup();resolve(data);};
        const exited=()=>{cleanup();reject(new Error("Harness exited."));};
        const cleanup=()=>{child.stdout.removeListener("data",got);child.removeListener("exit",exited);};
        child.stdout.once("data",got);child.once("exit",exited);
      });child.stdin.write(value+"\n");
      const data=await answer;requireTrue(String(data).trim() === "ok");
    }
    await action(page, "http://127.0.0.1:"+port, token, command);
  } catch (error) {
    failed = true;
    if(error instanceof Error) {
      for(const found of (error.stack ?? "").matchAll(/[\\/](?:reading|lifecycle|editing)\.spec\.js:(\d+):\d+/g)) {
        if(found[1]) test.info().annotations.push({type:"check",description:"source-line-"+found[1]});
      }
    }
  }
  finally {
    // Close all contexts before the runner's automatic failure snapshots.
    await browser.close();
    const finished = child.exitCode === null ? once(child,"exit") : Promise.resolve([child.exitCode]);
    child.stdin.end("stop\n");
    const result = await finished;
    if (result[0] !== 0) { failed = true; stage = "exit"; }
    if (stderrText) {
      for(const found of stderrText.matchAll(/check-line-([0-9]+)/g)) test.info().annotations.push({type:"check",description:"source-line-"+found[1]});
      failed = true;
      stage = ["Browser harness failed."].filter(v=>stderrText.includes(v)).join("|") || "other";
    }
  }
  if (failed) test.info().annotations.push({type:"gate",description:stage});
  requireTrue(!failed);
}
