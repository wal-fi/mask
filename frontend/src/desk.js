import { capture } from "./commands.js";
import { at, entry } from "./reader.js";
import { element, erase } from "./screen.js";
import { AccessError } from "./transport.js";

/** @typedef {Awaited<ReturnType<typeof import("./transport.js").open>>} DeskClient */
/** @typedef {(string|number)[]} Way */
/** @typedef {{value:string,text:string}} Choice */
/** @typedef {{id:string,label:string,help?:string|null,kind:"text"|"secret"|"integer"|"flag"|"choice"|"lines"|"records",path:Way,source?:Way|null,default?:string|number|boolean|null,optional?:boolean,choices?:Choice[],item?:string|null,items?:Field[],when?:{path:Way,value:string|number|boolean}|null}} Field */
/** @typedef {{id:string,label:string,title:string,call:string,place:"collection"|"detail"|"aside",stamp?:Way|null,origin?:Way|null,after?:"reread"|"list"|"open",lands?:Way|null,fields?:Field[],visible?:{path:Way,value:string|number|boolean}|null,confirm:string,typed?:Field|null,probe?:string|null,drop?:Way[],done:string,tone?:"plain"|"danger"}} Deed */
/** @typedef {{value:string,kind:"conflict"|"refused"|"busy"|"blocked"|"uncertain",text:string}} Result */
/** @typedef {{actions?:Deed[],outcomes?:Result[],reasons?:Choice[],latest?:Way|null,unknown?:string,guide:{label:string,banner:string,steps:{id:string,label:string,text:string,fields?:string[]}[],action?:string|null}}} Plan */
/** @typedef {{key:number,values:Map<string,unknown>}} Row */
/** @typedef {import("./transport.js").Written | {kind:"busy-local"} | {kind:"gone"} | {kind:"local"}} Sent */

/** Second-prefix writes (Phase 9, Stage 6). Drafts live only here, in memory;
 * one write at a time; every write needs an explicit gesture and a review;
 * a lost or uncertain answer blocks new writes until the state is read again.
 * @param {DeskClient} client @param {HTMLElement} root @param {Plan} plan
 * @param {{reread:(deed:Deed,value:unknown)=>void, refresh:()=>void}} hooks
 */
export function desk(client,root,plan,hooks) {
  const deeds=plan.actions ?? [], results=plan.outcomes ?? [], reasons=plan.reasons ?? [];
  /** @type {HTMLDialogElement | undefined} */ let dialog;
  /** @type {HTMLElement | undefined} */ let restore;
  /** @type {HTMLElement | undefined} */ let note;
  /** @type {Map<string,unknown>} */ let values=new Map();
  /** @type {Map<string,{node:HTMLElement,say:HTMLElement}>} */ let controls=new Map();
  let serial=0, rows=0, dirty=false, waiting=false, engaged=false, ended=false;
  /** Writes stay off after `blocked` (until restart) or `doubt` (until a fresh read). */
  let blocked=false, doubt=false;
  /** @type {(() => void) | undefined} */ let render;

  /** @param {string} text @param {() => void} action */
  function button(text,action) {const b=element("button",text);b.type="button";b.addEventListener("click",action);return b;}
  /** @param {string} text */
  function announce(text) {if(note) note.textContent=text;}
  function dismiss() {if(dialog) {dialog.close();erase(dialog);dialog.remove();dialog=undefined;} if(restore?.isConnected) restore.focus();}
  /** Forget every draft value, the secret included. */
  function forget() {values=new Map();controls=new Map();dirty=false;engaged=false;waiting=false;render=undefined;serial++;}
  function reset() {forget();dismiss();}
  /** Erase the draft (secret included) but keep the dialog able to show its end state. */
  function scrub() {values=new Map();dirty=false;}
  /** @param {HTMLDialogElement} box */
  function trap(box) {
    box.addEventListener("keydown",event=>{
      if(event.key !== "Tab") return;
      const focusable=Array.from(box.querySelectorAll("button,input,select,textarea,[tabindex]"))
        .filter(n=>n instanceof HTMLElement && n.tabIndex >= 0 && !n.hasAttribute("disabled") && n.getClientRects().length > 0);
      const index=focusable.indexOf(document.activeElement ?? box), target=event.shiftKey ? focusable.at(-1) : focusable[0];
      if(index < 0 || (event.shiftKey ? index === 0 : index === focusable.length-1)) {event.preventDefault();if(target instanceof HTMLElement) target.focus();else box.focus();}
    });
  }
  /** @param {string} title @param {string} tone */
  function modal(title,tone) {
    dismiss();dialog=element("dialog");dialog.className="desk "+tone;
    const heading=element("h2",title);heading.id="desk-title";heading.tabIndex=-1;
    dialog.setAttribute("aria-labelledby",heading.id);
    note=element("p");note.setAttribute("role","status");note.setAttribute("aria-live","polite");note.className="desk-note";
    dialog.append(heading,note);dialog.addEventListener("cancel",event=>{event.preventDefault();leave(()=>{});});
    trap(dialog);root.append(dialog);dialog.showModal();heading.focus();return dialog;
  }
  /** Leaving with a draft asks first; a pending write cannot be left.
   * @param {() => void} action
   */
  function leave(action) {
    if(waiting) {announce("Operação pendente. Aguarde o desfecho.");return;}
    if(!engaged || !dirty) {reset();action();return;}
    const prior=dialog;
    const confirm=element("dialog"), title=element("h2","Descartar rascunho?");title.id="desk-discard";
    confirm.setAttribute("aria-labelledby",title.id);confirm.append(title,element("p","As alterações não enviadas serão descartadas, inclusive a senha digitada."));
    const keep=()=>{confirm.close();erase(confirm);confirm.remove();(prior ?? restore)?.focus();};
    confirm.append(button("Continuar editando",keep),button("Descartar",()=>{keep();reset();action();}));
    confirm.addEventListener("cancel",event=>{event.preventDefault();keep();});trap(confirm);root.append(confirm);confirm.showModal();
  }

  // ---- values ---------------------------------------------------------------
  /** @param {Field} field @param {unknown} base */
  function initial(field,base) {
    if(field.kind === "secret") return "";
    const found=field.source && base !== undefined ? at(base,field.source) : undefined;
    if(field.kind === "records") {
      const list=Array.isArray(found) ? found : [];
      return list.map(item=>row(field.items ?? [],item));
    }
    if(found !== undefined && found !== null) return field.kind === "lines" && Array.isArray(found) ? found.map(String).join("\n") : field.kind === "integer" ? String(found) : found;
    if(field.kind === "flag") return field.default === true;
    if(field.kind === "lines") return "";
    if(field.kind === "choice") return typeof field.default === "string" ? field.default : field.choices?.[0]?.value ?? "";
    return field.default === undefined || field.default === null ? "" : String(field.default);
  }
  /** @param {Field[]} fields @param {unknown} item @returns {Row} */
  function row(fields,item) {
    /** @type {Map<string,unknown>} */ const map=new Map();
    for(const field of fields) map.set(field.id,initial(field,item));
    return {key:++rows,values:map};
  }
  /** @param {Row[] | undefined} list */
  function listOf(list) {return Array.isArray(list) ? list : [];}
  /** @param {Record<string,unknown>} body @param {Way} path @param {unknown} value */
  function put(body,path,value) {
    /** @type {Record<string,unknown>} */ let node=body;
    for(const [index,part] of path.entries()) {
      const name=String(part);
      if(index === path.length-1) {node[name]=value;break;}
      const next=node[name];
      if(!entry(next)) node[name]={};
      node=/** @type {Record<string,unknown>} */ (node[name]);
    }
  }
  /** @param {Field} field @param {Map<string,unknown>} map @param {Field[]} siblings */
  function shown(field,map,siblings) {
    if(!field.when) return true;
    const other=siblings.find(s=>JSON.stringify(s.path) === JSON.stringify(field.when?.path));
    return !!other && map.get(other.id) === field.when.value;
  }
  /** Builds a body by declared paths; returns local errors keyed by field id.
   * @param {Field[]} fields @param {Map<string,unknown>} map @param {string} prefix @param {Map<string,string>} errors
   */
  function build(fields,map,prefix,errors) {
    /** @type {Record<string,unknown>} */ const body={};
    for(const field of fields) {
      if(!shown(field,map,fields)) continue;
      const key=prefix+field.id, raw=map.get(field.id);
      if(field.kind === "records") {
        put(body,field.path,listOf(/** @type {Row[] | undefined} */ (raw)).map(r=>build(field.items ?? [],r.values,prefix+field.id+"."+r.key+".",errors)));
      } else if(field.kind === "flag") put(body,field.path,raw === true);
      else if(field.kind === "lines") put(body,field.path,String(raw ?? "").split("\n").map(v=>v.trim()).filter(v=>v.length > 0));
      else if(field.kind === "integer") {
        const text=String(raw ?? "").trim();
        if(!text) { if(!field.optional) errors.set(key,"Obrigatório."); continue; }
        if(!/^[0-9]{1,15}$/.test(text)) { errors.set(key,"Informe um número inteiro."); continue; }
        put(body,field.path,Number(text));
      } else {
        const text=field.kind === "secret" ? String(raw ?? "") : String(raw ?? "").trim();
        if(!text) { if(field.optional) continue; errors.set(key,"Obrigatório."); continue; }
        put(body,field.path,text);
      }
    }
    return body;
  }
  /** @param {Record<string,unknown>} body @param {Way} path */
  function drop(body,path) {
    const parent=path.length > 1 ? at(body,path.slice(0,-1)) : body, last=path.at(-1);
    if(entry(parent) && typeof last === "string") delete parent[last];
  }

  // ---- controls ---------------------------------------------------------------
  /** @param {HTMLElement} holder @param {Field[]} fields @param {Map<string,unknown>} map @param {string} prefix @param {() => void} redraw */
  function draw(holder,fields,map,prefix,redraw) {
    for(const field of fields) {
      if(!shown(field,map,fields)) continue;
      const key=prefix+field.id, id="f-"+key.replaceAll(".","-");
      const say=element("p");say.className="desk-error";say.id=id+"-error";say.hidden=true;
      const help=field.help ? element("p",field.help) : undefined;if(help) {help.className="desk-help";help.id=id+"-help";}
      const described=[help?.id,say.id].filter(v=>v).join(" ");
      if(field.kind === "records") {
        const set=element("fieldset");set.className="desk-records";const legend=element("legend",field.label);set.append(legend);
        if(help) set.append(help);
        const list=listOf(/** @type {Row[] | undefined} */ (map.get(field.id)));
        const name=field.item ?? "Item";
        if(!list.length) set.append(element("p","Nenhum item. Use o botão abaixo para adicionar."));
        for(const [index,item] of list.entries()) {
          const box=element("fieldset");box.className="desk-item";box.append(element("legend",name+" "+(index+1)));
          draw(box,field.items ?? [],item.values,prefix+field.id+"."+item.key+".",redraw);
          const moves=element("div");moves.className="desk-moves";
          const mover=(/** @type {number} */ step,/** @type {string} */ text)=>{
            const b=button(text,()=>{const next=[...list];const [taken]=next.splice(index,1);if(!taken) return;next.splice(index+step,0,taken);map.set(field.id,next);dirty=true;redraw();
              // Focus stays on the moved item: the same direction if still possible, else the other.
              const same=document.getElementById("m-"+taken.key+"-"+step), other=document.getElementById("m-"+taken.key+"-"+(-step));
              (same instanceof HTMLButtonElement && !same.disabled ? same : other)?.focus();});
            b.id="m-"+item.key+"-"+step;b.setAttribute("aria-label",text+": "+name+" "+(index+1));return b;
          };
          const up=mover(-1,"Mover para cima"), down=mover(1,"Mover para baixo");up.disabled=index === 0;down.disabled=index === list.length-1;
          const cut=button("Remover",()=>{map.set(field.id,list.filter(r=>r.key !== item.key));dirty=true;redraw();document.getElementById("a-"+key)?.focus();});
          cut.setAttribute("aria-label","Remover: "+name+" "+(index+1));
          moves.append(up,down,cut);box.append(moves);set.append(box);
        }
        const add=button("Adicionar "+name.toLocaleLowerCase("pt-BR"),()=>{const next=[...list,row(field.items ?? [],undefined)];map.set(field.id,next);dirty=true;redraw();
          const created=next.at(-1), first=created ? document.getElementById("f-"+(prefix+field.id+"."+created.key+".").replaceAll(".","-")+(field.items?.[0]?.id ?? "")) : null;first?.focus();});
        add.id="a-"+key;set.append(add,say);holder.append(set);controls.set(key,{node:add,say});continue;
      }
      const wrap=element("div");wrap.className="desk-field kind-"+field.kind;
      const label=element("label",field.label);label.htmlFor=id;
      /** @type {HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement} */ let input;
      if(field.kind === "choice") {
        const select=element("select");
        for(const option of field.choices ?? []) {const o=element("option",option.text);o.value=option.value;select.append(o);}
        select.value=String(map.get(field.id) ?? "");
        select.addEventListener("change",()=>{map.set(field.id,select.value);dirty=true;if(fields.some(f=>f.when && JSON.stringify(f.when.path) === JSON.stringify(field.path))) {redraw();document.getElementById(id)?.focus();}});
        input=select;
      } else if(field.kind === "lines") {
        const area=element("textarea");area.rows=3;area.value=String(map.get(field.id) ?? "");area.spellcheck=false;
        area.addEventListener("input",()=>{map.set(field.id,area.value);dirty=true;});input=area;
      } else {
        const box=element("input");
        if(field.kind === "flag") {box.type="checkbox";box.checked=map.get(field.id) === true;box.addEventListener("change",()=>{map.set(field.id,box.checked);dirty=true;});}
        else {
          box.type=field.kind === "secret" ? "password" : "text";box.value=String(map.get(field.id) ?? "");box.spellcheck=false;
          box.autocomplete=field.kind === "secret" ? "new-password" : "off";
          if(field.kind === "integer") box.inputMode="numeric";
          box.addEventListener("input",()=>{map.set(field.id,box.value);dirty=true;});
        }
        input=box;
      }
      input.id=id;if(described) input.setAttribute("aria-describedby",described);
      if(field.kind === "flag") {wrap.append(input,label);} else wrap.append(label,input);
      if(help) wrap.append(help);
      wrap.append(say);holder.append(wrap);controls.set(key,{node:input,say});
    }
  }
  /** @param {Map<string,string>} errors */
  function mark(errors) {
    let first=true;
    for(const [key,control] of controls) {
      const text=errors.get(key);control.say.hidden=!text;control.say.textContent=text ?? "";
      // Linked by aria-describedby; announced by the status line; focus goes to the first.
      if(text && first) {control.node.focus();first=false;}
    }
    return !first;
  }
  /** Server field reasons (`body.a.0.b`) map back to the declared controls.
   * @param {Field[]} fields @param {Map<string,unknown>} map @param {{path:string,reason:string}[]} found
   */
  function locate(fields,map,found) {
    /** @type {Map<string,string>} */ const errors=new Map();
    /** @param {Field[]} list @param {Map<string,unknown>} own @param {string[]} trail @param {string} prefix */
    const walk=(list,own,trail,prefix)=>{
      for(const field of list) {
        const at=[...trail,...field.path.map(String)];
        if(field.kind === "records") listOf(/** @type {Row[] | undefined} */ (own.get(field.id))).forEach((r,i)=>walk(field.items ?? [],r.values,[...at,String(i)],prefix+field.id+"."+r.key+"."));
        for(const item of found) if(item.path === ["body",...at].join(".") && !errors.has(prefix+field.id)) errors.set(prefix+field.id,reasons.find(r=>r.value === item.reason)?.text ?? "Valor inválido.");
      }
    };
    walk(fields,map,[],"");
    return errors;
  }

  // ---- summary ----------------------------------------------------------------
  /** Review text of the draft; the secret is never repeated.
   * @param {Field[]} fields @param {Map<string,unknown>} map
   */
  function summary(fields,map) {
    const list=element("dl");list.className="desk-summary";
    for(const field of fields) {
      if(!shown(field,map,fields)) continue;
      const raw=map.get(field.id), row=element("div");const body=element("dd");
      if(field.kind === "secret") body.textContent=String(raw ?? "") ? "Informada (não exibida)" : "Não informada";
      else if(field.kind === "flag") body.textContent=raw === true ? "Sim" : "Não";
      else if(field.kind === "choice") body.textContent=field.choices?.find(c=>c.value === raw)?.text ?? String(raw ?? "");
      else if(field.kind === "records") {
        const items=listOf(/** @type {Row[] | undefined} */ (raw));
        if(!items.length) body.textContent="Nenhum.";
        for(const [index,item] of items.entries()) {const sub=element("div");sub.className="desk-sub";sub.append(element("p",(field.item ?? "Item")+" "+(index+1)),summary(field.items ?? [],item.values));body.append(sub);}
      } else body.textContent=String(raw ?? "").trim() || "—";
      row.append(element("dt",field.label),body);list.append(row);
    }
    return list;
  }

  // ---- writes -----------------------------------------------------------------
  /** @param {string} category */
  function outcome(category) {return results.find(r=>r.value === category);}
  /** The version stamp observed by the server, when the closed envelope carries one.
   * @param {unknown} value */
  function latest(value) {const found=plan.latest ? at(value,plan.latest) : undefined;return typeof found === "number" ? found : undefined;}
  /** A test has no effect: its unknown result never blocks writes.
   * @param {Deed} deed
   */
  function isProbe(deed) {return client.quiet(deed.call);}
  /** @param {Deed} deed @param {unknown} base @param {string} typed */
  function body(deed,base,typed) {
    /** @type {Map<string,string>} */ const errors=new Map();
    const made=build(deed.fields ?? [],values,"",errors);
    if(deed.stamp && deed.origin) put(made,deed.stamp,at(base,deed.origin));
    if(deed.typed) {
      if(!typed.trim()) errors.set("typed","Obrigatório.");
      put(made,deed.typed.path,typed.trim());
    }
    return {made,errors};
  }
  /** Sends one write and interprets it. Never retries, rebases or queues.
   * @param {Deed} deed @param {string} call @param {Record<string,unknown>} made @param {string | undefined} identity
   * @returns {Promise<Sent>}
   */
  async function send(deed,call,made,identity) {
    void deed;
    if(waiting || client.busy()) return {kind:"busy-local"};
    waiting=true;const ticket=serial;
    try {
      const written=await client.submit(call,made,identity);
      if(ticket !== serial) return {kind:"gone"};
      return written;
    } catch(error) {
      if(error instanceof AccessError && error.kind === "authentication") return {kind:"gone"};
      // Refused before any flight: the local model check did not accept the body.
      return {kind:"local"};
    } finally {if(ticket === serial) waiting=false;}
  }

  /** Opens the form of one declared write over its base reading.
   * @param {Deed} deed @param {unknown} base @param {string | undefined} identity
   */
  function start(deed,base,identity) {
    if(ended || engaged || waiting) return;
    if(blocked || doubt) return;
    engaged=true;dirty=false;restore=document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
    for(const field of deed.fields ?? []) values.set(field.id,initial(field,base));
    let typed="";
    /** @type {"draft" | "review" | "pending" | "conflict" | "ending"} */ let stage=(deed.fields ?? []).length ? "draft" : "review";
    const box=modal(deed.title,deed.tone ?? "plain");
    const content=element("div");content.className="desk-content";box.append(content);
    render=()=>{
      erase(content);controls=new Map();
      if(stage === "draft") {
        const form=element("form");form.noValidate=true;form.addEventListener("submit",event=>event.preventDefault());
        draw(form,deed.fields ?? [],values,"",()=>render?.());
        const moves=element("div");moves.className="moves";
        moves.append(button("Revisar e confirmar",()=>{
          const {errors}=body(deed,base,typed);
          if(mark(errors)) {announce("Corrija os campos indicados.");return;}
          stage="review";render?.();announce("");
        }),button("Cancelar",()=>leave(()=>{})));
        form.append(moves);content.append(form);
      } else if(stage === "review" || stage === "pending") {
        if((deed.fields ?? []).length) content.append(element("h3","Resumo"),summary(deed.fields ?? [],values));
        const warn=element("p",deed.confirm);warn.className="desk-confirm "+(deed.tone ?? "plain");content.append(warn);
        if(deed.typed) {
          const field=deed.typed, wrap=element("div");wrap.className="desk-field kind-text";
          const label=element("label",field.label), input=element("input");input.id="f-typed";label.htmlFor=input.id;input.type="text";input.autocomplete="off";input.spellcheck=false;input.value=typed;
          const say=element("p");say.className="desk-error";say.id="f-typed-error";say.hidden=true;input.setAttribute("aria-describedby",say.id);
          input.addEventListener("input",()=>{typed=input.value;dirty=true;});
          wrap.append(label,input,say);content.append(wrap);controls.set("typed",{node:input,say});
        }
        const moves=element("div");moves.className="moves";
        const go=button(isProbe(deed) ? deed.label : "Confirmar",()=>{void confirm();});
        if(deed.tone === "danger") go.className="danger";
        const back=(deed.fields ?? []).length ? button("Voltar ao rascunho",()=>{stage="draft";render?.();}) : undefined;
        const cancel=button("Cancelar",()=>leave(()=>{}));
        if(stage === "pending") {go.disabled=true;cancel.disabled=true;if(back) back.disabled=true;}
        moves.append(go,...(back ? [back] : []),cancel);content.append(moves);
      } else if(stage === "conflict") {
        const moves=element("div");moves.className="moves";
        moves.append(button("Voltar ao rascunho",()=>{stage="draft";render?.();}),button("Descartar e reler",()=>{reset();hooks.refresh();}));
        content.append(moves);
      } else {
        content.append(button("Fechar",()=>{reset();hooks.refresh();}));
      }
    };
    const confirm=async()=>{
      const {made,errors}=body(deed,base,typed);
      if(mark(errors)) {announce("Corrija os campos indicados.");return;}
      stage="pending";render?.();announce(isProbe(deed) ? "Testando…" : "Enviando… aguarde.");
      const result=await send(deed,deed.call,made,identity);
      if(result.kind === "gone") return;
      if(result.kind === "busy-local") {stage="review";render?.();announce("Operação pendente. Aguarde o desfecho.");return;}
      if(result.kind === "local") {stage=(deed.fields ?? []).length ? "draft" : "review";render?.();announce("Algum valor está fora do formato aceito. Revise os campos.");return;}
      if(result.kind === "done") {
        for(const field of deed.fields ?? []) if(field.kind === "secret") values.set(field.id,"");
        if(isProbe(deed)) {stage="ending";render?.();announce(deed.done);return;}
        const value=result.value;const done=deed.done;reset();hooks.reread(deed,value);announceLater(done);return;
      }
      if(result.kind === "unknown") {
        if(isProbe(deed)) {stage="ending";render?.();announce("Resultado do teste desconhecido. Um teste nunca grava nem publica nada.");return;}
        doubt=true;scrub();stage="ending";render?.();announce(plan.unknown ?? "Resultado desconhecido.");return;
      }
      if(result.kind !== "refused") return;
      const known=outcome(result.category), kind=known?.kind ?? "uncertain", text=known?.text ?? (plan.unknown ?? "Resultado desconhecido.");
      if(kind === "uncertain") {
        if(isProbe(deed)) {stage="ending";render?.();announce(text);return;}
        doubt=true;scrub();stage="ending";render?.();announce(text);return;
      }
      if(kind === "blocked") {blocked=true;scrub();stage="ending";render?.();announce(text);return;}
      if(kind === "conflict") {stage="conflict";render?.();const now=latest(result.value);announce(text+(now !== undefined ? " Versão atual: "+now+"." : ""));return;}
      // Refused or busy: nothing was altered; the draft stays for an explicit new gesture.
      stage=(deed.fields ?? []).length ? "draft" : "review";render?.();
      const located=locate(deed.fields ?? [],values,result.fields);mark(located);announce(text);
    };
    render();
  }
  /** @type {string | undefined} */ let pendingNote;
  /** @param {string} text */
  function announceLater(text) {pendingNote=text;}

  return {
    /** Declared writes for one place, over the base reading that shows them.
     * @param {"collection"|"detail"|"aside"} place @param {unknown} base
     */
    offered:(place,base)=>deeds.filter(d=>d.place === place && (plan.guide.action !== d.id) && (!d.visible || at(base,d.visible.path) === d.visible.value)),
    start,
    active:()=>engaged && dirty,
    engaged:()=>engaged,
    leave,
    /** Writes are off while blocked (restart) or in doubt (until a fresh read). */
    locked:()=>blocked || doubt,
    why:()=>blocked ? "Alterações indisponíveis até o Gateway reiniciar." : doubt ? "Há uma escrita com resultado desconhecido. Releia o estado antes de novas alterações." : "",
    /** A successful read after a doubt restores writes; a block stays until restart. */
    settle:()=>{if(!engaged) doubt=false;},
    /** @returns {string | undefined} */
    take:()=>{const text=pendingNote;pendingNote=undefined;return text;},
    close:()=>{ended=true;reset();},
    /** The declared registration wizard, drawn in the page instead of a modal.
     * @param {HTMLElement} holder @param {number} step @param {unknown} base @param {(step:number)=>void} move @param {(value:unknown, deed:Deed)=>void} arrived
     */
    wizard:(holder,step,base,move,arrived)=>{
      const deed=deeds.find(d=>d.id === plan.guide.action);if(!deed) return false;
      if(!engaged) {engaged=true;dirty=false;values=new Map();for(const field of deed.fields ?? []) values.set(field.id,initial(field,undefined));}
      const steps=plan.guide.steps, current=steps[step];if(!current) return false;
      const own=(deed.fields ?? []).filter(f=>(current.fields ?? []).includes(f.id));
      note=element("p");note.setAttribute("role","status");note.setAttribute("aria-live","polite");note.className="desk-note";
      const card=element("section");card.className="card";card.setAttribute("aria-label",current.label);
      card.append(element("h3",(step+1)+". "+current.label),element("p",current.text),note);
      controls=new Map();
      const redraw=()=>{move(step);};
      if(own.length) {const form=element("form");form.noValidate=true;form.addEventListener("submit",event=>event.preventDefault());draw(form,own,values,"",redraw);card.append(form);}
      const last=step === steps.length-1, testing=!own.length && !last && !!deed.probe;
      const moves=element("div");moves.className="moves";
      const back=button("Anterior",()=>move(step-1));back.disabled=step === 0 || waiting;
      const next=button("Próximo",()=>{
        /** @type {Map<string,string>} */ const errors=new Map();build(own,values,"",errors);
        if(mark(errors)) {announce("Corrija os campos indicados.");return;}
        move(step+1);
      });next.disabled=last || waiting;
      if(testing) {
        const test=button("Testar conexão",()=>{void (async()=>{
          const {made,errors}=body(deed,base,"");
          if(errors.size) {announce("Há campos obrigatórios sem valor nos passos anteriores.");return;}
          for(const path of deed.drop ?? []) drop(made,path);
          if(!deed.probe) return;
          announce("Testando…");test.disabled=true;
          const result=await send(deed,deed.probe,made,undefined);test.disabled=false;
          if(result.kind === "gone") return;
          if(result.kind === "done") announce("Conexão verificada com este rascunho. Nada foi gravado nem publicado.");
          else if(result.kind === "refused") announce(outcome(result.category)?.text ?? "Teste recusado.");
          else if(result.kind === "local") announce("Algum valor está fora do formato aceito. Revise os passos anteriores.");
          else announce("Resultado do teste desconhecido. Um teste nunca grava nem publica nada.");
        })();});
        card.append(test);
      }
      if(last) {
        card.append(summary(deed.fields ?? [],values));
        const warn=element("p",deed.confirm);warn.className="desk-confirm plain";card.append(warn);
        const send1=button(deed.title,()=>{void (async()=>{
          if(blocked || doubt) {announce(blocked ? "Alterações indisponíveis até o Gateway reiniciar." : "Releia o estado antes de novas alterações.");return;}
          const {made,errors}=body(deed,base,"");
          if(errors.size) {announce("Há campos obrigatórios sem valor nos passos anteriores.");return;}
          announce("Enviando… aguarde.");send1.disabled=true;back.disabled=true;
          const result=await send(deed,deed.call,made,undefined);
          if(result.kind === "gone") return;
          send1.disabled=false;back.disabled=false;
          if(result.kind === "done") {const value=result.value;forget();arrived(value,deed);return;}
          if(result.kind === "local") {announce("Algum valor está fora do formato aceito. Revise os passos anteriores.");return;}
          if(result.kind === "unknown") {doubt=true;forget();announce(plan.unknown ?? "Resultado desconhecido.");send1.disabled=true;return;}
          if(result.kind !== "refused") return;
          const known=outcome(result.category), kind=known?.kind ?? "uncertain", text=known?.text ?? (plan.unknown ?? "Resultado desconhecido.");
          if(kind === "uncertain") {doubt=true;forget();send1.disabled=true;}
          if(kind === "blocked") {blocked=true;forget();send1.disabled=true;}
          const now=latest(result.value);announce(text+(kind === "conflict" && now !== undefined ? " Versão atual do catálogo: "+now+"." : ""));
        })();});
        send1.className="primary";card.append(send1);
      }
      moves.append(back,next);card.append(moves);
      holder.append(card);return true;
    },
    /** @returns {boolean} */
    draftOpen:()=>engaged,
  };
}
