import { at, entry, reader } from "./reader.js";
import { capture } from "./commands.js";

/** @param {unknown} value @returns {Record<string,unknown>[]} */
function rows(value) {if(!Array.isArray(value) || !value.every(entry)) throw new Error("Request refused.");return value;}
/** @param {unknown} value @returns {string} */
function word(value) {if(typeof value !== "string") throw new Error("Request refused.");return value;}
/** @param {unknown} value @returns {Record<string,unknown>} */
function authorRecord(value) {if(!entry(value)) throw new Error("Request refused.");return value;}
/** @param {unknown} value @returns {string[]} */
function trail(value) {if(!Array.isArray(value) || !value.every(v=>typeof v === "string" && !["__proto__","constructor","prototype"].includes(v))) throw new Error("Request refused.");return value;}
/** @param {unknown} source */
export function author(source) {
  const book=capture(source);if(!entry(book)) throw new Error("Request refused.");
  const calls=rows(book.calls), views=rows(book.views), models=rows(book.models), links=rows(book.bindings), editors=rows(book.editors), messages=rows(book.messages), lens=reader(book);
  /** @param {unknown} key */
  function shape(key) {const value=models.find(m=>m.id === key)?.shape;if(!entry(value)) throw new Error("Request refused.");return value;}
  /** @param {unknown} key */
  function fields(key) {return rows(shape(key).fields);}
  /** @param {unknown} key @param {string} role */
  function slot(key,role) {return links.filter(l=>l.model === key && l.role === role).map(l=>trail(l.path)[0]).filter(v=>v !== undefined);}
  const checkCall=authorRecord(calls.find(c=>c.operation === "check")), consentCall=authorRecord(calls.find(c=>c.operation === "confirm"));
  if(!checkCall || !consentCall) throw new Error("Request refused.");
  const home=views.find(v=>Array.isArray(v.actions) && v.actions.includes(checkCall.id));if(!home) throw new Error("Request refused.");
  const homeCall=authorRecord(calls.find(c=>c.id === home.call));
  const documentField=authorRecord(fields(homeCall.output).find(f=>shape(f.ref).type === "object"));
  const consent=rows(home.controls).find(c=>c.type === "confirm" && c.model === consentCall.input);if(!consent) throw new Error("Request refused.");
  /** @param {unknown} value */
  function documentValue(value) {const clean=capture(value);lens.inspectData(homeCall.output,clean);const doc=at(clean,[word(documentField.name)]);if(!entry(doc)) throw new Error("Request refused.");return doc;}
  /** @param {unknown} key @param {unknown} value @param {boolean} transient @returns {unknown} */
  function omit(key,value,transient) {
    const node=shape(key);
    if(node.type === "nullable") return value === null ? null : omit(node.item,value,transient);
    if(node.type === "list") {if(!Array.isArray(value)) throw new Error("Request refused.");return value.map(v=>omit(node.item,v,transient));}
    if(node.type !== "object") return value;
    if(!entry(value)) throw new Error("Request refused.");
    const excluded=[...slot(key,"order"),...(transient ? [...slot(key,"identity"),...slot(key,"version")] : [])];
    return Object.fromEntries(fields(key).filter(f=>!excluded.includes(word(f.name)) && Object.hasOwn(value,word(f.name))).map(f=>[word(f.name),omit(f.ref,value[word(f.name)],transient)]));
  }
  const profiles=views.flatMap(view=>{
    const actions=calls.filter(c=>Array.isArray(view.actions) && view.actions.includes(c.id));
    const create=actions.find(c=>c.operation === "create");if(!create) return [];
    const replace=actions.find(c=>c.operation === "replace"), remove=actions.find(c=>c.operation === "delete");if(!replace || !remove) throw new Error("Request refused.");
    const container=fields(create.input).find(f=>shape(f.ref).type === "object");if(!container) throw new Error("Request refused.");
    const controls=rows(view.controls).filter(c=>c.model === container.ref && c.type !== "confirm");
    const target=trail(rows(controls[0]?.projections)[0]?.target);if(target.length !== 1) throw new Error("Request refused.");
    const listField=fields(documentField.ref).find(f=>f.name === target[0]);if(!listField || shape(listField.ref).type !== "list") throw new Error("Request refused.");
    const itemKey=shape(listField.ref).item, identity=slot(itemKey,"identity")[0];if(!identity) throw new Error("Request refused.");
    const nested=fields(container.ref).find(f=>shape(f.ref).type === "object");
    const choice=controls.find(c=>c.type === "select" && shape(fields(container.ref).find(f=>f.name === trail(c.path)[0])?.ref).type === "string");
    const warning=rows(view.controls).find(c=>c.type === "confirm");
    const listing=calls.find(c=>c.id === view.call);if(!listing) throw new Error("Request refused.");
    const list=fields(listing.output).find(f=>shape(f.ref).type === "list");if(!list) throw new Error("Request refused.");
    return [{id:word(view.id),label:word(view.label),create:word(create.id),replace:word(replace.id),remove:word(remove.id),member:word(container.name),model:word(container.ref),controls,target,itemKey,identity,listing:word(list.name),output:listing.output,nested:nested ? word(nested.name) : undefined,choice:choice ? trail(choice.path)[0] : undefined,warning:warning ? word(warning.label) : undefined}];
  });
  /** @param {string} id */
  function profile(id) {const result=profiles.find(p=>p.id === id);if(!result) throw new Error("Request refused.");return result;}
  /** @param {string} id @param {unknown} value */
  function items(id,value) {const p=profile(id), list=at(documentValue(value),p.target);if(!Array.isArray(list)) throw new Error("Request refused.");return list;}
  /** @param {string} id @param {unknown} value */
  function content(id,value) {
    const p=profile(id), clean=authorRecord(capture(value));
    const result=Object.fromEntries(fields(p.model).filter(f=>Object.hasOwn(clean,word(f.name))).map(f=>[word(f.name),clean[word(f.name)]]));
    lens.inspectData(p.model,result);return capture(result);
  }
  /** @param {string} id @param {unknown} value */
  function defaults(id,value=undefined) {
    const p=profile(id);if(value !== undefined) return content(id,value);
    return capture(Object.fromEntries(p.controls.filter(c=>c.default !== null).map(c=>[word(trail(c.path)[0]),c.default])));
  }
  /** @param {string} id @param {unknown} value @param {unknown} registry */
  function checkedContent(id,value,registry) {
    const p=profile(id), clean=capture(value);lens.inspectData(p.model,clean);
    if(p.choice && p.nested) {
      const name=at(clean,[p.choice]), editor=editors.find(e=>e.name === name);
      if(!editor || !available(registry).includes(word(name))) throw new Error("Request refused.");
      const detail=at(clean,[p.nested]);lens.inspectData(editor.model,detail);
      for(const control of rows(editor.controls)) {
        const present=at(detail,control.path) !== undefined;
        if(entry(control.condition)) {
          const enabled=at(detail,control.condition.path) === control.condition.value;
          if(enabled !== present) throw new Error("Request refused.");
        }
      }
    }
    return clean;
  }
  // The sole unassociated, non-template read with a list of editor names is the registry.
  const registryCall=authorRecord(calls.find(c=>c.method === "GET" && c.identity === null && !views.some(v=>v.call === c.id)));
  /** @param {unknown} registry */
  function available(registry) {
    lens.inspectData(registryCall.output,registry);
    const list=fields(registryCall.output).find(f=>shape(f.ref).type === "list");if(!list) throw new Error("Request refused.");
    const values=at(registry,[word(list.name)]);if(!Array.isArray(values)) throw new Error("Request refused.");
    return editors.filter(e=>values.some(v=>{
      if(!entry(v) || v.name !== e.name) return false;
      const names=Object.values(v).flatMap(x=>Array.isArray(x) ? x : []);
      const wanted=rows(e.controls).map(c=>trail(c.path)[0]);
      return names.length === wanted.length && wanted.every(n=>names.includes(n));
    })).map(e=>word(e.name));
  }
  /** Display offsets never change snapshots or transport data.
   * @param {unknown} key @param {unknown} value @returns {unknown} */
  function display(key,value) {
    const node=shape(key);
    if(node.type === "nullable") return value === null ? null : display(node.item,value);
    if(node.type === "list") {if(!Array.isArray(value)) throw new Error("Request refused.");return value.map(v=>display(node.item,v));}
    if(node.type !== "object") return value;
    const raw=authorRecord(value), offsets=slot(key,"order");
    return Object.fromEntries(fields(key).filter(f=>Object.hasOwn(raw,word(f.name))).map(f=>{
      const name=word(f.name), item=raw[name];return [name,offsets.includes(name) && typeof item === "number" ? item+1 : display(f.ref,item)];
    }));
  }
  const batches=views.flatMap(view=>{
    const action=calls.find(c=>Array.isArray(view.actions) && view.actions.includes(c.id) && c.identity === null && ["move","replace","append"].includes(word(c.operation)));
    if(!action) return [];
    const controls=rows(view.controls).filter(c=>c.model === action.input && c.type !== "read");
    if(!controls.length) throw new Error("Request refused.");
    return [{id:word(view.id),call:word(action.id),model:action.input,operation:word(action.operation),label:action.operation === "replace" ? "Editar limites" : word(controls[0]?.label),controls}];
  });
  /** @param {string} id */
  function batch(id) {const p=batches.find(v=>v.id === id);if(!p) throw new Error("Request refused.");return p;}
  /** @param {Record<string,unknown>} control */
  function targetOf(control) {return trail(rows(control.projections)[0]?.target);}
  /** @param {string} id @param {unknown} base */
  function initial(id,base) {
    const p=batch(id), doc=documentValue(base);
    return capture(Object.fromEntries(p.controls.map(c=>{
      const value=at(doc,targetOf(c));
      if(p.operation === "move") {const q=profile(id);return [word(trail(c.path)[0]),rows(value).map(v=>v[q.identity])];}
      return [word(trail(c.path)[0]),p.operation === "append" ? [] : value];
    })));
  }
  /** @param {string} id @param {unknown} base @param {unknown} value */
  function checkedBatch(id,base,value) {
    const p=batch(id), clean=authorRecord(capture(value)), keys=p.controls.map(c=>word(trail(c.path)[0]));
    if(Object.keys(clean).length !== keys.length || !keys.every(k=>Object.hasOwn(clean,k))) throw new Error("Request refused.");
    const version=slot(p.model,"version")[0];if(!version) throw new Error("Request refused.");
    lens.inspectData(p.model,{...clean,[version]:1});
    if(!consented(base)) throw new Error("Request refused.");
    if(p.operation === "move") {
      const key=word(keys[0]), order=clean[key], original=at(initial(id,base),[key]);
      if(!Array.isArray(order) || !Array.isArray(original) || order.length !== original.length || new Set(order).size !== order.length || !original.every(v=>order.includes(v))) throw new Error("Request refused.");
    }
    if(p.operation === "append" && !keys.every(k=>Array.isArray(clean[k]) && clean[k].length > 0)) throw new Error("Request refused.");
    return capture(clean);
  }
  /** @param {string} id @param {unknown} base @param {unknown} value */
  function batchCandidate(id,base,value) {
    const p=batch(id), clean=authorRecord(checkedBatch(id,base,value)), doc=documentValue(base);
    let next={...doc};
    for(const control of p.controls) {
      const target=targetOf(control), key=word(trail(control.path)[0]);let item=clean[key];
      if(p.operation === "move") {const q=profile(id), original=items(id,base);if(!Array.isArray(item)) throw new Error("Request refused.");item=item.map(v=>original.find(row=>at(row,[q.identity]) === v));}
      if(p.operation === "append") {const original=at(doc,target);if(!Array.isArray(original) || !Array.isArray(item)) throw new Error("Request refused.");item=[...original,...item];}
      if(target.length === 1) next={...next,[word(target[0])]:item};
      else if(target.length === 2) next={...next,[word(target[0])]:{...authorRecord(next[word(target[0])]),[word(target[1])]:item}};
      else throw new Error("Request refused.");
    }
    const result=capture(omit(documentField.ref,next,true));lens.inspectData(checkCall.input,result);return result;
  }
  /** @param {unknown} base @param {{page:string,operation:"create"|"replace"|"delete",value:unknown,identity:string|undefined} | undefined} edit */
  function candidate(base,edit=undefined) {
    const doc=documentValue(base);let draft={...doc};
    if(edit) {
      const p=profile(edit.page), list=items(p.id,base), index=list.findIndex(v=>at(v,[p.identity]) === edit.identity);
      if(edit.operation !== "create" && index < 0) throw new Error("Request refused.");
      const value=capture(edit.value);if(edit.operation !== "delete") lens.inspectData(p.model,value);
      const next=[...list];
      if(edit.operation === "create") next.push(value);
      else if(edit.operation === "delete") next.splice(index,1);
      else {const prior=next[index];if(!entry(prior) || !entry(value)) throw new Error("Request refused.");next[index]={...value,[p.identity]:prior[p.identity]};}
      draft={...draft,[word(p.target[0])]:next};
    }
    // New identities never enter this transient projection. The snapshot stays intact.
    const result=capture(omit(documentField.ref,draft,true));lens.inspectData(checkCall.input,result);return result;
  }
  /** @param {unknown} value */
  function consented(value) {lens.inspectData(homeCall.output,value);return lens.bound(homeCall.output,value,"consent")[0] === true;}
  return Object.freeze({
    /** @param {string} id @param {unknown} value */ displayed:(id,value)=>{const c=calls.find(c=>c.id === id);if(!c) throw new Error("Request refused.");lens.inspectData(c.output,value);return display(c.output,value);},
    /** @param {string} id @param {unknown} base @param {unknown} value */ batchKnown:(id,base,value)=>{
      const p=batch(id);if(p.operation === "move") return [];
      const clean=authorRecord(checkedBatch(id,base,value));
      return p.controls.flatMap(c=>{
        const target=targetOf(c), name=word(c.label), data=clean[word(trail(c.path)[0])], current=at(documentValue(base),target);
        return p.operation === "append" && Array.isArray(data) && Array.isArray(current) ? data.map((_v,i)=>({path:[...target,current.length+i].join("."),label:name})) : [{path:target.join("."),label:name}];
      });
    },
    batches,batch,initial,checkedBatch,batchCandidate,profiles,profile,items,content,defaults,checkedContent,available,candidate,consented,shape,fields,editors,
    /** @param {string} id @param {unknown} value */ listed:(id,value)=>{const p=profile(id);lens.inspectData(p.output,value);return rows(at(value,[p.listing]));},
    /** @param {string} id @param {unknown} value */ changeable:(id,value)=>{const p=profile(id);lens.inspectData(p.output,value);return lens.bound(p.output,value,"consent")[0] === true;},
    home:word(home.id),read:word(home.call),registry:word(registryCall.id),check:word(checkCall.id),
    consent:{call:word(consentCall.id),field:word(trail(consent.path)[0]),text:word(consent.label),label:word(rows(home.controls).find(c=>c.type === "confirm" && Array.isArray(c.path) && c.path.length === 0)?.label)},
    /** @param {unknown} value */ inspectCheck:value=>{lens.inspectData(checkCall.output,value);},
    /** @param {unknown} value */ inspectError:value=>{lens.inspectData(checkCall.error,value);return messages;},
    /** @param {string} id @param {unknown} base @param {unknown} value @param {string|undefined} identity */ known:(id,base,value,identity)=>{
      const p=profile(id), list=items(id,base), index=identity === undefined ? list.length : list.findIndex(v=>at(v,[p.identity]) === identity);
      if(index < 0) throw new Error("Request refused.");
      const common=p.controls.map(c=>({path:[...p.target,index,...trail(c.path)].join("."),label:word(c.label)}));
      const selected=p.choice ? at(value,[p.choice]) : undefined, editor=editors.find(e=>e.name === selected);
      if(editor && p.nested) for(const c of rows(editor.controls)) common.push({path:[...p.target,index,p.nested,...trail(c.path)].join("."),label:word(c.label)});
      return common;
    },
    /** @param {unknown} value @param {{path:string,label:string}[]} known */ reasons:(value,known)=>{
      lens.inspectData(checkCall.error,value);
      if(!entry(value) || !Array.isArray(value.fields)) return [];
      return value.fields.flatMap(item=>{
        if(!entry(item)) return [];
        const control=known.find(k=>k.path === item.path);
        const message=messages.find(m=>Object.entries(item).some(([k,v])=>k !== "path" && v === m.name));
        return control && message ? [{label:control.label,text:word(message.text)}] : [];
      });
    },
  });
}
