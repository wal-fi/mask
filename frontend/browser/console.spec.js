import { test, expect } from "@playwright/test";
import { scenario, requireTrue } from "./harness.js";

// Phase 9, Stage 5: read-only Admin UX v2 against the real composition root,
// a real encrypted catalog with fictitious datasources and PostgreSQL 16.
/** @param {string} name */
function engine(name) { if(name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");return name; }
/** @param {import("@playwright/test").Page} page */
async function ready(page) {await expect.poll(async()=> (await page.getByRole("status").textContent())?.startsWith("Respondendo")).toBe(true);}
/** @param {import("@playwright/test").Page} page @param {string} origin @param {string} token */
async function enter(page,origin,token) {await page.goto(origin+"/admin/ui");await page.getByLabel("Token",{exact:true}).fill(token);await page.getByRole("button",{name:"Entrar",exact:true}).click();await ready(page);}
/** @param {import("@playwright/test").Page} page @param {string} name */
async function navigate(page,name) {
  // Narrow screens keep the single navigation behind an explicit disclosure control.
  const menu=page.getByRole("button",{name:/^Menu: /});
  if(await menu.isVisible()) await menu.click();
  await page.getByRole("navigation").getByRole("button",{name,exact:true}).click();
}
const CANARY="upstream-browser-canary-6d1f";
/** Token, upstream secret and admin state never reach URL, storage, attributes or text.
 * @param {import("@playwright/test").Page} page @param {string} token
 */
async function clean(page,token) {
  requireTrue(await page.evaluate(async ({key,canary})=>{
    const attrs=Array.from(document.querySelectorAll("*")).flatMap(e=>Array.from(e.attributes).map(a=>a.value));
    const text=document.documentElement.textContent ?? "";
    return !text.includes(key) && !text.includes(canary) && !attrs.some(a=>a.includes(key) || a.includes(canary))
      && !location.href.includes(key) && location.hash === "" && location.search === "" && history.state === null
      && localStorage.length===0 && sessionStorage.length===0 && document.cookie==="" && (await caches.keys()).length===0;
  },{key:token,canary:CANARY}),"clean");
}
/** @param {import("@playwright/test").Page} page @param {string} token */
function watch(page,token) {
  const seen={writes:0,leak:false,second:0};
  page.on("request",r=>{
    const url=new URL(r.url());
    if(url.pathname.startsWith("/admin/v") && r.method() !== "GET") seen.writes++;
    if(url.pathname.startsWith("/admin/v2/")) seen.second++;
    if(url.href.includes(token) || (r.postData() ?? "").includes(token)) seen.leak=true;
  });
  page.on("console",m=>{if(m.text().includes(token) || m.text().includes(CANARY)) seen.leak=true;});
  return seen;
}
const catalog={MASKGW_BROWSER_CONSOLE:"1"};

test("console: landing, list, search, detail tabs by keyboard, prototype and logout, GET only",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    requireTrue(await page.getByRole("heading",{name:"Painel",exact:true}).evaluate(e=>e===document.activeElement),"landing focus");
    requireTrue(await page.getByRole("navigation").count() === 1 && await page.getByRole("status").count() === 1,"one landmark");
    const cards=page.locator("dl.cards");
    requireTrue((await cards.textContent())?.includes("Datasources cadastrados") === true,"cards");
    requireTrue(await cards.locator("dd").first().textContent() === "3","total");
    await clean(page,token);

    await navigate(page,"Datasources");await ready(page);
    requireTrue(await page.getByRole("heading",{name:"Datasources",exact:true}).evaluate(e=>e===document.activeElement),"list focus");
    requireTrue(await page.locator("tbody tr").count() === 3,"rows");
    const search=page.getByLabel("Buscar por nome ou alias",{exact:true});
    await search.fill("finan");requireTrue(await page.locator("tbody tr").count() === 1,"search one");
    await search.fill("zzz");requireTrue((await page.getByText("Nenhum datasource corresponde à busca.",{exact:true}).count()) === 1,"search none");
    await search.fill("");requireTrue(await page.locator("tbody tr").count() === 3,"search reset");

    const before=seen.second;
    await page.getByRole("button",{name:"Ver detalhes: CRM de demonstração",exact:true}).click();await ready(page);
    requireTrue(seen.second === before+1,"one item read");
    requireTrue(await page.getByRole("heading",{name:"CRM de demonstração",exact:true}).evaluate(e=>e===document.activeElement),"detail focus");
    const tabs=page.getByRole("tab");requireTrue(await tabs.count() === 5,"tabs");
    const overview=page.getByRole("tabpanel");
    requireTrue(JSON.stringify(await overview.locator("h3").allTextContents()) === JSON.stringify(["Identidade","Estado no Gateway","Atividade do runtime","Última verificação de conexão"]),"overview groups");
    requireTrue(await overview.locator(".flag.neutral",{hasText:"Nunca verificado"}).count() === 1,"never checked is neutral");
    requireTrue(await overview.getByText("CRM de demonstração",{exact:true}).count() === 0,"name not repeated");
    await tabs.first().focus();await page.keyboard.press("ArrowRight");
    requireTrue(await page.getByRole("tab",{name:"Conexão",exact:true}).evaluate(e=>e===document.activeElement && e.getAttribute("aria-selected") === "true"),"arrow tab");
    const body=page.getByRole("tabpanel");
    requireTrue((await body.textContent())?.includes("db-crm.example.internal") === true,"connection host");
    requireTrue((await body.textContent())?.includes("Credencial configurada") === true,"credential state");
    requireTrue((await body.textContent())?.includes("Nenhum host público autorizado.") === true,"destinations explained");
    await page.keyboard.press("ArrowRight");
    await expect.poll(async()=>(await body.textContent())?.includes("HMAC-SHA-256")).toBe(true);
    requireTrue(await body.getByRole("listitem").count() === 3,"two ordered rules and one exception");
    requireTrue((await body.textContent())?.includes("Exceções têm prioridade") === true,"precedence explained");
    requireTrue((await body.textContent())?.includes("O nome da coluna contém o padrão") === true,"matching explained");
    requireTrue((await body.textContent())?.includes("case_sensitive") === false,"internal key hidden");
    await page.keyboard.press("End");
    requireTrue(await page.getByRole("tab",{name:"SQL",exact:true}).evaluate(e=>e===document.activeElement),"end tab");
    await expect.poll(async()=>(await body.textContent())?.includes("dblink_exec")).toBe(true);
    requireTrue((await body.textContent())?.includes("Nenhuma função adicional; a política padrão continua valendo.") === true,"empty additions explained");
    requireTrue((await body.textContent())?.includes("vale o menor") === true,"policy limits related to the effective ones");
    await page.keyboard.press("Home");
    requireTrue(await page.getByRole("tab",{name:"Visão geral",exact:true}).evaluate(e=>e.getAttribute("aria-selected") === "true"),"home tab");
    await clean(page,token);
    await page.getByRole("button",{name:"Voltar para a lista",exact:true}).click();await ready(page);
    requireTrue(await page.locator("tbody tr").count() === 3,"back");

    // Phase 9, Stage 6: the wizard is real; it reads the list once and writes nothing by itself.
    const beforeGuide=seen.second;
    await navigate(page,"Novo datasource");
    await expect(page.getByRole("region",{name:"Identificação",exact:true})).toBeVisible();
    requireTrue((await page.getByRole("note").textContent())?.includes("nunca é exibida de novo") === true,"banner");
    requireTrue(await page.getByLabel("Alias",{exact:true}).isVisible(),"real fields");
    await page.getByRole("button",{name:"Próximo",exact:true}).click();
    requireTrue(await page.getByText("Obrigatório.",{exact:true}).first().isVisible(),"required stays");
    requireTrue(await page.getByRole("region",{name:"Identificação",exact:true}).isVisible(),"no step without required fields");
    requireTrue(seen.second === beforeGuide+1 && seen.writes === 0,"one list read, no write");

    await page.getByRole("button",{name:"Tema: automático",exact:true}).click();
    requireTrue(await page.evaluate(()=>document.documentElement.dataset.theme) === "dark","dark");
    await page.getByRole("button",{name:"Tema: escuro",exact:true}).click();
    requireTrue(await page.evaluate(()=>document.documentElement.dataset.theme) === "light","light");

    await navigate(page,"Visão geral");await ready(page);
    requireTrue(await page.getByRole("heading",{name:"Visão geral",exact:true}).count() === 1,"v1 in shell");
    await page.getByRole("button",{name:"Sair",exact:true}).click();
    requireTrue(await page.getByRole("navigation").count() === 0,"logout");
    await clean(page,token);
    requireTrue(seen.writes === 0 && !seen.leak,"GET only, no leak");
  },catalog);
});

test("console: empty catalog guides without inventing data",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    await navigate(page,"Datasources");await ready(page);
    requireTrue(await page.getByText("Nenhum datasource cadastrado.",{exact:false}).count() === 1,"empty");
    requireTrue(await page.locator("table").count() === 0,"no table");
    requireTrue(seen.writes === 0 && !seen.leak,"GET only");
  },{...catalog,MASKGW_BROWSER_CATALOG:"empty"});
});

test("console: removed item and blocked catalog are explained, not guessed",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    await navigate(page,"Datasources");await ready(page);
    await page.getByRole("button",{name:"Ver detalhes: Financeiro de demonstração",exact:true}).click();await ready(page);
    await command("remove");
    await page.getByRole("button",{name:"Atualizar",exact:true}).click();
    await expect.poll(async()=>await page.getByRole("status").textContent()).toBe("Este datasource não existe mais. Volte para a lista e releia.");
    await command("block");
    await page.getByRole("button",{name:"Voltar para a lista",exact:true}).click();
    await expect.poll(async()=>(await page.getByRole("status").textContent())?.startsWith("O catálogo está indisponível")).toBe(true);
    await navigate(page,"Painel");await ready(page);
    const cards=page.locator("dl.cards");
    await expect.poll(async()=>(await cards.textContent())?.includes("Não informado")).toBe(true);
    requireTrue(seen.writes === 0 && !seen.leak,"GET only");
    await clean(page,token);
  },catalog);
});

const DETAIL_TABS=["Visão geral","Conexão","Masking","Limites","SQL"];
/** Relative luminance contrast, WCAG 2.x. */
const contrastScript=()=>{
  /** @param {string} value */
  const rgb=value=>{const m=value.match(/\d+(\.\d+)?/g)?.map(Number) ?? [0,0,0];return m.slice(0,3);};
  /** @param {number[]} c */
  const lum=c=>{const [r,g,b]=c.map(v=>{const s=(v ?? 0)/255;return s<=0.03928 ? s/12.92 : ((s+0.055)/1.055)**2.4;});return 0.2126*(r ?? 0)+0.7152*(g ?? 0)+0.0722*(b ?? 0);};
  /** @param {string} a @param {string} b */
  const ratio=(a,b)=>{const x=lum(rgb(a)),y=lum(rgb(b));return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);};
  /** @param {Element | null} node */
  const back=node=>{let n=node;while(n instanceof Element){const c=getComputedStyle(n).backgroundColor;if(!/rgba\(0, 0, 0, 0\)|transparent/.test(c)) return c;n=n.parentElement;}return getComputedStyle(document.body).backgroundColor;};
  /** @type {number[]} */ const found=[];
  for(const node of Array.from(document.querySelectorAll("main h1, main h2, main h3, nav button, .group, dt, dd, th, td, p, li, code, .flag, .tools button, .toolbar button, [role=tab]"))) {
    if(!(node instanceof HTMLElement) || !node.offsetParent || !node.textContent?.trim()) continue;
    found.push(ratio(getComputedStyle(node).color,back(node)));
  }
  return Math.min(...found);
};

test("console: 320 CSS px, 200% zoom, reduced motion, both themes and AA contrast",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.emulateMedia({reducedMotion:"reduce"});
    await enter(page,origin,token);
    for(const {width,height} of [{width:320,height:640},{width:640,height:720},{width:1280,height:800}]) {
      await page.setViewportSize({width,height});
      for(const place of ["Painel","Datasources","Novo datasource"]) {
        await navigate(page,place);
        if(place !== "Novo datasource") await ready(page);
        requireTrue(await page.evaluate(()=>document.documentElement.scrollWidth <= document.documentElement.clientWidth+1),"reflow "+width+" "+place);
      }
      await navigate(page,"Datasources");await ready(page);
      await page.getByRole("button",{name:"Ver detalhes: CRM de demonstração",exact:true}).click();await ready(page);
      for(const name of DETAIL_TABS) {
        await page.getByRole("tab",{name,exact:true}).click();
        await expect.poll(async()=>(await page.getByRole("tabpanel").textContent())?.includes("Carregando…")).toBe(false);
        requireTrue(await page.evaluate(()=>document.documentElement.scrollWidth <= document.documentElement.clientWidth+1),"reflow detail "+width+" "+name);
      }
    }
    requireTrue(await page.getByRole("button",{name:"Sair",exact:true}).evaluate(e=>getComputedStyle(e).transitionDuration.split(",").every(v=>parseFloat(v)===0)),"reduced motion");
    await page.setViewportSize({width:1280,height:800});
    for(const theme of ["light","dark"]) {
      await page.evaluate(value=>{document.documentElement.dataset.theme=value;},theme);
      for(const place of ["Painel","Datasources","Novo datasource"]) {
        await navigate(page,place);if(place !== "Novo datasource") await ready(page);
        const minimum=await page.evaluate(contrastScript);
        requireTrue(minimum >= 4.5,"contrast "+theme+" "+place+" "+minimum.toFixed(2));
      }
      // Grouped detail tabs: notes, pills, identifiers and metric cards.
      await navigate(page,"Datasources");await ready(page);
      await page.getByRole("button",{name:"Ver detalhes: CRM de demonstração",exact:true}).click();await ready(page);
      for(const name of DETAIL_TABS) {
        await page.getByRole("tab",{name,exact:true}).click();
        await expect.poll(async()=>(await page.getByRole("tabpanel").textContent())?.includes("Carregando…")).toBe(false);
        const minimum=await page.evaluate(contrastScript);
        requireTrue(minimum >= 4.5,"contrast "+theme+" detail "+name+" "+minimum.toFixed(2));
      }
    }
    for(const scheme of /** @type {const} */ (["dark","light"])) {
      await page.evaluate(()=>{delete document.documentElement.dataset.theme;});
      await page.emulateMedia({colorScheme:scheme,reducedMotion:"reduce"});
      const background=await page.evaluate(()=>getComputedStyle(document.body).backgroundColor);
      requireTrue(scheme === "dark" ? background === "rgb(15, 20, 27)" : background === "rgb(244, 246, 249)","system "+scheme);
    }
  },catalog);
});

test("console: narrow screens show content first and keep a labelled, keyboard-operable menu",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.setViewportSize({width:320,height:640});
    await enter(page,origin,token);
    const menu=page.getByRole("button",{name:"Menu: Painel",exact:true});
    requireTrue(await menu.isVisible() && await menu.getAttribute("aria-expanded") === "false","menu closed");
    requireTrue(await page.getByRole("navigation").isHidden(),"nav collapsed");
    const title=await page.getByRole("heading",{name:"Painel",exact:true}).boundingBox();
    requireTrue(title !== null && title.y < 640*0.6,"content in the first screen");
    await menu.focus();await page.keyboard.press("Enter");
    requireTrue(await menu.getAttribute("aria-expanded") === "true" && await page.getByRole("navigation").isVisible(),"menu open");
    requireTrue(await page.getByRole("navigation").getByRole("button").first().evaluate(e=>e===document.activeElement),"focus into menu");
    await page.keyboard.press("Escape");
    requireTrue(await menu.evaluate(e=>e===document.activeElement) && await menu.getAttribute("aria-expanded") === "false","escape");
    await menu.press("Enter");
    await page.getByRole("navigation").getByRole("button",{name:"Datasources",exact:true}).press("Enter");await ready(page);
    requireTrue(await page.getByRole("heading",{name:"Datasources",exact:true}).evaluate(e=>e===document.activeElement),"title focus");
    requireTrue(await page.getByRole("button",{name:"Menu: Datasources",exact:true}).getAttribute("aria-expanded") === "false","closed after choice");
    await page.setViewportSize({width:1280,height:800});
    // WebKit may apply the new media query a frame later: wait for the state, not for time.
    await expect.poll(async()=>await page.getByRole("navigation").isVisible() && await page.getByRole("button",{name:/^Menu: /}).isHidden()).toBe(true);
  },catalog);
});

// Política v1: each approved reading in Portuguese groups; secrets only as states.
const V1_PAGES=/** @type {Record<string,string[]>} */ ({"Visão geral":["Configuração em uso","Atividade desde o início do processo","Runtime","Segredos"],
  "Configuração":["Estado","Regras de masking","Exceções","Limites do banco","SQL"],"Regras":["Estado","Regras de masking"],"Exceções":["Estado","Exceções cadastradas"],
  "Banco":["Limites declarados","Estado"],"Política SQL":["Como cada coluna é tratada","Validação do SQL","Funções e relações","Sessão no PostgreSQL","Edição"]});
const V1_RAW=["adopted","counters","admin_operations_total","queries_total","retired_runtimes_open","secrets","admin_token","database_dsn","hmac_sha256_key",
  "configured","missing","validator_rules","unmatched_policy","pg_namespace_default","denied_relations","statement_timeout_enforced_by",
  "provenance_capability_required","case_sensitive","Proteção efetiva"];
const HMAC_TEST="chave-de-teste-para-hmac-com-tamanho-suficiente";
test("política v1: grouped readings, secret states only, focus, contrast and reflow in both themes",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    const dsn=process.env.MASKGW_TEST_DSN ?? "";
    let password="";try {password=decodeURIComponent(new URL(dsn).password);} catch {password="";}
    for(const theme of ["light","dark"]) {
      await page.evaluate(value=>{document.documentElement.dataset.theme=value;},theme);
      for(const width of [320,1280]) {
        await page.setViewportSize({width,height:800});
        // WebKit may apply the media query a frame later: wait for the matching layout.
        await expect.poll(async()=>await page.getByRole("button",{name:/^Menu: /}).isVisible()).toBe(width < 768);
        for(const [index,[label,groups]] of Object.entries(V1_PAGES).entries()) {
          await navigate(page,label);await ready(page);
          requireTrue(await page.getByRole("heading",{name:label,exact:true}).count() === 1,"v1 unique title "+index);
          requireTrue(await page.getByRole("heading",{name:label,exact:true}).evaluate(e=>e===document.activeElement),"v1 focus "+index);
          const region=page.getByRole("region",{name:"Leitura",exact:true});
          requireTrue(JSON.stringify(await region.locator(".facet > h3").allTextContents()) === JSON.stringify(groups),"v1 groups "+index);
          const text=(await region.textContent()) ?? "";
          requireTrue(V1_RAW.every(word=>!text.includes(word)),"v1 raw names "+index);
          requireTrue(!text.includes(HMAC_TEST) && (!password || !text.includes(password)) && (!dsn || !text.includes(dsn)),"v1 secret "+index);
          requireTrue(await page.evaluate(()=>document.documentElement.scrollWidth <= document.documentElement.clientWidth+1),"v1 reflow "+width+" "+index);
          const minimum=await page.evaluate(contrastScript);
          requireTrue(minimum >= 4.5,"v1 contrast "+theme+" "+width+" "+index+" "+minimum.toFixed(2));
        }
      }
    }
    await navigate(page,"Visão geral");await ready(page);
    const states=await page.getByRole("region",{name:"Leitura",exact:true}).locator(".facet",{hasText:"Segredos"}).locator(".flag").allTextContents();
    requireTrue(states.length === 3 && states.every(s=>/^(✓ Configurado|✕ Ausente|○ Ausente)$/.test(s)),"secret states only");
    await clean(page,token);
    requireTrue(seen.writes === 0 && !seen.leak,"GET only, no leak");
  },catalog);
});

test("console: keyboard reaches every navigation entry and returns focus to titles",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await enter(page,origin,token);
    const entries=["Painel","Datasources","Novo datasource","Visão geral","Configuração","Regras","Exceções","Banco","Política SQL"];
    requireTrue(await page.getByRole("navigation").getByRole("button").count() === entries.length,"entries");
    await page.getByRole("navigation").getByRole("button",{name:"Painel",exact:true}).focus();
    for(const label of entries.slice(1)) {
      await page.keyboard.press("Tab");
      requireTrue(await page.getByRole("button",{name:label,exact:true}).evaluate(e=>e===document.activeElement),"tab "+label);
    }
    for(const label of ["Datasources","Novo datasource","Painel"]) {
      const button=page.getByRole("navigation").getByRole("button",{name:label,exact:true});await button.focus();await page.keyboard.press("Enter");
      // Stage 6: the wizard reads the list (catalog stamp) like the other entries.
      if(label !== "Novo datasource") await ready(page);
      else await expect(page.getByRole("region",{name:"Identificação",exact:true})).toBeVisible();
      requireTrue(await page.getByRole("heading",{level:2}).first().evaluate(e=>e===document.activeElement),"title focus "+label);
      requireTrue(await button.getAttribute("aria-current") === "page","current "+label);
    }
  },catalog);
});

test("without the catalog the shell lands on the first-prefix overview and explains the second",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    requireTrue(await page.getByRole("heading",{name:"Visão geral",exact:true}).count() === 1,"fallback");
    await navigate(page,"Painel");
    await expect.poll(async()=>(await page.getByRole("status").textContent())?.startsWith("O catálogo de datasources não está habilitado")).toBe(true);
    requireTrue(seen.writes === 0 && !seen.leak,"GET only");
  },{MASKGW_BROWSER_READ_ONLY:"1"});
});
