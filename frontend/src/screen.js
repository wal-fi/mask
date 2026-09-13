import { open, AccessError } from "./transport.js";
import { at, entry } from "./reader.js";

/** @template {keyof HTMLElementTagNameMap} K @param {K} tag @param {string} text */
function element(tag,text="") { const node=document.createElement(tag); node.textContent=text; return node; }
/** @param {unknown} value @returns {HTMLElement} */
function plain(value) {
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
function erase(node) {
  node.querySelectorAll("input").forEach(input=>{input.value="";});
  node.querySelectorAll("*").forEach(child=>child.replaceChildren());
  node.replaceChildren();
}
/** @typedef {Awaited<ReturnType<typeof open>>} Client */
/** @typedef {ReturnType<Client["describe"]>["views"][number]} PageItem */
/** @typedef {{tag:"authentication"} | {tag:"pending",stop:AbortController} | {tag:"ready",client:Client,stop:AbortController,views:PageItem[]}} Access */
/** @typedef {{tag:"loading"} | {tag:"success",value:unknown,version:number,time:number} | {tag:"unknown",prior:Sheet | undefined,stale:boolean}} Sheet */

/** Installs only a local entry form; all private labels arrive after entry.
 * @param {HTMLElement} root
 */
export function mount(root) {
  /** @type {Access} */ let access={tag:"authentication"};
  /** @type {Sheet | undefined} */ let sheet;
  /** @type {AbortController | undefined} */ let flight;
  let generation=0, turn=0, selected=0, busy=false, paused=true;
  /** @type {ReturnType<typeof setTimeout> | undefined} */ let timer;
  /** @type {HTMLElement | undefined} */ let panel;
  /** @type {HTMLElement | undefined} */ let notice;
  /** @type {HTMLButtonElement | undefined} */ let retry;
  function stopClock() { if(timer !== undefined) clearTimeout(timer); timer=undefined; }
  function clear() {
    generation++; turn++; flight?.abort(); flight=undefined; stopClock(); paused=true; busy=false; sheet=undefined;
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
      const mine=++generation;
      enter.disabled=true; info.textContent="Carregando…";
      const attempt=open(key,stop.signal,()=>{if(mine === generation) login("Autenticação necessária.");}); key="";
      void attempt.then(client=>{
        if(mine !== generation) {client.close();return;}
        access={tag:"ready",client,stop,views:client.describe().views}; selected=0;
        shell(); void load(true);
      }).catch(()=>{ if(mine === generation) login("Não foi possível entrar. Tente novamente."); });
    });
    if(focus) input.focus();
  }
  function shell() {
    if(access.tag !== "ready") return;
    erase(root);
    const top=element("header");top.append(element("h1","Administração local"));
    const leave=element("button","Sair"); leave.type="button"; leave.addEventListener("click",()=>login());top.append(leave);
    const nav=element("nav"); nav.setAttribute("aria-label","Navegação");
    for(const [index,view] of access.views.entries()) {
      const button=element("button",view.label);button.type="button";
      if(index === selected) button.setAttribute("aria-current","page");
      button.addEventListener("click",()=>{
        if(access.tag !== "ready") return;
        selected=index; sheet=undefined; shell(); void load(true);
      });
      nav.append(button);
    }
    notice=element("p");notice.setAttribute("role","status");notice.setAttribute("aria-live","polite");
    retry=element("button","Atualizar");retry.type="button";retry.addEventListener("click",()=>{void load(true);});
    panel=element("section"); panel.setAttribute("aria-label","Leitura");
    root.append(top,nav,notice,retry,panel);
  }
  /** @param {boolean} focus */
  function show(focus) {
    if(access.tag !== "ready" || !panel || !notice) return;
    const view=access.views[selected]; if(!view) return;
    const restore=focus || document.activeElement === panel.firstElementChild;
    erase(panel);
    const title=element("h2",view.label); title.tabIndex=-1; panel.append(title);
    if(sheet?.tag === "success") {
      for(const control of view.controls) {
        if(typeof control.label !== "string") continue;
        const section=element("section");section.append(element("h3",control.label),plain(at(sheet.value,control.path)));panel.append(section);
      }
      notice.textContent="Respondendo · Última leitura: "+new Date(sheet.time).toLocaleTimeString();
    } else if(sheet?.tag === "unknown") {
      notice.textContent=sheet.stale ? "Leitura desatualizada. Tente novamente." : "Leitura indisponível. Tente novamente.";
      if(sheet.prior?.tag === "success") {
        for(const control of view.controls) if(typeof control.label === "string") {
          const section=element("section");section.append(element("h3",control.label),plain(at(sheet.prior.value,control.path)));panel.append(section);
        }
      }
    } else notice.textContent="Carregando…";
    if(retry) retry.disabled=busy;
    if(restore) title.focus();
  }
  function schedule() {
    stopClock();
    if(access.tag === "ready" && !paused && !busy && document.visibilityState === "visible") timer=setTimeout(()=>{void poll();},15000);
  }
  /** @param {boolean} focus */
  async function load(focus) {
    if(access.tag !== "ready") return;
    const client=access.client, view=access.views[selected]; if(!view) return;
    flight?.abort(); flight=new AbortController();
    const mine=generation, ticket=++turn; busy=true;paused=true;stopClock();
    const prior=sheet?.tag === "success" ? sheet : sheet?.tag === "unknown" ? sheet.prior : undefined;
    sheet={tag:"loading"};show(focus);
    try {
      const value=await client.read(view.call,flight.signal);
      if(mine !== generation || ticket !== turn) return;
      // The transport has already checked this envelope before it reaches state.
      const book=client.describe();
      const version=book.inspectDataFor(view.call,value);
      sheet={tag:"success",value,version,time:Date.now()};paused=false;
    } catch(error) {
      if(mine !== generation || ticket !== turn) return;
      if(error instanceof AccessError && error.kind === "authentication") { login("Autenticação necessária.");return; }
      sheet={tag:"unknown",prior,stale:prior !== undefined};paused=true;
    } finally { if(mine === generation && ticket === turn) { busy=false;show(false);schedule(); } }
  }
  async function poll() {
    if(access.tag !== "ready" || busy || paused || document.visibilityState !== "visible") return;
    const client=access.client, first=access.views[0];if(!first) return;
    flight=new AbortController();
    const mine=generation, ticket=++turn;busy=true;show(false);
    try {
      const value=await client.read(first.call,flight.signal);
      if(mine !== generation || ticket !== turn) return;
      const version=client.describe().inspectDataFor(first.call,value);
      if(sheet?.tag === "success" && version !== sheet.version) {
        sheet={tag:"unknown",prior:undefined,stale:true};paused=true;
      } else if(selected === 0) sheet={tag:"success",value,version,time:Date.now()};
    } catch(error) {
      if(mine !== generation || ticket !== turn) return;
      if(error instanceof AccessError && error.kind === "authentication") { login("Autenticação necessária.");return; }
      sheet={tag:"unknown",prior:sheet?.tag === "success" ? sheet : undefined,stale:sheet?.tag === "success"};paused=true;
    } finally {if(mine === generation && ticket === turn) {busy=false;show(false);schedule();}}
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
