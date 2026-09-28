import { test, expect } from "@playwright/test";
import { scenario, requireTrue } from "./harness.js";

// Phase 9, Stage 6: visual CRUD of datasources and policies against the real
// composition root, the real encrypted catalog and the approved /admin/v2 writes.
// Upstream adapters are doubles; every write is the browser's own request.
/** @param {string} name */
function engine(name) { if(name !== "chromium" && name !== "firefox" && name !== "webkit") throw new Error("Engine refused.");return name; }
/** Status line after a read; a write's result may precede it. @param {import("@playwright/test").Page} page */
async function ready(page) {await expect.poll(async()=> (await page.getByRole("status").first().textContent())?.includes("Respondendo")).toBe(true);}
/** @param {import("@playwright/test").Page} page @param {string} origin @param {string} token */
async function enter(page,origin,token) {await page.goto(origin+"/admin/ui");await page.getByLabel("Token",{exact:true}).fill(token);await page.getByRole("button",{name:"Entrar",exact:true}).click();await ready(page);}
/** @param {import("@playwright/test").Page} page @param {string} name */
async function navigate(page,name) {
  const menu=page.getByRole("button",{name:/^Menu: /});
  if(await menu.isVisible()) await menu.click();
  await page.getByRole("navigation").getByRole("button",{name,exact:true}).click();
}
/** @param {import("@playwright/test").Page} page @param {string} name */
async function openItem(page,name) {
  await navigate(page,"Datasources");await ready(page);
  await page.getByRole("button",{name:"Ver detalhes: "+name,exact:true}).click();await ready(page);
}
/** The action bar of the detail (outside any dialog). @param {import("@playwright/test").Page} page @param {string} name */
function act(page,name) {return page.getByRole("region",{name:"Leitura",exact:true}).getByRole("group",{name:"Ações"}).getByRole("button",{name,exact:true});}
/** @param {import("@playwright/test").Page} page */
function dialog(page) {return page.getByRole("dialog");}
/** A write ended: the dialog is gone and its result opens the status line.
 * @param {import("@playwright/test").Page} page @param {string} text
 */
async function landed(page,text) {
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(async()=> (await page.getByRole("status").first().textContent())?.startsWith(text)).toBe(true);
}
/** @param {import("@playwright/test").Page} page @param {string} text */
async function says(page,text) {await expect.poll(async()=> (await dialog(page).getByRole("status").textContent())?.includes(text)).toBe(true);}

const CADASTRO="senha-cadastro-6e1a", ROTACAO="senha-rotacao-9c3b", CANARY="upstream-browser-canary-6d1f";
const writing={MASKGW_BROWSER_CONSOLE:"1",MASKGW_BROWSER_WRITE:"1"};
// A stuck action is a failure with its source line, never a silent wait.
test.use({actionTimeout:15000});

/** Token, typed passwords and the upstream secret never reach URL, storage, attributes, text or inputs.
 * @param {import("@playwright/test").Page} page @param {string} token
 */
async function clean(page,token) {
  requireTrue(await page.evaluate(async secrets=>{
    const attrs=Array.from(document.querySelectorAll("*")).flatMap(e=>Array.from(e.attributes).map(a=>a.value));
    const text=document.documentElement.textContent ?? "";
    const inputs=Array.from(document.querySelectorAll("input,textarea")).map(i=>i instanceof HTMLInputElement || i instanceof HTMLTextAreaElement ? i.value : "");
    return secrets.every(s=>!text.includes(s) && !attrs.some(a=>a.includes(s)) && !inputs.some(v=>v.includes(s)) && !location.href.includes(s))
      && location.hash === "" && location.search === "" && history.state === null
      && localStorage.length === 0 && sessionStorage.length === 0 && document.cookie === "" && (await caches.keys()).length === 0;
  },[token,CADASTRO,ROTACAO,CANARY]),"clean");
}
/** Every write request; the token only in the header, never in URL or body.
 * @param {import("@playwright/test").Page} page @param {string} token
 */
function watch(page,token) {
  /** @type {{method:string,path:string,body:string}[]} */ const writes=[];const seen={leak:false,writes};
  page.on("request",r=>{
    const url=new URL(r.url());
    if(url.pathname.startsWith("/admin/v") && r.method() !== "GET") writes.push({method:r.method(),path:url.pathname,body:r.postData() ?? ""});
    if(url.href.includes(token) || (r.postData() ?? "").includes(token)) seen.leak=true;
  });
  page.on("console",m=>{if([token,CADASTRO,ROTACAO,CANARY].some(s=>m.text().includes(s))) seen.leak=true;});
  return seen;
}

test("registration wizard: draft test, write-only password, review and explicit confirmation",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    await navigate(page,"Datasources");await ready(page);
    await page.getByRole("region",{name:"Leitura",exact:true}).getByRole("button",{name:"Novo datasource",exact:true}).click();
    await expect(page.getByRole("region",{name:"Identificação",exact:true})).toBeVisible();
    const next=()=>page.getByRole("button",{name:"Próximo",exact:true}).click();
    await page.getByLabel("Alias",{exact:true}).fill("novo-demo");
    await page.getByLabel("Nome de apresentação",{exact:true}).fill("Novo de demonstração");
    await next();
    // Moving on is refused while a required field is empty, with the reason on the field.
    await next();
    requireTrue(await page.getByText("Obrigatório.",{exact:true}).first().isVisible(),"required on the field");
    await page.getByLabel("Host",{exact:true}).fill("db-novo.example.internal");
    await page.getByLabel("Banco",{exact:true}).fill("app_demo");
    await page.getByLabel("Usuário técnico",{exact:true}).fill("gateway_novo");
    await next();
    const secret=page.getByLabel("Senha técnica",{exact:true});
    requireTrue(await secret.getAttribute("type") === "password" && await secret.getAttribute("autocomplete") === "new-password","masked secret");
    await secret.fill(CADASTRO);
    await next();await next();await next();
    await page.getByRole("button",{name:"Testar conexão",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("region",{name:"Teste",exact:true}).textContent())?.includes("Conexão verificada")).toBe(true);
    requireTrue(seen.writes.length === 1 && seen.writes[0]?.path === "/admin/v2/datasources:test","one draft test");
    requireTrue(!JSON.parse(seen.writes[0]?.body ?? "{}").expected_catalog_revision,"test carries no stamp");
    await command("expect-absent:novo-demo");
    await next();
    const review=page.getByRole("region",{name:"Revisão",exact:true});
    requireTrue((await review.textContent())?.includes("Informada (não exibida)") === true,"secret not repeated");
    await clean(page,token);
    await review.getByRole("button",{name:"Cadastrar datasource",exact:true}).click();
    await expect(page.getByRole("heading",{name:"Novo de demonstração",exact:true})).toBeVisible();
    requireTrue(seen.writes.length === 2 && seen.writes[1]?.method === "POST" && seen.writes[1]?.path === "/admin/v2/datasources","one registration");
    await command("expect-enabled:novo-demo");await command("expect-secret:"+CADASTRO);
    await clean(page,token);
    requireTrue(!seen.leak,"no leak");
  },writing);
});

test("edit, password rotation, test, disable, enable and removal confirmed by alias",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    await openItem(page,"CRM de demonstração");
    await act(page,"Editar conexão e limites").click();
    await dialog(page).getByLabel("Nome de apresentação",{exact:true}).fill("CRM editado");
    await dialog(page).getByRole("button",{name:"Revisar e confirmar",exact:true}).click();
    requireTrue((await dialog(page).textContent())?.includes("CRM editado") === true,"review shows the draft");
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();
    await expect(page.getByRole("heading",{name:"CRM editado",exact:true})).toBeVisible();
    await expect.poll(async()=> (await page.getByRole("status").first().textContent())?.startsWith("Datasource atualizado.")).toBe(true);

    await act(page,"Trocar senha").click();
    await dialog(page).getByLabel("Senha técnica",{exact:true}).fill(ROTACAO);
    await dialog(page).getByRole("button",{name:"Revisar e confirmar",exact:true}).click();
    requireTrue((await dialog(page).textContent())?.includes("Informada (não exibida)") === true,"rotation review hides the secret");
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();await landed(page,"Senha trocada.");
    await command("expect-secret:"+ROTACAO);
    await clean(page,token);

    await act(page,"Testar conexão").click();
    await dialog(page).getByRole("button",{name:"Testar conexão",exact:true}).click();
    await says(page,"Conexão verificada");
    await dialog(page).getByRole("button",{name:"Fechar",exact:true}).click();await ready(page);

    await act(page,"Desabilitar").click();
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();await landed(page,"Datasource desabilitado.");
    await command("expect-disabled:crm-demo");
    requireTrue(await act(page,"Habilitar").isVisible() && await act(page,"Testar conexão").count() === 0,"disabled offers enable, not test");
    await act(page,"Habilitar").click();
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();await landed(page,"Datasource habilitado.");
    await command("expect-enabled:crm-demo");

    await act(page,"Remover").click();
    const typed=dialog(page).getByLabel("Digite o alias para confirmar",{exact:true});
    await typed.fill("crm");
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();
    await says(page,"não confere");
    await command("expect-present:crm-demo");
    await typed.fill("crm-demo");
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();await ready(page);
    await expect(page.getByRole("heading",{name:"Datasources",exact:true})).toBeVisible();
    requireTrue(await page.getByRole("button",{name:"Ver detalhes: CRM editado",exact:true}).count() === 0,"removed from the list");
    await command("expect-absent:crm-demo");
    const methods=seen.writes.map(w=>w.method+" "+w.path.replace(/dso_[0-9a-f]{32}/,"{id}"));
    requireTrue(JSON.stringify(methods) === JSON.stringify(["PUT /admin/v2/datasources/{id}","POST /admin/v2/datasources/{id}:rotate-credential","POST /admin/v2/datasources/{id}:test",
      "POST /admin/v2/datasources/{id}:disable","POST /admin/v2/datasources/{id}:enable","DELETE /admin/v2/datasources/{id}","DELETE /admin/v2/datasources/{id}"]),"exact writes, no retry");
    requireTrue(!seen.leak,"no leak");await clean(page,token);
  },writing);
});

test("policy editor: visible order, keyboard reorder and transformer parameters",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    await openItem(page,"Financeiro de demonstração");
    await page.getByRole("tab",{name:"Masking",exact:true}).click();
    await expect(page.getByRole("tabpanel").getByRole("button",{name:"Editar política",exact:true})).toBeVisible();
    await page.getByRole("tabpanel").getByRole("button",{name:"Editar política",exact:true}).click();
    const box=dialog(page);
    await box.getByRole("button",{name:"Mover para cima: Regra 2",exact:true}).focus();
    await page.keyboard.press("Enter");
    // At the top "up" is disabled, so focus stays on the same rule's "down".
    requireTrue(await box.getByRole("button",{name:"Mover para baixo: Regra 1",exact:true}).evaluate(e=>e===document.activeElement),"focus follows the moved rule");
    requireTrue(await box.getByRole("button",{name:"Mover para cima: Regra 1",exact:true}).isDisabled(),"no move past the top");
    await box.getByRole("button",{name:"Adicionar regra",exact:true}).click();
    const third=box.getByRole("group",{name:"Regra 3",exact:true});
    await third.getByLabel("Padrão da coluna",{exact:true}).fill("telefone");
    await third.getByLabel("Transformação",{exact:true}).selectOption("truncate");
    await third.getByLabel("Comprimento",{exact:true}).fill("4");
    await box.getByLabel("Funções negadas adicionalmente",{exact:true}).fill("dblink_exec\npg_sleep");
    await box.getByRole("button",{name:"Revisar e confirmar",exact:true}).click();
    await box.getByRole("button",{name:"Confirmar",exact:true}).click();await landed(page,"Política gravada.");
    const sent=JSON.parse(seen.writes.at(-1)?.body ?? "{}");
    requireTrue(JSON.stringify(sent.policy.masking.map((/** @type {{match:string}} */ r)=>r.match)) === JSON.stringify(["email","cpf","telefone"]),"order sent");
    requireTrue(JSON.stringify(sent.policy.masking[2].config) === JSON.stringify({length:4}),"only visible parameters");
    requireTrue(!("allowed_pg_functions" in sent.policy.sql),"protected list never sent");
    await page.getByRole("tab",{name:"Masking",exact:true}).click();
    await expect.poll(async()=> (await page.getByRole("tabpanel").textContent())?.includes("telefone")).toBe(true);
    const text=(await page.getByRole("tabpanel").textContent()) ?? "";
    requireTrue(text.indexOf("email") < text.indexOf("cpf"),"new order read back");
    requireTrue(!seen.leak,"no leak");
  },writing);
});

test("two sessions: a stale draft conflicts once, stays preserved and is never rebased",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    const other=await page.context().newPage();await enter(other,origin,token);
    await openItem(page,"CRM de demonstração");await openItem(other,"CRM de demonstração");
    await act(page,"Editar conexão e limites").click();
    await dialog(page).getByLabel("Nome de apresentação",{exact:true}).fill("Nome da sessão A");
    await dialog(page).getByRole("button",{name:"Revisar e confirmar",exact:true}).click();
    await act(other,"Editar conexão e limites").click();
    await dialog(other).getByLabel("Nome de apresentação",{exact:true}).fill("Nome da sessão B");
    await dialog(other).getByRole("button",{name:"Revisar e confirmar",exact:true}).click();
    await dialog(other).getByRole("button",{name:"Confirmar",exact:true}).click();await landed(other,"Datasource atualizado.");
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();
    await says(page,"Outra sessão alterou este item");await says(page,"Versão atual:");
    requireTrue(seen.writes.filter(w=>w.method === "PUT").length === 1,"no automatic retry");
    await dialog(page).getByRole("button",{name:"Voltar ao rascunho",exact:true}).click();
    requireTrue(await dialog(page).getByLabel("Nome de apresentação",{exact:true}).inputValue() === "Nome da sessão A","draft preserved");
    await dialog(page).getByRole("button",{name:"Cancelar",exact:true}).click();
    await page.getByRole("button",{name:"Descartar",exact:true}).click();
    await page.getByRole("button",{name:"Atualizar",exact:true}).click();await ready(page);
    await expect(page.getByRole("heading",{name:"Nome da sessão B",exact:true})).toBeVisible();
    await other.close();
  },writing);
});

test("refused candidates keep the draft; a lost answer blocks writes until a fresh read",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    await openItem(page,"CRM de demonstração");
    await command("connect-fail");
    await act(page,"Trocar senha").click();
    await dialog(page).getByLabel("Senha técnica",{exact:true}).fill(ROTACAO);
    await dialog(page).getByRole("button",{name:"Revisar e confirmar",exact:true}).click();
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();
    await says(page,"A conexão com o PostgreSQL falhou");
    requireTrue(await dialog(page).getByLabel("Senha técnica",{exact:true}).isVisible(),"back to the draft");
    await command("capability");
    await dialog(page).getByRole("button",{name:"Revisar e confirmar",exact:true}).click();
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();
    await says(page,"não oferece as garantias");
    await command("heal");
    await dialog(page).getByRole("button",{name:"Cancelar",exact:true}).click();
    await page.getByRole("button",{name:"Descartar",exact:true}).click();
    await clean(page,token);

    // The server applies the change, but the answer never reaches the page.
    await page.route("**/admin/v2/datasources/*:disable",async route=>{await route.fetch();await route.abort("failed");});
    await act(page,"Desabilitar").click();
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();
    await says(page,"Resultado desconhecido");
    await command("expect-disabled:crm-demo");
    await page.unrouteAll();
    // Closing rereads; only then may a new write start.
    await dialog(page).getByRole("button",{name:"Fechar",exact:true}).click();await ready(page);
    await expect.poll(async()=>await act(page,"Habilitar").isEnabled()).toBe(true);

    // A timeout before the server: also unknown, and the state is confirmed unchanged.
    await page.route("**/admin/v2/datasources/*:enable",route=>route.abort("timedout"));
    await act(page,"Habilitar").click();
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();
    await says(page,"Resultado desconhecido");
    await page.unrouteAll();
    await dialog(page).getByRole("button",{name:"Fechar",exact:true}).click();await ready(page);
    await command("expect-disabled:crm-demo");
    requireTrue(await act(page,"Habilitar").isVisible(),"state read again, unchanged");
    requireTrue(seen.writes.filter(w=>w.path.endsWith(":rotate-credential")).length === 2,"each refusal was one gesture");
    requireTrue(!seen.leak,"no leak");await clean(page,token);
  },writing);
});

test("a failed persistence blocks writes until restart; an uncertain one needs a new read",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);
    await openItem(page,"Financeiro de demonstração");
    await command("uncertain");
    await act(page,"Desabilitar").click();
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();
    await says(page,"Não é possível saber se a alteração foi gravada");
    await dialog(page).getByRole("button",{name:"Fechar",exact:true}).click();
    // The store now requires reopening: reads are refused and writes stay off.
    await expect.poll(async()=> (await page.getByRole("status").first().textContent())?.includes("indisponível")).toBe(true);
    await navigate(page,"Datasources");
    await expect.poll(async()=> (await page.getByRole("status").first().textContent())?.includes("indisponível")).toBe(true);
    await navigate(page,"Novo datasource");
    await expect.poll(async()=> (await page.getByRole("region",{name:"Leitura",exact:true}).textContent())?.includes("indisponível")).toBe(true);
    requireTrue(await page.getByRole("button",{name:"Próximo",exact:true}).count() === 0,"no wizard while blocked");
  },writing);
});

test("persistence failure before the replace: nothing changed, writes off until restart",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token,command)=>{
    await enter(page,origin,token);
    await openItem(page,"Financeiro de demonstração");
    await command("fail-next");
    await act(page,"Desabilitar").click();
    await dialog(page).getByRole("button",{name:"Confirmar",exact:true}).click();
    await says(page,"o estado anterior foi mantido");
    await dialog(page).getByRole("button",{name:"Fechar",exact:true}).click();
    // The store requires reopening (D-081/D-094): reads are refused too, so no stale state is shown.
    await expect.poll(async()=> (await page.getByRole("status").first().textContent())?.includes("indisponível")).toBe(true);
    requireTrue(await page.getByRole("group",{name:"Ações"}).count() === 0,"no action over a refused read");
  },writing);
});

/** Relative luminance contrast, WCAG 2.x, over the open dialog. */
const contrast=()=>{
  /** @param {string} value */
  const rgb=value=>{const m=value.match(/\d+(\.\d+)?/g)?.map(Number) ?? [0,0,0];return m.slice(0,3);};
  /** @param {number[]} c */
  const lum=c=>{const [r,g,b]=c.map(v=>{const s=(v ?? 0)/255;return s<=0.03928 ? s/12.92 : ((s+0.055)/1.055)**2.4;});return 0.2126*(r ?? 0)+0.7152*(g ?? 0)+0.0722*(b ?? 0);};
  /** @param {Element | null} node */
  const back=node=>{let n=node;while(n instanceof Element){const c=getComputedStyle(n).backgroundColor;if(!/rgba\(0, 0, 0, 0\)|transparent/.test(c)) return c;n=n.parentElement;}return getComputedStyle(document.body).backgroundColor;};
  /** @type {number[]} */ const found=[];
  for(const node of Array.from(document.querySelectorAll("dialog h2, dialog h3, dialog label, dialog legend, dialog p, dialog dt, dialog dd, dialog button, dialog option"))) {
    if(!(node instanceof HTMLElement) || !node.getClientRects().length || !node.textContent?.trim()) continue;
    const a=getComputedStyle(node).color, b=back(node);
    const x=lum(rgb(a)),y=lum(rgb(b));found.push((Math.max(x,y)+0.05)/(Math.min(x,y)+0.05));
  }
  return Math.min(...found);
};

test("forms: 320 px and 200%, both themes, contrast, focus trap, Escape and logout discard",async({},info)=>{
  test.setTimeout(120000);
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    await page.emulateMedia({reducedMotion:"reduce"});
    await enter(page,origin,token);
    for(const [width,height] of [[320,640],[640,720],[1280,800]]) {
      await page.setViewportSize({width:Number(width),height:Number(height)});
      await expect.poll(async()=>await page.getByRole("button",{name:/^Menu: /}).isVisible()).toBe(Number(width) < 768);
      await openItem(page,"CRM de demonstração");
      for(const theme of ["light","dark"]) {
        await page.evaluate(value=>{document.documentElement.dataset.theme=value;},theme);
        await act(page,"Editar conexão e limites").click();
        requireTrue(await page.evaluate(()=>document.documentElement.scrollWidth <= document.documentElement.clientWidth+1),"reflow "+width);
        const minimum=await page.evaluate(contrast);
        requireTrue(minimum >= 4.5,"contrast "+theme+" "+width+" "+minimum.toFixed(2));
        await dialog(page).getByRole("button",{name:"Cancelar",exact:true}).click();
      }
    }
    await act(page,"Editar conexão e limites").click();
    // Focus stays in the dialog: Tab from the last control returns to the first.
    const heading=dialog(page).getByRole("heading",{name:"Editar datasource",exact:true});
    requireTrue(await heading.evaluate(e=>e===document.activeElement),"dialog focus");
    await dialog(page).getByRole("button",{name:"Cancelar",exact:true}).focus();await page.keyboard.press("Tab");
    requireTrue(await page.evaluate(()=>document.activeElement?.closest("dialog") !== null),"focus trapped");
    await dialog(page).getByLabel("Nome de apresentação",{exact:true}).fill("Rascunho");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("heading",{name:"Descartar rascunho?",exact:true})).toBeVisible();
    await page.getByRole("button",{name:"Continuar editando",exact:true}).click();
    await page.keyboard.press("Escape");await page.getByRole("button",{name:"Descartar",exact:true}).click();
    await act(page,"Trocar senha").click();
    await dialog(page).getByLabel("Senha técnica",{exact:true}).fill(ROTACAO);
    // Logout discards the draft and its secret; nothing survives in the page.
    await page.keyboard.press("Escape");await page.getByRole("button",{name:"Descartar",exact:true}).click();
    await page.getByRole("button",{name:"Sair",exact:true}).click();
    requireTrue(await page.getByRole("dialog").count() === 0,"no dialog after logout");
    await clean(page,token);
  },writing);
});

test("pagehide discards an open wizard draft and its password",async({},info)=>{
  await scenario(engine(info.project.name),async(page,origin,token)=>{
    const seen=watch(page,token);
    await enter(page,origin,token);
    await navigate(page,"Novo datasource");
    await expect(page.getByRole("region",{name:"Identificação",exact:true})).toBeVisible();
    await page.getByLabel("Alias",{exact:true}).fill("rascunho-demo");
    await page.getByLabel("Nome de apresentação",{exact:true}).fill("Rascunho");
    await page.getByRole("button",{name:"Próximo",exact:true}).click();
    await page.getByLabel("Host",{exact:true}).fill("db-rascunho.example.internal");
    await page.getByLabel("Banco",{exact:true}).fill("app_demo");
    await page.getByLabel("Usuário técnico",{exact:true}).fill("gateway_demo");
    await page.getByRole("button",{name:"Próximo",exact:true}).click();
    await page.getByLabel("Senha técnica",{exact:true}).fill(CADASTRO);
    await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true})));
    await expect(page.getByLabel("Token",{exact:true})).toBeVisible();
    await clean(page,token);
    requireTrue(seen.writes.length === 0 && !seen.leak,"nothing sent, nothing leaked");
  },writing);
});
