import { coordinate } from "./coordinator.js";
import { capture } from "./commands.js";
import { at, entry } from "./reader.js";
import { element, plain, erase } from "./screen.js";

/** @typedef {Awaited<ReturnType<typeof import("./transport.js").open>>} WorkClient */
/** @typedef {ReturnType<WorkClient["design"]>} Design */
/** @typedef {{page:string,operation:"create"|"replace"|"delete",identity:string|undefined}} Intent */
/** Local editing owns one coordinator and one modal. No operation starts implicitly.
 * @param {WorkClient} client @param {HTMLElement} root @param {() => void} refreshed
 */
export function workbench(client,root,refreshed) {
  const plan=client.design();
  /** @type {ReturnType<typeof coordinate> | undefined} */ let flow;
  /** @type {HTMLDialogElement | undefined} */ let dialog;
  /** @type {HTMLElement | undefined} */ let restore;
  /** @type {Intent | undefined} */ let intent;
  /** @type {string | undefined} */ let batchPage;
  /** @type {unknown} */ let base;
  /** @type {unknown} */ let raw;
  /** @type {unknown} */ let registry;
  /** @type {AbortController | undefined} */ let active;
  let ended=false, engaged=false, dirty=false, waiting=false, serial=0, checked=false, locked=false, examining=false;
  /** @type {HTMLParagraphElement | undefined} */ let note;
  /** @type {HTMLElement | undefined} */ let proof;
  /** @type {() => void} */ let detach=()=>{};
  function dismiss() {if(dialog) {dialog.close();erase(dialog);dialog.remove();dialog=undefined;}if(restore?.isConnected) restore.focus();}
  function reset() {serial++;active?.abort();active=undefined;flow?.release();flow=undefined;intent=undefined;batchPage=undefined;base=undefined;raw=undefined;registry=undefined;dirty=false;engaged=false;waiting=false;examining=false;checked=false;proof=undefined;note=undefined;dismiss();}
  function close() {ended=true;reset();detach();restore=undefined;}
  detach=client.onClose(close);
  /** @param {string} text @param {() => void} action */
  function button(text,action) {const b=element("button",text);b.type="button";b.addEventListener("click",action);return b;}
  /** @param {string} text */
  function announce(text) {if(note) note.textContent=text;}
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
  /** @param {string} title @param {() => void} cancel */
  function modal(title,cancel) {
    dismiss();dialog=element("dialog");const heading=element("h2",title);heading.id="edit-title";heading.tabIndex=-1;
    dialog.setAttribute("aria-labelledby",heading.id);note=element("p");note.setAttribute("role","status");note.setAttribute("aria-live","polite");
    dialog.append(heading,note);dialog.addEventListener("cancel",event=>{event.preventDefault();cancel();});
    trap(dialog);root.append(dialog);dialog.showModal();heading.focus();return dialog;
  }
  /** @param {() => void} action */
  function leave(action) {
    if(waiting) {announce("Operação pendente. Aguarde o desfecho.");return;}
    if(!engaged || !dirty) {reset();action();return;}
    const prior=dialog;if(!prior) return;
    // Keep the original controls in memory, inert under the nested modal.
    const confirm=element("dialog"), title=element("h2","Descartar rascunho?");title.id="discard-title";
    confirm.setAttribute("aria-labelledby",title.id);confirm.append(title,element("p","As alterações não salvas serão descartadas."));
    const keep=()=>{confirm.close();erase(confirm);confirm.remove();prior.focus();};
    confirm.append(button("Continuar editando",keep),button("Descartar",()=>{keep();reset();action();}));
    confirm.addEventListener("cancel",event=>{event.preventDefault();keep();});trap(confirm);root.append(confirm);confirm.showModal();
  }
  /** @param {string} title */
  async function start(title) {
    if(ended || engaged) return false;
    engaged=true;restore=document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
    active=new AbortController();flow=coordinate(client,plan.read);const ticket=++serial;waiting=true;
    const box=modal(title,()=>leave(()=>{}));box.append(button("Cancelar",()=>leave(()=>{})));announce("Carregando…");
    const good=await flow.load();
    if(ended || ticket !== serial) return false;
    waiting=false;const state=flow.getState();
    if(!good || state.tag !== "reading") {announce("Leitura indisponível. Feche e tente novamente.");return false;}
    base=state.snapshot.value;return true;
  }
  /** @param {string} page @param {"create"|"replace"|"delete"} operation @param {string | undefined} identity */
  async function edit(page,operation,identity=undefined) {
    try {
      if(locked) return;
      if(!await start(operation === "create" ? "Criar item" : operation === "replace" ? "Editar item" : "Excluir item")) return;
      const p=plan.profile(page);if(!plan.consented(base)) {announce("Adoção explícita necessária antes de editar.");return;}
      const selected=operation === "create" ? undefined : plan.items(page,base).find(v=>at(v,[p.identity]) === identity);
      if(operation !== "create" && selected === undefined) {announce("Item indisponível. Atualize a leitura.");return;}
      intent={page,operation,identity};
      if(operation === "delete") {raw={};renderDelete();return;}
      const ticket=serial;waiting=true;registry=await client.read(plan.registry,active?.signal);
      if(ended || ticket !== serial) return;waiting=false;
      if(client.describe().inspectDataFor(plan.registry,registry) !== client.describe().inspectDataFor(plan.read,base)) throw new Error("Request refused.");
      raw=plan.defaults(page,selected);
      if(selected !== undefined) plan.checkedContent(page,raw,registry);
      renderForm();
    } catch {if(!ended) {waiting=false;announce("Conteúdo incompatível. A leitura foi preservada; edição bloqueada.");}}
  }
  /** @param {string} page */
  async function editBatch(page) {
    try {
      if(locked) return;
      const p=plan.batch(page);if(!await start(p.label)) return;
      if(!plan.consented(base)) {announce("Adoção explícita necessária antes de editar.");return;}
      batchPage=page;raw=plan.initial(page,base);renderBatch();
    } catch {if(!ended) {waiting=false;announce("Conteúdo incompatível. Edição bloqueada.");}}
  }
  function renderBatch() {
    if(!batchPage || !entry(raw)) return;
    const page=batchPage,p=plan.batch(page),values={...raw};
    const box=modal(p.label,()=>leave(()=>{})), form=element("form");form.noValidate=true;
    const sync=()=>{raw=capture(values);};
    if(p.operation === "move") {
      const q=plan.profile(page), control=p.controls[0], key=control && Array.isArray(control.path) ? control.path[0] : undefined;
      if(typeof key !== "string" || !Array.isArray(values[key])) throw new Error("Request refused.");
      const order=[...values[key]], original=plan.items(page,base), list=element("section");
      const label=element("label","Filtrar exibição"), search=element("input");search.id="local-filter";label.htmlFor=search.id;search.autocomplete="off";
      form.append(element("p","Posições a partir de 1. O filtro muda somente a exibição; mover usa a ordem completa."),label,search,list);
      function draw() {
        erase(list);
        for(const [index,id] of order.entries()) {
          const item=original.find(v=>at(v,[q.identity]) === id), view=plan.content(page,item);
          if(!JSON.stringify(view).toLocaleLowerCase().includes(search.value.toLocaleLowerCase())) continue;
          const row=element("section");row.append(element("h3","Posição "+(index+1)),plain(view));
          for(const [text,delta] of [["Mover para cima",-1],["Mover para baixo",1]]) {
            const next=index+Number(delta), buttonId="move-"+index+"-"+delta;
            const move=button(String(text),()=>{
              if(waiting || ended || next<0 || next>=order.length) return;
              [order[index],order[next]]=[order[next],order[index]];values[key]=order;sync();changedDraft();draw();
              const target=document.getElementById("move-"+next+"-"+delta);if(target instanceof HTMLButtonElement && !target.disabled) target.focus();else {const fallback=list.querySelector("button:not(:disabled)");if(fallback instanceof HTMLElement) fallback.focus();}
            });move.id=buttonId;move.disabled=next<0 || next>=order.length;row.append(move);
          }
          list.append(row);
        }
      }
      search.addEventListener("input",draw);draw();
    } else if(p.operation === "append") {
      const c=p.controls[0], key=c && Array.isArray(c.path) ? c.path[0] : undefined;
      if(typeof key !== "string") throw new Error("Request refused.");
      form.append(element("h3","Base somente leitura"),plain(base),element("p","Somente inclusões. A releitura do servidor confirma nomes e duplicatas."));
      const label=element("label","Novos nomes, um por linha"), input=element("textarea");input.id="new-names";input.autocomplete="off";input.spellcheck=false;label.htmlFor=input.id;
      input.value=Array.isArray(values[key]) ? values[key].join("\n") : "";
      input.addEventListener("input",()=>{if(waiting && !examining) return;values[key]=input.value.split("\n");sync();changedDraft();});form.append(label,input);
    } else for(const c of p.controls) controlNode(c,values,form,sync);
    const save=button("Revisar alterações",()=>{
      if(waiting) return;
      try {plan.checkedBatch(page,base,raw);reviewBatch();} catch {announce("Confira os campos conhecidos antes de salvar.");}
    });
    form.addEventListener("submit",event=>{event.preventDefault();});
    form.append(button("Validar proposta",()=>{void examineDraft();}),save,button("Cancelar",()=>leave(()=>{})));box.append(form);
  }
  function reviewBatch() {
    if(!batchPage) return;
    const box=modal("Confirmar operação",renderBatch);
    box.append(element("p","Revise a proposta completa. Nada foi salvo."),plain(plan.batchCandidate(batchPage,base,raw)),button("Voltar ao rascunho",renderBatch),button("Cancelar",()=>leave(()=>{})),button("Confirmar",()=>{void commit();}));
  }
  function changedDraft() {checked=false;if(proof) erase(proof);dialog?.querySelectorAll("[aria-describedby]").forEach(n=>n.removeAttribute("aria-describedby"));serial++;active?.abort();active=new AbortController();if(examining) {waiting=false;examining=false;}dirty=true;announce("Rascunho não salvo. Resultado anterior descartado.");}
  /** @param {Record<string,unknown>} control @param {Record<string,unknown>} values @param {HTMLElement} parent @param {() => void} changed */
  function controlNode(control,values,parent,changed) {
    if(!Array.isArray(control.path) || typeof control.path[0] !== "string" || typeof control.label !== "string") throw new Error("Request refused.");
    const key=control.path[0], field=plan.fields(control.model).find(f=>f.name === key);if(!field) throw new Error("Request refused.");
    const shape=plan.shape(field.ref), label=element("label",control.label), id="field-"+String(control.id);
    const node=control.type === "select" ? element("select") : element("input");node.id=id;label.htmlFor=id;
    if(node instanceof HTMLSelectElement) {
      const empty=element("option","Escolha explicitamente");empty.value="";node.append(empty);
      const choices=Array.isArray(shape.choices) ? shape.choices : plan.available(registry);
      for(const choice of choices) {const option=element("option",String(choice));option.value=String(choice);node.append(option);}
      node.value=typeof values[key] === "string" ? values[key] : "";
    } else {
      node.autocomplete="off";node.spellcheck=false;
      node.type=control.type === "checkbox" ? "checkbox" : "text";
      if(control.type === "integer") node.inputMode="numeric";
      if(node.type === "checkbox") node.checked=values[key] === true;
      else node.value=values[key] === undefined ? "" : String(values[key]);
    }
    const update=()=>{
      if((waiting && !examining) || ended) return;
      let value;
      if(node instanceof HTMLInputElement && node.type === "checkbox") value=node.checked;
      else if(control.type === "integer") value=/^(0|[1-9][0-9]*)$/.test(node.value) && Number.isSafeInteger(Number(node.value)) ? Number(node.value) : node.value;
      else value=node.value;
      values[key]=value;changedDraft();changed();
    };
    node.addEventListener(node instanceof HTMLSelectElement || control.type === "checkbox" ? "change" : "input",update);parent.append(label,node);return node;
  }
  function renderForm() {
    if(!intent || !entry(raw)) return;
    const p=plan.profile(intent.page);let values={...raw};
    const box=modal(intent.operation === "create" ? "Criar item" : "Editar item",()=>leave(()=>{})), form=element("form");form.noValidate=true;
    const detail=element("section");
    function sync() {raw=capture(values);}
    function nested() {
      const focusId=document.activeElement instanceof HTMLElement && (detail.compareDocumentPosition(document.activeElement) & Node.DOCUMENT_POSITION_CONTAINED_BY) ? document.activeElement.id : undefined;
      erase(detail);if(!p.choice || !p.nested) return;
      const editor=plan.editors.find(e=>e.name === values[p.choice ?? ""]);if(!editor) return;
      const parentKey=p.nested, prior=values[parentKey];const local=entry(prior) ? {...prior} : {};
      for(const c of rowsForControls(editor.controls)) if(Array.isArray(c.path) && typeof c.path[0] === "string" && !Object.hasOwn(local,c.path[0]) && c.default !== null) local[c.path[0]]=c.default;
      values[parentKey]=local;detail.append(element("p",typeof editor.help === "string" ? editor.help : ""));
      for(const c of rowsForControls(editor.controls)) {
        if(entry(c.condition) && at(local,c.condition.path) !== c.condition.value) {if(Array.isArray(c.path) && typeof c.path[0] === "string") delete local[c.path[0]];continue;}
        controlNode(c,local,detail,()=>{sync();if(c.type === "checkbox") nested();});
      }
      sync();
      if(focusId) {const target=document.getElementById(focusId);if(target && (detail.compareDocumentPosition(target) & Node.DOCUMENT_POSITION_CONTAINED_BY)) target.focus();}
    }
    for(const c of p.controls) controlNode(c,values,form,()=>{
      if(Array.isArray(c.path) && c.path[0] === p.choice && p.nested) {values[p.nested]={};nested();}
      sync();
    });
    nested();sync();form.append(detail);
    const examine=button("Validar proposta",()=>{void examineDraft();});
    const save=element("button","Salvar");save.type="submit";
    form.append(examine,save,button("Cancelar",()=>leave(()=>{})));box.append(form);
    form.addEventListener("submit",event=>{event.preventDefault();if(waiting) return;try {if(!intent) return;plan.checkedContent(intent.page,raw,registry);if(p.warning) confirmNotice(p.warning,()=>{void commit();});else void commit();} catch {announce("Confira os campos conhecidos antes de salvar.");}});
  }
  /** @param {string} text @param {() => void} action */
  function confirmNotice(text,action) {
    const box=modal("Confirmar operação",()=>renderForm());box.append(element("p",text),button("Cancelar",()=>renderForm()),button("Confirmar",action));
  }
  function renderDelete() {
    const box=modal("Excluir item",()=>leave(()=>{}));box.append(element("p","Confirme a exclusão somente deste item."),button("Cancelar",()=>leave(()=>{})),button("Excluir",()=>{void commit();}));
  }
  async function examineDraft() {
    if(ended || waiting || !base) return;
    let ticket=serial;
    try {
      const edit=intent ? {...intent,value:plan.checkedContent(intent.page,raw,registry)} : undefined;
      const candidate=batchPage ? plan.batchCandidate(batchPage,base,raw) : plan.candidate(base,edit);ticket=++serial;waiting=true;examining=true;active=new AbortController();announce("Validando conteúdo…");
      const known=batchPage ? plan.batchKnown(batchPage,base,raw) : intent ? plan.known(intent.page,base,raw,intent.identity) : [];
      const result=await client.assess(candidate,known,active.signal);
      if(ended || ticket !== serial) return;
      checked=result.ok;announce(result.ok ? "Conteúdo e compilação válidos. Não salvo; conexão não testada; não garante segurança para todos os dados." : "Proposta inválida. Confira os campos conhecidos.");
      if(proof) {erase(proof);proof.remove();}proof=element("section");dialog?.append(proof);
      if(!result.ok) for(const [index,issue] of result.issues.entries()) {
        const message=element("p",issue.label+": "+issue.text);message.id="reason-"+index;proof.append(message);
        const label=Array.from(dialog?.querySelectorAll("label") ?? []).find(n=>n.textContent === issue.label);
        label?.control?.setAttribute("aria-describedby",message.id);
      }
    } catch {if(!ended && ticket === serial) announce("Validação indisponível ou incompatível. Nenhuma gravação foi solicitada.");}
    finally {if(ticket === serial) {waiting=false;examining=false;}}
  }
  async function commit() {
    if(ended || waiting || !flow) return;
    try {
      if(batchPage) {
        const p=plan.batch(batchPage), body=plan.checkedBatch(batchPage,base,raw);
        if(flow.getState().tag === "reading") flow.begin(p.call,body);
        else if(flow.getState().tag === "draft") flow.change(body);
      } else if(intent) {
        const p=plan.profile(intent.page), body=intent.operation === "delete" ? {} : {[p.member]:plan.checkedContent(intent.page,raw,registry)};
        const call=intent.operation === "create" ? p.create : intent.operation === "replace" ? p.replace : p.remove;
        if(flow.getState().tag === "reading") flow.begin(call,body,intent.identity);
        else if(flow.getState().tag === "draft") flow.change(body);
      }
      const ticket=serial;waiting=true;checked=false;dirty=true;
      const pending=flow.confirm();renderOutcome();await pending;
      if(ended || ticket !== serial) return;waiting=false;renderOutcome();
    } catch {if(!ended) {waiting=false;announce("Operação recusada. Rascunho preservado.");}}
  }
  function renderOutcome() {
    if(!flow || ended) return;
    const state=flow.getState(), box=modal("Resultado da operação",()=>{});
    if(state.tag === "unknown" || state.tag === "uncertain" || state.tag === "incompatible") locked=true;
    announce("message" in state ? state.message : state.tag === "pending" ? "Operação pendente. Não repita." : "Confira o estado.");
    if("edit" in state && state.edit) {box.append(element("h3","Base original"),plain(state.edit.base.value),element("h3","Rascunho preservado"),plain(raw));}
    if("newBase" in state && state.newBase) box.append(element("h3","Nova base separada"),plain(state.newBase.value));
    if(waiting) return;
    if(state.tag === "success" && state.newBase) box.append(button("Concluir",()=>{if(flow?.finish()) {reset();refreshed();}}));
    if(["success","conflict","unknown","uncertain"].includes(state.tag)) box.append(button("Reler estado",()=>{void (async()=>{if(!flow || waiting) return;waiting=true;const ticket=serial;await flow.reconcile();if(!ended && ticket === serial) {waiting=false;renderOutcome();}})();}));
    if(state.tag === "busy") box.append(button("Tentar novamente",()=>{void commit();}));
    if(state.tag === "conflict" && state.newBase && intent && intent.operation !== "delete") box.append(button("Revisar rascunho com nova base",()=>{
      if(!flow || !intent) return;const p=plan.profile(intent.page);
      try {if(flow.review({[p.member]:plan.checkedContent(p.id,raw,registry)})) {base=state.newBase?.value;checked=false;renderForm();}} catch {announce("Revisão incompatível. Rascunho preservado.");}
    }));
    if(state.tag === "conflict" && state.newBase && batchPage) box.append(button("Revisar rascunho com nova base",()=>{
      if(!flow || !batchPage) return;
      try {const body=plan.checkedBatch(batchPage,state.newBase?.value,raw);if(flow.review(body)) {base=state.newBase?.value;checked=false;renderBatch();}}
      catch {announce("Revisão incompatível. Rascunho preservado; descarte e inicie novamente para usar outra lista.");}
    }));
    box.append(button("Fechar e descartar rascunho",()=>leave(()=>refreshed())));
  }
  async function consentStart() {
    if(locked) return;
    if(!await start("Adoção explícita")) return;
    if(plan.consented(base)) {announce("Já adotada. Atualize a leitura; não repita a operação.");return;}
    const box=modal("Adoção explícita",()=>leave(()=>{})), label=element("label","Li e compreendi as consequências"), input=element("input");input.type="checkbox";input.checked=false;input.id="consent-entry";label.htmlFor=input.id;
    const submit=button(plan.consent.label,()=>{
      if(waiting || !input.checked || !flow) return;
      flow.begin(plan.consent.call,{[plan.consent.field]:true});void commit();
    });submit.disabled=true;input.addEventListener("change",()=>{submit.disabled=!input.checked;});
    box.append(element("p",plan.consent.text),label,input,button("Cancelar",()=>leave(()=>{})),submit);
  }
  /** @param {HTMLElement} panel @param {string} page @param {unknown} value */
  function attach(panel,page,value) {
    if(ended || engaged) return;
    if(page === plan.home) {
      panel.append(button("Validar documento",()=>{void (async()=>{if(await start("Validar documento")) await examineDraft();})();}));
      if(!plan.consented(value)) panel.append(button("Adoção explícita",()=>{void consentStart();}));
    }
    const bulk=plan.batches.find(v=>v.id === page);
    if(bulk) {const change=button(bulk.label,()=>{void editBatch(page);});change.disabled=locked;panel.append(change);}
    const p=plan.profiles.find(v=>v.id === page);if(!p) return;
    const permitted=!locked && plan.changeable(page,value), add=button("Criar",()=>{void edit(page,"create");});add.disabled=!permitted;panel.append(add);
    if(locked) panel.append(element("p","Escritas bloqueadas nesta sessão. Verificação operacional necessária."));
    if(!plan.changeable(page,value)) panel.append(element("p","Adoção explícita necessária antes de editar."));
    for(const [index,item] of plan.listed(page,value).entries()) {
      const identity=at(item,[p.identity]);if(typeof identity !== "string") continue;
      const row=element("section");row.append(element("h3","Item "+(index+1)));
      const change=button("Editar",()=>{void edit(page,"replace",identity);}), remove=button("Excluir",()=>{void edit(page,"delete",identity);});change.disabled=!permitted;remove.disabled=!permitted;row.append(change,remove);panel.append(row);
    }
  }
  return {attach,leave,close,active:()=>engaged,pending:()=>waiting,examined:()=>checked};
}
/** @param {unknown} value @returns {Record<string,unknown>[]} */
function rowsForControls(value) {if(!Array.isArray(value) || !value.every(entry)) throw new Error("Request refused.");return value;}
