import { test, expect } from "@playwright/test";
import { at, entry, reader } from "../src/reader.js";
import { book } from "../test/samples.js";
import { scenario, requireTrue } from "./harness.js";

/** @param {string} name */
function engine(name) { if(name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");return name; }
/** @param {import("@playwright/test").Page} page */
async function ready(page) {await expect.poll(async()=> (await page.getByRole("status").textContent())?.startsWith("Respondendo")).toBe(true);}
/** @param {import("@playwright/test").Page} page @param {string} token */
async function enter(page,token) {
  await page.getByLabel("Token",{exact:true}).fill(token);
  await page.getByRole("button",{name:"Entrar",exact:true}).click();
  await ready(page);
}
/** @param {import("@playwright/test").Page} page @param {string} token */
async function clean(page,token) {
  requireTrue(await page.evaluate(async key=>{
    const fields=Array.from(document.querySelectorAll("input"));
    const attrs=Array.from(document.querySelectorAll("*")).flatMap(e=>Array.from(e.attributes).map(a=>a.value));
    return !document.documentElement.textContent?.includes(key) && fields.every(f=>f.value === "")
      && !attrs.some(a=>a.includes(key)) && !location.href.includes(key) && history.state === null
      && localStorage.length===0 && sessionStorage.length===0 && document.cookie===""
      && (await caches.keys()).length===0
      && !Object.values(Object.getOwnPropertyDescriptors(window)).some(d=>typeof d.value === "string" && d.value.includes(key));
  },token));
}
const readonly={MASKGW_BROWSER_READ_ONLY:"1"};

test("read-only entry, six views, keyboard and logout without effects",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    /** @type {string[]} */ const calls=[];
    let leak=false;
    page.on("request",r=>{const url=new URL(r.url());if(url.pathname.startsWith("/admin/v1/")){calls.push(r.method());if(r.method()!=="GET")leak=true;}if(url.href.includes(token)||r.postData()?.includes(token))leak=true;});
    page.on("console",m=>{if(m.text().includes(token))leak=true;});
    await page.goto(origin+"/admin/ui");requireTrue(calls.length===0);
    await page.getByLabel("Token",{exact:true}).fill(token);
    await page.keyboard.press("Tab");await page.keyboard.press("Enter");await ready(page);await clean(page,token);
    const views=["Visão geral","Configuração","Regras","Exceções","Banco","Política SQL"];
    requireTrue(await page.getByRole("navigation").getByRole("button").count()===6);
    for(const label of ["Atualizar",...views.slice().reverse(),"Sair"]) {
      await page.keyboard.press("Shift+Tab");
      requireTrue(await page.getByRole("button",{name:label,exact:true}).evaluate(e=>e===document.activeElement));
    }
    for(const label of views) {
      await page.keyboard.press("Tab");
      requireTrue(await page.getByRole("button",{name:label,exact:true}).evaluate(e=>e===document.activeElement));
    }
    for(const label of views) {
      const button=page.getByRole("button",{name:label,exact:true});await button.focus();await page.keyboard.press("Enter");await ready(page);
      requireTrue(await page.getByRole("heading",{name:label,exact:true}).evaluate(e=>e===document.activeElement));
      requireTrue(page.url()===origin+"/admin/ui");await clean(page,token);
    }
    await page.getByRole("button",{name:"Sair",exact:true}).focus();await page.keyboard.press("Enter");
    requireTrue(await page.getByLabel("Token",{exact:true}).evaluate(e=>e===document.activeElement));
    requireTrue(await page.getByRole("navigation").count()===0 && !leak && calls.every(v=>v==="GET"));await clean(page,token);
  },readonly);
});

test("failed entry clears field and never exposes response details",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.goto(origin+"/admin/ui");await page.getByLabel("Token",{exact:true}).fill(token+"wrong");
    await page.getByRole("button",{name:"Entrar",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("status").textContent())?.startsWith("Autenticação necessária")).toBe(true);
    await clean(page,token);requireTrue(await page.getByRole("navigation").count()===0);
  },readonly);
});

for(const event of ["pagehide","pageshow","logout"]) test("late read cannot restore after "+event,async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.goto(origin+"/admin/ui");await enter(page,token);
    let release=()=>{};
    let intercepted=false;
    const held=new Promise(resolve=>{release=()=>resolve(undefined);});
    await page.route("**/admin/v1/rules",async route=>{const response=await route.fetch();intercepted=true;await held;await route.fulfill({response}).catch(()=>{});});
    await page.getByRole("button",{name:"Regras",exact:true}).click();await expect.poll(()=>intercepted).toBe(true);
    if(event === "logout") await page.getByRole("button",{name:"Sair",exact:true}).click();
    else await page.evaluate(event=>window.dispatchEvent(new PageTransitionEvent(event,{persisted:true})),event);
    requireTrue(await page.getByRole("navigation").count()===0);await clean(page,token);release();
    await page.unrouteAll({behavior:"wait"});await enter(page,token);await ready(page);await clean(page,token);
    requireTrue(await page.getByRole("heading",{name:"Visão geral",exact:true}).count()===1);
  },readonly);
});

test("401 clears private state immediately and reload demands entry",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.goto(origin+"/admin/ui");await enter(page,token);
    await page.route("**/admin/v1/rules",r=>r.fulfill({status:401,contentType:"application/json",body:JSON.stringify({detail:token})}));
    await page.getByRole("button",{name:"Regras",exact:true}).click();await page.getByLabel("Token",{exact:true}).waitFor();
    await clean(page,token);requireTrue(await page.getByRole("navigation").count()===0);
    await page.unrouteAll();await enter(page,token);await page.reload();await page.getByLabel("Token",{exact:true}).waitFor();await clean(page,token);
  },readonly);
});

test("loading, empty, sanitized error and explicit retry",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.goto(origin+"/admin/ui");await enter(page,token);
    await page.route("**/admin/v1/rules",r=>r.fulfill({status:500,contentType:"text/plain",body:token+"<script>"}));
    await page.getByRole("button",{name:"Regras",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("status").textContent())?.includes("indisponível")).toBe(true);
    await clean(page,token);await page.unrouteAll();await page.getByRole("button",{name:"Atualizar",exact:true}).click();await ready(page);
    requireTrue(await page.getByText("Lista vazia.",{exact:true}).count()===1);
  },readonly);
});

for(const fault of ["unsafe","shape","incoherent"]) test("component refuses response "+fault,async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.route("**/admin/v1/status",async route=>{
      const response=await route.fetch();
      /** @type {unknown} */ const data=await response.json();
      if(!entry(data) || !entry(data.runtime)) throw new Error("Fixture failed.");
      if(fault==="unsafe") data.revision=9007199254740992;
      if(fault==="shape") data.extra="hostile";
      if(fault==="incoherent") data.runtime.revision=1;
      await route.fulfill({response,json:data});
    });
    await page.goto(origin+"/admin/ui");await page.getByLabel("Token",{exact:true}).fill(token);await page.getByRole("button",{name:"Entrar",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("status").textContent())?.includes("indisponível")).toBe(true);
    requireTrue(await page.getByRole("heading",{level:3}).count()===0);await clean(page,token);
  },readonly);
});

test("stored hostile values remain text across new sessions",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    let external=false;
    page.on("request",r=>{if(new URL(r.url()).origin!==origin)external=true;});
    for(let round=0;round<2;round++) {
      await page.goto(origin+"/admin/ui");await enter(page,token);
      for(const label of ["Configuração","Regras","Exceções"]) {
        await page.getByRole("button",{name:label,exact:true}).click();await ready(page);
        requireTrue(await page.getByRole("region",{name:"Leitura"}).evaluate(e=>e.textContent?.includes("<img src=x") && e.querySelectorAll("img,svg,a,script").length===0));
      }
      requireTrue(await page.evaluate(()=>document.documentElement.dataset.compromised===undefined) && !external);await clean(page,token);
      await page.getByRole("button",{name:"Sair",exact:true}).click();await clean(page,token);
    }
  },{...readonly,MASKGW_BROWSER_HOSTILE:"1"});
});

test("responsive reading at 320px, 200 percent and reduced motion",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.setViewportSize({width:320,height:800});await page.emulateMedia({reducedMotion:"reduce"});
    await page.goto(origin+"/admin/ui");await enter(page,token);
    for(const label of ["Configuração","Regras","Exceções","Banco","Política SQL"]) {
      await page.getByRole("button",{name:label,exact:true}).click();await ready(page);
      requireTrue(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    // CSS zoom is injected by the private harness, never an application style.
    await page.evaluate(()=>{document.documentElement.style.zoom="2";});
    requireTrue(await page.evaluate(()=>getComputedStyle(document.documentElement).zoom==="2"));
    requireTrue(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.getByRole("button",{name:"Sair",exact:true}).focus();await page.keyboard.press("Enter");await clean(page,token);
    requireTrue(await page.getByLabel("Token",{exact:true}).evaluate(e=>getComputedStyle(e).animationName==="none"));
  },{...readonly,MASKGW_BROWSER_HOSTILE:"1"});
});

test("PostgreSQL disconnect preserves reads; API loss suspends polling",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await page.goto(origin+"/admin/ui");await enter(page,token);await command("disconnect");
    await page.getByRole("button",{name:"Configuração",exact:true}).click();await ready(page);
    await command("stop-api");await page.getByRole("button",{name:"Atualizar",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("status").textContent())?.includes("desatualizada")).toBe(true);
    await clean(page,token);await page.getByRole("button",{name:"Sair",exact:true}).click();await clean(page,token);
  },readonly);
});

test("polling is visible-only, serial and stops after failure",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.clock.install();let reads=0;
    page.on("request",r=>{if(new URL(r.url()).pathname==="/admin/v1/status") reads++;});
    await page.goto(origin+"/admin/ui");await enter(page,token);requireTrue(reads===1);
    await page.clock.runFor(15000);await expect.poll(()=>reads).toBe(2);await expect(page.getByRole("button",{name:"Atualizar",exact:true})).toBeEnabled();await ready(page);
    let held=false;let release=()=>{};
    const pending=new Promise(resolve=>{release=()=>resolve(undefined);});
    await page.route("**/admin/v1/status",async route=>{const response=await route.fetch();held=true;await pending;await route.fulfill({response}).catch(()=>{});});
    await page.clock.runFor(15000);await expect.poll(()=>held).toBe(true);await page.clock.runFor(20000);requireTrue(reads===3);release();await page.unrouteAll({behavior:"wait"});await expect(page.getByRole("button",{name:"Atualizar",exact:true})).toBeEnabled();await ready(page);
    await page.route("**/admin/v1/status",r=>r.fulfill({status:503,body:"unavailable"}));
    await page.clock.runFor(15000);await expect.poll(async()=> (await page.getByRole("status").textContent())?.includes("desatualizada")).toBe(true);
    const failed=reads;await page.clock.runFor(60000);requireTrue(reads===failed);
    await page.unrouteAll();await page.getByRole("button",{name:"Atualizar",exact:true}).click();await ready(page);
    const resumed=reads;
    await page.evaluate(()=>{Object.defineProperty(document,"visibilityState",{configurable:true,get:()=>"hidden"});document.dispatchEvent(new Event("visibilitychange"));});
    await page.clock.runFor(60000);requireTrue(reads===resumed);
    await page.evaluate(()=>{Object.defineProperty(document,"visibilityState",{configurable:true,get:()=>"visible"});document.dispatchEvent(new Event("visibilitychange"));});
    await page.clock.runFor(15000);await expect.poll(()=>reads).toBe(resumed+1);await ready(page);
    await page.getByRole("button",{name:"Sair",exact:true}).click();const closed=reads;await page.clock.runFor(60000);requireTrue(reads===closed);await clean(page,token);
  },readonly);
});

test("different snapshots are discarded instead of combined",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.clock.install();await page.goto(origin+"/admin/ui");await enter(page,token);
    await page.getByRole("button",{name:"Configuração",exact:true}).click();await ready(page);
    await page.route("**/admin/v1/status",async route=>{const response=await route.fetch();
      /** @type {unknown} */const data=await response.json();if(!entry(data)||!entry(data.runtime))throw new Error("Fixture failed.");
      data.revision=1;data.adopted=true;data.runtime.revision=1;await route.fulfill({response,json:data});});
    await page.clock.runFor(15000);await expect.poll(async()=> (await page.getByRole("status").textContent())?.includes("desatualizada")).toBe(true);
    requireTrue(await page.getByRole("heading",{level:3}).count()===0);await clean(page,token);
  },readonly);
});

test("history navigation cannot retain private document",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.goto(origin+"/admin/ui");await enter(page,token);await page.goto("about:blank");await page.goBack();
    await page.getByLabel("Token",{exact:true}).waitFor();await clean(page,token);
    requireTrue(await page.getByRole("navigation").count()===0 && page.url()===origin+"/admin/ui");
  },readonly);
});

/** @param {unknown} value @param {(string | number)[]} path @returns {(string | number)[][]} */
function textPaths(value,path=[]) {
  if(typeof value === "string")return [path];
  if(Array.isArray(value))return value.flatMap((v,i)=>textPaths(v,[...path,i]));
  if(entry(value))return Object.entries(value).flatMap(([k,v])=>textPaths(v,[...path,k]));
  return [];
}

test("every displayed string rejects or renders hostile reflection as text",async({},info)=>{
  test.setTimeout(180000);
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    const lens=reader(book);
    const hostile='<img src=x onerror="document.documentElement.dataset.compromised=1">';
    let outside=false;page.on("request",r=>{if(new URL(r.url()).origin!==origin)outside=true;});
    await page.goto(origin+"/admin/ui");await enter(page,token);
    const targets=[
      ["Visão geral","c0","status"],["Configuração","c1","config"],
      ["Regras","c2","rules"],["Exceções","c4","exceptions"],
      ["Banco","c1","config"],["Política SQL","c7","protected"],
    ];
    let checked=0;
    for(const target of targets) {
      const [label,id,path]=target;if(!label || !id || !path)throw new Error("Fixture failed.");
      const response=await page.request.get(origin+"/admin/v1/"+path,{headers:{Authorization:"Bearer "+token}});
      /** @type {unknown} */const data=await response.json();
      lens.inspectDataFor(id,data);
      for(const parts of textPaths(data)) {
        const value=structuredClone(data),parent=at(value,parts.slice(0,-1)),key=parts.at(-1);
        if(Array.isArray(parent) && typeof key === "number")parent[key]=hostile;
        else if(entry(parent) && typeof key === "string")parent[key]=hostile;
        else throw new Error("Fixture failed.");
        let accepted=true;try {lens.inspectDataFor(id,value);} catch {accepted=false;}
        await page.route("**/admin/v1/"+path,r=>r.fulfill({status:200,contentType:"application/json",json:value}));
        await page.getByRole("button",{name:label,exact:true}).dispatchEvent("click");
        if(accepted) {
          await ready(page);
          // Some source fields are deliberately outside the selected view.
          requireTrue(await page.getByRole("region",{name:"Leitura"}).evaluate(e=>e.querySelectorAll("img,svg,a,script").length === 0));
        } else {
          await expect.poll(async()=> (await page.getByRole("status").textContent())?.includes("indisponível")).toBe(true);
          requireTrue(await page.getByRole("heading",{level:3}).count() === 0);
        }
        requireTrue(await page.evaluate(()=>document.documentElement.dataset.compromised === undefined) && !outside);
        await clean(page,token);await page.unrouteAll();checked++;
      }
    }
    requireTrue(checked > 50);
  },{...readonly,MASKGW_BROWSER_HOSTILE:"1"});
});
