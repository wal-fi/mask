import { open, AccessError } from "./transport.js";
import { at, entry } from "./reader.js";
import { workbench } from "./workbench.js";

/** @template {keyof HTMLElementTagNameMap} K @param {K} tag @param {string} text */
export function element(tag,text="") { const node=document.createElement(tag); node.textContent=text; return node; }
/** @param {unknown} value @returns {HTMLElement} */
export function plain(value) {
  if(Array.isArray(value)) {
    if(!value.length) return element("p","Lista vazia.");
    const list=element("ol");
    for(const item of value) { const row=element("li"); row.append(plain(item)); list.append(row); }
    return list;
  }
  if(entry(value)) {
    if(!Object.keys(value).length) return element("p","Sem valores.");
    const list=element("dl");
    for(const [key,item] of Object.entries(value)) { const body=element("dd"); body.append(plain(item)); list.append(element("dt",key),body); }
    return list;
  }
  return element("span",value === null ? "Não informado" : value === true ? "Sim" : value === false ? "Não" : String(value));
}
/** @param {HTMLElement} node */
export function erase(node) {
  node.querySelectorAll("input,select,textarea").forEach(input=>{if(input instanceof HTMLInputElement || input instanceof HTMLSelectElement || input instanceof HTMLTextAreaElement) input.value="";});
  node.querySelectorAll("input").forEach(input=>{input.checked=false;});
  node.querySelectorAll("*").forEach(child=>child.replaceChildren());
  node.replaceChildren();
}
/** @typedef {Awaited<ReturnType<typeof open>>} Client */
/** @typedef {ReturnType<Client["describe"]>["views"][number]} PageItem */
/** @typedef {{tag:"authentication"} | {tag:"pending",stop:AbortController} | {tag:"ready",client:Client,stop:AbortController,views:PageItem[],board:Board}} Access */
/** @typedef {{tag:"loading"} | {tag:"success",value:unknown,version:number,time:number} | {tag:"unknown",prior:Sheet | undefined,stale:boolean}} Sheet */
/** @typedef {{tag:"loading"} | {tag:"ready",value:unknown,time:number} | {tag:"absent"} | {tag:"unavailable"} | {tag:"broken"}} Pane */
/** @typedef {(string|number)[]} Trail */
/** @typedef {{id:string,label:string,path:Trail,kind:"count"|"flag"|"text"|"list"|"tree",wording:{value:string,text:string}[]}} Figure */
/** @typedef {{id:string,label:string,source:"main"|"extra",entries:Figure[]}} Tab */
/** @typedef {{brand:string,tagline:string,main:string,legacy:string,yes:string,no:string,blank:string,failure:string,unavailable:string,
 * summary:{id:string,label:string,call:string,figures:Figure[],notes:string[],absent:string},
 * collection:{id:string,label:string,call:string,items:Trail,key:Trail,title:Trail,columns:Figure[],search:string,searchable:Trail[],empty:string,nothing:string,open:string},
 * detail:{id:string,call:string,extra:string,back:string,tabs:Tab[],gone:string},
 * guide:{id:string,label:string,banner:string,steps:{id:string,label:string,text:string}[]}}} Board */
/** @typedef {{kind:"view",index:number} | {kind:"summary"} | {kind:"collection"} | {kind:"detail",key:string,title:string,tab:number} | {kind:"guide",step:number}} Place */

const THEMES=/** @type {const} */ (["auto","dark","light"]);
const THEME_TEXT={auto:"Tema: automático",dark:"Tema: escuro",light:"Tema: claro"};

/** Installs only a local entry form; all private labels arrive after entry.
 * @param {HTMLElement} root
 */
export function mount(root) {
  /** @type {Access} */ let access={tag:"authentication"};
  /** @type {Sheet | undefined} */ let sheet;
  /** @type {Pane | undefined} */ let pane;
  /** @type {Pane | undefined} */ let side;
  /** @type {AbortController | undefined} */ let flight;
  /** @type {AbortController | undefined} */ let lateral;
  /** @type {Place} */ let place={kind:"view",index:0};
  let epoch=0, turn=0, busy=false, paused=true, filter="";
  /** @type {"auto"|"dark"|"light"} */ let theme="auto";
  /** @type {ReturnType<typeof setTimeout> | undefined} */ let timer;
  /** @type {HTMLElement | undefined} */ let panel;
  /** @type {HTMLElement | undefined} */ let notice;
  /** @type {HTMLButtonElement | undefined} */ let retry;
  /** @type {ReturnType<typeof workbench> | undefined} */ let editor;
  function stopClock() { if(timer !== undefined) clearTimeout(timer); timer=undefined; }
  function clear() {
    epoch++; turn++; flight?.abort(); flight=undefined; lateral?.abort(); lateral=undefined; stopClock(); paused=true; busy=false;
    sheet=undefined; pane=undefined; side=undefined; filter=""; place={kind:"view",index:0};
    editor?.close();editor=undefined;
    if(access.tag === "ready") access.client.close();
    if(access.tag !== "authentication") access.stop.abort();
    access={tag:"authentication"}; panel=undefined; notice=undefined; retry=undefined;
    // Erase detached descendants as well as removing them from the live tree.
    erase(root);
  }
  /** @param {string} message @param {boolean} focus */
  function login(message="",focus=true) {
    clear();
    const heading=element("h1","Acesso local");
    const form=element("form");
    const label=element("label","Token");
    const input=element("input"); input.id="entry-key"; input.type="password"; input.autocomplete="off"; input.spellcheck=false; input.required=true;
    label.htmlFor=input.id;
    const enter=element("button","Entrar"); enter.type="submit";
    const info=element("p",message); info.setAttribute("role","status"); info.setAttribute("aria-live","polite");
    form.append(label,input,enter);root.append(heading,form,info);
    form.addEventListener("submit",event=>{
      event.preventDefault();
      if(access.tag !== "authentication") return;
      let key=input.value; input.value="";
      if(!key) { info.textContent="Autenticação necessária."; input.focus(); return; }
      const stop=new AbortController();access={tag:"pending",stop};
      const mine=++epoch;
      enter.disabled=true; info.textContent="Carregando…";
      const attempt=open(key,stop.signal,()=>{if(mine === epoch) login("Autenticação necessária.");}); key="";
      void attempt.then(client=>{
        if(mine !== epoch) {client.close();return;}
        const book=client.describe();
        access={tag:"ready",client,stop,views:book.views,board:/** @type {Board} */ (book.board())};
        editor=workbench(client,root,()=>{sheet=undefined;shell();void load(true);});
        void land(mine);
      }).catch(()=>{ if(mine === epoch) login("Não foi possível entrar. Tente novamente."); });
    });
    if(focus) input.focus();
  }
  /** The overview of the second prefix is the landing page; without it, the first view.
   * @param {number} mine
   */
  async function land(mine) {
    if(access.tag !== "ready") return;
    place={kind:"summary"};shell();
    await read(true);
    if(mine !== epoch || access.tag !== "ready") return;
    if(pane?.tag === "absent") {place={kind:"view",index:0};pane=undefined;shell();void load(true);}
  }
  /** @param {Place} next */
  function go(next) {
    const navigate=()=>{
      place=next; sheet=undefined; pane=undefined; side=undefined; lateral?.abort(); lateral=undefined;
      if(next.kind !== "collection" && next.kind !== "detail") filter="";
      shell();
      if(next.kind === "view") void load(true); else if(next.kind === "guide") {show(true);} else void read(true);
    };
    if(editor?.active()) editor.leave(navigate);else navigate();
  }
  /** @param {string} text @param {boolean} current @param {() => void} action */
  function link(text,current,action) {
    const button=element("button",text);button.type="button";
    if(current) button.setAttribute("aria-current","page");
    button.addEventListener("click",()=>{if(access.tag === "ready") action();});
    return button;
  }
  function shell() {
    if(access.tag !== "ready") return;
    const board=access.board;
    erase(root);
    const top=element("header");top.className="bar";
    const brand=element("div");brand.className="brand";
    const title=element("h1","Administração local");const tag=element("p",board.brand);tag.className="tag";
    brand.append(tag,title);
    const tools=element("div");tools.className="tools";
    // Narrow screens: the single navigation landmark collapses behind an
    // explicit disclosure control; wide screens always show it (CSS only).
    const here=place.kind === "summary" ? board.summary.label : place.kind === "collection" || place.kind === "detail" ? board.collection.label
      : place.kind === "guide" ? board.guide.label : access.views[place.index]?.label ?? "";
    const menu=element("button","Menu: "+here);menu.type="button";menu.className="menu";
    menu.setAttribute("aria-expanded","false");menu.setAttribute("aria-controls","side-nav");
    const shade=element("button",THEME_TEXT[theme]);shade.type="button";
    shade.addEventListener("click",()=>{theme=THEMES[(THEMES.indexOf(theme)+1)%THEMES.length] ?? "auto";paint();shade.textContent=THEME_TEXT[theme];});
    const leave=element("button","Sair"); leave.type="button"; leave.addEventListener("click",()=>login());
    tools.append(menu,shade,leave);top.append(brand,tools);
    const frame=element("div");frame.className="frame";
    const nav=element("nav"); nav.setAttribute("aria-label","Navegação");nav.id="side-nav";
    /** @param {boolean} open */
    const unfold=open=>{nav.dataset.open=String(open);menu.setAttribute("aria-expanded",String(open));};
    menu.addEventListener("click",()=>{
      const open=nav.dataset.open !== "true";unfold(open);
      if(open) nav.querySelector("button")?.focus();
    });
    nav.addEventListener("keydown",event=>{if(event.key === "Escape" && nav.dataset.open === "true") {unfold(false);menu.focus();}});
    const first=element("p",board.main);first.className="group";
    const second=element("p",board.legacy);second.className="group";
    nav.append(first,
      link(board.summary.label,place.kind === "summary",()=>go({kind:"summary"})),
      link(board.collection.label,place.kind === "collection" || place.kind === "detail",()=>go({kind:"collection"})),
      link(board.guide.label,place.kind === "guide",()=>go({kind:"guide",step:0})),
      second);
    for(const [index,view] of access.views.entries()) nav.append(link(view.label,place.kind === "view" && place.index === index,()=>go({kind:"view",index})));
    const stage=element("div");stage.className="stage";
    notice=element("p");notice.setAttribute("role","status");notice.setAttribute("aria-live","polite");
    retry=element("button","Atualizar");retry.type="button";retry.addEventListener("click",()=>{
      const again=()=>{if(place.kind === "view") void load(true); else if(place.kind !== "guide") void read(true);};
      if(editor?.active()) editor.leave(again);else again();
    });
    panel=element("section"); panel.setAttribute("aria-label","Leitura");
    // Same DOM order as before (status, refresh, reading); only grouped visually.
    const toolbar=element("div");toolbar.className="toolbar";toolbar.append(notice,retry);
    stage.append(toolbar,panel);frame.append(nav,stage);
    root.append(top,frame);
    retry.hidden=place.kind === "guide";
  }
  function paint() {
    if(theme === "auto") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme=theme;
  }
  /** @param {boolean} focus */
  function show(focus) {
    if(access.tag !== "ready" || !panel || !notice) return;
    if(place.kind !== "view") { surface(focus); return; }
    const view=access.views[place.index]; if(!view) return;
    const restore=focus || document.activeElement === panel.firstElementChild;
    erase(panel);
    const title=element("h2",view.label); title.tabIndex=-1; panel.append(title);
    if(sheet?.tag === "success") {
      for(const control of view.controls) {
        if(control.type !== "read" || typeof control.label !== "string") continue;
        const section=element("section");section.append(element("h3",control.label),plain(at(access.client.design().displayed(view.call,sheet.value),control.path)));panel.append(section);
      }
      notice.textContent="Respondendo · Última leitura: "+new Date(sheet.time).toLocaleTimeString();
      editor?.attach(panel,view.id,sheet.value);
    } else if(sheet?.tag === "unknown") {
      notice.textContent=sheet.stale ? "Leitura desatualizada. Tente novamente." : "Leitura indisponível. Tente novamente.";
      if(sheet.prior?.tag === "success") {
        for(const control of view.controls) if(control.type === "read" && typeof control.label === "string") {
          const section=element("section");section.append(element("h3",control.label),plain(at(access.client.design().displayed(view.call,sheet.prior.value),control.path)));panel.append(section);
        }
      }
    } else notice.textContent="Carregando…";
    if(retry) retry.disabled=busy;
    if(restore) title.focus();
  }
  /** @param {unknown} value @param {Figure} figure @returns {HTMLElement} */
  function figure(value,figure) {
    if(access.tag !== "ready") return element("span");
    const board=access.board;
    if(value === undefined || value === null) { const node=element("span",board.blank);node.className="muted";return node; }
    if(figure.kind === "flag" && typeof value === "boolean") {
      const said=figure.wording.find(w=>w.value === String(value));
      // Declared convention: the first wording of a signal is its healthy state.
      const good=said ? said === figure.wording[0] : value;
      const node=element("span",(good ? "✓ " : "✕ ")+(said ? said.text : value ? board.yes : board.no));
      node.className=good ? "flag on" : "flag off";return node;
    }
    if(figure.kind === "count" && typeof value === "number") return element("span",value.toLocaleString("pt-BR"));
    if(figure.kind === "text" && typeof value === "string") {
      const known=figure.wording.find(w=>w.value === value);
      return element("span",known ? known.text : value);
    }
    if(figure.kind === "list" && Array.isArray(value)) {
      if(!value.length) return element("span","Lista vazia.");
      const list=element("ul");list.className="chips";
      for(const item of value) list.append(element("li",String(item)));
      return list;
    }
    return plain(value);
  }
  /** @param {Figure[]} figures @param {unknown} value */
  function facts(figures,value) {
    const list=element("dl");list.className="facts";
    for(const item of figures) {
      const row=element("div");const body=element("dd");body.append(figure(at(value,item.path),item));
      row.append(element("dt",item.label),body);list.append(row);
    }
    return list;
  }
  /** @param {Pane | undefined} state @param {string} absentText */
  function report(state,absentText) {
    if(access.tag !== "ready" || !notice) return;
    const board=access.board;
    if(state?.tag === "ready") notice.textContent="Respondendo · Última leitura: "+new Date(state.time).toLocaleTimeString();
    else if(state?.tag === "absent") notice.textContent=absentText;
    else if(state?.tag === "unavailable") notice.textContent=board.unavailable;
    else if(state?.tag === "broken") notice.textContent=board.failure;
    else notice.textContent="Carregando…";
  }
  /** Visible explanation in the reading region; the status line keeps the same text.
   * @param {HTMLElement} target @param {string} text @param {"plain"|"info"|"warn"} tone
   */
  function hint(target,text,tone="plain") { const node=element("p",text);node.className=tone === "plain" ? "hint" : "hint callout "+tone;target.append(node); }
  /** @param {boolean} focus */
  function surface(focus) {
    if(access.tag !== "ready" || !panel || !notice) return;
    const board=access.board;
    const restore=focus || document.activeElement === panel.firstElementChild;
    erase(panel);panel.setAttribute("aria-busy",pane?.tag === "loading" ? "true" : "false");
    if(retry) retry.disabled=busy;
    if(place.kind === "summary") {
      const title=element("h2",board.summary.label);title.tabIndex=-1;panel.append(title);
      report(pane,board.summary.absent);
      if(pane?.tag === "absent") hint(panel,board.summary.absent,"info");
      else if(pane?.tag === "loading" || pane === undefined) hint(panel,"Carregando…");
      else if(pane?.tag === "ready") {
        // Declared order is priority: the first three counts lead; the rest are details.
        const counts=board.summary.figures.filter(f=>f.kind === "count");
        const signals=board.summary.figures.filter(f=>f.kind === "flag");
        const health=element("ul");health.className="signals";health.setAttribute("aria-label","Saúde do catálogo");
        for(const item of signals) { const row=element("li");row.append(figure(at(pane.value,item.path),item));health.append(row); }
        const cards=facts(counts.slice(0,3),pane.value);cards.className="cards";
        const more=counts.slice(3);
        panel.append(health,cards);
        if(more.length) { const list=facts(more,pane.value);list.className="facts details";panel.append(list); }
        const notes=element("div");notes.className="notes";
        for(const text of board.summary.notes) { const node=element("p",text);node.className="note";notes.append(node); }
        panel.append(notes);
      } else hint(panel,pane.tag === "unavailable" ? board.unavailable : board.failure,"warn");
      if(restore) title.focus();
    } else if(place.kind === "collection") {
      const title=element("h2",board.collection.label);title.tabIndex=-1;panel.append(title);
      report(pane,board.summary.absent);
      if(pane?.tag === "ready") listing(pane.value);
      else if(pane?.tag === "absent") hint(panel,board.summary.absent,"info");
      else if(pane?.tag === "loading" || pane === undefined) hint(panel,"Carregando…");
      else hint(panel,pane.tag === "unavailable" ? board.unavailable : board.failure,"warn");
      if(restore) title.focus();
    } else if(place.kind === "detail") {
      const here=place;
      const back=element("button",board.detail.back);back.type="button";back.className="back";
      back.addEventListener("click",()=>go({kind:"collection"}));
      const title=element("h2",here.title);title.tabIndex=-1;panel.append(back,title);
      report(pane,board.detail.gone);
      if(pane?.tag === "ready") tabs(here,pane.value);
      else if(pane?.tag === "absent") hint(panel,board.detail.gone,"info");
      else if(pane?.tag === "loading" || pane === undefined) hint(panel,"Carregando…");
      else hint(panel,pane.tag === "unavailable" ? board.unavailable : board.failure,"warn");
      if(restore) title.focus();
    } else if(place.kind === "guide") {
      guide(place.step,restore);
    }
  }
  /** @param {unknown} value */
  function listing(value) {
    if(access.tag !== "ready" || !panel) return;
    const spec=access.board.collection;
    const rows=at(value,spec.items);
    if(!Array.isArray(rows)) { hint(panel,access.board.failure); return; }
    const search=element("div");search.className="search";
    const label=element("label",spec.search);const input=element("input");input.id="find-items";input.type="search";input.autocomplete="off";input.spellcheck=false;input.value=filter;
    label.htmlFor=input.id;search.append(label,input);panel.append(search);
    const count=element("p");count.className="count";panel.append(count);
    const holder=element("div");holder.className="grid";panel.append(holder);
    const draw=()=>{
      erase(holder);
      const needle=filter.trim().toLocaleLowerCase("pt-BR");
      const shown=rows.filter(row=>!needle || spec.searchable.some(p=>{const found=at(row,p);return typeof found === "string" && found.toLocaleLowerCase("pt-BR").includes(needle);}));
      count.textContent=rows.length ? shown.length+" de "+rows.length : "";
      if(!rows.length) { hint(holder,spec.empty,"info"); return; }
      if(!shown.length) { hint(holder,spec.nothing,"info"); return; }
      const table=element("table");const caption=element("caption",spec.label);table.append(caption);
      const head=element("thead");const top=element("tr");
      for(const column of spec.columns) { const cell=element("th",column.label);cell.scope="col";top.append(cell); }
      const empty=element("th");empty.scope="col";const hidden=element("span",spec.open);hidden.className="hidden";empty.append(hidden);top.append(empty);
      head.append(top);table.append(head);
      const body=element("tbody");
      for(const row of shown) {
        const line=element("tr");
        for(const column of spec.columns) { const cell=element("td");cell.dataset.label=column.label;cell.append(figure(at(row,column.path),column));line.append(cell); }
        const key=at(row,spec.key), name=at(row,spec.title);
        const cell=element("td");
        if(typeof key === "string") {
          const button=element("button",spec.open);button.type="button";
          button.setAttribute("aria-label",spec.open+": "+(typeof name === "string" ? name : key));
          button.addEventListener("click",()=>go({kind:"detail",key,title:typeof name === "string" ? name : key,tab:0}));
          cell.append(button);
        }
        line.append(cell);body.append(line);
      }
      table.append(body);holder.append(table);
    };
    input.addEventListener("input",()=>{filter=input.value;draw();});
    draw();
  }
  /** @param {{kind:"detail",key:string,title:string,tab:number}} here @param {unknown} value */
  function tabs(here,value) {
    if(access.tag !== "ready" || !panel) return;
    const list=access.board.detail.tabs;
    const bar=element("div");bar.setAttribute("role","tablist");bar.setAttribute("aria-label",here.title);bar.className="tabs";
    /** @type {HTMLButtonElement[]} */ const buttons=[];
    const body=element("div");body.setAttribute("role","tabpanel");body.id="tab-body";body.tabIndex=0;
    for(const [index,tab] of list.entries()) {
      const button=element("button",tab.label);button.type="button";button.setAttribute("role","tab");button.id="tab-"+index;
      button.setAttribute("aria-selected",String(index === here.tab));button.setAttribute("aria-controls",body.id);button.tabIndex=index === here.tab ? 0 : -1;
      button.addEventListener("click",()=>pick(index,false));
      button.addEventListener("keydown",event=>{
        const last=list.length-1;
        const next=event.key === "ArrowRight" ? (index === last ? 0 : index+1) : event.key === "ArrowLeft" ? (index === 0 ? last : index-1) : event.key === "Home" ? 0 : event.key === "End" ? last : -1;
        if(next >= 0) {event.preventDefault();pick(next,true);}
      });
      buttons.push(button);bar.append(button);
    }
    /** @param {number} index @param {boolean} focus */
    const pick=(index,focus)=>{
      if(place.kind !== "detail") return;
      place={...place,tab:index};
      for(const [i,button] of buttons.entries()) {button.setAttribute("aria-selected",String(i === index));button.tabIndex=i === index ? 0 : -1;}
      if(focus) buttons[index]?.focus();
      fill(value);
    };
    const fill=(/** @type {unknown} */ main)=>{
      if(place.kind !== "detail") return;
      erase(body);
      const tab=list[place.tab];if(!tab) return;
      body.setAttribute("aria-labelledby","tab-"+place.tab);
      if(tab.source === "main") { body.append(facts(tab.entries,main)); return; }
      if(side?.tag === "ready") { body.append(facts(tab.entries,side.value)); return; }
      if(side?.tag === "absent") { hint(body,access.tag === "ready" ? access.board.detail.gone : ""); return; }
      if(side?.tag === "unavailable" || side?.tag === "broken") { hint(body,access.tag === "ready" ? (side.tag === "unavailable" ? access.board.unavailable : access.board.failure) : ""); return; }
      hint(body,"Carregando…");
      if(side === undefined) void aside(here.key,()=>fill(main));
    };
    panel.append(bar,body);fill(value);
  }
  /** @param {string} key @param {() => void} done */
  async function aside(key,done) {
    if(access.tag !== "ready") return;
    const client=access.client, call=access.board.detail.extra, mine=epoch;
    lateral?.abort();lateral=new AbortController();side={tag:"loading"};
    try {
      const value=await client.read(call,lateral.signal,key);
      if(mine !== epoch) return;
      side={tag:"ready",value,time:Date.now()};
    } catch(error) {
      if(mine !== epoch) return;
      if(error instanceof AccessError && error.kind === "authentication") { login("Autenticação necessária.");return; }
      side={tag:error instanceof AccessError && error.kind === "absent" ? "absent" : error instanceof AccessError && error.kind === "unavailable" ? "unavailable" : "broken"};
    }
    if(place.kind === "detail" && place.key === key) done();
  }
  /** @param {number} step @param {boolean} restore */
  function guide(step,restore) {
    if(access.tag !== "ready" || !panel || !notice) return;
    const spec=access.board.guide;
    notice.textContent=spec.banner;
    const title=element("h2",spec.label);title.tabIndex=-1;
    const banner=element("p",spec.banner);banner.className="banner";banner.setAttribute("role","note");
    const trail=element("ol");trail.className="steps";trail.setAttribute("aria-label",spec.label);
    for(const [index,item] of spec.steps.entries()) {
      const node=element("li",(index+1)+". "+item.label);if(index === step) node.setAttribute("aria-current","step");
      node.className=index === step ? "now" : "other";trail.append(node);
    }
    const current=spec.steps[step];
    const card=element("section");card.className="card";card.setAttribute("aria-label",current?.label ?? spec.label);
    if(current) card.append(element("h3",(step+1)+". "+current.label),element("p",current.text));
    const moves=element("div");moves.className="moves";
    const back=element("button","Anterior");back.type="button";back.disabled=step === 0;
    const next=element("button","Próximo");next.type="button";next.disabled=step >= spec.steps.length-1;
    back.addEventListener("click",()=>{place={kind:"guide",step:step-1};guide(step-1,false);});
    next.addEventListener("click",()=>{place={kind:"guide",step:step+1};guide(step+1,false);});
    moves.append(back,next);
    erase(panel);panel.append(title,banner,trail,card,moves);
    if(restore) title.focus();
  }
  function schedule() {
    stopClock();
    if(access.tag === "ready" && !paused && !busy && document.visibilityState === "visible" && (place.kind === "view" || place.kind === "summary")) timer=setTimeout(()=>{void (place.kind === "summary" ? read(false) : poll());},15000);
  }
  /** Reads the declared second-prefix call of the current place.
   * @param {boolean} focus
   */
  async function read(focus) {
    if(access.tag !== "ready") return;
    const client=access.client, board=access.board, here=place;
    const call=here.kind === "summary" ? board.summary.call : here.kind === "collection" ? board.collection.call : here.kind === "detail" ? board.detail.call : undefined;
    if(!call) return;
    flight?.abort(); flight=new AbortController();
    const mine=epoch, ticket=++turn;busy=true;paused=true;stopClock();
    if(!(here.kind === "summary" && pane?.tag === "ready" && !focus)) {pane={tag:"loading"};show(focus);}
    try {
      const value=await client.read(call,flight.signal,here.kind === "detail" ? here.key : undefined);
      if(mine !== epoch || ticket !== turn) return;
      pane={tag:"ready",value,time:Date.now()};paused=false;
    } catch(error) {
      if(mine !== epoch || ticket !== turn) return;
      if(error instanceof AccessError && error.kind === "authentication") { login("Autenticação necessária.");return; }
      pane={tag:error instanceof AccessError && error.kind === "absent" ? "absent" : error instanceof AccessError && error.kind === "unavailable" ? "unavailable" : "broken"};paused=true;
    } finally { if(mine === epoch && ticket === turn) { busy=false;show(focus);schedule(); } }
  }
  /** @param {boolean} focus */
  async function load(focus) {
    if(access.tag !== "ready" || place.kind !== "view") return;
    const client=access.client, view=access.views[place.index]; if(!view) return;
    flight?.abort(); flight=new AbortController();
    const mine=epoch, ticket=++turn; busy=true;paused=true;stopClock();
    const prior=sheet?.tag === "success" ? sheet : sheet?.tag === "unknown" ? sheet.prior : undefined;
    sheet={tag:"loading"};show(focus);
    try {
      const value=await client.read(view.call,flight.signal);
      if(mine !== epoch || ticket !== turn) return;
      // The transport has already checked this envelope before it reaches state.
      const book=client.describe();
      const version=book.inspectDataFor(view.call,value);
      sheet={tag:"success",value,version,time:Date.now()};paused=false;
    } catch(error) {
      if(mine !== epoch || ticket !== turn) return;
      if(error instanceof AccessError && error.kind === "authentication") { login("Autenticação necessária.");return; }
      sheet={tag:"unknown",prior,stale:prior !== undefined};paused=true;
    } finally { if(mine === epoch && ticket === turn) { busy=false;show(false);schedule(); } }
  }
  async function poll() {
    if(access.tag !== "ready" || busy || paused || editor?.active() || document.visibilityState !== "visible" || place.kind !== "view") {schedule();return;}
    const client=access.client, first=access.views[0];if(!first) return;
    flight=new AbortController();
    const mine=epoch, ticket=++turn;busy=true;show(false);
    try {
      const value=await client.read(first.call,flight.signal);
      if(mine !== epoch || ticket !== turn) return;
      const version=client.describe().inspectDataFor(first.call,value);
      if(sheet?.tag === "success" && version !== sheet.version) {
        sheet={tag:"unknown",prior:undefined,stale:true};paused=true;
      } else if(place.kind === "view" && place.index === 0) sheet={tag:"success",value,version,time:Date.now()};
    } catch(error) {
      if(mine !== epoch || ticket !== turn) return;
      if(error instanceof AccessError && error.kind === "authentication") { login("Autenticação necessária.");return; }
      sheet={tag:"unknown",prior:sheet?.tag === "success" ? sheet : undefined,stale:sheet?.tag === "success"};paused=true;
    } finally {if(mine === epoch && ticket === turn) {busy=false;show(false);schedule();}}
  }
  const hide=()=>login("",false);
  const appear=()=>login("",true);
  const visibility=()=>{if(document.visibilityState !== "visible") stopClock();else schedule();};
  window.addEventListener("pagehide",hide);window.addEventListener("pageshow",appear);document.addEventListener("visibilitychange",visibility);
  login("",false);
  return ()=>{clear();window.removeEventListener("pagehide",hide);window.removeEventListener("pageshow",appear);document.removeEventListener("visibilitychange",visibility);};
}

if(typeof document !== "undefined") {
  const root=document.querySelector("main");
  if(root instanceof HTMLElement) mount(root);
}
