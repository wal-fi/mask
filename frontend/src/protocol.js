/** Second-prefix writes (Phase 9, Stage 6): operation and its only method. */
const writing=Object.freeze({register:"POST",probe:"POST",renew:"POST",resume:"POST",pause:"POST",revise:"PUT",retire:"DELETE",amend:"PUT"});
/** @param {unknown} operation @returns {operation is keyof typeof writing} */
function written(operation) { return typeof operation === "string" && Object.hasOwn(writing,operation); }
/** @param {unknown} value @returns {value is Record<string, unknown>} */
function record(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
}
/** @param {unknown} value @returns {value is unknown[]} */
function sequence(value) { return Array.isArray(value); }
/** @param {unknown} value @returns {value is string[]} */
function strings(value) { return sequence(value) && value.every(v => typeof v === "string"); }
const denied = new Set(["__proto__", "constructor", "prototype"]);
/** @param {unknown} value @param {number} depth @param {Set<object>} seen @returns {boolean} */
function safe(value, depth, seen) {
  if (depth > 16) return false;
  if (typeof value === "number") return Number.isSafeInteger(value);
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (!record(value) && !sequence(value)) return false;
  if (seen.has(value)) return false;
  seen.add(value);
  const ok = Object.keys(value).every(k => !denied.has(k))
    && Object.values(value).every(v => safe(v, depth + 1, seen));
  seen.delete(value);
  return ok;
}
/** @param {unknown} value @param {unknown} node @param {Record<string,unknown>} defs @param {number} depth @returns {boolean} */
function accepts(value, node, defs, depth) {
  if (!record(node) || depth > 32) return false;
  if (typeof node.$ref === "string") return accepts(value, defs[node.$ref.split("/").at(-1) ?? ""], defs, depth+1);
  if ("const" in node && value !== node.const) return false;
  if (sequence(node.enum) && !node.enum.some(v => v === value)) return false;
  if (sequence(node.anyOf) && !node.anyOf.some(n => accepts(value,n,defs,depth+1))) return false;
  if (sequence(node.oneOf) && node.oneOf.filter(n => accepts(value,n,defs,depth+1)).length !== 1) return false;
  if (node.type === "null" && value !== null) return false;
  if (node.type === "boolean" && typeof value !== "boolean") return false;
  if (node.type === "integer" && (typeof value !== "number" || !Number.isSafeInteger(value))) return false;
  if (node.type === "string" && typeof value !== "string") return false;
  if (typeof value === "number") {
    if (typeof node.minimum === "number" && value < node.minimum) return false;
    if (typeof node.maximum === "number" && value > node.maximum) return false;
  }
  if (typeof value === "string") {
    if (typeof node.minLength === "number" && [...value].length < node.minLength) return false;
    if (typeof node.maxLength === "number" && [...value].length > node.maxLength) return false;
  }
  if (node.type === "array") {
    if (!sequence(value)) return false;
    if (typeof node.minItems === "number" && value.length < node.minItems) return false;
    if (typeof node.maxItems === "number" && value.length > node.maxItems) return false;
    if (!value.every(v => accepts(v,node.items,defs,depth+1))) return false;
  }
  if (node.type === "object") {
    if (!record(value) || !record(node.properties)) return false;
    const props = node.properties;
    if (strings(node.required) && !node.required.every(k => Object.hasOwn(value,k))) return false;
    if (!Object.keys(value).every(k => Object.hasOwn(props,k))) return false;
    if (!Object.entries(value).every(([k,v]) => accepts(v,props[k],defs,depth+1))) return false;
  }
  return true;
}
/** @param {unknown} value @returns {value is Record<string,unknown>[]} */
function records(value) { return sequence(value) && value.every(record); }
/** @param {unknown} value @param {unknown} descriptor @returns {boolean} */
function inspect(value, descriptor) {
  if (!record(descriptor) || !record(descriptor.$defs) || !safe(value,0,new Set())) return false;
  if (!accepts(value,descriptor,descriptor.$defs,0) || !record(value)) return false;
  if (!records(value.models) || !records(value.calls) || !records(value.views)
    || !records(value.editors) || !records(value.bindings) || !records(value.messages)) return false;
  if (!record(value.console)) return false;
  const surface = value.console;
  if (!record(surface.summary) || !record(surface.collection) || !record(surface.detail) || !record(surface.guide)) return false;
  const summary = surface.summary, collection = surface.collection, detail = surface.detail, guide = surface.guide;
  if (!records(summary.figures) || !records(collection.columns) || !records(detail.tabs) || !records(guide.steps)) return false;
  /** @type {Record<string,unknown>[]} */ const tabItems=[];
  for (const tab of detail.tabs) { if (!records(tab.entries)) return false; tabItems.push(...tab.entries); }
  /** @type {Record<string,unknown>[]} */ const pageItems=[];
  /** Every action, typed confirmation and nested form field carries an opaque id.
   * @param {unknown} list @param {number} depth @returns {Record<string,unknown>[] | undefined} */
  const nested=(list,depth)=>{
    if(!records(list) || depth > 2) return undefined;
    /** @type {Record<string,unknown>[]} */ const found=[];
    for(const field of list) { found.push(field); if(field.items !== undefined) { const inner=nested(field.items,depth+1); if(!inner) return undefined; found.push(...inner); } }
    return found;
  };
  if (surface.actions !== undefined) {
    if (!records(surface.actions)) return false;
    for (const action of surface.actions) {
      const inner=nested([...(action.fields === undefined ? [] : sequence(action.fields) ? action.fields : [null]),...(action.typed === undefined || action.typed === null ? [] : [action.typed])],0);
      if(!inner) return false;
      pageItems.push(action,...inner);
    }
  }
  if (surface.pages !== undefined) {
    if (!records(surface.pages)) return false;
    for (const page of surface.pages) {
      if (!records(page.sections)) return false;
      for (const section of page.sections) { if (!records(section.entries)) return false; pageItems.push(...section.entries); }
    }
  }
  const all = [...value.models,...value.calls,...value.views,...value.editors,...value.bindings,...value.messages,
    summary,collection,detail,guide,...summary.figures,...collection.columns,...detail.tabs,...tabItems,...guide.steps,...pageItems];
  /** @type {Record<string,unknown>[]} */ const controls=[];
  for (const owner of [...value.views,...value.editors]) {
    if (!records(owner.controls)) return false;
    controls.push(...owner.controls);
  }
  if (controls.length > 512) return false;
  all.push(...controls);
  const ids=all.map(v=>v.id);
  if (!ids.every(v => typeof v === "string" && /^[a-z][0-9]+$/.test(v)) || new Set(ids).size !== ids.length) return false;
  /** @type {Map<string,Record<string,unknown>>} */ const models=new Map();
  for (const item of value.models) {
    if (typeof item.id !== "string" || !record(item.shape)) return false;
    models.set(item.id,item.shape);
  }
  /** @type {Map<string,number>} */ const heights=new Map();
  /** @param {string} key @param {Set<string>} seen @returns {number} */
  function visit(key,seen) {
    const node=models.get(key);
    if (!node || seen.has(key) || seen.size >= 16) return 0;
    const cached=heights.get(key);
    if(cached !== undefined) return cached;
    const next=new Set([...seen,key]);
    /** @type {unknown[]} */ let refs=[];
    if (node.type === "object") {
      if (!records(node.fields)) return 0;
      const names=node.fields.map(f=>f.name);
      if (!names.every(n=>typeof n === "string" && n.length > 0 && !denied.has(n)) || new Set(names).size !== names.length) return 0;
      refs=node.fields.map(f=>f.ref);
    }
    if (node.type === "list" || node.type === "nullable") refs=[node.item];
    if (node.type === "union") {
      if (typeof node.tag !== "string" || !node.tag || denied.has(node.tag) || !records(node.variants)) return 0;
      const values=node.variants.map(v=>JSON.stringify(v.value));
      if (new Set(values).size !== values.length) return 0;
      refs=node.variants.map(v=>v.ref);
      for (const variant of node.variants) {
        if (typeof variant.ref !== "string") return 0;
        const target=models.get(variant.ref);
        if (!target || target.type !== "object" || !records(target.fields)) return 0;
        const link=target.fields.find(f=>f.name === node.tag && f.required === true);
        if (!link || typeof link.ref !== "string") return 0;
        const tag=models.get(link.ref);
        if (!tag || tag.type !== "enum" || !sequence(tag.choices) || tag.choices.length !== 1 || tag.choices[0] !== variant.value) return 0;
      }
    }
    if (typeof node.min === "number" && typeof node.max === "number" && node.min > node.max) return 0;
    if (sequence(node.choices)) {
      const values=node.choices.map(v=>JSON.stringify(v));
      if (new Set(values).size !== values.length) return 0;
    }
    const levels=refs.map(ref=>typeof ref === "string" ? visit(ref,next) : 0);
    if(levels.some(v=>v===0)) return 0;
    const height=1+Math.max(0,...levels);
    if(height>16) return 0;
    heights.set(key,height);
    return height;
  }
  if (![...models.keys()].every(key=>visit(key,new Set()))) return false;
  /** @param {unknown} key @param {unknown} parts @returns {Record<string,unknown> | undefined} */
  function leaf(key,parts) {
    if (typeof key !== "string" || !sequence(parts) || parts.length > 16 || !models.has(key)) return undefined;
    let node=models.get(key);
    for (const part of parts) {
      while (node?.type === "nullable" && typeof node.item === "string") node=models.get(node.item);
      if (typeof part === "string" && part && !denied.has(part) && node?.type === "object" && records(node.fields)) {
        const field=node.fields.find(f=>f.name === part);
        if (!field || typeof field.ref !== "string") return undefined;
        node=models.get(field.ref);
      } else if (typeof part === "number" && Number.isSafeInteger(part) && part >= 0 && node?.type === "list" && typeof node.item === "string") node=models.get(node.item);
      else return undefined;
    }
    return node;
  }
  /** @param {unknown} key @param {unknown} parts */
  function linked(key,parts) { return leaf(key,parts) !== undefined; }
  /** @param {unknown} value @param {Record<string,unknown> | undefined} node @returns {boolean} */
  function fits(value,node) {
    if(value === null || value === undefined) return true;
    while(node?.type === "nullable" && typeof node.item === "string") node=models.get(node.item);
    if(!node) return false;
    if(node.type === "boolean") return typeof value === "boolean";
    if(node.type === "integer") return typeof value === "number" && Number.isSafeInteger(value) && value >= (typeof node.min === "number" ? node.min : 0) && value <= (typeof node.max === "number" ? node.max : Number.MAX_SAFE_INTEGER);
    if(node.type === "enum") return sequence(node.choices) && node.choices.some(v=>v === value);
    if(node.type === "string") {
      if(typeof value !== "string") return false;
      const prefix=typeof node.prefix === "string" ? node.prefix : "";
      const alphabet=typeof node.alphabet === "string" ? node.alphabet : "";
      return [...value].length >= (typeof node.min === "number" ? node.min : 0) && [...value].length <= (typeof node.max === "number" ? node.max : Number.MAX_SAFE_INTEGER) && value.startsWith(prefix) && (!alphabet || [...value.slice(prefix.length)].every(c=>alphabet.includes(c)));
    }
    return false;
  }
  for(const node of models.values()) if(node.type === "object" && records(node.fields)) {
    for(const field of node.fields) if(typeof field.ref !== "string" || !fits(field.default,models.get(field.ref))) return false;
  }
  for(const control of controls) if(!fits(control.default,leaf(control.model,control.path))) return false;
  const calls=new Map(value.calls.map(c=>[c.id,c]));
  for (const call of value.calls) {
    if (typeof call.path !== "string" || !(call.path.startsWith("/admin/v1/") || call.path.startsWith("/admin/v2/")) || /[?#%\\]|\/\//.test(call.path)) return false;
    // The second prefix only carries authenticated reads (Phase 9, Stage 5).
    // Second prefix: reads are GET; writes only with their own operation and method.
    if (call.path.startsWith("/admin/v2/") && !(call.method === "GET" ? call.operation === "read" : written(call.operation) && writing[call.operation] === call.method && typeof call.input === "string")) return false;
    if (call.path.startsWith("/admin/v1/") && written(call.operation)) return false;
    const parts=call.path.split("/").slice(3);
    if (parts.some(p=>!p || p === "." || p === "..")) return false;
    const slots=parts.filter(p=>p.includes("{") || p.includes("}"));
    if (slots.length > 1 || (slots.length === 0 && call.identity !== null)) return false;
    if (slots.length === 1 && (typeof call.identity !== "string" || denied.has(call.identity) || !/^[a-z_]+$/.test(call.identity) || !(slots[0] === "{"+call.identity+"}" || (slots[0]?.startsWith("{"+call.identity+"}:") && /^[a-z]+(?:-[a-z]+)*$/.test(slots[0].slice(call.identity.length+3)))))) return false;
    if (typeof call.error !== "string" || !models.has(call.error) || typeof call.output !== "string" || !models.has(call.output)) return false;
    if ((call.method === "GET") !== (call.input === null)) return false;
    if (call.input !== null && (typeof call.input !== "string" || !models.has(call.input))) return false;
  }
  for (const view of value.views) {
    if (calls.get(view.call)?.method !== "GET" || !sequence(view.actions) || !view.actions.every(a=>calls.has(a) && !written(calls.get(a)?.operation))) return false;
  }
  for (const editor of value.editors) if (typeof editor.model !== "string" || !models.has(editor.model)) return false;
  for (const control of controls) {
    if (control.projections !== undefined) {
      if(!records(control.projections)) return false;
      for (const projection of control.projections) {
        if(!sequence(projection.paths) || !projection.paths.every(p=>linked(control.model,p))) return false;
        if(!sequence(projection.target) || projection.target.length>16 || !projection.target.every(p=>(typeof p === "string" && p.length>0 && !denied.has(p)) || (typeof p === "number" && Number.isSafeInteger(p) && p>=0))) return false;
      }
    }
  }
  for (const item of [...controls,...value.bindings]) {
    if (!linked(item.model,item.path)) return false;
    if (item.condition !== null && item.condition !== undefined && (!record(item.condition) || !linked(item.model,item.condition.path))) return false;
  }
  /** @param {unknown} id @param {boolean} identity @returns {Record<string,unknown> | undefined} */
  function surfaceCall(id,identity) {
    const call=typeof id === "string" ? calls.get(id) : undefined;
    if (!call || typeof call.path !== "string" || !call.path.startsWith("/admin/v2/") || call.method !== "GET" || call.operation !== "read") return undefined;
    return (typeof call.identity === "string") === identity ? call : undefined;
  }
  const head=surfaceCall(summary.call,false), listing=surfaceCall(collection.call,false);
  const main=surfaceCall(detail.call,true), aside=surfaceCall(detail.extra,true);
  if (!head || !listing || !main || !aside || main.identity !== aside.identity) return false;
  if (!summary.figures.every(f=>linked(head.output,f.path))) return false;
  const rows=leaf(listing.output,collection.items);
  if (rows?.type !== "list" || typeof rows.item !== "string") return false;
  const row=rows.item;
  if (leaf(row,collection.key)?.type !== "string" || !linked(row,collection.title)) return false;
  if (!collection.columns.every(c=>linked(row,c.path))) return false;
  if (!sequence(collection.searchable) || !collection.searchable.every(p=>leaf(row,p)?.type === "string")) return false;
  for (const tab of detail.tabs) {
    const owner=tab.source === "main" ? main.output : aside.output;
    if (!records(tab.entries) || !tab.entries.every(e=>linked(owner,e.path))) return false;
    // Declared groups only arrange entries: every entry belongs to one and only one group.
    if (tab.groups !== undefined) {
      if (!records(tab.groups)) return false;
      const members=tab.groups.flatMap(g=>strings(g.members) ? g.members : [""]);
      const ids=tab.entries.map(e=>e.id);
      if (tab.groups.length && (members.length !== ids.length || new Set(members).size !== ids.length || !ids.every(id=>typeof id === "string" && members.includes(id)))) return false;
    }
  }
  if (detail.title !== undefined && detail.title !== null && (!sequence(detail.title) || leaf(main.output,detail.title)?.type !== "string")) return false;
  /** Form fields: target paths in the write input, sources in the base read.
   * @param {unknown} list @param {string} target @param {string | undefined} base @param {number} depth @returns {boolean}
   */
  function formed(list,target,base,depth) {
    if(!records(list) || depth > 2) return false;
    for(const field of list) {
      if(!sequence(field.path) || !linked(target,field.path)) return false;
      const sourced=field.source !== undefined && field.source !== null;
      if(sourced && (base === undefined || !linked(base,field.source))) return false;
      if(field.kind === "secret" && sourced) return false;
      const many=field.kind === "records", items=records(field.items) ? field.items : [];
      if(many !== (items.length > 0)) return false;
      if((field.kind === "choice") !== (records(field.choices) && field.choices.length > 0)) return false;
      if(many) {
        const into=leaf(target,field.path), from=base !== undefined && sourced ? leaf(base,field.source) : undefined;
        if(into?.type !== "list" || typeof into.item !== "string") return false;
        if(!formed(items,into.item,from?.type === "list" && typeof from.item === "string" ? from.item : undefined,depth+1)) return false;
      }
    }
    return true;
  }
  if (surface.actions !== undefined && records(surface.actions)) {
    /** @type {Record<string,string>} */ const bases={collection:String(listing.output),detail:String(main.output),aside:String(aside.output)};
    for (const action of surface.actions) {
      const call=typeof action.call === "string" ? calls.get(action.call) : undefined;
      if(!call || !written(call.operation) || typeof call.input !== "string" || typeof action.place !== "string" || !Object.hasOwn(bases,action.place)) return false;
      const base=bases[action.place] ?? "";
      if((action.place === "collection") !== (call.identity === null)) return false;
      if(action.place !== "collection" && call.identity !== main.identity) return false;
      if(!formed(action.fields === undefined ? [] : action.fields,call.input,base,0)) return false;
      const bare=(/** @type {unknown} */ v)=>v === undefined || v === null;
      if(bare(action.stamp) !== bare(action.origin)) return false;
      if(!bare(action.stamp) && (leaf(call.input,action.stamp)?.type !== "integer" || leaf(base,action.origin)?.type !== "integer")) return false;
      if((action.after === "open") !== !bare(action.lands)) return false;
      if(!bare(action.lands) && leaf(call.output,action.lands)?.type !== "string") return false;
      if(!bare(action.typed) && (!record(action.typed) || action.typed.kind !== "text" || !sequence(action.typed.source) || !formed([action.typed],call.input,base,0))) return false;
      if(!bare(action.visible) && (!record(action.visible) || !linked(base,action.visible.path))) return false;
      if(!bare(action.probe)) {
        const probe=typeof action.probe === "string" ? calls.get(action.probe) : undefined;
        if(!probe || probe.operation !== "probe" || typeof probe.input !== "string" || (probe.identity === null) !== (call.identity === null)) return false;
      }
      if(action.drop !== undefined && (!sequence(action.drop) || !action.drop.every(p=>linked(call.input,p)))) return false;
    }
    if(guide.action !== undefined && guide.action !== null) {
      const wizard=surface.actions.find(a=>a.id === guide.action);
      const call=wizard && typeof wizard.call === "string" ? calls.get(wizard.call) : undefined;
      if(!wizard || wizard.place !== "collection" || call?.operation !== "register" || !records(wizard.fields)) return false;
      const placed=guide.steps.flatMap(s=>strings(s.fields) ? s.fields : [""]);
      const own=wizard.fields.map(f=>f.id);
      if(placed.length !== own.length || !own.every(id=>typeof id === "string" && placed.includes(id))) return false;
    }
  }
  /** Terminal paths under an object; lists, text and choices end a path.
   * @param {Record<string,unknown> | undefined} node @param {string[]} path @param {number} depth @returns {string[][]}
   */
  function ends(node,path,depth) {
    while (node?.type === "nullable" && typeof node.item === "string") node=models.get(node.item);
    if (depth > 16) return [["\u0000"]];
    if (node?.type !== "object" || !records(node.fields)) return [path];
    return node.fields.flatMap(f=>typeof f.ref === "string" && typeof f.name === "string" ? ends(models.get(f.ref),[...path,f.name],depth+1) : [["\u0000"]]);
  }
  /** @param {string[]} whole @param {string[]} start */
  const starts=(whole,start)=>start.length <= whole.length && start.every((p,i)=>whole[i] === p);
  // Política v1 pages only arrange approved readings: one page per view, paths
  // inside that view's response, nothing read left out and nothing else shown.
  if (surface.pages !== undefined && records(surface.pages)) {
    /** @type {Set<unknown>} */ const pagesSeen=new Set();
    for (const page of surface.pages) {
      const view=value.views.find(v=>v.id === page.view);
      if (!view || pagesSeen.has(page.view) || !records(view.controls) || !records(page.sections)) return false;
      pagesSeen.add(page.view);
      const output=calls.get(view.call)?.output;
      const reads=view.controls.filter(c=>c.type === "read");
      if (typeof output !== "string" || !reads.length || !reads.every(c=>c.model === output && strings(c.path))) return false;
      const roots=reads.map(c=>strings(c.path) ? c.path : []);
      /** @type {string[][]} */ const shown=[];
      for (const section of page.sections) {
        if (!records(section.entries)) return false;
        for (const entry of section.entries) { if (!strings(entry.path) || !linked(output,entry.path)) return false; shown.push(entry.path); }
      }
      if (!shown.every(p=>roots.some(r=>starts(p,r)))) return false;
      for (const root of roots) for (const end of ends(leaf(output,root),root,0)) if (!shown.some(p=>starts(end,p))) return false;
    }
  }
  return true;
}
export {};
