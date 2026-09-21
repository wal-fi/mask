import { test, expect } from "@playwright/test";
import { scenario, requireTrue } from "./harness.js";
/** @param {string} name */
function engine(name) {if(name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");return name;}
/** @param {import("@playwright/test").Page} page @param {string} origin @param {string} token */
async function enter(page,origin,token) {await page.goto(origin+"/admin/ui");await page.getByLabel("Token",{exact:true}).fill(token);await page.getByRole("button",{name:"Entrar",exact:true}).click();await ready(page);}
/** @param {import("@playwright/test").Page} page */
async function ready(page) {await expect.poll(async()=> (await page.getByRole("status").first().textContent())?.startsWith("Respondendo")).toBe(true);}
/** @param {import("@playwright/test").Page} page @param {string} name */
async function navigate(page,name) {await page.getByRole("navigation").getByRole("button",{name,exact:true}).click();await ready(page);}
/** @param {import("@playwright/test").Page} page */
async function finish(page) {await page.getByRole("dialog").getByRole("button",{name:"Concluir",exact:true}).click();await ready(page);}
/** @param {import("@playwright/test").Page} page */
async function adopt(page) {await navigate(page,"Configuração");await page.getByRole("button",{name:"Adoção explícita",exact:true}).click();await page.getByLabel("Li e compreendi as consequências").check();await page.getByRole("button",{name:"Adotar configuração",exact:true}).click();await finish(page);}
/** @param {import("@playwright/test").Page} page @param {string} match @param {string} value */
async function createRule(page,match,value) {
  await navigate(page,"Regras");await page.getByRole("button",{name:"Criar",exact:true}).click();
  await page.getByLabel("match",{exact:true}).fill(match);
  requireTrue(await page.getByLabel("mode",{exact:true}).inputValue()==="contains");
  requireTrue(!await page.getByLabel("case_sensitive",{exact:true}).isChecked());
  await page.getByLabel("transformer",{exact:true}).selectOption("fixed");await page.getByLabel("value",{exact:true}).fill(value);
  await page.getByRole("button",{name:"Salvar",exact:true}).click();await finish(page);
}
const mutable={MASKGW_BROWSER_EDIT:"1"};
/** @param {import("@playwright/test").Page} page @param {string} value */
async function draft(page,value="masked") {
  await navigate(page,"Regras");await page.getByRole("button",{name:"Criar",exact:true}).click();
  await page.getByLabel("match",{exact:true}).fill("protected_value");await page.getByLabel("transformer",{exact:true}).selectOption("fixed");await page.getByLabel("value",{exact:true}).fill(value);
}
/** @param {import("@playwright/test").Page} page @param {string} text */
async function outcome(page,text) {await expect.poll(async()=> (await page.getByRole("dialog").getByRole("status").textContent())?.includes(text)).toBe(true);}

test("external disk edit after validation blocks writes and preserves draft and runtime",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await draft(page);
    await page.getByRole("button",{name:"Validar proposta",exact:true}).click();await outcome(page,"Conteúdo e compilação válidos");
    await command("external-edit");let writes=0;page.on("request",r=>{if(r.method()!=="GET")writes++;});
    await page.getByRole("button",{name:"Salvar",exact:true}).click();
    await expect(page.getByRole("heading",{name:"Rascunho preservado",exact:true})).toBeVisible();
    requireTrue(writes===1 && (await page.getByRole("dialog").textContent())?.includes("masked"));
    requireTrue(await page.getByRole("button",{name:"Tentar novamente",exact:true}).count()===0);
    requireTrue(await page.getByRole("button",{name:"Revisar rascunho com nova base",exact:true}).count()===0);
    await command("verify:1");await command("backup");
    await page.getByRole("button",{name:"Fechar e descartar rascunho",exact:true}).click();await page.getByRole("button",{name:"Descartar",exact:true}).click();await ready(page);
    requireTrue(await page.getByRole("button",{name:"Criar",exact:true}).isDisabled() && writes===1);
  },mutable);
});

test("real adoption, root validation, granular CRUD, audit, MCP and restart",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    /** @type {{path:string,method:string,body:string|null}[]} */ const requests=[];let leak=false;
    page.on("request",r=>{const path=new URL(r.url()).pathname;if(r.method()!=="GET")requests.push({path,method:r.method(),body:r.postData()});if(r.url().includes(token)||r.postData()?.includes(token))leak=true;});
    page.on("console",m=>{if(m.text().includes(token))leak=true;});
    await enter(page,origin,token);await navigate(page,"Regras");requireTrue(await page.getByRole("button",{name:"Criar",exact:true}).isDisabled());
    await navigate(page,"Configuração");await page.getByRole("button",{name:"Adoção explícita",exact:true}).click();
    requireTrue(!await page.getByLabel("Li e compreendi as consequências").isChecked());requireTrue(await page.getByRole("button",{name:"Adotar configuração",exact:true}).isDisabled());
    await page.getByRole("dialog").getByRole("button",{name:"Cancelar",exact:true}).click();requireTrue(requests.length===0);
    await page.getByRole("button",{name:"Validar documento",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("dialog").getByRole("status").textContent())?.startsWith("Conteúdo e compilação válidos")).toBe(true);
    await page.getByRole("dialog").getByRole("button",{name:"Cancelar",exact:true}).click();await command("verify:0");
    await adopt(page);await command("verify:1");await command("backup");
    await createRule(page,"protected_value","masked");await command("verify:2");await command("masking");
    await page.getByRole("button",{name:"Editar",exact:true}).click();await page.getByLabel("match",{exact:true}).fill("  literal match  ");
    await page.getByRole("button",{name:"Validar proposta",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("dialog").getByRole("status").textContent())?.startsWith("Conteúdo e compilação válidos")).toBe(true);
    await page.getByLabel("match",{exact:true}).fill("  literal match  ");requireTrue((await page.getByRole("dialog").getByRole("status").textContent())?.includes("descartado"));
    await page.getByRole("button",{name:"Salvar",exact:true}).click();await finish(page);await command("verify:3");
    const put=requests.find(r=>r.method==="PUT");requireTrue(put && JSON.parse(put.body ?? "{}").rule.match==="  literal match  ");
    await navigate(page,"Exceções");await page.getByRole("button",{name:"Criar",exact:true}).click();
    requireTrue(await page.getByLabel("mode",{exact:true}).inputValue()==="exact");requireTrue(await page.getByLabel("transformer",{exact:true}).count()===0);
    await page.getByLabel("match",{exact:true}).fill("narrow");await page.getByRole("button",{name:"Salvar",exact:true}).click();
    const before=requests.length;await page.getByRole("button",{name:"Cancelar",exact:true}).click();requireTrue(requests.length===before);
    await page.getByRole("button",{name:"Salvar",exact:true}).click();await page.getByRole("button",{name:"Confirmar",exact:true}).click();await finish(page);await command("verify:4");
    await page.getByRole("button",{name:"Editar",exact:true}).click();await page.getByLabel("mode",{exact:true}).selectOption("contains");
    await page.getByRole("button",{name:"Salvar",exact:true}).click();await page.getByRole("button",{name:"Confirmar",exact:true}).click();await finish(page);await command("verify:5");
    await page.getByRole("button",{name:"Excluir",exact:true}).click();await page.getByRole("dialog").getByRole("button",{name:"Cancelar",exact:true}).click();await command("verify:5");
    await page.getByRole("button",{name:"Excluir",exact:true}).click();await page.getByRole("dialog").getByRole("button",{name:"Excluir",exact:true}).click();await finish(page);await command("verify:6");
    await navigate(page,"Regras");await page.getByRole("button",{name:"Excluir",exact:true}).click();await page.getByRole("dialog").getByRole("button",{name:"Excluir",exact:true}).click();await finish(page);await command("verify:7");await command("restart");
    requireTrue(!leak && requests.every(r=>!r.path.endsWith(":reorder") && !r.path.endsWith("/database") && !r.path.endsWith("/sql") && !(r.method==="PUT" && r.path.endsWith("/config"))));
    await page.reload();requireTrue(await page.getByLabel("Token",{exact:true}).inputValue()==="");
  },mutable);
});

test("two tabs preserve drafts on conflict and never rebase without review",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);const other=await page.context().newPage();await enter(other,origin,token);
    await draft(page,"one");await draft(other,"two");
    await page.getByRole("button",{name:"Salvar",exact:true}).click();await finish(page);await command("verify:2");
    await other.getByRole("button",{name:"Salvar",exact:true}).click();await outcome(other,"mudou");
    requireTrue(await other.getByRole("heading",{name:"Nova base separada",exact:true}).count()===1);
    requireTrue((await other.getByRole("dialog").textContent())?.includes("two"));await command("verify:2");
    await other.getByRole("button",{name:"Revisar rascunho com nova base",exact:true}).click();
    requireTrue(await other.getByLabel("value",{exact:true}).inputValue()==="two");await other.getByRole("button",{name:"Salvar",exact:true}).click();await finish(other);await command("verify:3");
    await other.close();
  },mutable);
});

test("already adopted is reconciled without another adoption",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);const other=await page.context().newPage();await enter(other,origin,token);
    for(const tab of [page,other]) {await navigate(tab,"Configuração");await tab.getByRole("button",{name:"Adoção explícita",exact:true}).click();await tab.getByLabel("Li e compreendi as consequências").check();}
    await page.getByRole("button",{name:"Adotar configuração",exact:true}).click();await finish(page);
    await other.getByRole("button",{name:"Adotar configuração",exact:true}).click();await outcome(other,"já foi adotada");
    requireTrue(await other.getByRole("button",{name:"Tentar novamente",exact:true}).count()===0);await command("verify:1");await command("backup");await other.close();
  },mutable);
});

test("real retired runtime busy admits only a manual attempt",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await command("hold");await createRule(page,"one","masked");
    await draft(page);await page.getByRole("button",{name:"Salvar",exact:true}).click();await outcome(page,"runtime aposentado");await command("verify:2");
    requireTrue(await page.getByRole("button",{name:"Tentar novamente",exact:true}).count()===1);await command("release");
    await page.getByRole("button",{name:"Tentar novamente",exact:true}).click();await finish(page);await command("verify:3");
  },mutable);
});

for(const [fault,message,next] of [["pre","persistência falhou",1],["reload","compilar ou verificar",1],["durability","durabilidade não foi confirmada",2]]) test("real fault without retry "+fault,async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await draft(page);await command("fault:"+fault);
    let writes=0;page.on("request",r=>{if(r.method()==="POST" && new URL(r.url()).pathname==="/admin/v1/rules")writes++;});
    await page.getByRole("button",{name:"Salvar",exact:true}).click();await outcome(page,String(message));await command("verify:"+next);
    requireTrue(writes===1 && await page.getByRole("button",{name:"Tentar novamente",exact:true}).count()===0);
    if(fault==="durability") {await page.getByRole("button",{name:"Reler estado",exact:true}).click();await outcome(page,String(message));await command("verify:2");requireTrue(writes===1);}
    await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true})));
    requireTrue(await page.getByRole("dialog").count()===0 && await page.getByLabel("Token",{exact:true}).inputValue()==="");
  },mutable);
});

test("lost real commit response stays unknown despite higher revision",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await draft(page);let writes=0;
    await page.route("**/admin/v1/rules",async route=>{if(route.request().method()==="POST") {writes++;await route.fetch();await route.abort();}else await route.continue();});
    await page.getByRole("button",{name:"Salvar",exact:true}).click();await outcome(page,"Resultado desconhecido");await command("verify:2");
    await page.getByRole("button",{name:"Reler estado",exact:true}).click();await outcome(page,"Resultado desconhecido");requireTrue(writes===1);
    requireTrue(await page.getByRole("button",{name:"Concluir",exact:true}).count()===0);
    await page.getByRole("button",{name:"Fechar e descartar rascunho",exact:true}).click();await page.getByRole("button",{name:"Descartar",exact:true}).click();await ready(page);
    requireTrue(await page.getByRole("button",{name:"Criar",exact:true}).isDisabled());await command("verify:2");
  },mutable);
});

test("eight editors, conditional integer, explicit validation, keyboard and discard",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await draft(page);let writes=0,checks=0;
    page.on("request",r=>{if(r.method()!=="GET") {if(r.url().endsWith("config:validate"))checks++;else writes++;}});
    /** @type {Record<string,string[]>} */
    const expected={md5:[],sha256:[],sha512:[],hmac_sha256:[],fixed:["value"],truncate:["length"],regex:["pattern","replacement"],random:["strategy","preserve_length"]};
    for(const [name,fields] of Object.entries(expected)) {
      await page.getByLabel("transformer",{exact:true}).selectOption(name);
      for(const label of fields) requireTrue(await page.getByLabel(label,{exact:true}).count()===1);
      for(const label of ["value","length","pattern","replacement","strategy","preserve_length"]) if(!fields.includes(label)) requireTrue(await page.getByLabel(label,{exact:true}).count()===0);
    }
    await page.getByLabel("strategy",{exact:true}).selectOption("digits");await page.getByLabel("preserve_length",{exact:true}).uncheck();
    await page.getByLabel("length",{exact:true}).fill("1.5");await page.getByRole("button",{name:"Salvar",exact:true}).click();requireTrue(writes===0);
    await page.getByLabel("length",{exact:true}).fill("0");await page.getByRole("button",{name:"Validar proposta",exact:true}).click();await outcome(page,"Conteúdo e compilação válidos");requireTrue(checks===1 && writes===0);
    await page.getByLabel("length",{exact:true}).fill("2");await outcome(page,"descartado");requireTrue(checks===1);
    await page.getByLabel("preserve_length",{exact:true}).check();requireTrue(await page.getByLabel("length",{exact:true}).count()===0);
    await page.setViewportSize({width:320,height:700});await page.emulateMedia({reducedMotion:"reduce"});
    for(let n=0;n<18;n++) {await page.keyboard.press("Tab");requireTrue(await page.getByRole("dialog").evaluate(d=>d.contains(document.activeElement)));}
    requireTrue(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    await page.setViewportSize({width:640,height:900});
    await page.evaluate(()=>{document.documentElement.style.zoom="2";});
    requireTrue(await page.evaluate(()=>getComputedStyle(document.documentElement).zoom==="2" && document.documentElement.scrollWidth<=window.innerWidth));
    await page.keyboard.press("Escape");await page.getByRole("button",{name:"Continuar editando",exact:true}).click();
    requireTrue(await page.getByLabel("match",{exact:true}).inputValue()==="protected_value");
    await page.getByRole("button",{name:"Cancelar",exact:true}).click();await page.getByRole("button",{name:"Descartar",exact:true}).click();
    requireTrue(await page.getByRole("dialog").count()===0 && writes===0);await command("verify:1");
  },mutable);
});

test("stored form XSS stays text in another session and unknown editor blocks changes",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    const hostile='<img src=x onerror="document.documentElement.dataset.compromised=1"></script>javascript:';
    let external=false;page.on("request",r=>{if(!r.url().startsWith(origin))external=true;});
    await enter(page,origin,token);await adopt(page);await createRule(page,hostile,hostile);await command("verify:2");
    const other=await page.context().newPage();other.on("request",r=>{if(!r.url().startsWith(origin))external=true;});await enter(other,origin,token);await navigate(other,"Regras");
    requireTrue((await other.getByRole("region",{name:"Leitura",exact:true}).textContent())?.includes(hostile));
    requireTrue(await other.evaluate(()=>!document.documentElement.dataset.compromised && document.querySelectorAll("img,svg").length===0));
    await other.route("**/admin/v1/transformers",async route=>{const response=await route.fetch();const value=await response.json();value.transformers=value.transformers.filter((/** @type {{name:string}} */ e)=>e.name!=="fixed");await route.fulfill({response,json:value});});
    await other.getByRole("button",{name:"Editar",exact:true}).click();await outcome(other,"Conteúdo incompatível");
    requireTrue(await other.getByRole("button",{name:"Salvar",exact:true}).count()===0);await command("verify:2");
    await other.evaluate(()=>window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true})));requireTrue(await other.getByRole("dialog").count()===0);
    requireTrue(!external);await other.close();
  },mutable);
});

test("late validation and 401 cannot restore a draft or dialog",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await draft(page);
    let arrived=false,release=()=>{};const held=new Promise(resolve=>{release=()=>resolve(undefined);});
    await page.route("**/admin/v1/config:validate",async route=>{const response=await route.fetch();arrived=true;await held;await route.fulfill({response}).catch(()=>{});});
    await page.getByRole("button",{name:"Validar proposta",exact:true}).click();await expect.poll(()=>arrived).toBe(true);
    await page.getByLabel("match",{exact:true}).fill("changed");release();await page.unrouteAll({behavior:"wait"});await outcome(page,"descartado");
    await page.route("**/admin/v1/rules",async route=>{if(route.request().method()==="POST") await route.fulfill({status:401,contentType:"application/json",body:'{"error":"UNAUTHORIZED","detail":"hidden"}'});else await route.continue();});
    await page.getByRole("button",{name:"Salvar",exact:true}).click();await expect.poll(async()=>await page.getByRole("dialog").count()).toBe(0);
    requireTrue(await page.getByLabel("Token",{exact:true}).inputValue()==="" && !(await page.locator("body").textContent())?.includes("changed"));await command("verify:1");
  },mutable);
});

test("confirmed save with failed readback stays saved until explicit read",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await draft(page);
    await page.route("**/admin/v1/config",route=>route.abort());
    await page.getByRole("button",{name:"Salvar",exact:true}).click();await outcome(page,"Salva; visualização ainda não atualizada");await command("verify:2");
    requireTrue(await page.getByRole("button",{name:"Concluir",exact:true}).count()===0);await page.unrouteAll({behavior:"wait"});
    await page.getByRole("button",{name:"Reler estado",exact:true}).click();await finish(page);await command("verify:2");
  },mutable);
});

test("double submit and pagehide after admission cannot replay or restore draft",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await draft(page);
    const field=await page.getByLabel("match",{exact:true}).elementHandle();
    let admitted=false,writes=0,release=()=>{};const held=new Promise(resolve=>{release=()=>resolve(undefined);});
    await page.route("**/admin/v1/rules",async route=>{
      if(route.request().method()!=="POST") {await route.continue();return;}
      writes++;const response=await route.fetch();admitted=true;await held;await route.fulfill({response}).catch(()=>{});
    });
    await page.getByRole("button",{name:"Salvar",exact:true}).evaluate(b=>{if(b instanceof HTMLButtonElement){b.click();b.click();}});
    await expect.poll(()=>admitted).toBe(true);requireTrue(writes===1);await command("verify:2");
    await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true})));
    requireTrue(await page.getByRole("dialog").count()===0 && await page.getByLabel("Token",{exact:true}).inputValue()==="");
    requireTrue(await field?.evaluate(e=>e instanceof HTMLInputElement && e.value===""));
    release();await page.unrouteAll({behavior:"wait"});requireTrue(await page.getByRole("dialog").count()===0 && writes===1);await command("verify:2");
  },mutable);
});

test("sanitized field reasons cannot render hostile paths or details",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await draft(page);
    const hostile='<img src=x onerror="document.documentElement.dataset.compromised=1">';
    await page.route("**/admin/v1/config:validate",route=>route.fulfill({status:422,contentType:"application/json",json:{error:"SCHEMA_INVALID",detail:hostile,fields:[{path:"masking.0.match",reason:"missing"},{path:hostile,reason:"missing"}]}}));
    await page.getByRole("button",{name:"Validar proposta",exact:true}).click();await outcome(page,"Proposta inválida");
    requireTrue(await page.getByLabel("match",{exact:true}).getAttribute("aria-describedby")==="reason-0");
    requireTrue(!(await page.getByRole("dialog").textContent())?.includes(hostile) && await page.locator("img").count()===0);
    await page.getByLabel("match",{exact:true}).fill("changed");requireTrue(await page.getByLabel("match",{exact:true}).getAttribute("aria-describedby")===null);
    await command("verify:1");await page.unrouteAll({behavior:"wait"});
    await page.keyboard.press("Escape");await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true})));
    requireTrue(await page.getByRole("dialog").count()===0 && await page.getByLabel("Token",{exact:true}).inputValue()==="");
  },mutable);
});
