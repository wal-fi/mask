import { test, expect } from "@playwright/test";
import { createServer } from "node:http";
import { once } from "node:events";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { scenario, requireTrue, root } from "./harness.js";
import { responseFor } from "../test/samples.js";

/** @param {string} name */
function engine(name) {if(name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");return name;}

test("component lifecycle on history return and native Chromium BFCache",async({},info)=>{
  await scenario(engine(info.project.name),async(page,_origin,token)=>{
    // A private cache-eligible fixture isolates actual restoration from the
    // production no-store policy. All executable bytes are the built component.
    const server=createServer((request,response)=>{
      const path=request.url;
      if(path === "/away") {response.setHeader("Content-Type","text/html");response.end("<!doctype html><title>Away</title><p>Away</p>");return;}
      const file=path === "/admin/ui" ? "index.html" : path === "/admin/ui/assets/ui.js" ? "ui.js" : path === "/admin/ui/assets/ui.css" ? "ui.css" : path === "/admin/ui/presentation.json" ? "presentation.json" : undefined;
      if(path === "/admin/ui/presentation.json" || path === "/admin/v1/status") {
        if(request.headers.authorization !== "Bearer "+token) {response.writeHead(401);response.end();return;}
        response.setHeader("Content-Type","application/json");response.setHeader("Cache-Control","no-store");
        response.end(path === "/admin/v1/status" ? JSON.stringify(responseFor("c0")) : readFileSync(join(root,"src/maskgw/admin/ui/assets/presentation.json")));return;
      }
      if(!file) {response.writeHead(404);response.end();return;}
      response.setHeader("Content-Type",file === "index.html" ? "text/html; charset=utf-8" : file.endsWith(".js") ? "text/javascript" : "text/css");
      response.setHeader("Cache-Control","private, max-age=60");response.end(readFileSync(join(root,"src/maskgw/admin/ui/assets",file)));
    });
    server.listen(0,"127.0.0.1");await once(server,"listening");
    try {
      const address=server.address();if(!address || typeof address === "string") throw new Error("Fixture failed.");
      const origin="http://127.0.0.1:"+address.port;
      await page.addInitScript(()=>window.addEventListener("pageshow",event=>{document.documentElement.dataset.restored=String(event.persisted);}));
      await page.goto(origin+"/admin/ui");await page.getByLabel("Token",{exact:true}).fill(token);await page.getByRole("button",{name:"Entrar",exact:true}).click();
      await expect.poll(async()=> (await page.getByRole("status").textContent())?.startsWith("Respondendo")).toBe(true);
      if(info.project.name === "chromium") {
        // Playwright 1.63 does not track BFCache navigations. Observe this
        // extra native proof through the browser's supported CDP interface.
        const cdp=await page.context().newCDPSession(page);
        const history=await cdp.send("Page.getNavigationHistory");
        const back=history.entries[history.currentIndex];if(!back)throw new Error("Fixture failed.");
        await page.goto(origin+"/away");await cdp.send("Page.navigateToHistoryEntry",{entryId:back.id});
        await expect.poll(async()=>{
          const result=await cdp.send("Runtime.evaluate",{expression:"document.documentElement.dataset.restored === 'true' && document.querySelectorAll('nav').length === 0 && document.querySelector('input')?.value === '' && document.querySelector('main')?.textContent === 'Acesso localTokenEntrar'",returnByValue:true});
          return result.result.value === true;
        }).toBe(true);
        await cdp.detach();
      } else {
        // The fixed Firefox/WebKit automation disables native BFCache. Test
        // real history return, then the persisted event contract explicitly.
        await page.goto(origin+"/away");await page.goBack();await page.getByLabel("Token",{exact:true}).waitFor();
        await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true})));
        requireTrue(await page.getByRole("navigation").count() === 0);
        requireTrue(await page.getByLabel("Token",{exact:true}).inputValue() === "");
        requireTrue(await page.evaluate(key=>!document.documentElement.textContent?.includes(key),token));
      }
    } finally {server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
  },{MASKGW_BROWSER_READ_ONLY:"1",MASKGW_BROWSER_BFCACHE:"1"});
});

test("pending metadata is cleared before late completion and a new entry",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    let release=()=>{};let held=false;let reads=0;
    const pending=new Promise(resolve=>{release=()=>resolve(undefined);});
    page.on("request",request=>{if(new URL(request.url()).pathname.startsWith("/admin/v1/"))reads++;});
    await page.route("**/admin/ui/presentation.json",async route=>{const response=await route.fetch();held=true;await pending;await route.fulfill({response}).catch(()=>{});});
    await page.goto(origin+"/admin/ui");await page.getByLabel("Token",{exact:true}).fill(token);await page.getByRole("button",{name:"Entrar",exact:true}).click();
    await expect.poll(()=>held).toBe(true);requireTrue(await page.getByLabel("Token",{exact:true}).inputValue() === "");
    requireTrue(await page.getByRole("status").textContent() === "Carregando…");
    await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true})));
    release();await page.unrouteAll({behavior:"wait"});requireTrue(reads === 0);
    await page.getByLabel("Token",{exact:true}).fill(token);await page.getByRole("button",{name:"Entrar",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("status").textContent())?.startsWith("Respondendo")).toBe(true);requireTrue(reads === 1);
  },{MASKGW_BROWSER_READ_ONLY:"1"});
});
