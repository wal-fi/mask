// Reference captures of the read-only Admin UX v2 (Phase 9, Stage 5, D-098).
// A local fixture only: the packaged UI bytes are served by request
// interception, every administrative answer is synthetic and fictitious, no
// backend process exists and the entry value is a throwaway string typed into
// a masked field. The test reporter keeps screenshots disabled; this tool is
// run explicitly and writes PNG files for human review.
import { readFileSync, readdirSync, mkdirSync, rmSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { chromium, firefox, webkit } from "@playwright/test";
import { responseFor } from "../test/samples.js";

const assets=new URL("../../src/maskgw/admin/ui/assets/",import.meta.url);
const out=new URL("../../docs/ux-v2/",import.meta.url);
const origin="http://127.0.0.1:18765";
/** @param {string} name */
const bytes=name=>readFileSync(new URL(name,assets));
const book=JSON.parse(bytes("presentation.json").toString("utf8"));
/** @type {Record<string,string>} */ const firstPrefix={};
for (const call of book.calls) if (call.method === "GET" && call.identity === null && String(call.path).startsWith("/admin/v1/")) firstPrefix[call.path]=call.id;

const hex=(/** @type {string} */ c)=>"dso_"+c.repeat(32);
const rows=[
  {id:hex("a"),alias:"crm-demo",display_name:"CRM de demonstração",enabled:true,revision:4,last_test:{status:"never",checked_at:null},runtime:{published:true,generation:7,sessions:2}},
  {id:hex("b"),alias:"financeiro-demo",display_name:"Financeiro de demonstração",enabled:true,revision:2,last_test:{status:"never",checked_at:null},runtime:{published:true,generation:3,sessions:0}},
  {id:hex("c"),alias:"legado-demo",display_name:"Legado desabilitado",enabled:false,revision:5,last_test:{status:"never",checked_at:null},runtime:{published:false,generation:null,sessions:0}},
];
const summary={catalog_available:true,catalog_revision:12,datasources:{total:3,enabled:2,published:2},
  registry:{published:2,sessions:2,retired_open:0,candidates:0,closing:false},limits:{max_sessions:32,max_retired:4,max_candidates:2},
  writes_blocked:false,dns_timeout_ms:5000};
const blocked={...summary,catalog_available:false,catalog_revision:null,datasources:null,writes_blocked:true};
const detail={catalog_revision:12,datasource:{...rows[0],
  connection:{host:"db-crm.example.internal",port:5432,database:"app_demo",username:"gateway_demo",tls:{mode:"verify-full",server_name:"db-crm.example.internal"}},
  credential:{configured:true},limits:{statement_timeout_ms:30000,max_rows:1000,max_sessions:8},effective_limits:{statement_timeout_ms:5000,max_rows:200},
  destination_policy:{allow_public:false,allow_loopback:false,allowed_hosts:[]}}};
const policy={catalog_revision:12,datasource_id:hex("a"),revision:4,policy:{
  masking:[{match:"cpf",mode:"contains",case_sensitive:false,transformer:"hmac_sha256",config:{}},{match:"email",mode:"contains",case_sensitive:false,transformer:"fixed",config:{value:"[EMAIL]"}}],
  exceptions:[{match:"tipo_cpf",mode:"exact",case_sensitive:false}],database:{statement_timeout_ms:5000,max_rows:200},
  sql:{allowed_pg_functions:[],denied_functions:["dblink_exec"]}}};

/** @param {"rich"|"empty"|"off"|"blocked"} mode @returns {(path:string)=>{status:number,body:unknown}} */
function answers(mode) {
  return path=>{
    if (mode === "off" && path.startsWith("/admin/v2/")) return {status:404,body:{error:"NOT_FOUND",detail:"x"}};
    if (mode === "blocked" && path !== "/admin/v2/status" && path.startsWith("/admin/v2/")) return {status:503,body:{error:"CATALOG_BLOCKED",detail:"x"}};
    if (path === "/admin/v2/status") return {status:200,body:mode === "blocked" ? blocked : mode === "empty" ? {...summary,catalog_revision:1,datasources:{total:0,enabled:0,published:0},registry:{...summary.registry,published:0,sessions:0}} : summary};
    if (path === "/admin/v2/datasources") return {status:200,body:{catalog_revision:12,datasources:mode === "empty" ? [] : rows}};
    if (path === "/admin/v2/datasources/"+hex("a")) return {status:200,body:detail};
    if (path === "/admin/v2/datasources/"+hex("a")+"/policy") return {status:200,body:policy};
    const id=firstPrefix[path];
    if (id) return {status:200,body:responseFor(id)};
    return {status:404,body:{error:"NOT_FOUND",detail:"x"}};
  };
}
const files={"/admin/ui":["index.html","text/html; charset=utf-8"],"/admin/ui/assets/ui.js":["ui.js","text/javascript; charset=utf-8"],
  "/admin/ui/assets/ui.css":["ui.css","text/css; charset=utf-8"],"/admin/ui/presentation.json":["presentation.json","application/json"]};

/** @param {import("@playwright/test").Page} page @param {"rich"|"empty"|"off"|"blocked"} mode */
async function serve(page,mode) {
  const reply=answers(mode);
  await page.route(origin+"/**",async route=>{
    const path=new URL(route.request().url()).pathname;
    const file=/** @type {Record<string,string[]>} */ (files)[path];
    if (file) { await route.fulfill({status:200,headers:{"content-type":String(file[1]),"cache-control":"no-store"},body:bytes(String(file[0]))}); return; }
    if (route.request().method() !== "GET") throw new Error("Fixture refused a write.");
    const answer=reply(path);
    await route.fulfill({status:answer.status,headers:{"content-type":"application/json","cache-control":"no-store"},body:JSON.stringify(answer.body)});
  });
}
/** @param {import("@playwright/test").Page} page */
async function enter(page) {
  await page.getByLabel("Token",{exact:true}).fill("fixture-"+randomBytes(8).toString("hex"));
  await page.getByRole("button",{name:"Entrar",exact:true}).click();
  await page.waitForFunction(()=>{const s=document.querySelector("[role=status]");return !!s && s.textContent !== "Carregando…" && s.textContent !== "";});
}
/** @param {import("@playwright/test").Page} page @param {string} name */
async function go(page,name) {
  const menu=page.getByRole("button",{name:/^Menu: /});
  if(await menu.isVisible()) await menu.click();
  await page.getByRole("navigation").getByRole("button",{name,exact:true}).click();
  await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
}
/** @param {import("@playwright/test").Page} page @param {string} file */
async function shot(page,file) { await page.screenshot({path:new URL(file+".png",out).pathname.replace(/^\/([A-Za-z]:)/,"$1"),fullPage:true,animations:"disabled"}); }

// Only the current captures are replaced; the "antes" comparison set is kept.
mkdirSync(out,{recursive:true});
for (const name of readdirSync(out)) if (name.endsWith(".png")) rmSync(new URL(name,out));
const engines={chromium,firefox,webkit};
/** @type {string[]} */ const made=[];
for (const [engine,launcher] of Object.entries(engines)) {
  const browser=await launcher.launch();
  const variants=engine === "chromium"
    ? [["light",1280,860],["dark",1280,860],["light",320,900],["dark",320,900]]
    : [["light",1280,860]];
  for (const [theme,width,height] of variants) {
    const context=await browser.newContext({viewport:{width:Number(width),height:Number(height)},colorScheme:theme === "dark" ? "dark" : "light",reducedMotion:"reduce",locale:"pt-BR"});
    const page=await context.newPage();
    const tag=engine+"-"+theme+"-"+width;
    await serve(page,"rich");
    await page.goto(origin+"/admin/ui");await shot(page,tag+"-01-entrada");made.push(tag+"-01-entrada");
    await enter(page);await shot(page,tag+"-02-painel");made.push(tag+"-02-painel");
    if (Number(width) < 700) {
      await page.getByRole("button",{name:/^Menu: /}).click();
      await shot(page,tag+"-02b-menu-aberto");made.push(tag+"-02b-menu-aberto");
      await page.keyboard.press("Escape");
    }
    await go(page,"Datasources");await shot(page,tag+"-03-lista");made.push(tag+"-03-lista");
    if (engine === "chromium") {
      await page.getByLabel("Buscar por nome ou alias",{exact:true}).fill("zzz");await shot(page,tag+"-04-busca-vazia");made.push(tag+"-04-busca-vazia");
      await page.getByLabel("Buscar por nome ou alias",{exact:true}).fill("");
      await page.getByRole("button",{name:"Ver detalhes: CRM de demonstração",exact:true}).click();
      await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
      await shot(page,tag+"-05-detalhe-visao");made.push(tag+"-05-detalhe-visao");
      await page.getByRole("tab",{name:"Conexão",exact:true}).click();await shot(page,tag+"-06-detalhe-conexao");made.push(tag+"-06-detalhe-conexao");
      await page.getByRole("tab",{name:"Masking",exact:true}).click();await page.waitForFunction(()=>document.querySelector("[role=tabpanel]")?.textContent?.includes("cpf"));
      await shot(page,tag+"-07-detalhe-masking");made.push(tag+"-07-detalhe-masking");
      await page.getByRole("tab",{name:"Limites",exact:true}).click();await shot(page,tag+"-08-detalhe-limites");made.push(tag+"-08-detalhe-limites");
      await go(page,"Novo datasource");await shot(page,tag+"-09-prototipo-inicio");made.push(tag+"-09-prototipo-inicio");
      for (let i=0;i<6;i++) await page.getByRole("button",{name:"Próximo",exact:true}).click();
      await shot(page,tag+"-10-prototipo-revisao");made.push(tag+"-10-prototipo-revisao");
      await go(page,"Visão geral");await shot(page,tag+"-11-politica-v1");made.push(tag+"-11-politica-v1");
    }
    await context.close();
  }
  if (engine === "chromium") {
    for (const [mode,width] of /** @type {const} */ ([["empty",1280],["off",1280],["blocked",1280],["off",320],["blocked",320]])) {
      const context=await browser.newContext({viewport:{width,height:width === 320 ? 900 : 860},colorScheme:"light",reducedMotion:"reduce",locale:"pt-BR"});
      const page=await context.newPage();await serve(page,mode);
      await page.goto(origin+"/admin/ui");await enter(page);
      if (mode !== "off") await go(page,"Datasources"); else await go(page,"Painel");
      const name="chromium-estado-"+(mode === "empty" ? "vazio" : mode === "off" ? "catalogo-desligado" : "catalogo-bloqueado")+(width === 320 ? "-320" : "");
      await shot(page,name);made.push(name);
      await context.close();
    }
  }
  await browser.close();
}
console.log("Reference captures:",made.length);
