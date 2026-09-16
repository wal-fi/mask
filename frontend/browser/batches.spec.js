import { test, expect } from "@playwright/test";
import { scenario, requireTrue } from "./harness.js";
/** @param {string} name */
function engine(name) {if(name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");return name;}
/** @param {import("@playwright/test").Page} page */
async function ready(page) {await expect.poll(async()=> (await page.getByRole("status").first().textContent())?.startsWith("Respondendo")).toBe(true);}
/** @param {import("@playwright/test").Page} page @param {string} origin @param {string} token */
async function enter(page,origin,token) {await page.goto(origin+"/admin/ui");await page.getByLabel("Token",{exact:true}).fill(token);await page.getByRole("button",{name:"Entrar",exact:true}).click();await ready(page);}
/** @param {import("@playwright/test").Page} page @param {string} name */
async function navigate(page,name) {await page.getByRole("navigation").getByRole("button",{name,exact:true}).click();await ready(page);}
/** @param {import("@playwright/test").Page} page */
async function finish(page) {await page.getByRole("dialog").getByRole("button",{name:"Concluir",exact:true}).click();await ready(page);}
/** @param {import("@playwright/test").Page} page */
async function adopt(page) {await navigate(page,"Configuração");await page.getByRole("button",{name:"Adoção explícita",exact:true}).click();await page.getByLabel("Li e compreendi as consequências").check();await page.getByRole("button",{name:"Adotar configuração",exact:true}).click();await finish(page);}
/** @param {import("@playwright/test").Page} page @param {string} text */
async function outcome(page,text) {
  try {await expect.poll(async()=> (await page.getByRole("dialog").getByRole("status").textContent())?.includes(text)).toBe(true);}
  catch(error) {
    const value=await page.getByRole("dialog").getByRole("status").textContent({timeout:1000}).catch(()=>null);
    const state=value?.includes("pendente")?"pending":value?.includes("desconhecido")?"unknown":value?.includes("runtime aposentado")?"busy":value?.includes("mudou")?"conflict":value?.includes("Salva")?"success":"other";
    test.info().annotations.push({type:"check",description:"batch-state-"+state});throw error;
  }
}
/** @param {import("@playwright/test").Page} page */
async function save(page) {await page.getByRole("button",{name:"Revisar alterações",exact:true}).click();await page.getByRole("button",{name:"Confirmar",exact:true}).click();}
/** @param {import("@playwright/test").Page} page */
async function reorder(page) {await navigate(page,"Regras");await page.getByRole("button",{name:"Reordenar regras",exact:true}).click();await page.getByRole("button",{name:"Mover para baixo",exact:true}).first().click();}
/** @param {import("@playwright/test").Page} page */
async function limits(page) {await navigate(page,"Banco");await page.getByRole("button",{name:"Editar limites",exact:true}).click();await page.getByLabel("statement_timeout_ms",{exact:true}).fill("100");await page.getByLabel("max_rows",{exact:true}).fill("1");}
/** @param {"both"|"first"|"second"|"removed"|"conflict"|"reviewed"|"verified"|"closed"} step */
function mark(step) {test.info().annotations.push({type:"check",description:"batch-step-"+step});}
const mutable={MASKGW_BROWSER_EDIT:"1",MASKGW_BROWSER_BATCH:"1"};

test("keyboard filtered full reorder, exact cancel, complete limits, additive SQL and real MCP restart",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    /** @type {{path:string,body:Record<string,unknown>}[]} */const writes=[];let leak=false;
    page.on("request",r=>{if(r.method()!=="GET")writes.push({path:new URL(r.url()).pathname,body:JSON.parse(r.postData()??"{}")});if(r.url().includes(token)||r.postData()?.includes(token)||!r.url().startsWith(origin))leak=true;});
    await enter(page,origin,token);await command("batch-before");await adopt(page);const count=writes.length;
    await navigate(page,"Regras");await page.getByRole("button",{name:"Reordenar regras",exact:true}).click();
    await page.getByLabel("Filtrar exibição").fill("first");requireTrue(await page.getByRole("button",{name:"Mover para baixo",exact:true}).count()===1);
    await page.getByRole("button",{name:"Mover para baixo",exact:true}).focus();await page.keyboard.press("Enter");
    requireTrue(await page.getByRole("heading",{name:"Posição 2",exact:true}).count()===1);
    await page.getByRole("button",{name:"Revisar alterações",exact:true}).click();requireTrue(writes.length===count);
    await page.getByRole("button",{name:"Cancelar",exact:true}).click();await page.getByRole("button",{name:"Descartar",exact:true}).click();await command("verify:1");requireTrue(writes.length===count);
    await page.getByRole("button",{name:"Reordenar regras",exact:true}).click();
    requireTrue((await page.getByRole("dialog").locator("section section").first().textContent())?.includes("first"));
    await page.getByLabel("Filtrar exibição").fill("first");await page.getByRole("button",{name:"Mover para baixo",exact:true}).press("Space");
    await page.getByRole("button",{name:"Validar proposta",exact:true}).click();await outcome(page,"Conteúdo e compilação válidos");
    await save(page);await finish(page);await command("verify:2");
    const moved=writes.find(r=>r.path.endsWith(":reorder"));requireTrue(moved && Array.isArray(moved.body.rule_ids)&&moved.body.rule_ids.length===2);
    await limits(page);await page.getByRole("button",{name:"Validar proposta",exact:true}).click();await outcome(page,"Conteúdo e compilação válidos");await save(page);await finish(page);await command("verify:3");
    const bound=writes.find(r=>r.path.endsWith("/database"));requireTrue(bound && Object.keys(bound.body).length===3 && bound.body.statement_timeout_ms===100 && bound.body.max_rows===1);
    await navigate(page,"Política SQL");await page.getByRole("button",{name:"Adicionar funções negadas",exact:true}).click();await page.getByLabel("Novos nomes, um por linha").fill("UPPER\nupper\nLOWER\nStraße\nSTRASSE");
    await page.getByRole("button",{name:"Validar proposta",exact:true}).click();await outcome(page,"Conteúdo e compilação válidos");await save(page);await finish(page);await command("verify:4");
    const added=writes.find(r=>r.path.endsWith("/sql"));requireTrue(added&&JSON.stringify(added.body.denied_functions)===JSON.stringify(["UPPER","upper","LOWER","Straße","STRASSE"]));
    requireTrue(!leak && writes.filter(r=>!r.path.endsWith(":validate")).every(r=>!JSON.stringify(r.body).includes("allowed_pg_functions")));
    await command("batch-effects");await command("restart");await command("batch-effects");
    await navigate(page,"Política SQL");requireTrue((await page.getByRole("region",{name:"Leitura"}).textContent())?.includes("upper"));
    await page.getByRole("button",{name:"Adicionar funções negadas",exact:true}).click();await expect(page.getByLabel("Novos nomes, um por linha")).toBeVisible();requireTrue((await page.getByRole("dialog").textContent())?.includes("UPPER"));
  },mutable);
});

test("literal integer input failures never request and unchanged second limit is sent",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);await navigate(page,"Banco");await page.getByRole("button",{name:"Editar limites",exact:true}).click();let writes=0;page.on("request",r=>{if(r.method()!=="GET")writes++;});
    /** @type {[string,string[]][]} */ const cases=[["statement_timeout_ms",["99","600001","true","1.5"," 100","100 ","01","1e2","9007199254740992"]],["max_rows",["0","1000001","false","1.0","+1"," 1"]]];
    for(const [field,values] of cases) {
      for(const value of values) {await page.getByLabel(String(field),{exact:true}).fill(value);await page.getByRole("button",{name:"Revisar alterações",exact:true}).click();requireTrue(await page.getByRole("button",{name:"Confirmar",exact:true}).count()===0 && writes===0);}
      await page.getByLabel(String(field),{exact:true}).fill(field==="max_rows"?"1000":"100");
    }
    await save(page);await finish(page);requireTrue(writes===1);await command("verify:2");
  },mutable);
});

test("two tabs reorder conflict preserves full draft and explicit review only",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);const other=await page.context().newPage();await enter(other,origin,token);
    await reorder(page);await reorder(other);mark("both");await save(page);await finish(page);mark("first");await save(other);mark("second");await outcome(other,"mudou");await command("verify:2");
    requireTrue(await other.getByRole("heading",{name:"Rascunho preservado",exact:true}).count()===1);
    await other.getByRole("button",{name:"Revisar rascunho com nova base",exact:true}).click();await save(other);await finish(other);await command("verify:3");await other.close();
  },mutable);
});

for(const kind of ["lost","readback","busy","durability","unauthorized","lifecycle"]) test("batch coordinator remains closed on "+kind,async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);
    if(kind==="busy") {await command("hold");await reorder(page);await save(page);await finish(page);}
    await limits(page);let writes=0;
    page.on("request",r=>{if(r.method()==="PUT"&&r.url().endsWith("/database"))writes++;});
    if(kind==="lost" || kind==="readback" || kind==="unauthorized") await page.route("**/admin/v1/database",async route=>{
      if(kind==="unauthorized") {await route.fulfill({status:401,contentType:"application/json",body:'{"error":"UNAUTHORIZED","detail":""}'});return;}
      const response=await route.fetch();
      if(kind==="lost") await route.abort();else {await page.route("**/admin/v1/config",r=>r.abort());await route.fulfill({response});}
    });
    if(kind==="durability") await command("fault:durability");
    if(kind==="lifecycle") {await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true})));requireTrue(writes===0 && await page.getByRole("dialog").count()===0 && await page.getByLabel("Token",{exact:true}).inputValue()==="");return;}
    await save(page);
    if(kind==="unauthorized") {await expect(page.getByLabel("Token",{exact:true})).toBeVisible();requireTrue(writes===1 && await page.getByRole("dialog").count()===0);return;}
    if(kind==="busy") {await outcome(page,"runtime aposentado");await command("release");await page.getByRole("button",{name:"Tentar novamente",exact:true}).click();await finish(page);requireTrue(writes===2);await command("verify:3");return;}
    if(kind==="readback") {await expect(page.getByRole("button",{name:"Reler estado",exact:true})).toBeVisible();requireTrue(await page.getByRole("button",{name:"Concluir",exact:true}).count()===0 && writes===1);await page.unroute("**/admin/v1/config");await page.getByRole("button",{name:"Reler estado",exact:true}).click();await finish(page);await command("verify:2");return;}
    await outcome(page,kind==="lost"?"Resultado desconhecido":"durabilidade não foi confirmada");await command("verify:2");
    await page.getByRole("button",{name:"Reler estado",exact:true}).click();requireTrue(writes===1);
    await page.getByRole("button",{name:"Fechar e descartar rascunho",exact:true}).click();await page.getByRole("button",{name:"Descartar",exact:true}).click();await ready(page);requireTrue(await page.getByRole("button",{name:"Editar limites",exact:true}).isDisabled());
  },mutable);
});


test("obsolete permutation cannot be reviewed after another tab deletes an ID",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);await adopt(page);const other=await page.context().newPage();await enter(other,origin,token);await reorder(page);
    await navigate(other,"Regras");await other.getByRole("button",{name:"Excluir",exact:true}).first().click();await other.getByRole("dialog").getByRole("button",{name:"Excluir",exact:true}).click();await finish(other);
    let writes=0;page.on("request",r=>{if(r.method()!=="GET")writes++;});
    mark("removed");await save(page);mark("second");await outcome(page,"mudou");mark("conflict");requireTrue(writes===1);
    await page.getByRole("button",{name:"Revisar rascunho com nova base",exact:true}).click();mark("reviewed");await outcome(page,"Revisão incompatível");requireTrue(writes===1);await command("verify:2");mark("verified");await other.close();mark("closed");
  },mutable);
});


test("stored hostile text remains inert in filtered reorder at narrow width",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    const hostile='<img src=x onerror="document.documentElement.dataset.compromised=1"></script>javascript:';
    let external=false;page.on("request",r=>{if(!r.url().startsWith(origin))external=true;});
    await enter(page,origin,token);await adopt(page);await navigate(page,"Regras");await page.getByRole("button",{name:"Criar",exact:true}).click();
    await page.getByLabel("match",{exact:true}).fill(hostile);await page.getByLabel("transformer",{exact:true}).selectOption("fixed");await page.getByLabel("value",{exact:true}).fill(hostile);await page.getByRole("button",{name:"Salvar",exact:true}).click();await finish(page);
    await page.getByRole("button",{name:"Reordenar regras",exact:true}).click();await page.getByLabel("Filtrar exibição").fill("javascript:");
    await page.setViewportSize({width:320,height:700});requireTrue(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth && !document.documentElement.dataset.compromised));
    requireTrue((await page.getByRole("dialog").textContent())?.includes(hostile));
    await page.getByRole("button",{name:"Mover para cima",exact:true}).press("Enter");await save(page);await finish(page);await command("verify:3");requireTrue(!external);
  },mutable);
});
