import { test } from "@playwright/test";
import { scenario, requireTrue } from "./harness.js";
import { responseFor } from "../test/samples.js";
/** @param {string} name */
function componentEngine(name) {if(name !== "chromium" && name !== "firefox" && name !== "webkit")throw new Error("Engine refused.");return name;}
/** @param {unknown} value @returns {value is Record<string,unknown>} */
function record(value) {return typeof value === "object" && value !== null && !Array.isArray(value);}
/** @param {number} version */
function fixture(version) {
  const value=responseFor("c1");if(!record(value) || !record(value.config))throw new Error("Fixture failed.");
  value.revision=version;value.adopted=true;value.config.revision=version;return value;
}

for(const kind of ["success","conflict","busy","uncertain","unknown","incompatible","read-failure","repeat-failure"]) test("component coordinator outcome "+kind,async({},info)=>{
  await scenario(componentEngine(info.project.name),async(page,origin,token)=>{
    let writes=0,reads=0;
    /** @type {boolean[]} */ const seen=[];
    await page.route("**/admin/v1/**",async route=>{
      const request=route.request();
      if(request.method() === "GET") {
        reads++;
        if(writes && (kind === "read-failure" || (kind === "repeat-failure" && reads > 2))) {await route.abort("connectionfailed");return;}
        await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(fixture(writes ? 2 : 1))});return;
      }
      writes++;
      /** @type {unknown} */ const payload=JSON.parse(request.postData() ?? "null");
      seen.push(request.method() === "PUT" && new URL(request.url()).pathname === "/admin/v1/database" && request.headers()["content-type"] === "application/json" && record(payload)
        && Object.keys(payload).sort().join(",") === "expected_revision,max_rows,statement_timeout_ms" && payload.expected_revision === 1 && payload.statement_timeout_ms === 100 && payload.max_rows === 1);
      const outcome=["conflict","repeat-failure"].includes(kind) ? {error:"REVISION_CONFLICT",detail:"<img src=x onerror=alert(1)>",current_revision:2}
        : kind === "busy" ? {error:"RELOAD_BUSY",detail:"private",current_revision:1}
        : kind === "uncertain" ? {error:"CONFIG_DURABILITY_ERROR",detail:"private",current_revision:2,applied:true}
        : kind === "unknown" ? {error:"INTERNAL_ERROR",detail:"private"}
        : kind === "incompatible" ? {error:"CONFIG_OUT_OF_SYNC",detail:"private",current_revision:1}
        : {revision:2,applied:true};
      await route.fulfill({status:["conflict","repeat-failure","busy","incompatible"].includes(kind) ? 409 : ["uncertain","unknown"].includes(kind) ? 500 : 200,contentType:"application/json",body:JSON.stringify(outcome)});
    });
    await page.goto(origin+"/admin/ui");
    const result=await page.evaluate(async({key,kind})=>{
      const module=await import("/admin/ui/assets/ui.js");
      const client=await module.open(key), flow=module.coordinate(client,"c1");
      await flow.load();flow.begin("c17",{statement_timeout_ms:100,max_rows:1});
      const before=flow.getState();const sending=flow.confirm();const blocked=await flow.confirm() === false;
      await sending;
      if(kind === "repeat-failure") await flow.reconcile();
      const after=flow.getState();
      const expected=kind === "read-failure" ? "success" : kind === "repeat-failure" ? "conflict" : kind;
      const ok=after.tag === expected && blocked && before.tag === "draft" && (after.tag === "success" || after.tag === "conflict" || after.tag === "busy" || after.tag === "uncertain" || after.tag === "unknown" || after.tag === "incompatible")
        && JSON.stringify(after.edit?.draft) === JSON.stringify(before.edit.draft) && !JSON.stringify(after).includes(key)
        && (kind !== "read-failure" || (after.tag === "success" && after.newBase === undefined && after.message === "Salva; visualização ainda não atualizada."))
        && (kind !== "repeat-failure" || (after.tag === "conflict" && after.newBase === undefined && !flow.review({statement_timeout_ms:200,max_rows:1})));
      const noWriteControl=document.querySelectorAll("button").length === 1 && document.querySelectorAll("input").length === 1;
      flow.close();return ok && noWriteControl && flow.getState().tag === "authentication";
    },{key:token,kind});
    requireTrue(result,"component-outcome");requireTrue(writes === 1,"single-command");requireTrue(seen.every(Boolean),"closed-body");requireTrue(reads === (["busy","incompatible"].includes(kind) ? 1 : kind === "repeat-failure" ? 3 : 2),"readback-count");
    requireTrue(await page.getByRole("button",{name:"Entrar",exact:true}).count() === 1);
  },{MASKGW_BROWSER_READ_ONLY:"1"});
});

for(const action of ["cancel","pagehide","pageshow","401"]) test("component pending cleanup "+action,async({},info)=>{
  await scenario(componentEngine(info.project.name),async(page,origin,token)=>{
    await page.goto(origin+"/admin/ui");
    const value=fixture(1);
    // Fetch control is private to this evaluation. The actual ESM coordinator
    // and transport run in the engine; no write reaches the real backend.
    const result=await page.evaluate(async({key,value,action})=>{
      const module=await import("/admin/ui/assets/ui.js");const client=await module.open(key), flow=module.coordinate(client,"c1");
      const native=window.fetch;let release=()=>{};let writes=0;
      const gate=new Promise(resolve=>{release=()=>resolve(undefined);});
      window.fetch=async(_input,init)=>{
        if(init?.method === "GET")return new Response(JSON.stringify(value),{headers:{"Content-Type":"application/json"}});
        writes++;await gate;return new Response('{"revision":2,"applied":true}',{headers:{"Content-Type":"application/json"}});
      };
      try {
        await flow.load();flow.begin("c17",{statement_timeout_ms:100,max_rows:1});const pending=flow.confirm();
        if(action === "cancel") flow.cancel();
        else if(action === "401") {window.fetch=async()=>new Response("",{status:401});await client.read("c1").catch(()=>{});}
        else window.dispatchEvent(new PageTransitionEvent(action,{persisted:true}));
        const expected=action === "cancel" ? "unknown" : "authentication";
        const before=JSON.stringify(flow.getState());release();await pending;
        return flow.getState().tag === expected && JSON.stringify(flow.getState()) === before && writes === 1 && !before.includes(key);
      } finally {release();flow.close();window.fetch=native;}
    },{key:token,value,action});
    requireTrue(result);requireTrue(await page.getByRole("navigation").count() === 0);
  },{MASKGW_BROWSER_READ_ONLY:"1"});
});
