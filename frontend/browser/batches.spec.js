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
/** @param {"entered"|"adopted"|"opened"|"ready"|"drafted"|"checked"|"both"|"first"|"second"|"removed"|"conflict"|"reviewed"|"verified"|"closed"} step */
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
    await page.goto("about:blank");await command("rollback-off");await command("batch-effects");await command("backup");
    for(const path of ["/admin/ui","/admin/ui/assets/ui.js","/admin/ui/assets/ui.css","/admin/ui/presentation.json"]) {
      const absent=await page.request.get(origin+path,{headers:{Authorization:"Bearer "+token}});
      requireTrue(absent.status()===404 && absent.headers()["content-security-policy"]===undefined);
    }
    const native=await page.request.get(origin+"/admin/v1/config",{headers:{Authorization:"Bearer "+token}});
    requireTrue(native.status()===200 && (await native.json()).revision===4);
    const foreign=await page.request.get(origin+"/admin/v1/config",{headers:{Authorization:"Bearer "+token,Origin:origin}});requireTrue(foreign.status()===403);
    await command("rollback-on");await command("batch-effects");await command("verify:4");await enter(page,origin,token);
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
    await enter(page,origin,token);mark("entered");await adopt(page);mark("adopted");const other=await page.context().newPage();mark("opened");await enter(other,origin,token);mark("ready");
    await reorder(page);mark("drafted");await reorder(other);mark("both");await other.getByRole("button",{name:"Validar proposta",exact:true}).click();await outcome(other,"Conteúdo e compilação válidos");mark("checked");await save(page);await finish(page);mark("first");await save(other);mark("second");await outcome(other,"mudou");await command("verify:2");
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

// Política v1 (D-102): each card holds only its own Editar/Excluir. The write a
// button sends must name exactly the identity shown in that card, before and
// after reordering, editing and removal; a duplicated identity gets no actions.
test("item actions stay with their own card across reorder, edit and removal",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    /** @type {{method:string,path:string}[]} */ const writes=[];
    page.on("request",r=>{const path=new URL(r.url()).pathname;if(r.method()!=="GET" && !path.endsWith(":validate"))writes.push({method:r.method(),path});});
    await enter(page,origin,token);await adopt(page);
    /** @param {string} name @param {string} item @param {RegExp} pattern @param {string} field */
    const cards=async(name,item,pattern,field)=>{
      await navigate(page,name);
      const list=page.locator("li.sequence-card");/** @type {{id:string,value:string}[]} */ const found=[];
      for(let i=0;i<await list.count();i++) {
        const card=list.nth(i),text=(await card.textContent()) ?? "",id=text.match(pattern)?.[0] ?? "";
        const value=(await card.locator("dt:text-is('"+field+"') + dd").first().textContent())?.trim() ?? "";
        requireTrue(id !== "" && value !== "","card identity");
        requireTrue(await card.getByRole("group",{name:"Ações: "+item+" "+(i+1),exact:true}).count() === 1,"card group");
        requireTrue(await card.getByRole("button",{name:"Editar",exact:true}).count() === 1 && await card.getByRole("button",{name:"Excluir",exact:true}).count() === 1,"card buttons");
        found.push({id,value});
      }
      requireTrue(await page.getByRole("heading",{name:/^Item [0-9]+$/}).count() === 0,"no detached rows");
      requireTrue(await page.getByRole("button",{name:"Editar",exact:true}).count() === found.length,"no extra actions");
      requireTrue(new Set(found.map(f=>f.id)).size === found.length,"distinct identities");
      return found;
    };
    /** Opens the card's own Editar and returns the value its form was loaded with. @param {number} index @param {string} label */
    const opened=async(index,label)=>{
      await page.locator("li.sequence-card").nth(index).getByRole("button",{name:"Editar",exact:true}).click();
      const loaded=await page.getByRole("dialog").getByLabel(label,{exact:true}).inputValue();
      await page.getByRole("dialog").getByRole("button",{name:"Cancelar",exact:true}).click();
      const discard=page.getByRole("button",{name:"Descartar",exact:true});if(await discard.isVisible()) await discard.click();
      return loaded;
    };
    const rule=/rul_[0-9a-f]{32}/;
    const before=await cards("Regras","Regra",rule,"Valor substituto");
    requireTrue(JSON.stringify(before.map(c=>c.value)) === JSON.stringify(["first","second"]),"initial order");
    for(const [index,card] of before.entries()) requireTrue(await opened(index,"value") === card.value,"edit loads own card");

    // Reorder: identities travel with their cards, never with the positions.
    await page.getByRole("button",{name:"Reordenar regras",exact:true}).click();await page.getByRole("button",{name:"Mover para baixo",exact:true}).first().click();
    await page.getByRole("button",{name:"Validar proposta",exact:true}).click();await outcome(page,"Conteúdo e compilação válidos");await save(page);await finish(page);
    const after=await cards("Regras","Regra",rule,"Valor substituto");
    requireTrue(JSON.stringify(after.map(c=>c.id)) === JSON.stringify([before[1]?.id,before[0]?.id]),"identities follow cards");
    for(const [index,card] of after.entries()) requireTrue(await opened(index,"value") === card.value,"edit after reorder");

    // Edit the first card: the replacement names that card's identity only.
    let count=writes.length;
    await page.locator("li.sequence-card").nth(0).getByRole("button",{name:"Editar",exact:true}).click();
    await page.getByRole("dialog").getByLabel("value",{exact:true}).fill("segundo");
    await page.getByRole("button",{name:"Salvar",exact:true}).click();await finish(page);
    requireTrue(writes.length === count+1 && writes[count]?.method === "PUT" && writes[count]?.path === "/admin/v1/rules/"+after[0]?.id,"edit targets own identity");
    const edited=await cards("Regras","Regra",rule,"Valor substituto");
    requireTrue(JSON.stringify(edited) === JSON.stringify([{id:after[0]?.id,value:"segundo"},{id:after[1]?.id,value:"first"}]),"edit changed own card only");

    // Remove the second card: the deletion names that card's identity only.
    count=writes.length;
    await page.locator("li.sequence-card").nth(1).getByRole("button",{name:"Excluir",exact:true}).click();
    await page.getByRole("dialog").getByRole("button",{name:"Excluir",exact:true}).click();await finish(page);
    requireTrue(writes.length === count+1 && writes[count]?.method === "DELETE" && writes[count]?.path === "/admin/v1/rules/"+after[1]?.id,"delete targets own identity");
    const left=await cards("Regras","Regra",rule,"Valor substituto");
    requireTrue(JSON.stringify(left) === JSON.stringify([{id:after[0]?.id,value:"segundo"}]),"removed card is gone, the other intact");
    requireTrue(await opened(0,"value") === "segundo","remaining edit loads remaining card");

    // Exceptions use the same association.
    const kept=await cards("Exceções","Exceção",/exc_[0-9a-f]{32}/,"Correspondência");
    requireTrue(kept.length === 1 && await opened(0,"match") === "keep","exception actions stay with their card");

    // A repeated identity is refused by the reader before any card or action exists
    // (identity binding); the screen's own ambiguity guard is a second layer.
    await page.route("**/admin/v1/rules",async route=>{
      const response=await route.fetch();/** @type {{rules:Record<string,unknown>[]}} */ const data=await response.json();
      const first=data.rules[0];if(!first) throw new Error("Fixture failed.");
      data.rules=[first,{...first,position:1,config:{value:"clone"}}];await route.fulfill({response,json:data});
    });
    count=writes.length;
    await page.getByRole("navigation").getByRole("button",{name:"Regras",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("status").first().textContent())?.includes("indisponível")).toBe(true);
    requireTrue(await page.locator("li.sequence-card").count() === 0,"repeated identity renders no card");
    requireTrue(await page.getByRole("button",{name:"Editar",exact:true}).count() === 0 && await page.getByRole("button",{name:"Excluir",exact:true}).count() === 0,"repeated identity offers no action");
    await page.unrouteAll();requireTrue(writes.length === count,"no write from a refused reading");
  },mutable);
});
