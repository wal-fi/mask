import { replies } from "./replies.js";
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
  const started=performance.now();
  /** @param {string} step */
  const mark=step=>test.info().annotations.push({type:"check",description:"harness-"+step+"-ms-"+Math.round(performance.now()-started)});
  mark("launch");
  const token = randomBytes(32).toString("hex");
  const browser = await engines[name].launch(name === "chromium" && extra.MASKGW_BROWSER_BFCACHE === "1" ? {channel:"chromium",ignoreDefaultArgs:["--disable-back-forward-cache"]} : {});
  mark("launched");
  const child = spawn(join(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python"),
    ["-u", "-m", extra.MASKGW_BROWSER_EDIT === "1" ? "tests.browser_edit_server" : "tests.browser_server"], {cwd:root, env:{...process.env,...extra,MASKGW_BROWSER_TOKEN:token}, stdio:["pipe","pipe","pipe"]});
  const channel=replies(child.stdout);
  child.once("error",()=>channel.close());
  let stderrText = "";
  child.stderr.on("data", data => { stderrText += String(data); });
  let failed = false;
  let stage = "port";
  try {
    const port=await channel.read();requireTrue(/^[0-9]+$/.test(port));
    mark("port");
    stage = "version";
    requireTrue(browser.version() === expected[name]);
    writeFileSync(join(tmpdir(), "maskgw-browser-version-"+name+".json"), JSON.stringify({name,version:browser.version()}));
    const context = await browser.newContext();
    const page = await context.newPage();
    mark("page");
    stage = "action";
    /** @param {string} value */
    async function command(value) {
      child.stdin.write(value+"\n");
      requireTrue(await channel.read() === "ok");
    }
    await action(page, "http://127.0.0.1:"+port, token, command);
    mark("acted");
  } catch (error) {
    mark("caught");
    failed = true;
    if(error instanceof Error) {
      for(const found of (error.stack ?? "").matchAll(/[\\/](?:reading|lifecycle|editing|batches)\.spec\.js:(\d+):\d+/g)) {
        if(found[1]) test.info().annotations.push({type:"check",description:"source-line-"+found[1]});
      }
    }
  }
  finally {
    // Close all contexts before the runner's automatic failure snapshots.
    test.info().annotations.push({type:"check",description:"harness-closing-browser"});
    mark("closing");
    await browser.close();
    mark("closed");
    test.info().annotations.push({type:"check",description:"harness-browser-closed"});
    const finished = child.exitCode === null ? once(child,"exit") : Promise.resolve([child.exitCode]);
    child.stdin.end("stop\n");
    test.info().annotations.push({type:"check",description:"harness-stopping-child"});
    const result = await finished;channel.close();
    test.info().annotations.push({type:"check",description:"harness-child-stopped"});
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
