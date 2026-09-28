// Reference captures of the read-only Admin UX v2 (Phase 9, Stage 5, D-098).
// A local fixture only: the packaged UI bytes are served by request
// interception, every administrative answer is synthetic and fictitious, no
// backend process exists and the entry value is a throwaway string typed into
// a masked field. The test reporter keeps screenshots disabled; this tool is
// run explicitly and writes PNG files for human review.
import { readFileSync, readdirSync, mkdirSync, rmSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { strict as assert } from "node:assert";
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
// Disabled and unpublished: neutral states, no generation, never checked.
const idle={catalog_revision:12,datasource:{...rows[2],
  connection:{host:"10.20.0.15",port:5432,database:"legado",username:"gateway_legado",tls:{mode:"disable",server_name:null}},
  credential:{configured:true},limits:{statement_timeout_ms:10000,max_rows:500,max_sessions:2},effective_limits:{statement_timeout_ms:5000,max_rows:200},
  destination_policy:{allow_public:false,allow_loopback:false,allowed_hosts:[]}}};
const policy={catalog_revision:12,datasource_id:hex("a"),revision:4,policy:{
  masking:[{match:"cpf",mode:"contains",case_sensitive:false,transformer:"hmac_sha256",config:{}},{match:"email",mode:"contains",case_sensitive:false,transformer:"fixed",config:{value:"[EMAIL]"}}],
  exceptions:[{match:"tipo_cpf",mode:"exact",case_sensitive:false}],database:{statement_timeout_ms:5000,max_rows:200},
  sql:{allowed_pg_functions:[],denied_functions:["dblink_exec"]}}};

// Política v1: fictitious, coherent readings (one revision everywhere). The
// "unadopted" variant is the file served as is: revision 0 and no IDs yet.
/** @param {boolean} adopted */
function legacy(adopted) {
  const revision=adopted ? 3 : 0, rid=(/** @type {string} */ c)=>adopted ? "rul_"+c.repeat(32) : null, eid=(/** @type {string} */ c)=>adopted ? "exc_"+c.repeat(32) : null;
  const masking=[{id:rid("1"),match:"cpf",mode:"contains",case_sensitive:false,transformer:"hmac_sha256",config:{}},
    {id:rid("2"),match:"email",mode:"contains",case_sensitive:false,transformer:"fixed",config:{value:"[EMAIL]"}}];
  const exceptions=[{id:eid("3"),match:"tipo_cpf",mode:"exact",case_sensitive:false}];
  const document={revision,database:{statement_timeout_ms:5000,max_rows:200},masking,exceptions,sql:{allowed_pg_functions:[],denied_functions:["dblink_exec"]}};
  return {
    "/admin/v1/status":{adopted,revision,counters:{admin_operations_total:adopted ? 4 : 0,queries_total:128},runtime:{retired_runtimes_open:0,revision},
      secrets:{admin_token:"configured",database_dsn:"configured",hmac_sha256_key:"configured"}},
    "/admin/v1/config":{adopted,revision,config:document},
    "/admin/v1/rules":{adopted,revision,rules:masking.map((r,position)=>({...r,position}))},
    "/admin/v1/exceptions":{adopted,revision,exceptions:exceptions.map((r,position)=>({...r,position}))},
    "/admin/v1/protected":{revision,allowed_pg_functions:[],denied_function_prefixes:["dblink","lo_","pg_ls_","pg_read_"],
      denied_functions:["dblink_exec","lo_export","lo_import","pg_read_file","set_config"],denied_relations:["pg_statistic","pg_stats","pg_stats_ext"],
      editable:false,pg_namespace_default:"deny",pipeline:["DERIVED","EXCEPTION","MASKING","ORIGINAL"],
      session:{provenance_capability_required:true,read_only:true,statement_timeout_enforced_by:"postgresql"},unmatched_policy:"allow",
      validator_rules:["exactly one executable statement","the root node must be a SELECT statement","no other statement node anywhere in the tree, including nested CTEs","INTO and locking clauses are rejected at any depth"]},
  };
}
/** @param {"rich"|"empty"|"off"|"blocked"|"unadopted"} mode @returns {(path:string)=>{status:number,body:unknown}} */
function answers(mode) {
  const first=/** @type {Record<string,unknown>} */ (legacy(mode !== "unadopted"));
  return path=>{
    if (Object.hasOwn(first,path)) return {status:200,body:first[path]};
    if (mode === "off" && path.startsWith("/admin/v2/")) return {status:404,body:{error:"NOT_FOUND",detail:"x"}};
    if (mode === "blocked" && path !== "/admin/v2/status" && path.startsWith("/admin/v2/")) return {status:503,body:{error:"CATALOG_BLOCKED",detail:"x"}};
    if (path === "/admin/v2/status") return {status:200,body:mode === "blocked" ? blocked : mode === "empty" ? {...summary,catalog_revision:1,datasources:{total:0,enabled:0,published:0},registry:{...summary.registry,published:0,sessions:0}} : summary};
    if (path === "/admin/v2/datasources") return {status:200,body:{catalog_revision:12,datasources:mode === "empty" ? [] : rows}};
    if (path === "/admin/v2/datasources/"+hex("a")) return {status:200,body:detail};
    if (path === "/admin/v2/datasources/"+hex("c")) return {status:200,body:idle};
    if (path === "/admin/v2/datasources/"+hex("a")+"/policy") return {status:200,body:policy};
    const id=firstPrefix[path];
    if (id) return {status:200,body:responseFor(id)};
    return {status:404,body:{error:"NOT_FOUND",detail:"x"}};
  };
}
const files={"/admin/ui":["index.html","text/html; charset=utf-8"],"/admin/ui/assets/ui.js":["ui.js","text/javascript; charset=utf-8"],
  "/admin/ui/assets/ui.css":["ui.css","text/css; charset=utf-8"],"/admin/ui/presentation.json":["presentation.json","application/json"]};

/** Synthetic answer of the next second-prefix write (Stage 6 captures only). */
const next={state:/** @type {"done"|"conflict"|"unknown"|"blocked"} */ ("done")};
/** @param {import("@playwright/test").Page} page @param {"rich"|"empty"|"off"|"blocked"|"unadopted"} mode */
async function serve(page,mode) {
  const reply=answers(mode);
  await page.route(origin+"/**",async route=>{
    const path=new URL(route.request().url()).pathname;
    const file=/** @type {Record<string,string[]>} */ (files)[path];
    if (file) { await route.fulfill({status:200,headers:{"content-type":String(file[1]),"cache-control":"no-store"},body:bytes(String(file[0]))}); return; }
    if (route.request().method() !== "GET") {
      // Only fictitious answers; nothing is stored and no backend exists.
      if (!path.startsWith("/admin/v2/")) throw new Error("Fixture refused a write.");
      const json=(/** @type {number} */ status,/** @type {unknown} */ body)=>route.fulfill({status,headers:{"content-type":"application/json","cache-control":"no-store"},body:JSON.stringify(body)});
      if (path.endsWith(":test")) { await json(200,{passed:true,persisted:false,published:false}); return; }
      if (next.state === "unknown") { await route.abort("failed"); return; }
      if (next.state === "conflict") { await json(409,{error:"REVISION_CONFLICT",detail:"x",current_revision:5}); return; }
      if (next.state === "blocked") { await json(503,{error:"CATALOG_BLOCKED",detail:"x"}); return; }
      if (route.request().method() === "DELETE") { await json(200,{catalog_revision:13,removed:true}); return; }
      await json(200,{catalog_revision:13,datasource_id:hex("a"),datasource_revision:5,changed:true});
      return;
    }
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
/** Navigation that may be interrupted by a discard question (no waiting).
 * @param {import("@playwright/test").Page} page @param {string} name
 */
async function go2(page,name) {
  const menu=page.getByRole("button",{name:/^Menu: /});
  if(await menu.isVisible()) await menu.click();
  await page.getByRole("navigation").getByRole("button",{name,exact:true}).click();
}
/** @param {import("@playwright/test").Page} page @param {string} name */
async function go(page,name) {
  const menu=page.getByRole("button",{name:/^Menu: /});
  if(await menu.isVisible()) await menu.click();
  await page.getByRole("navigation").getByRole("button",{name,exact:true}).click();
  await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
}
/** @param {import("@playwright/test").Page} page */
async function overview(page) {
  const body=page.getByRole("tabpanel");
  assert.deepEqual(await body.locator("h3").allTextContents(),["Identidade","Estado no Gateway","Atividade do runtime","Última verificação de conexão"]);
  assert.equal(await body.getByText("Nome",{exact:true}).count(),0);
  assert.equal(await body.locator(".flag.neutral",{hasText:"Nunca verificado"}).count(),1);
}
/** @param {import("@playwright/test").Page} page @param {string} file */
async function shot(page,file) { await page.screenshot({path:new URL(file+".png",out).pathname.replace(/^\/([A-Za-z]:)/,"$1"),fullPage:true,animations:"disabled"}); }

// Only the current captures are replaced; the "antes" comparison set is kept.
mkdirSync(out,{recursive:true});
for (const name of readdirSync(out)) if (name.endsWith(".png")) rmSync(new URL(name,out));
/** @type {[string,string][]} */ const V1_PAGES=[["Configuração","12-v1-configuracao"],["Regras","13-v1-regras"],["Exceções","14-v1-excecoes"],["Banco","15-v1-banco"],["Política SQL","16-v1-politica-sql"]];
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
    if (engine !== "chromium") {
      await page.getByRole("button",{name:"Ver detalhes: CRM de demonstração",exact:true}).click();
      await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
      await overview(page);await shot(page,tag+"-05-detalhe-visao");made.push(tag+"-05-detalhe-visao");
      await page.getByRole("button",{name:"Editar conexão e limites",exact:true}).click();await page.getByRole("dialog").waitFor();
      await shot(page,tag+"-17-editar-rascunho");made.push(tag+"-17-editar-rascunho");
      await page.getByRole("dialog").getByRole("button",{name:"Cancelar",exact:true}).click();
    }
    if (engine === "chromium") {
      await page.getByLabel("Buscar por nome ou alias",{exact:true}).fill("zzz");await shot(page,tag+"-04-busca-vazia");made.push(tag+"-04-busca-vazia");
      await page.getByLabel("Buscar por nome ou alias",{exact:true}).fill("");
      await page.getByRole("button",{name:"Ver detalhes: CRM de demonstração",exact:true}).click();
      await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
      await overview(page);
      await shot(page,tag+"-05-detalhe-visao");made.push(tag+"-05-detalhe-visao");
      await page.getByRole("tab",{name:"Conexão",exact:true}).click();await shot(page,tag+"-06-detalhe-conexao");made.push(tag+"-06-detalhe-conexao");
      await page.getByRole("tab",{name:"Masking",exact:true}).click();await page.waitForFunction(()=>document.querySelector("[role=tabpanel]")?.textContent?.includes("cpf"));
      assert.equal(await page.locator("[role=tabpanel] .sequence-card").count(),3);
      assert.match(String(await page.getByRole("tabpanel").textContent()),/Exceções têm prioridade/);
      assert.doesNotMatch(String(await page.getByRole("tabpanel").textContent()),/case_sensitive|hmac_sha256/);
      await shot(page,tag+"-07-detalhe-masking");made.push(tag+"-07-detalhe-masking");
      await page.getByRole("tab",{name:"Limites",exact:true}).click();await shot(page,tag+"-08-detalhe-limites");made.push(tag+"-08-detalhe-limites");
      await page.getByRole("tab",{name:"SQL",exact:true}).click();
      assert.match(String(await page.getByRole("tabpanel").textContent()),/a política padrão continua valendo/);
      await shot(page,tag+"-08b-detalhe-sql");made.push(tag+"-08b-detalhe-sql");
      // Stage 6: the registration wizard over a fictitious draft; the secret is a throwaway masked value.
      await go(page,"Novo datasource");
      const onward=()=>page.getByRole("button",{name:"Próximo",exact:true}).click();
      await page.getByLabel("Alias",{exact:true}).fill("vendas-demo");
      await page.getByLabel("Nome de apresentação",{exact:true}).fill("Vendas de demonstração");
      await shot(page,tag+"-09-cadastro-inicio");made.push(tag+"-09-cadastro-inicio");
      await onward();
      await page.getByLabel("Host",{exact:true}).fill("db-vendas.example.internal");
      await page.getByLabel("Banco",{exact:true}).fill("app_demo");
      await page.getByLabel("Usuário técnico",{exact:true}).fill("gateway_demo");
      await onward();await page.getByLabel("Senha técnica",{exact:true}).fill("fixture-"+randomBytes(6).toString("hex"));
      await onward();await onward();
      await page.getByRole("button",{name:"Adicionar regra",exact:true}).click();
      await page.getByLabel("Padrão da coluna",{exact:true}).first().fill("cpf");
      await shot(page,tag+"-09b-cadastro-politica");made.push(tag+"-09b-cadastro-politica");
      await onward();await page.getByRole("button",{name:"Testar conexão",exact:true}).click();
      await page.getByText("Conexão verificada com este rascunho",{exact:false}).waitFor();
      await shot(page,tag+"-09c-cadastro-teste");made.push(tag+"-09c-cadastro-teste");
      await onward();
      assert.match(String(await page.getByRole("region",{name:"Revisão",exact:true}).textContent()),/Informada \(não exibida\)/);
      await shot(page,tag+"-10-cadastro-revisao");made.push(tag+"-10-cadastro-revisao");
      // Leaving the wizard with a draft asks first.
      await go2(page,"Datasources");await page.getByRole("button",{name:"Descartar",exact:true}).click();
      await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
      await page.getByRole("button",{name:"Ver detalhes: CRM de demonstração",exact:true}).click();
      await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
      const box=page.getByRole("dialog");
      await page.getByRole("button",{name:"Editar conexão e limites",exact:true}).click();await box.waitFor();
      await box.getByLabel("Nome de apresentação",{exact:true}).fill("CRM de demonstração (editado)");
      await shot(page,tag+"-17-editar-rascunho");made.push(tag+"-17-editar-rascunho");
      await box.getByRole("button",{name:"Revisar e confirmar",exact:true}).click();
      await shot(page,tag+"-18-editar-revisao");made.push(tag+"-18-editar-revisao");
      next.state="conflict";await box.getByRole("button",{name:"Confirmar",exact:true}).click();
      await box.getByText("Outra sessão alterou este item",{exact:false}).waitFor();
      await shot(page,tag+"-19-conflito");made.push(tag+"-19-conflito");
      next.state="done";await box.getByRole("button",{name:"Descartar e reler",exact:true}).click();
      await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
      await page.getByRole("tab",{name:"Masking",exact:true}).click();
      await page.getByRole("button",{name:"Editar política",exact:true}).click();await box.waitFor();
      await shot(page,tag+"-20-politica-editor");made.push(tag+"-20-politica-editor");
      await box.getByRole("button",{name:"Cancelar",exact:true}).click();
      await page.getByRole("button",{name:"Remover",exact:true}).click();await box.waitFor();
      await box.getByLabel("Digite o alias para confirmar",{exact:true}).fill("crm-demo");
      await shot(page,tag+"-21-remover");made.push(tag+"-21-remover");
      await box.getByRole("button",{name:"Cancelar",exact:true}).click();await page.getByRole("button",{name:"Descartar",exact:true}).click();
      next.state="unknown";
      await page.getByRole("button",{name:"Desabilitar",exact:true}).click();await box.waitFor();
      await box.getByRole("button",{name:"Confirmar",exact:true}).click();
      await box.getByText("Resultado desconhecido",{exact:false}).waitFor();
      await shot(page,tag+"-22-resultado-desconhecido");made.push(tag+"-22-resultado-desconhecido");
      next.state="done";await box.getByRole("button",{name:"Fechar",exact:true}).click();
      await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
      await go(page,"Datasources");
      await page.getByRole("button",{name:"Ver detalhes: Legado desabilitado",exact:true}).click();
      await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent !== "Carregando…");
      assert.match(String(await page.getByRole("tabpanel").textContent()),/Desabilitado.*Não publicado.*Nenhuma/s);
      await shot(page,tag+"-05b-detalhe-desabilitado");made.push(tag+"-05b-detalhe-desabilitado");
      await go(page,"Visão geral");await shot(page,tag+"-11-politica-v1");made.push(tag+"-11-politica-v1");
      // The other Política v1 readings (Configuração, Regras, Exceções, Banco, Política SQL).
      for (const [label,slug] of V1_PAGES) { await go(page,label);await shot(page,tag+"-"+slug);made.push(tag+"-"+slug); }
    }
    await context.close();
  }
  if (engine === "chromium") {
    for (const [mode,width] of /** @type {const} */ ([["empty",1280],["off",1280],["blocked",1280],["off",320],["blocked",320]])) {
      const context=await browser.newContext({viewport:{width,height:width === 320 ? 900 : 860},colorScheme:"light",reducedMotion:"reduce",locale:"pt-BR"});
      const page=await context.newPage();await serve(page,mode);
      await page.goto(origin+"/admin/ui");await enter(page);
      if (mode === "blocked") {
        await go(page,"Painel");
        assert.equal(await page.locator(".signals .flag.off").count(),2);
        const board="chromium-estado-painel-bloqueado"+(width === 320 ? "-320" : "");
        await shot(page,board);made.push(board);
      }
      if (mode !== "off") await go(page,"Datasources"); else await go(page,"Painel");
      const name="chromium-estado-"+(mode === "empty" ? "vazio" : mode === "off" ? "catalogo-desligado" : "catalogo-bloqueado")+(width === 320 ? "-320" : "");
      await shot(page,name);made.push(name);
      await context.close();
    }
  }
  if (engine === "chromium") {
    for (const [theme,width] of /** @type {const} */ ([["light",1280],["light",320]])) {
      const context=await browser.newContext({viewport:{width,height:width === 320 ? 900 : 860},colorScheme:theme,reducedMotion:"reduce",locale:"pt-BR"});
      const page=await context.newPage();await serve(page,"unadopted");
      await page.goto(origin+"/admin/ui");await enter(page);
      for (const [label,slug] of /** @type {[string,string][]} */ ([["Visão geral","v1-nao-adotada-visao"],["Regras","v1-nao-adotada-regras"]])) {
        await go(page,label);const name="chromium-estado-"+slug+(width === 320 ? "-320" : "");await shot(page,name);made.push(name);
      }
      await context.close();
    }
  }
  await browser.close();
}
console.log("Reference captures:",made.length);
