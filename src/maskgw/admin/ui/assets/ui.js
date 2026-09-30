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

/** @type {unknown} */
const layout={
  "$defs": {
    "Action": {
      "additionalProperties": false,
      "description": "Escrita v2 declarada (Etapa 6, D-103/D-104): corpo por caminhos.",
      "properties": {
        "after": {
          "default": "reread",
          "enum": [
            "reread",
            "list",
            "open"
          ],
          "title": "After",
          "type": "string"
        },
        "call": {
          "title": "Call",
          "type": "string"
        },
        "confirm": {
          "maxLength": 400,
          "minLength": 1,
          "title": "Confirm",
          "type": "string"
        },
        "done": {
          "maxLength": 300,
          "minLength": 1,
          "title": "Done",
          "type": "string"
        },
        "drop": {
          "items": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array"
          },
          "maxItems": 4,
          "title": "Drop",
          "type": "array"
        },
        "fields": {
          "items": {
            "$ref": "#/$defs/FormField"
          },
          "maxItems": 32,
          "title": "Fields",
          "type": "array"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "label": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "lands": {
          "anyOf": [
            {
              "items": {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "type": "integer"
                  }
                ]
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Lands"
        },
        "origin": {
          "anyOf": [
            {
              "items": {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "type": "integer"
                  }
                ]
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Origin"
        },
        "place": {
          "enum": [
            "collection",
            "detail",
            "aside"
          ],
          "title": "Place",
          "type": "string"
        },
        "probe": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Probe"
        },
        "stamp": {
          "anyOf": [
            {
              "items": {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "type": "integer"
                  }
                ]
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stamp"
        },
        "title": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Title",
          "type": "string"
        },
        "tone": {
          "default": "plain",
          "enum": [
            "plain",
            "danger"
          ],
          "title": "Tone",
          "type": "string"
        },
        "typed": {
          "anyOf": [
            {
              "$ref": "#/$defs/FormField"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "visible": {
          "anyOf": [
            {
              "$ref": "#/$defs/Visible"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "id",
        "label",
        "title",
        "call",
        "place",
        "confirm",
        "done"
      ],
      "title": "Action",
      "type": "object"
    },
    "Binding": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "model": {
          "title": "Model",
          "type": "string"
        },
        "path": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Path",
          "type": "array"
        },
        "role": {
          "enum": [
            "version",
            "identity",
            "order",
            "consent",
            "result"
          ],
          "title": "Role",
          "type": "string"
        }
      },
      "required": [
        "id",
        "role",
        "model",
        "path"
      ],
      "title": "Binding",
      "type": "object"
    },
    "Boolean": {
      "additionalProperties": false,
      "properties": {
        "type": {
          "const": "boolean",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type"
      ],
      "title": "Boolean",
      "type": "object"
    },
    "Call": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "title": "Error",
          "type": "string"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "identity": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Identity"
        },
        "input": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Input"
        },
        "method": {
          "enum": [
            "GET",
            "POST",
            "PUT",
            "DELETE"
          ],
          "title": "Method",
          "type": "string"
        },
        "operation": {
          "enum": [
            "read",
            "create",
            "replace",
            "delete",
            "move",
            "check",
            "confirm",
            "append",
            "register",
            "probe",
            "renew",
            "resume",
            "pause",
            "revise",
            "retire",
            "amend"
          ],
          "title": "Operation",
          "type": "string"
        },
        "output": {
          "title": "Output",
          "type": "string"
        },
        "path": {
          "title": "Path",
          "type": "string"
        }
      },
      "required": [
        "id",
        "method",
        "path",
        "input",
        "output",
        "error",
        "operation",
        "identity"
      ],
      "title": "Call",
      "type": "object"
    },
    "Choice": {
      "additionalProperties": false,
      "properties": {
        "choices": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              },
              {
                "type": "boolean"
              }
            ]
          },
          "minItems": 1,
          "title": "Choices",
          "type": "array"
        },
        "type": {
          "const": "enum",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type",
        "choices"
      ],
      "title": "Choice",
      "type": "object"
    },
    "Collection": {
      "additionalProperties": false,
      "properties": {
        "call": {
          "title": "Call",
          "type": "string"
        },
        "columns": {
          "items": {
            "$ref": "#/$defs/Figure"
          },
          "maxItems": 12,
          "minItems": 1,
          "title": "Columns",
          "type": "array"
        },
        "empty": {
          "maxLength": 400,
          "minLength": 1,
          "title": "Empty",
          "type": "string"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "items": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Items",
          "type": "array"
        },
        "key": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Key",
          "type": "array"
        },
        "label": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "nothing": {
          "maxLength": 400,
          "minLength": 1,
          "title": "Nothing",
          "type": "string"
        },
        "open": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Open",
          "type": "string"
        },
        "search": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Search",
          "type": "string"
        },
        "searchable": {
          "items": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array"
          },
          "maxItems": 4,
          "minItems": 1,
          "title": "Searchable",
          "type": "array"
        },
        "title": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Title",
          "type": "array"
        }
      },
      "required": [
        "id",
        "label",
        "call",
        "items",
        "key",
        "title",
        "columns",
        "search",
        "searchable",
        "empty",
        "nothing",
        "open"
      ],
      "title": "Collection",
      "type": "object"
    },
    "Condition": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Path",
          "type": "array"
        },
        "type": {
          "enum": [
            "present",
            "equal",
            "choice",
            "boolean"
          ],
          "title": "Type",
          "type": "string"
        },
        "value": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "boolean"
            },
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Value"
        }
      },
      "required": [
        "type",
        "path"
      ],
      "title": "Condition",
      "type": "object"
    },
    "Console": {
      "additionalProperties": false,
      "properties": {
        "actions": {
          "items": {
            "$ref": "#/$defs/Action"
          },
          "maxItems": 12,
          "title": "Actions",
          "type": "array"
        },
        "blank": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Blank",
          "type": "string"
        },
        "brand": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Brand",
          "type": "string"
        },
        "collection": {
          "$ref": "#/$defs/Collection"
        },
        "detail": {
          "$ref": "#/$defs/Detail"
        },
        "failure": {
          "maxLength": 400,
          "minLength": 1,
          "title": "Failure",
          "type": "string"
        },
        "guide": {
          "$ref": "#/$defs/Guide"
        },
        "latest": {
          "anyOf": [
            {
              "items": {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "type": "integer"
                  }
                ]
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Latest"
        },
        "legacy": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Legacy",
          "type": "string"
        },
        "main": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Main",
          "type": "string"
        },
        "no": {
          "maxLength": 20,
          "minLength": 1,
          "title": "No",
          "type": "string"
        },
        "outcomes": {
          "items": {
            "$ref": "#/$defs/Outcome"
          },
          "maxItems": 40,
          "title": "Outcomes",
          "type": "array"
        },
        "pages": {
          "items": {
            "$ref": "#/$defs/Page"
          },
          "maxItems": 6,
          "title": "Pages",
          "type": "array"
        },
        "reasons": {
          "items": {
            "$ref": "#/$defs/Wording"
          },
          "maxItems": 8,
          "title": "Reasons",
          "type": "array"
        },
        "summary": {
          "$ref": "#/$defs/Summary"
        },
        "tagline": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Tagline",
          "type": "string"
        },
        "unavailable": {
          "maxLength": 400,
          "minLength": 1,
          "title": "Unavailable",
          "type": "string"
        },
        "unknown": {
          "default": "Resultado desconhecido. Releia o estado antes de decidir.",
          "maxLength": 300,
          "minLength": 1,
          "title": "Unknown",
          "type": "string"
        },
        "yes": {
          "maxLength": 20,
          "minLength": 1,
          "title": "Yes",
          "type": "string"
        }
      },
      "required": [
        "brand",
        "tagline",
        "main",
        "legacy",
        "yes",
        "no",
        "blank",
        "failure",
        "unavailable",
        "summary",
        "collection",
        "detail",
        "guide"
      ],
      "title": "Console",
      "type": "object"
    },
    "Control": {
      "additionalProperties": false,
      "properties": {
        "condition": {
          "anyOf": [
            {
              "$ref": "#/$defs/Condition"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "default": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "boolean"
            },
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Default"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "label": {
          "title": "Label",
          "type": "string"
        },
        "model": {
          "title": "Model",
          "type": "string"
        },
        "path": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Path",
          "type": "array"
        },
        "projections": {
          "items": {
            "$ref": "#/$defs/Projection"
          },
          "maxItems": 512,
          "title": "Projections",
          "type": "array"
        },
        "type": {
          "enum": [
            "text",
            "integer",
            "checkbox",
            "select",
            "table",
            "list",
            "read",
            "confirm"
          ],
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "id",
        "type",
        "path",
        "model",
        "label"
      ],
      "title": "Control",
      "type": "object"
    },
    "Definition": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "shape": {
          "discriminator": {
            "mapping": {
              "boolean": "#/$defs/Boolean",
              "enum": "#/$defs/Choice",
              "integer": "#/$defs/Integer",
              "list": "#/$defs/Sequence",
              "nullable": "#/$defs/Sequence",
              "object": "#/$defs/Object",
              "string": "#/$defs/Text",
              "union": "#/$defs/Union"
            },
            "propertyName": "type"
          },
          "oneOf": [
            {
              "$ref": "#/$defs/Text"
            },
            {
              "$ref": "#/$defs/Integer"
            },
            {
              "$ref": "#/$defs/Boolean"
            },
            {
              "$ref": "#/$defs/Choice"
            },
            {
              "$ref": "#/$defs/Object"
            },
            {
              "$ref": "#/$defs/Sequence"
            },
            {
              "$ref": "#/$defs/Union"
            }
          ],
          "title": "Shape"
        }
      },
      "required": [
        "id",
        "shape"
      ],
      "title": "Definition",
      "type": "object"
    },
    "Detail": {
      "additionalProperties": false,
      "properties": {
        "back": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Back",
          "type": "string"
        },
        "call": {
          "title": "Call",
          "type": "string"
        },
        "extra": {
          "title": "Extra",
          "type": "string"
        },
        "gone": {
          "maxLength": 400,
          "minLength": 1,
          "title": "Gone",
          "type": "string"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "tabs": {
          "items": {
            "$ref": "#/$defs/Tab"
          },
          "maxItems": 6,
          "minItems": 1,
          "title": "Tabs",
          "type": "array"
        },
        "title": {
          "anyOf": [
            {
              "items": {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "type": "integer"
                  }
                ]
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Title"
        }
      },
      "required": [
        "id",
        "call",
        "extra",
        "back",
        "tabs",
        "gone"
      ],
      "title": "Detail",
      "type": "object"
    },
    "Editor": {
      "additionalProperties": false,
      "properties": {
        "controls": {
          "items": {
            "$ref": "#/$defs/Control"
          },
          "title": "Controls",
          "type": "array"
        },
        "help": {
          "title": "Help",
          "type": "string"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "model": {
          "title": "Model",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "model",
        "controls",
        "help"
      ],
      "title": "Editor",
      "type": "object"
    },
    "FieldLink": {
      "additionalProperties": false,
      "properties": {
        "default": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "boolean"
            },
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Default"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "ref": {
          "title": "Ref",
          "type": "string"
        },
        "required": {
          "title": "Required",
          "type": "boolean"
        }
      },
      "required": [
        "name",
        "ref",
        "required"
      ],
      "title": "FieldLink",
      "type": "object"
    },
    "Figure": {
      "additionalProperties": false,
      "description": "Um valor exibido: contagem, sim/nao ou texto. Caminho, nunca expressao.",
      "properties": {
        "blank": {
          "anyOf": [
            {
              "maxLength": 120,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Blank"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "kind": {
          "enum": [
            "count",
            "flag",
            "text",
            "list",
            "tree"
          ],
          "title": "Kind",
          "type": "string"
        },
        "label": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "path": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Path",
          "type": "array"
        },
        "show": {
          "default": "fact",
          "enum": [
            "fact",
            "metric",
            "code",
            "ordered"
          ],
          "title": "Show",
          "type": "string"
        },
        "wording": {
          "items": {
            "$ref": "#/$defs/Wording"
          },
          "maxItems": 32,
          "title": "Wording",
          "type": "array"
        }
      },
      "required": [
        "id",
        "label",
        "path",
        "kind"
      ],
      "title": "Figure",
      "type": "object"
    },
    "FormField": {
      "additionalProperties": false,
      "description": "Campo de formulario: so caminho, rotulo e tipo; nenhum codigo.",
      "properties": {
        "choices": {
          "items": {
            "$ref": "#/$defs/Wording"
          },
          "maxItems": 32,
          "title": "Choices",
          "type": "array"
        },
        "default": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "boolean"
            },
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Default"
        },
        "help": {
          "anyOf": [
            {
              "maxLength": 300,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Help"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "item": {
          "anyOf": [
            {
              "maxLength": 60,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Item"
        },
        "items": {
          "items": {
            "$ref": "#/$defs/FormField"
          },
          "maxItems": 24,
          "title": "Items",
          "type": "array"
        },
        "kind": {
          "enum": [
            "text",
            "secret",
            "integer",
            "flag",
            "choice",
            "lines",
            "records"
          ],
          "title": "Kind",
          "type": "string"
        },
        "label": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "optional": {
          "default": false,
          "title": "Optional",
          "type": "boolean"
        },
        "path": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Path",
          "type": "array"
        },
        "source": {
          "anyOf": [
            {
              "items": {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "type": "integer"
                  }
                ]
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source"
        },
        "when": {
          "anyOf": [
            {
              "$ref": "#/$defs/Visible"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "id",
        "label",
        "kind",
        "path"
      ],
      "title": "FormField",
      "type": "object"
    },
    "Group": {
      "additionalProperties": false,
      "description": "Agrupamento visual de itens de uma aba, com titulo e explicacao.",
      "properties": {
        "label": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "members": {
          "items": {
            "type": "string"
          },
          "maxItems": 16,
          "minItems": 1,
          "title": "Members",
          "type": "array"
        },
        "note": {
          "anyOf": [
            {
              "maxLength": 300,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Note"
        }
      },
      "required": [
        "label",
        "members"
      ],
      "title": "Group",
      "type": "object"
    },
    "Guide": {
      "additionalProperties": false,
      "description": "Prototipo de navegacao: sem campo, envio, teste ou gravacao.",
      "properties": {
        "action": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Action"
        },
        "banner": {
          "maxLength": 400,
          "minLength": 1,
          "title": "Banner",
          "type": "string"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "label": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "steps": {
          "items": {
            "$ref": "#/$defs/Step"
          },
          "maxItems": 10,
          "minItems": 2,
          "title": "Steps",
          "type": "array"
        }
      },
      "required": [
        "id",
        "label",
        "banner",
        "steps"
      ],
      "title": "Guide",
      "type": "object"
    },
    "Integer": {
      "additionalProperties": false,
      "properties": {
        "max": {
          "default": 9007199254740991,
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Max",
          "type": "integer"
        },
        "min": {
          "default": 0,
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Min",
          "type": "integer"
        },
        "type": {
          "const": "integer",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type"
      ],
      "title": "Integer",
      "type": "object"
    },
    "Message": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "state": {
          "enum": [
            "loading",
            "authentication",
            "draft",
            "pending",
            "success",
            "conflict",
            "busy",
            "incompatible",
            "unknown",
            "uncertain"
          ],
          "title": "State",
          "type": "string"
        },
        "text": {
          "title": "Text",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "text",
        "state"
      ],
      "title": "Message",
      "type": "object"
    },
    "Object": {
      "additionalProperties": false,
      "properties": {
        "fields": {
          "items": {
            "$ref": "#/$defs/FieldLink"
          },
          "title": "Fields",
          "type": "array"
        },
        "type": {
          "const": "object",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type",
        "fields"
      ],
      "title": "Object",
      "type": "object"
    },
    "Outcome": {
      "additionalProperties": false,
      "description": "Categoria fechada da v2 -> estado abstrato e texto fixo.",
      "properties": {
        "kind": {
          "enum": [
            "conflict",
            "refused",
            "busy",
            "blocked",
            "uncertain"
          ],
          "title": "Kind",
          "type": "string"
        },
        "text": {
          "maxLength": 400,
          "minLength": 1,
          "title": "Text",
          "type": "string"
        },
        "value": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Value",
          "type": "string"
        }
      },
      "required": [
        "value",
        "kind",
        "text"
      ],
      "title": "Outcome",
      "type": "object"
    },
    "Page": {
      "additionalProperties": false,
      "description": "Apresentacao de uma vista v1 ja aprovada. So arruma e nomeia o que a\nvista le; nao cria leitura, chamada, controle nem caminho novo.",
      "properties": {
        "sections": {
          "items": {
            "$ref": "#/$defs/Section"
          },
          "maxItems": 8,
          "minItems": 1,
          "title": "Sections",
          "type": "array"
        },
        "view": {
          "title": "View",
          "type": "string"
        }
      },
      "required": [
        "view",
        "sections"
      ],
      "title": "Page",
      "type": "object"
    },
    "Projection": {
      "additionalProperties": false,
      "properties": {
        "paths": {
          "items": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array"
          },
          "maxItems": 512,
          "title": "Paths",
          "type": "array"
        },
        "source": {
          "enum": [
            "base",
            "draft"
          ],
          "title": "Source",
          "type": "string"
        },
        "target": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Target",
          "type": "array"
        },
        "type": {
          "enum": [
            "copy",
            "object",
            "list",
            "omit",
            "insert",
            "replace",
            "remove",
            "permute"
          ],
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type",
        "source",
        "paths",
        "target"
      ],
      "title": "Projection",
      "type": "object"
    },
    "Section": {
      "additionalProperties": false,
      "description": "Grupo de uma leitura da Politica v1: titulo, explicacao e valores.",
      "properties": {
        "entries": {
          "items": {
            "$ref": "#/$defs/Figure"
          },
          "maxItems": 12,
          "minItems": 1,
          "title": "Entries",
          "type": "array"
        },
        "label": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "note": {
          "anyOf": [
            {
              "maxLength": 400,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Note"
        }
      },
      "required": [
        "label",
        "entries"
      ],
      "title": "Section",
      "type": "object"
    },
    "Sequence": {
      "additionalProperties": false,
      "properties": {
        "item": {
          "title": "Item",
          "type": "string"
        },
        "type": {
          "enum": [
            "list",
            "nullable"
          ],
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type",
        "item"
      ],
      "title": "Sequence",
      "type": "object"
    },
    "Step": {
      "additionalProperties": false,
      "properties": {
        "fields": {
          "items": {
            "type": "string"
          },
          "maxItems": 16,
          "title": "Fields",
          "type": "array"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "label": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "text": {
          "maxLength": 600,
          "minLength": 1,
          "title": "Text",
          "type": "string"
        }
      },
      "required": [
        "id",
        "label",
        "text"
      ],
      "title": "Step",
      "type": "object"
    },
    "Summary": {
      "additionalProperties": false,
      "properties": {
        "absent": {
          "maxLength": 400,
          "minLength": 1,
          "title": "Absent",
          "type": "string"
        },
        "call": {
          "title": "Call",
          "type": "string"
        },
        "figures": {
          "items": {
            "$ref": "#/$defs/Figure"
          },
          "maxItems": 16,
          "minItems": 1,
          "title": "Figures",
          "type": "array"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "label": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "notes": {
          "items": {
            "maxLength": 400,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 4,
          "title": "Notes",
          "type": "array"
        }
      },
      "required": [
        "id",
        "label",
        "call",
        "figures",
        "notes",
        "absent"
      ],
      "title": "Summary",
      "type": "object"
    },
    "Tab": {
      "additionalProperties": false,
      "properties": {
        "entries": {
          "items": {
            "$ref": "#/$defs/Figure"
          },
          "maxItems": 16,
          "minItems": 1,
          "title": "Entries",
          "type": "array"
        },
        "groups": {
          "items": {
            "$ref": "#/$defs/Group"
          },
          "maxItems": 6,
          "title": "Groups",
          "type": "array"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "label": {
          "maxLength": 60,
          "minLength": 1,
          "title": "Label",
          "type": "string"
        },
        "source": {
          "enum": [
            "main",
            "extra"
          ],
          "title": "Source",
          "type": "string"
        }
      },
      "required": [
        "id",
        "label",
        "source",
        "entries"
      ],
      "title": "Tab",
      "type": "object"
    },
    "Text": {
      "additionalProperties": false,
      "properties": {
        "alphabet": {
          "default": "",
          "title": "Alphabet",
          "type": "string"
        },
        "max": {
          "default": 9007199254740991,
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Max",
          "type": "integer"
        },
        "min": {
          "default": 0,
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Min",
          "type": "integer"
        },
        "prefix": {
          "default": "",
          "title": "Prefix",
          "type": "string"
        },
        "type": {
          "const": "string",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type"
      ],
      "title": "Text",
      "type": "object"
    },
    "Union": {
      "additionalProperties": false,
      "properties": {
        "tag": {
          "title": "Tag",
          "type": "string"
        },
        "type": {
          "const": "union",
          "title": "Type",
          "type": "string"
        },
        "variants": {
          "items": {
            "$ref": "#/$defs/Variant"
          },
          "minItems": 1,
          "title": "Variants",
          "type": "array"
        }
      },
      "required": [
        "type",
        "tag",
        "variants"
      ],
      "title": "Union",
      "type": "object"
    },
    "Variant": {
      "additionalProperties": false,
      "properties": {
        "ref": {
          "title": "Ref",
          "type": "string"
        },
        "value": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "boolean"
            },
            {
              "type": "integer"
            }
          ],
          "title": "Value"
        }
      },
      "required": [
        "value",
        "ref"
      ],
      "title": "Variant",
      "type": "object"
    },
    "View": {
      "additionalProperties": false,
      "properties": {
        "actions": {
          "items": {
            "type": "string"
          },
          "title": "Actions",
          "type": "array"
        },
        "call": {
          "title": "Call",
          "type": "string"
        },
        "controls": {
          "items": {
            "$ref": "#/$defs/Control"
          },
          "title": "Controls",
          "type": "array"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "label": {
          "title": "Label",
          "type": "string"
        }
      },
      "required": [
        "id",
        "label",
        "call",
        "controls",
        "actions"
      ],
      "title": "View",
      "type": "object"
    },
    "Visible": {
      "additionalProperties": false,
      "description": "Condicao de exibicao: valor em caminho declarado, nunca expressao.",
      "properties": {
        "path": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Path",
          "type": "array"
        },
        "value": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "integer"
            },
            {
              "type": "boolean"
            }
          ],
          "title": "Value"
        }
      },
      "required": [
        "path",
        "value"
      ],
      "title": "Visible",
      "type": "object"
    },
    "Wording": {
      "additionalProperties": false,
      "description": "Texto fixo exibido no lugar de um valor enumerado conhecido.",
      "properties": {
        "text": {
          "maxLength": 160,
          "minLength": 1,
          "title": "Text",
          "type": "string"
        },
        "tone": {
          "anyOf": [
            {
              "enum": [
                "good",
                "neutral",
                "attention"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Tone"
        },
        "value": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Value",
          "type": "string"
        }
      },
      "required": [
        "value",
        "text"
      ],
      "title": "Wording",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "bindings": {
      "items": {
        "$ref": "#/$defs/Binding"
      },
      "title": "Bindings",
      "type": "array"
    },
    "calls": {
      "items": {
        "$ref": "#/$defs/Call"
      },
      "maxItems": 32,
      "minItems": 32,
      "title": "Calls",
      "type": "array"
    },
    "console": {
      "$ref": "#/$defs/Console"
    },
    "editors": {
      "items": {
        "$ref": "#/$defs/Editor"
      },
      "maxItems": 8,
      "minItems": 8,
      "title": "Editors",
      "type": "array"
    },
    "format": {
      "const": 2,
      "title": "Format",
      "type": "integer"
    },
    "messages": {
      "items": {
        "$ref": "#/$defs/Message"
      },
      "title": "Messages",
      "type": "array"
    },
    "models": {
      "items": {
        "$ref": "#/$defs/Definition"
      },
      "maxItems": 320,
      "minItems": 1,
      "title": "Models",
      "type": "array"
    },
    "views": {
      "items": {
        "$ref": "#/$defs/View"
      },
      "maxItems": 6,
      "minItems": 6,
      "title": "Views",
      "type": "array"
    }
  },
  "required": [
    "format",
    "models",
    "calls",
    "views",
    "editors",
    "bindings",
    "messages",
    "console"
  ],
  "title": "Presentation",
  "type": "object"
};
export const digest="0964dc7cc7599a0ef9fd1335191a33e3451cfd8cd8ae86a93eb3aca406669a3b";
/** @param {unknown} value */
export function check(value) { return inspect(value,layout); }
/** @param {unknown} item @returns {item is Record<string, unknown>} */
export function entry(item) {
  return typeof item === "object" && item !== null && !Array.isArray(item)
    && (Object.getPrototypeOf(item) === Object.prototype || Object.getPrototypeOf(item) === null);
}
/** @param {unknown} item @returns {item is Record<string, unknown>[]} */
function entries(item) { return Array.isArray(item) && item.every(entry); }
/** @param {unknown} item @param {unknown} parts @returns {unknown} */
export function at(item, parts) {
  if (!Array.isArray(parts)) return undefined;
  for (const part of parts) {
    if ((typeof part !== "string" && typeof part !== "number") || ["__proto__","constructor","prototype"].includes(String(part))) return undefined;
    if (Array.isArray(item) && typeof part === "number") item = item[part];
    else if (entry(item) && typeof part === "string" && Object.hasOwn(item,part)) item = item[part];
    else return undefined;
  }
  return item;
}
/** A bounded interpreter of the authenticated descriptor, never wire names.
 * @param {unknown} book
 */
export function reader(book) {
  if (!entry(book) || !entries(book.models) || !entries(book.bindings) || !entries(book.views) || !entries(book.calls)) throw new Error("Request unsuccessful.");
  const models = new Map(book.models.map(n=>[n.id,n.shape]));
  const links = book.bindings;
  /** @param {unknown} key @param {unknown} value @param {number} depth @param {Set<object>} seen @param {number[]} versions @param {boolean[]} consents @returns {boolean} */
  function acceptsData(key,value,depth,seen,versions,consents) {
    const node = models.get(key);
    if (!entry(node) || depth > 16) return false;
    if (value !== null && typeof value === "object") {
      if (seen.has(value) || Object.keys(value).some(k=>["__proto__","constructor","prototype"].includes(k))) return false;
    }
    for (const link of links.filter(l=>l.model === key)) {
      const found=at(value,link.path);
      if(found === undefined) continue;
      if(link.role === "version") {
        if(typeof found !== "number" || !Number.isSafeInteger(found) || found < 0) return false;
        versions.push(found);
      }
      if(link.role === "consent") {
        if(typeof found !== "boolean") return false;
        consents.push(found);
      }
    }
    if (node.type === "nullable") return value === null || acceptsData(node.item,value,depth+1,seen,versions,consents);
    if (node.type === "boolean") return typeof value === "boolean";
    if (node.type === "integer") return typeof value === "number" && Number.isSafeInteger(value) && typeof node.min === "number" && typeof node.max === "number" && value >= node.min && value <= node.max;
    if (node.type === "enum") return Array.isArray(node.choices) && node.choices.some(v=>v === value);
    if (node.type === "string") {
      if(typeof value !== "string" || typeof node.min !== "number" || typeof node.max !== "number") return false;
      const prefix=typeof node.prefix === "string" ? node.prefix : "";
      const alphabet=typeof node.alphabet === "string" ? node.alphabet : "";
      return [...value].length >= node.min && [...value].length <= node.max && value.startsWith(prefix) && (!alphabet || [...value.slice(prefix.length)].every(c=>alphabet.includes(c)));
    }
    if (node.type === "union" && typeof node.tag === "string" && entries(node.variants) && entry(value)) {
      const tag=node.tag;
      const target=node.variants.find(n=>n.value === value[tag]);
      return !!target && acceptsData(target.ref,value,depth+1,seen,versions,consents);
    }
    if (node.type === "list") {
      if(!Array.isArray(value)) return false;
      const next=new Set([...seen,value]);
      const ids=new Set();
      for(let index=0;index<value.length;index++) {
        const child=value[index];
        if(!acceptsData(node.item,child,depth+1,next,versions,consents)) return false;
        for(const link of links.filter(l=>l.model === node.item)) {
          const found=at(child,link.path);
          if(found === undefined) continue;
          if(link.role === "order" && found !== index) return false;
          if(link.role === "identity" && found !== null) { if(ids.has(found)) return false; ids.add(found); }
        }
      }
      return true;
    }
    if (node.type === "object" && entries(node.fields) && entry(value)) {
      const fields=node.fields;
      if(Object.keys(value).some(k=>!fields.some(f=>f.name === k))) return false;
      const next=new Set([...seen,value]);
      return fields.every(f=>typeof f.name === "string" && (Object.hasOwn(value,f.name) ? acceptsData(f.ref,value[f.name],depth+1,next,versions,consents) : f.required === false));
    }
    return false;
  }
  /** @param {unknown} key @param {unknown} value */
  function inspectData(key,value) {
    /** @type {number[]} */ const versions=[];
    /** @type {boolean[]} */ const consents=[];
    if(!acceptsData(key,value,0,new Set(),versions,consents) || new Set(versions).size > 1 || new Set(consents).size > 1) throw new Error("Request unsuccessful.");
    const version=versions[0];
    if(version !== undefined && consents.some(c=>c !== (version > 0))) throw new Error("Request unsuccessful.");
    return version;
  }
  const calls=book.calls;
  const views=book.views.map(view=>{
    const call=calls.find(c=>c.id === view.call);
    if(typeof view.id !== "string" || typeof view.label !== "string" || !entries(view.controls)
      || !call || typeof call.id !== "string" || call.method !== "GET" || call.identity !== null) throw new Error("Request unsuccessful.");
    return {id:view.id,label:view.label,call:call.id,controls:view.controls};
  });
  /** @param {string} id @param {unknown} value */
  function inspectDataFor(id,value) {
    const call=calls.find(c=>c.id === id && c.method === "GET");
    if(!call) throw new Error("Request unsuccessful.");
    const version=inspectData(call.output,value);
    if(version === undefined) throw new Error("Request unsuccessful.");
    return version;
  }
  /** @param {unknown} key @param {unknown} value @param {string} role */
  function bound(key,value,role) {
    return links.filter(l=>l.model === key && l.role === role).map(l=>at(value,l.path)).filter(v=>v !== undefined);
  }
  /** Model identifier reached by a declared path; never a wire name.
   * @param {unknown} key @param {unknown} parts @returns {string}
   */
  function modelAt(key,parts) {
    if (typeof key !== "string" || !Array.isArray(parts)) throw new Error("Request unsuccessful.");
    let current=key;
    for (const part of parts) {
      let node=models.get(current);
      while (entry(node) && node.type === "nullable" && typeof node.item === "string") { current=node.item; node=models.get(current); }
      if (!entry(node)) throw new Error("Request unsuccessful.");
      if (typeof part === "string" && node.type === "object" && entries(node.fields)) {
        const field=node.fields.find(f=>f.name === part);
        if (!field || typeof field.ref !== "string") throw new Error("Request unsuccessful.");
        current=field.ref;
      } else if (typeof part === "number" && node.type === "list" && typeof node.item === "string") current=node.item;
      else throw new Error("Request unsuccessful.");
    }
    return current;
  }
  const surface=entry(book.console) ? book.console : undefined;
  /** Declared read-only console; checked by the protocol before this point. */
  function board() {
    if (!surface) throw new Error("Request unsuccessful.");
    return surface;
  }
  /** Model of a row key: the only accepted identity of an item read. */
  function identityModel() {
    const spec=board().collection;
    if (!entry(spec)) throw new Error("Request unsuccessful.");
    const listing=calls.find(c=>c.id === spec.call);
    if (!listing) throw new Error("Request unsuccessful.");
    const rows=modelAt(listing.output,spec.items);
    const shape=models.get(rows);
    if (!entry(shape) || shape.type !== "list" || typeof shape.item !== "string") throw new Error("Request unsuccessful.");
    return modelAt(shape.item,spec.key);
  }
  return {views,inspectData,inspectDataFor,bound,board,identityModel};
}


/** @typedef {"authentication" | "conflict" | "busy" | "incompatible" | "unknown" | "uncertain"} FailureKind */
/** @typedef {{kind:"success",version:number,message:string} | {kind:FailureKind,version:number | undefined,message:string}} Outcome */
/** @typedef {{id:string,version:number,draft:unknown,identity:string | undefined}} Command */
/** @param {unknown} value @returns {number} */
export function safeVersion(value) {
  if(typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new Error("Request refused.");
  return value;
}
/** Copy JSON data without accessors, custom prototypes, coercion or shared references.
 * @param {unknown} value @param {number} depth @param {Set<object>} seen @returns {unknown}
 */
export function capture(value,depth=0,seen=new Set()) {
  if(depth > 16) throw new Error("Request refused.");
  if(value === null || typeof value === "string" || typeof value === "boolean") return value;
  if(typeof value === "number" && Number.isSafeInteger(value)) return value;
  if(typeof value !== "object" || value === null || seen.has(value) || (!Array.isArray(value) && !entry(value))) throw new Error("Request refused.");
  const next=new Set([...seen,value]);
  const descriptors=Object.getOwnPropertyDescriptors(value);
  if(Reflect.ownKeys(value).some(k=>typeof k !== "string" || ["__proto__","constructor","prototype"].includes(k))) throw new Error("Request refused.");
  for(const [key,d] of Object.entries(descriptors)) if(!("value" in d) || (!d.enumerable && !(Array.isArray(value) && key === "length"))) throw new Error("Request refused.");
  if(Array.isArray(value)) {
    if(Object.keys(value).length !== value.length) throw new Error("Request refused.");
    return Object.freeze(value.map(v=>capture(v,depth+1,next)));
  }
  return Object.freeze(Object.fromEntries(Object.entries(value).map(([k,v])=>[k,capture(v,depth+1,next)])));
}
/** @param {unknown} value @returns {value is Record<string,unknown>[]} */
function commandEntries(value) { return Array.isArray(value) && value.every(entry); }
/** The model itself is the closed object/list/select-copy projection plan.
 * No caller supplies field paths, destinations, methods or executable projections.
 * @param {unknown} source
 */
export function commands(source) {
  const book=capture(source);
  if(!entry(book) || !commandEntries(book.calls) || !commandEntries(book.models) || !commandEntries(book.bindings) || !commandEntries(book.messages)) throw new Error("Request refused.");
  const catalog=book.calls, models=new Map(book.models.map(m=>[m.id,m.shape])), links=book.bindings, messages=book.messages;
  const lens=reader(book);
  /** @param {string} id */
  function lookup(id) {
    const call=catalog.find(c=>c.id === id);
    if(!call || typeof call.path !== "string" || typeof call.output !== "string" || typeof call.error !== "string"
      || (call.method !== "GET" && call.method !== "POST" && call.method !== "PUT" && call.method !== "DELETE")
      || (call.identity !== null && typeof call.identity !== "string")) throw new Error("Request refused.");
    return {id,path:call.path,output:call.output,error:call.error,input:call.input,operation:call.operation,identity:call.identity,method:call.method};
  }
  /** Locate the identity leaf in the paired authenticated read model.
   * @param {unknown} key @param {number} depth @returns {unknown[]}
   */
  function leaves(key,depth=0) {
    const shape=models.get(key);if(!entry(shape) || depth > 16) throw new Error("Request refused.");
    if(shape.type === "nullable") return leaves(shape.item,depth+1);
    if(shape.type !== "object" || !commandEntries(shape.fields)) return [];
    const fields=shape.fields;
    return fields.flatMap(f=>links.some(l=>l.model === key && l.role === "identity" && Array.isArray(l.path) && l.path.length === 1 && l.path[0] === f.name) ? [f.ref] : leaves(f.ref,depth+1));
  }
  /** @param {ReturnType<typeof lookup>} call @param {string | undefined} identity */
  function resolve(call,identity) {
    if(call.identity === null) {if(identity !== undefined) throw new Error("Request refused.");return call.path;}
    if(typeof identity !== "string" || !identity || /[%/?#\\{}:]|\s/.test(identity) || [".","..","__proto__","constructor","prototype"].includes(identity)) throw new Error("Request refused.");
    const parts=call.path.split("/"), marker="{"+call.identity+"}";
    if(parts.filter(p=>p === marker).length !== 1 || parts.some(p=>/[{}]/.test(p) && p !== marker)) throw new Error("Request refused.");
    const paired=catalog.find(c=>c.path === call.path && c.method === "GET");
    if(!paired) throw new Error("Request refused.");
    const keys=leaves(paired.output);if(keys.length !== 1) throw new Error("Request refused.");
    const shape=models.get(keys[0]);
    const key=entry(shape) && shape.type === "nullable" ? shape.item : keys[0];
    lens.inspectData(key,identity);
    return parts.map(p=>p === marker ? identity : p).join("/");
  }
  /** Construct only the declared writable fields; the bound version has a separate source.
   * @param {Command} command
   */
  function prepare(command) {
    const call=lookup(command.id), version=safeVersion(command.version);
    if(call.method === "GET" || !["create","replace","delete","move","confirm","append"].includes(String(call.operation)) || version === Number.MAX_SAFE_INTEGER) throw new Error("Request refused.");
    if(call.operation === "confirm" ? version !== 0 : version === 0) throw new Error("Request refused.");
    const shape=models.get(call.input), draft=capture(command.draft);
    if(!entry(shape) || shape.type !== "object" || !commandEntries(shape.fields) || !entry(draft)) throw new Error("Request refused.");
    const fields=shape.fields;
    const bindings=links.filter(l=>l.model === call.input && l.role === "version");
    const binding=bindings[0];
    if(bindings.length !== 1 || !binding || !Array.isArray(binding.path) || binding.path.length !== 1 || typeof binding.path[0] !== "string") throw new Error("Request refused.");
    const slot=binding.path[0];
    if(Object.keys(draft).some(k=>k === slot || !fields.some(f=>f.name === k))) throw new Error("Request refused.");
    const body=Object.fromEntries(fields.flatMap(f=>typeof f.name !== "string" ? [] : f.name === slot ? [[f.name,version]] : Object.hasOwn(draft,f.name) ? [[f.name,at(draft,[f.name])]] : []));
    lens.inspectData(call.input,body);
    return {call,path:resolve(call,command.identity),body:capture(body),version};
  }
  /** @param {ReturnType<typeof lookup>} call @param {unknown} value @param {number} status @param {number} base @returns {Outcome} */
  function outcome(call,value,status,base) {
    safeVersion(base);
    const data=capture(value);
    if(status >= 200 && status < 300) {
      const version=lens.inspectData(call.output,data);
      if(version !== base+1 || !Number.isSafeInteger(version) || lens.bound(call.output,data,"result").length !== 1 || lens.bound(call.output,data,"result")[0] !== true) throw new Error("Request refused.");
      return {kind:"success",version,message:"Salva; visualização ainda não atualizada."};
    }
    const version=lens.inspectData(call.error,data), shape=models.get(call.error);
    if(!entry(shape) || shape.type !== "union" || typeof shape.tag !== "string") throw new Error("Request refused.");
    const name=at(data,[shape.tag]), message=messages.find(m=>m.name === name);
    if(!message || typeof message.text !== "string") throw new Error("Request refused.");
    const kind=message.state;
    if(kind !== "authentication" && kind !== "conflict" && kind !== "busy" && kind !== "incompatible" && kind !== "unknown" && kind !== "uncertain") throw new Error("Request refused.");
    if(status < 400 || status > 599 || (kind === "busy" && status !== 409) || (kind === "conflict" && status !== 409 && status !== 404)
      || (kind === "uncertain" && (status !== 500 || version !== base+1)) || (kind === "authentication" && status !== 401)) throw new Error("Request refused.");
    return {kind,version,message:message.text};
  }
  return Object.freeze({lookup,resolve,prepare,outcome});
}


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
  /** @param {string} id @param {unknown} value @param {unknown} editorList */
  function checkedContent(id,value,editorList) {
    const p=profile(id), clean=capture(value);lens.inspectData(p.model,clean);
    if(p.choice && p.nested) {
      const name=at(clean,[p.choice]), editor=editors.find(e=>e.name === name);
      if(!editor || !available(editorList).includes(word(name))) throw new Error("Request refused.");
      const detail=at(clean,[p.nested]);lens.inspectData(editor.model,detail);
      for(const control of rows(editor.controls)) {
        const present=at(detail,control.path) !== undefined;
        if(entry(control.condition)) {
          const holds=at(detail,control.condition.path) === control.condition.value;
          if(holds !== present) throw new Error("Request refused.");
        }
      }
    }
    return clean;
  }
  // The sole unassociated, non-template read with a list of editor names is the editorList.
  // Only the first prefix: the read-only second prefix never feeds authoring.
  const editorCatalogCall=authorRecord(calls.find(c=>c.method === "GET" && c.identity === null && typeof c.path === "string" && c.path.startsWith("/admin/v1/") && !views.some(v=>v.call === c.id)));
  /** @param {unknown} editorList */
  function available(editorList) {
    lens.inspectData(editorCatalogCall.output,editorList);
    const list=fields(editorCatalogCall.output).find(f=>shape(f.ref).type === "list");if(!list) throw new Error("Request refused.");
    const values=at(editorList,[word(list.name)]);if(!Array.isArray(values)) throw new Error("Request refused.");
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
    home:word(home.id),read:word(home.call),editorCatalog:word(editorCatalogCall.id),check:word(checkCall.id),
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


/** @param {unknown} value @returns {value is Record<string, unknown>} */
function object(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Second-prefix writes: operation and its only method (Phase 9, Stage 6). */
const writes=Object.freeze({register:"POST",probe:"POST",renew:"POST",resume:"POST",pause:"POST",revise:"PUT",retire:"DELETE",amend:"PUT"});
/** The second administrative prefix admits reads, and writes only through `submit`.
 * @param {string} path @param {boolean} first @param {string} method @param {boolean} mutating
 */
function destination(path, first, method="GET", mutating=false) {
  const second=path.startsWith("/admin/v2/");
  if (first ? path !== "/admin/ui/presentation.json" : !(path.startsWith("/admin/v1/") || second)) throw new Error("Request refused.");
  if (second && method !== "GET" && !mutating) throw new Error("Request refused.");
  if (mutating && !second) throw new Error("Request refused.");
  if (/[?#%\\{}]|\/\//.test(path) || path.split("/").some(v => v === "." || v === "..")) throw new Error("Request refused.");
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin || url.pathname !== path) throw new Error("Request refused.");
  return url;
}

/** Substitutes the single identity slot, `{name}` or `{name}:action`.
 * @param {string} path @param {string} name @param {string} identity
 */
function place(path,name,identity) {
  const marker="{"+name+"}", parts=path.split("/");
  const slot=parts.filter(p=>p === marker || (p.startsWith(marker+":") && /^[a-z]+(?:-[a-z]+)*$/.test(p.slice(marker.length+1))));
  if(slot.length !== 1 || parts.filter(p=>p.includes("{") || p.includes("}")).length !== 1) throw new Error("Request refused.");
  return parts.map(p=>p === slot[0] ? identity+p.slice(marker.length) : p).join("/");
}

/** Entry is explicit; no DOM, persistent state, automatic request or write.
 * @param {string} token
 * @param {AbortSignal | undefined} signal
 * @param {() => void} expired
 */
export async function open(token, signal=undefined, expired=()=>{}) {
  if (!token || /[\r\n]/.test(token)) throw new Error("Request refused.");
  const stop = new AbortController();
  let ended = false;
  let writing = false;
  /** @type {Set<() => void>} */ const listeners=new Set();
  /** @type {Map<string, {path:string, method:"GET" | "POST", operation:string, output:string, identity:string | null}>} */ const calls = new Map();
  /** @type {Map<string, {path:string, method:"POST" | "PUT" | "DELETE", operation:string, input:string, output:string, error:string, identity:string | null}>} */ const changes = new Map();
  /** @type {ReturnType<typeof reader> | undefined} */ let lens;
  /** @type {ReturnType<typeof commands> | undefined} */ let actions;
  /** @type {ReturnType<typeof author> | undefined} */ let forms;
  function close() { ended=true; token=""; calls.clear(); changes.clear(); lens=undefined; actions=undefined; forms=undefined; stop.abort(); signal?.removeEventListener("abort",close); for(const listener of listeners) listener(); listeners.clear(); }
  signal?.addEventListener("abort",close,{once:true});
  if(signal?.aborted) close();
  /** @param {string} path @param {string} method @param {string | undefined} body @param {boolean} first @param {AbortSignal | undefined} extra @param {boolean} errors @param {boolean} mutating */
  async function send(path, method, body, first, extra=undefined,errors=false,mutating=false) {
    if(ended) throw new AccessError("authentication");
    if(extra?.aborted) throw new AccessError("unknown");
    const url = destination(path, first, method, mutating);
    if (body !== undefined && (body.includes(JSON.stringify(token).slice(1,-1)) || new TextEncoder().encode(body).length > 1048576)) throw new Error("Request refused.");
    const headers = new Headers();
    headers.set("Authorization", "Bearer " + token);
    if (body !== undefined) headers.set("Content-Type", "application/json");
    const response = await fetch(url, {
      signal:AbortSignal.any([stop.signal,AbortSignal.timeout(30000),...(extra ? [extra] : [])]), method, headers, ...(body === undefined ? {} : {body}), mode: "cors",
      credentials: "omit", redirect: "error", cache: "no-store", referrerPolicy: "no-referrer",
    });
    if(ended) throw new AccessError("authentication");
    if(response.status === 401) { close(); expired(); throw new AccessError("authentication"); }
    if ((!response.ok && !errors) || response.headers.get("Content-Type") !== "application/json") throw new AccessError("unknown");
    return response;
  }
  try {
    const response = await send("/admin/ui/presentation.json", "GET", undefined, true);
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength > 262144) throw new Error("Request refused.");
    const sum = await crypto.subtle.digest("SHA-256", bytes);
    const hex = [...new Uint8Array(sum)].map(v => v.toString(16).padStart(2,"0")).join("");
    if (hex !== digest) throw new Error("Request refused.");
    /** @type {unknown} */ const data = JSON.parse(new TextDecoder("utf-8", {fatal:true}).decode(bytes));
    if (!check(data) || !object(data) || !Array.isArray(data.calls)) throw new Error("Request refused.");
    const frozen=capture(data);
    lens=reader(frozen); actions=commands(frozen);
    /** @type {unknown[]} */ const entries = data.calls;
    for (const item of entries) {
      if (object(item) && typeof item.id === "string" && typeof item.path === "string" && typeof item.output === "string" && item.identity === null
        && ((item.method === "GET" && item.operation === "read") || (item.method === "POST" && item.operation === "check"))) {
        calls.set(item.id, {path:item.path, method:item.method, operation:item.operation, output:item.output, identity:null});
      }
      // Item reads exist only under the read-only second prefix.
      if (object(item) && typeof item.id === "string" && typeof item.path === "string" && typeof item.output === "string"
        && typeof item.identity === "string" && item.method === "GET" && item.operation === "read" && item.path.startsWith("/admin/v2/")) {
        calls.set(item.id, {path:item.path, method:"GET", operation:"read", output:item.output, identity:item.identity});
      }
      // Second-prefix writes are kept apart from reads and from the first prefix.
      if (object(item) && typeof item.id === "string" && typeof item.path === "string" && item.path.startsWith("/admin/v2/")
        && typeof item.operation === "string" && Object.hasOwn(writes,item.operation) && writes[/** @type {keyof typeof writes} */ (item.operation)] === item.method
        && typeof item.input === "string" && typeof item.output === "string" && typeof item.error === "string" && (item.identity === null || typeof item.identity === "string")) {
        changes.set(item.id, {path:item.path, method:writes[/** @type {keyof typeof writes} */ (item.operation)], operation:item.operation, input:item.input, output:item.output, error:item.error, identity:item.identity});
      }
    }
    /** @param {string} id @param {"GET" | "POST"} method @param {unknown} body @param {AbortSignal | undefined} extra @param {string | undefined} identity */
    async function run(id, method, body, extra=undefined, identity=undefined) {
      try {
        const call = calls.get(id);
        if (!call || call.method !== method) throw new Error("Request refused.");
        if(method === "POST") {
          if(!actions || !lens) throw new AccessError("authentication");
          lens.inspectData(actions.lookup(id).input,capture(body));
        }
        let path=call.path;
        if (call.identity === null) { if (identity !== undefined) throw new Error("Request refused."); }
        else {
          if(!lens || typeof identity !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(identity)) throw new Error("Request refused.");
          lens.inspectData(lens.identityModel(),identity);
          path=place(path,call.identity,identity);
        }
        const second=path.startsWith("/admin/v2/");
        const response = await send(path, method, method === "GET" ? undefined : JSON.stringify(body), false, extra, second);
        // Only HTTP status is interpreted here; closed categories stay private.
        if(second && response.status === 404) throw new AccessError("absent");
        if(second && response.status === 503) throw new AccessError("unavailable");
        if(!response.ok) throw new AccessError("unknown");
        /** @type {unknown} */ const value = await response.json();
        if(ended || extra?.aborted || !lens) throw new AccessError("authentication");
        if(JSON.stringify(value).includes(JSON.stringify(token).slice(1,-1))) throw new AccessError("incompatible");
        lens.inspectData(call.output,value);
        return capture(value);
      } catch (error) { if(ended) throw new AccessError("authentication"); if(error instanceof AccessError) throw error; throw new AccessError("unknown"); }
    }
    if(ended) throw new AccessError("authentication");
    return Object.freeze({
      close,
      /** @param {() => void} listener */ onClose: listener=>{ if(ended) listener(); else listeners.add(listener); return ()=>{listeners.delete(listener);}; },
      describe: () => { if(ended || !lens) throw new AccessError("authentication"); return lens; },
      design: () => {if(ended) throw new AccessError("authentication");forms ??= author(frozen);return forms;},
      /** @param {unknown} candidate @param {{path:string,label:string}[]} known @param {AbortSignal | undefined} extra */
      assess: async(candidate,known=[],extra=undefined)=>{
        if(ended || writing || !lens || !actions) throw new AccessError("incompatible");
        forms ??= author(frozen);
        const plan=forms, call=actions.lookup(plan.check), clean=capture(candidate);
        lens.inspectData(call.input,clean);
        const response=await send(call.path,call.method,JSON.stringify(clean),false,extra,true);
        /** @type {unknown} */ const value=await response.json();
        if(ended || extra?.aborted) throw new AccessError("authentication");
        if(JSON.stringify(value).includes(JSON.stringify(token).slice(1,-1))) throw new AccessError("incompatible");
        if(response.ok) {plan.inspectCheck(value);return {ok:true,issues:[]};}
        return {ok:false,issues:plan.reasons(value,known)};
      },
      /** @param {Command} command */ prepare: command=>{
        if(ended || !actions) throw new AccessError("authentication");
        const prepared=actions.prepare(command);
        const body=JSON.stringify(prepared.body);
        if(body.includes(JSON.stringify(token).slice(1,-1)) || new TextEncoder().encode(body).length > 1048576) throw new AccessError("incompatible");
        destination(prepared.path,false);
      },
      /** @param {Command} command @param {AbortSignal | undefined} extra @returns {Promise<Outcome>} */
      mutate: async(command,extra=undefined)=>{
        if(ended || !actions) throw new AccessError("authentication");
        if(writing) throw new AccessError("incompatible");
        const prepared=actions.prepare(command);
        const body=JSON.stringify(prepared.body);
        // Full checking precedes the flight and every bearer construction.
        if(extra?.aborted || body.includes(JSON.stringify(token).slice(1,-1)) || new TextEncoder().encode(body).length > 1048576) throw new AccessError("incompatible");
        destination(prepared.path,false);
        writing=true;
        try {
          const response=await send(prepared.path,prepared.call.method,body,false,extra,true);
          /** @type {unknown} */ const value=await response.json();
          if(ended || !actions) throw new AccessError("authentication");
          if(extra?.aborted || JSON.stringify(value).includes(JSON.stringify(token).slice(1,-1))) throw new AccessError("unknown");
          return actions.outcome(prepared.call,value,response.status,prepared.version);
        } catch(error) {
          if(ended) throw new AccessError("authentication");
          return {kind:"unknown",version:undefined,message:"Resultado desconhecido. Releia o estado antes de decidir."};
        } finally {writing=false;}
      },
      /** One second-prefix write. The body is checked against its input model before any
       * request; a failure after the flight began is `unknown`, never "nothing happened".
       * @param {string} id @param {unknown} body @param {string | undefined} identity @param {AbortSignal | undefined} extra
       * @returns {Promise<Written>}
       */
      submit: async(id,body,identity=undefined,extra=undefined)=>{
        if(ended || !lens) throw new AccessError("authentication");
        if(writing) throw new AccessError("incompatible");
        const call=changes.get(id);
        if(!call) throw new Error("Request refused.");
        const clean=capture(body);
        lens.inspectData(call.input,clean);
        let path=call.path;
        if(call.identity === null) { if(identity !== undefined) throw new Error("Request refused."); }
        else {
          if(typeof identity !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(identity)) throw new Error("Request refused.");
          lens.inspectData(lens.identityModel(),identity);
          path=place(path,call.identity,identity);
        }
        const text=JSON.stringify(clean);
        if(extra?.aborted || text.includes(JSON.stringify(token).slice(1,-1)) || new TextEncoder().encode(text).length > 1048576) throw new AccessError("incompatible");
        destination(path,false,call.method,true);
        writing=true;
        try {
          const response=await send(path,call.method,text,false,extra,true,true);
          /** @type {unknown} */ const value=await response.json();
          if(ended || !lens) throw new AccessError("authentication");
          if(extra?.aborted || JSON.stringify(value).includes(JSON.stringify(token).slice(1,-1))) return {kind:"unknown"};
          if(response.ok) { lens.inspectData(call.output,value); return {kind:"done",value:capture(value)}; }
          // Closed error envelope: category, optional version stamp and field reasons only.
          lens.inspectData(call.error,value);
          if(!object(value) || typeof value.error !== "string") return {kind:"unknown"};
          /** @type {{path:string,reason:string}[]} */ const fields=[];
          if(Array.isArray(value.fields)) for(const item of value.fields) if(object(item) && typeof item.path === "string" && typeof item.reason === "string") fields.push({path:item.path,reason:item.reason});
          return {kind:"refused",status:response.status,category:value.error,value:capture(value),fields};
        } catch(error) {
          if(ended) throw new AccessError("authentication");
          return {kind:"unknown"};
        } finally {writing=false;}
      },
      busy: ()=>writing,
      /** @param {string} id */ quiet: id=>changes.get(id)?.operation === "probe",
      /** @param {string} id @param {AbortSignal | undefined} extra @param {string | undefined} identity */ read: (id, extra=undefined, identity=undefined) => run(id, "GET", undefined,extra,identity),
      /** @param {string} id @param {unknown} body */ check: (id, body) => run(id, "POST", body),
    });
  } catch (error) { close(); if(error instanceof AccessError) throw error; throw new AccessError("unknown"); }
}


/** @typedef {{kind:"done",value:unknown} | {kind:"refused",status:number,category:string,value:unknown,fields:{path:string,reason:string}[]} | {kind:"unknown"}} Written */

export class AccessError extends Error {
  /** @param {"authentication" | "incompatible" | "unknown" | "absent" | "unavailable"} kind */
  constructor(kind) { super("Request unsuccessful."); this.kind=kind; }
}


/** @typedef {{value:unknown,version:number}} Snapshot */
/** @typedef {{base:Snapshot,draft:unknown,command:Command}} Editing */
/** @typedef {{tag:"authentication"} | {tag:"loading"} | {tag:"reading",snapshot:Snapshot} | {tag:"draft",edit:Editing} | {tag:"pending",edit:Editing} | {tag:"success",edit:Editing,version:number,newBase:Snapshot | undefined,message:string} | {tag:"conflict" | "busy" | "incompatible" | "unknown" | "uncertain",edit:Editing | undefined,newBase:Snapshot | undefined,message:string}} Flow */
/** @typedef {Awaited<ReturnType<typeof open>>} WriteClient */

/** Pure coordinator: no DOM control, timer, queue or implicit business operation.
 * The caller must explicitly choose a read and confirm each abstract command.
 * @param {WriteClient} client @param {string} readId
 */
export function coordinate(client,readId) {
  /** @type {Flow} */ let state={tag:"loading"};
  let epoch=0, sequence=0, closed=false, occupied=false, minimum=0;
  /** @type {AbortController | undefined} */ let active;
  /** @type {Snapshot | undefined} */ let observed;
  /** @type {() => void} */ let detach=()=>{};
  function clear() {
    if(closed) return;
    closed=true;epoch++;sequence++;active?.abort();active=undefined;observed=undefined;state={tag:"authentication"};occupied=false;minimum=0;detach();
    if(typeof window !== "undefined" && typeof window.removeEventListener === "function") {window.removeEventListener("pagehide",close);window.removeEventListener("pageshow",close);}
  }
  function close() {clear();client.close();}
  detach=client.onClose(clear);
  if(!closed && typeof window !== "undefined" && typeof window.addEventListener === "function") {window.addEventListener("pagehide",close);window.addEventListener("pageshow",close);}
  /** @param {unknown} value */
  function snapshot(value) { const clean=capture(value);return Object.freeze({value:clean,version:safeVersion(client.describe().inspectDataFor(readId,clean))}); }
  /** @param {unknown} error */
  function expires(error) {if(error instanceof AccessError && error.kind === "authentication") {close();return true;}return false;}
  async function load() {
    if(closed || occupied || (state.tag !== "loading" && state.tag !== "reading" && !(state.tag === "incompatible" && !state.edit))) return false;
    const mine=epoch,ticket=++sequence;active?.abort();active=new AbortController();state={tag:"loading"};
    try {const value=await client.read(readId,active.signal);if(closed || mine !== epoch || ticket !== sequence) return false;state={tag:"reading",snapshot:snapshot(value)};return true;}
    catch(error) {if(!closed && mine === epoch && ticket === sequence && !expires(error)) state={tag:"incompatible",edit:undefined,newBase:undefined,message:"Leitura indisponível. Tente novamente."};return false;}
  }
  /** Begin/replace an abstract draft only after an explicit, checked read.
   * @param {string} id @param {unknown} draft @param {string | undefined} identity
   */
  function begin(id,draft,identity=undefined) {
    if(closed || occupied || state.tag !== "reading") return false;
    const clean=capture(draft), base=state.snapshot;
    const command=Object.freeze({id,version:safeVersion(base.version),draft:clean,identity});
    client.prepare(command);
    sequence++;active?.abort();observed=undefined;minimum=base.version;
    state={tag:"draft",edit:Object.freeze({base,draft:clean,command})};return true;
  }
  /** Polls can only record a separate observation while a draft exists.
   * @param {unknown} value
   */
  function poll(value) {
    if(closed || occupied || state.tag === "pending" || (state.tag !== "reading" && state.tag !== "draft")) return false;
    const fresh=snapshot(value);
    if(state.tag === "reading") {
      if(fresh.version < state.snapshot.version) return false;
      if(fresh.version === state.snapshot.version && JSON.stringify(fresh.value) !== JSON.stringify(state.snapshot.value)) throw new Error("Request refused.");
      state={tag:"reading",snapshot:fresh};
    } else {
      if(fresh.version < state.edit.base.version || (observed && fresh.version < observed.version)) return false;
      if(fresh.version === state.edit.base.version && JSON.stringify(fresh.value) !== JSON.stringify(state.edit.base.value)) throw new Error("Request refused.");
      observed=fresh;
    }
    return true;
  }
  /** Readback never attributes a higher version to a lost command. */
  async function reconcile() {
    if(closed || occupied || !["success","conflict","unknown","uncertain"].includes(state.tag)) return false;
    const prior=state;
    if(prior.tag !== "success" && prior.tag !== "conflict" && prior.tag !== "unknown" && prior.tag !== "uncertain") return false;
    state={...prior,newBase:undefined,message:prior.tag === "success" ? "Salva; visualização ainda não atualizada." : prior.message};
    occupied=true;const mine=epoch,ticket=++sequence;active=new AbortController();
    try {
      const value=await client.read(readId,active.signal);
      if(closed || mine !== epoch || ticket !== sequence) return false;
      const fresh=snapshot(value), floor=prior.tag === "success" ? prior.version : prior.edit?.base.version;
      if(fresh.version < minimum || (floor !== undefined && fresh.version < floor)) throw new Error("Request refused.");
      state={...prior,newBase:fresh,message:prior.tag === "success" ? "Salva; visualização atualizada." : prior.message};return true;
    } catch(error) {if(!closed && mine === epoch && ticket === sequence) expires(error);return false;}
    finally {if(mine === epoch && ticket === sequence) {occupied=false;active=undefined;}}
  }
  /** Confirmed content and its base travel as one frozen command. */
  async function confirm() {
    if(closed || occupied || (state.tag !== "draft" && state.tag !== "busy")) return false;
    const edit=state.edit;if(!edit) return false;
    client.prepare(edit.command);
    occupied=true;sequence++;active?.abort();active=new AbortController();const mine=epoch,ticket=sequence;
    state={tag:"pending",edit};
    try {
      const result=await client.mutate(edit.command,active.signal);
      if(closed || mine !== epoch || ticket !== sequence) return false;
      if(result.version !== undefined) safeVersion(result.version);
      minimum=result.version ?? edit.base.version;
      if(result.kind === "authentication") {close();return false;}
      if(result.kind === "success") {
        if(result.version !== edit.base.version+1) throw new Error("Request refused.");
        state={tag:"success",edit,version:result.version,newBase:undefined,message:result.message};
      } else state={tag:result.kind,edit,newBase:undefined,message:result.message};
    } catch(error) {
      if(closed || mine !== epoch || ticket !== sequence || expires(error)) return false;
      state={tag:"unknown",edit,newBase:undefined,message:"Resultado desconhecido. Releia o estado antes de decidir."};
    } finally {if(mine === epoch && ticket === sequence) {occupied=false;active=undefined;}}
    if(!closed) await reconcile();
    return !closed;
  }
  // Abort only ends waiting locally; it does not assert server cancellation.
  function cancel() {
    if(closed || !occupied) return false;
    if(state.tag === "pending") {
      const edit=state.edit;sequence++;active?.abort();active=undefined;occupied=false;
      state={tag:"unknown",edit,newBase:undefined,message:"Resultado desconhecido. Releia o estado antes de decidir."};return true;
    }
    return false;
  }
  /** Explicit human review is required to choose a conflict's separate base.
   * @param {unknown} draft
   */
  function review(draft) {
    if(closed || occupied || state.tag !== "conflict" || !state.newBase || !state.edit) return false;
    const edit=state.edit, base=state.newBase, clean=capture(draft);
    const command=Object.freeze({...edit.command,version:safeVersion(base.version),draft:clean});
    client.prepare(command);state={tag:"draft",edit:Object.freeze({base,draft:clean,command})};observed=undefined;return true;
  }
  function finish() {
    if(closed || occupied || state.tag !== "success" || !state.newBase) return false;
    state={tag:"reading",snapshot:state.newBase};observed=undefined;return true;
  }
  /** @param {unknown} draft */
  function change(draft) {
    if(closed || occupied || state.tag !== "draft") return false;
    const edit=state.edit, clean=capture(draft), command=Object.freeze({...edit.command,draft:clean});
    client.prepare(command);state={tag:"draft",edit:Object.freeze({...edit,draft:clean,command})};return true;
  }
  function discard() {
    if(closed || occupied || state.tag !== "draft") return false;
    state={tag:"reading",snapshot:state.edit.base};observed=undefined;return true;
  }
  return Object.freeze({load,begin,poll,confirm,cancel,reconcile,review,finish,change,discard,close,release:clear,
    getState:()=>Object.freeze(state),getObservation:()=>observed});
}


/** @typedef {Awaited<ReturnType<typeof open>>} WorkClient */
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
  /** @type {unknown} */ let editorList;
  /** @type {AbortController | undefined} */ let active;
  let ended=false, engaged=false, dirty=false, waiting=false, serial=0, checked=false, locked=false, examining=false;
  /** @type {HTMLParagraphElement | undefined} */ let note;
  /** @type {HTMLElement | undefined} */ let proof;
  /** @type {() => void} */ let detach=()=>{};
  function dismiss() {if(dialog) {dialog.close();erase(dialog);dialog.remove();dialog=undefined;}if(restore?.isConnected) restore.focus();}
  function reset() {serial++;active?.abort();active=undefined;flow?.release();flow=undefined;intent=undefined;batchPage=undefined;base=undefined;raw=undefined;editorList=undefined;dirty=false;engaged=false;waiting=false;examining=false;checked=false;proof=undefined;note=undefined;dismiss();}
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
      const ticket=serial;waiting=true;editorList=await client.read(plan.editorCatalog,active?.signal);
      if(ended || ticket !== serial) return;waiting=false;
      if(client.describe().inspectDataFor(plan.editorCatalog,editorList) !== client.describe().inspectDataFor(plan.read,base)) throw new Error("Request refused.");
      raw=plan.defaults(page,selected);
      if(selected !== undefined) plan.checkedContent(page,raw,editorList);
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
              [order[index],order[next]]=[order[next],order[index]];values[key]=order;sync();draftTouched();draw();
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
      input.addEventListener("input",()=>{if(waiting && !examining) return;values[key]=input.value.split("\n");sync();draftTouched();});form.append(label,input);
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
  function draftTouched() {checked=false;if(proof) erase(proof);dialog?.querySelectorAll("[aria-describedby]").forEach(n=>n.removeAttribute("aria-describedby"));serial++;active?.abort();active=new AbortController();if(examining) {waiting=false;examining=false;}dirty=true;announce("Rascunho não salvo. Resultado anterior descartado.");}
  /** @param {Record<string,unknown>} control @param {Record<string,unknown>} values @param {HTMLElement} parent @param {() => void} onEdit */
  function controlNode(control,values,parent,onEdit) {
    if(!Array.isArray(control.path) || typeof control.path[0] !== "string" || typeof control.label !== "string") throw new Error("Request refused.");
    const key=control.path[0], field=plan.fields(control.model).find(f=>f.name === key);if(!field) throw new Error("Request refused.");
    const shape=plan.shape(field.ref), label=element("label",control.label), id="field-"+String(control.id);
    const node=control.type === "select" ? element("select") : element("input");node.id=id;label.htmlFor=id;
    if(node instanceof HTMLSelectElement) {
      const empty=element("option","Escolha explicitamente");empty.value="";node.append(empty);
      const choices=Array.isArray(shape.choices) ? shape.choices : plan.available(editorList);
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
      values[key]=value;draftTouched();onEdit();
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
    form.addEventListener("submit",event=>{event.preventDefault();if(waiting) return;try {if(!intent) return;plan.checkedContent(intent.page,raw,editorList);if(p.warning) confirmNotice(p.warning,()=>{void commit();});else void commit();} catch {announce("Confira os campos conhecidos antes de salvar.");}});
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
      const edit=intent ? {...intent,value:plan.checkedContent(intent.page,raw,editorList)} : undefined;
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
        const p=plan.profile(intent.page), body=intent.operation === "delete" ? {} : {[p.member]:plan.checkedContent(intent.page,raw,editorList)};
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
      try {if(flow.review({[p.member]:plan.checkedContent(p.id,raw,editorList)})) {base=state.newBase?.value;checked=false;renderForm();}} catch {announce("Revisão incompatível. Rascunho preservado.");}
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
  /** `slot` only places an item's buttons: it receives the identity those
   * buttons already target and returns the card that displays that same
   * identity, or nothing. Handlers, identity and order never depend on it.
   * @param {HTMLElement} panel @param {string} page @param {unknown} value
   * @param {((identity:string)=>{node:HTMLElement,name:string}|undefined)|undefined} slot
   */
  function attach(panel,page,value,slot=undefined) {
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
      const change=button("Editar",()=>{void edit(page,"replace",identity);}), remove=button("Excluir",()=>{void edit(page,"delete",identity);});change.disabled=!permitted;remove.disabled=!permitted;
      const home=slot?.(identity);
      if(home) {
        const row=element("div");row.className="item-actions";row.setAttribute("role","group");row.setAttribute("aria-label","Ações: "+home.name);
        row.append(change,remove);home.node.append(row);
      } else {
        const row=element("section");row.append(element("h3","Item "+(index+1)));row.append(change,remove);panel.append(row);
      }
    }
  }
  return {attach,leave,close,active:()=>engaged,pending:()=>waiting,examined:()=>checked};
}
/** @param {unknown} value @returns {Record<string,unknown>[]} */
function rowsForControls(value) {if(!Array.isArray(value) || !value.every(entry)) throw new Error("Request refused.");return value;}


/** @typedef {Awaited<ReturnType<typeof open>>} DeskClient */
/** @typedef {(string|number)[]} Way */
/** @typedef {{value:string,text:string}} Choice */
/** @typedef {{id:string,label:string,help?:string|null,kind:"text"|"secret"|"integer"|"flag"|"choice"|"lines"|"records",path:Way,source?:Way|null,default?:string|number|boolean|null,optional?:boolean,choices?:Choice[],item?:string|null,items?:Field[],when?:{path:Way,value:string|number|boolean}|null}} Field */
/** @typedef {{id:string,label:string,title:string,call:string,place:"collection"|"detail"|"aside",stamp?:Way|null,origin?:Way|null,after?:"reread"|"list"|"open",lands?:Way|null,fields?:Field[],visible?:{path:Way,value:string|number|boolean}|null,confirm:string,typed?:Field|null,probe?:string|null,drop?:Way[],done:string,tone?:"plain"|"danger"}} Deed */
/** @typedef {{value:string,kind:"conflict"|"refused"|"busy"|"blocked"|"uncertain",text:string}} Result */
/** @typedef {{actions?:Deed[],outcomes?:Result[],reasons?:Choice[],latest?:Way|null,unknown?:string,guide:{label:string,banner:string,steps:{id:string,label:string,text:string,fields?:string[]}[],action?:string|null}}} Plan */
/** @typedef {{key:number,values:Map<string,unknown>}} Row */
/** @typedef {Written | {kind:"busy-local"} | {kind:"gone"} | {kind:"local"}} Sent */

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
  /** @param {string} title @param {string} tone @param {() => void} [escaped] */
  function modal(title,tone,escaped) {
    dismiss();dialog=element("dialog");dialog.className="desk "+tone;
    const heading=element("h2",title);heading.id="desk-title";heading.tabIndex=-1;
    dialog.setAttribute("aria-labelledby",heading.id);
    note=element("p");note.setAttribute("role","status");note.setAttribute("aria-live","polite");note.className="desk-note";
    // Esc runs the caller's per-stage exit (default: leave with no reread) so it mirrors the visible button.
    dialog.append(heading,note);dialog.addEventListener("cancel",event=>{event.preventDefault();(escaped ?? (()=>leave(()=>{})))();});
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
    // Esc mirrors the visible button: conflict and ending stages reread like "Descartar e reler"/"Fechar";
    // the conflict draft still asks before discarding. Other stages keep the plain leave.
    const box=modal(deed.title,deed.tone ?? "plain",()=>leave(stage === "conflict" || stage === "ending" ? hooks.refresh : ()=>{}));
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
/** @typedef {"good"|"neutral"|"attention"} Tone */
/** @typedef {{id:string,label:string,path:Trail,kind:"count"|"flag"|"text"|"list"|"tree",wording:{value:string,text:string,tone?:Tone|null}[],show?:"fact"|"metric"|"code"|"ordered",blank?:string|null}} Figure */
/** @typedef {{label:string,note?:string|null,members:string[]}} Group */
/** @typedef {{id:string,label:string,source:"main"|"extra",entries:Figure[],groups?:Group[]}} Tab */
/** @typedef {{brand:string,tagline:string,main:string,legacy:string,yes:string,no:string,blank:string,failure:string,unavailable:string,
 * summary:{id:string,label:string,call:string,figures:Figure[],notes:string[],absent:string},
 * collection:{id:string,label:string,call:string,items:Trail,key:Trail,title:Trail,columns:Figure[],search:string,searchable:Trail[],empty:string,nothing:string,open:string},
 * detail:{id:string,call:string,extra:string,back:string,title?:Trail|null,tabs:Tab[],gone:string},
 * guide:{id:string,label:string,banner:string,steps:{id:string,label:string,text:string,fields?:string[]}[],action?:string|null},
 * actions?:Deed[],outcomes?:Result[],reasons?:{value:string,text:string}[],unknown?:string,
 * pages?:{view:string,sections:{label:string,note?:string|null,entries:Figure[]}[]}[]}} Board */
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
  /** Second-prefix writes (Stage 6): volatile drafts, one write, explicit review.
   * @type {ReturnType<typeof desk> | undefined} */ let office;
  /** Cards of the current v1 reading by displayed identity; `null` marks an
   * identity shown twice, which never receives actions.
   * @type {Map<string,{node:HTMLElement,name:string}|null>} */ let cards=new Map();
  function stopClock() { if(timer !== undefined) clearTimeout(timer); timer=undefined; }
  function clear() {
    epoch++; turn++; flight?.abort(); flight=undefined; lateral?.abort(); lateral=undefined; stopClock(); paused=true; busy=false;
    sheet=undefined; pane=undefined; side=undefined; filter=""; place={kind:"view",index:0};
    editor?.close();editor=undefined;office?.close();office=undefined;
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
        office=desk(client,root,access.board,{
          // After a write: removal returns to the list; anything else reads the item again.
          reread:(deed,value)=>{
            void value;
            if(deed.after === "list") {go({kind:"collection"});return;}
            if(deed.place === "aside") side=undefined;
            void read(true);
          },
          refresh:()=>{side=undefined;void read(true);},
        });
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
      if(next.kind === "view") void load(true);
      else if(next.kind === "guide" && !(access.tag === "ready" && access.board.guide.action)) {show(true);}
      else void read(true);
    };
    if(editor?.active()) editor.leave(navigate);
    else if(office?.engaged()) office.leave(navigate);
    else navigate();
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
      reading(panel,view,sheet.value);
      notice.textContent="Respondendo · Última leitura: "+new Date(sheet.time).toLocaleTimeString();
      editor?.attach(panel,view.id,sheet.value,identity=>cards.get(identity) ?? undefined);
    } else if(sheet?.tag === "unknown") {
      notice.textContent=sheet.stale ? "Leitura desatualizada. Tente novamente." : "Leitura indisponível. Tente novamente.";
      if(sheet.prior?.tag === "success") reading(panel,view,sheet.prior.value);
    } else notice.textContent="Carregando…";
    if(retry) retry.disabled=busy;
    if(restore) title.focus();
  }
  /** A Política v1 reading: the declared page groups the same displayed value;
   * without a page the approved read controls are shown as before.
   * @param {HTMLElement} target @param {PageItem} view @param {unknown} value
   */
  function reading(target,view,value) {
    if(access.tag !== "ready") return;
    cards=new Map();
    const shown=access.client.design().displayed(view.call,value);
    const page=access.board.pages?.find(p=>p.view === view.id);
    if(page) {
      target.append(grouped({entries:page.sections.flatMap(s=>s.entries),groups:page.sections.map(s=>({label:s.label,note:s.note ?? null,members:s.entries.map(e=>e.id)}))},shown));
      return;
    }
    for(const control of view.controls) {
      if(control.type !== "read" || typeof control.label !== "string") continue;
      const section=element("section");section.append(element("h3",control.label),plain(at(shown,control.path)));target.append(section);
    }
  }
  /** @param {unknown} value @param {Figure} figure @returns {HTMLElement} */
  function figure(value,figure) {
    if(access.tag !== "ready") return element("span");
    const board=access.board;
    if(value === undefined || value === null) { const node=element("span",figure.blank ?? board.blank);node.className="muted";return node; }
    if(figure.kind === "flag" && typeof value === "boolean") {
      const said=figure.wording.find(w=>w.value === String(value));
      // A declared tone wins; without it, the first wording of a signal is its healthy state.
      const tone=said?.tone ?? ((said ? said === figure.wording[0] : value) ? "good" : "attention");
      return badge(said ? said.text : value ? board.yes : board.no,tone);
    }
    if(figure.kind === "count" && typeof value === "number") return element("span",value.toLocaleString("pt-BR"));
    if(figure.kind === "text" && typeof value === "string") {
      const known=figure.wording.find(w=>w.value === value);
      if(known?.tone) return badge(known.text,known.tone);
      if(!known && figure.show === "code") return element("code",value);
      return element("span",known ? known.text : value);
    }
    if(figure.show === "code" && typeof value === "number") return element("code",String(value));
    if(figure.kind === "list" && Array.isArray(value)) {
      if(!value.length) return element("span",figure.wording.find(w=>w.value === "@empty")?.text ?? "Lista vazia.");
      const ordered=figure.show === "ordered";
      const list=element(ordered ? "ol" : "ul");list.className=ordered ? "ordered" : "chips";
      // Known items read as declared text; anything else stays as received.
      for(const item of value) { const known=String(item).startsWith("@") ? undefined : figure.wording.find(w=>w.value === String(item));list.append(element("li",known ? known.text : String(item))); }
      return list;
    }
    if(figure.kind === "tree" && Array.isArray(value)) return sequence(value,figure);
    return plain(value);
  }
  /** Pill with a glyph and its own text, so the state never depends on colour alone.
   * @param {string} text @param {Tone} tone @returns {HTMLElement}
   */
  function badge(text,tone) {
    const node=element("span",(tone === "good" ? "✓ " : tone === "attention" ? "✕ " : "○ ")+text);
    node.className="flag "+(tone === "good" ? "on" : tone === "attention" ? "off" : "neutral");return node;
  }
  /** @param {Record<string,unknown>} source @param {Map<string,string>} words @param {string | undefined} omit @returns {HTMLElement} */
  function properties(source,words,omit=undefined) {
    const list=element("dl");list.className="sequence-fields";
    // Declared label order first; keys without a label keep their received order.
    const order=[...words.keys()];
    const rank=(/** @type {string} */ key)=>{const found=order.indexOf("key:"+key);return found < 0 ? order.length : found;};
    for(const [key,value] of Object.entries(source).sort((a,b)=>rank(a[0])-rank(b[0]))) {
      if(key === omit) continue;
      const row=element("div");const label=element("dt",words.get("key:"+key) ?? key);
      const body=element("dd");
      if(entry(value)) body.append(Object.keys(value).length ? properties(value,words) : element("span",words.get("@empty-object") ?? "Sem valores."));
      else { const known=words.get("value:"+key+":"+String(value));body.append(known === undefined ? plain(value) : element("span",known)); }
      row.append(label,body);list.append(row);
    }
    return list;
  }
  /** @param {unknown[]} values @param {Figure} figure @returns {HTMLElement} */
  function sequence(values,figure) {
    const words=new Map(figure.wording.map(w=>[w.value,w.text]));
    const wrap=element("div");wrap.className="sequence-wrap";
    const hintText=words.get("@hint");
    if(hintText) { const hint=element("p",hintText);hint.className="sequence-hint";wrap.append(hint); }
    if(!values.length) { const empty=element("p",words.get("@empty") ?? "Nenhum item cadastrado.");empty.className="sequence-empty";wrap.append(empty);return wrap; }
    const list=element("ol");list.className="sequence-cards";
    for(const [index,value] of values.entries()) {
      if(!entry(value)) { const row=element("li");row.append(plain(value));list.append(row);continue; }
      const row=element("li");row.className="sequence-card";
      const name=(words.get("@item") ?? "Item")+" "+(index+1);
      row.append(element("h3",name));
      // Declared identity key: the card can receive that item's own actions.
      const key=words.get("@identity"), identity=key ? value[key] : undefined;
      if(typeof identity === "string") cards.set(identity,cards.has(identity) ? null : {node:row,name});
      const headline=words.get("@headline");
      const visibleHeadline=headline && typeof value[headline] === "string" ? headline : undefined;
      if(visibleHeadline) {
        const caption=element("p");caption.className="sequence-headline";
        caption.append(element("span",words.get("@headline-label") ?? "Valor"),element("code",String(value[visibleHeadline])));
        row.append(caption);
      }
      row.append(properties(value,words,visibleHeadline));list.append(row);
    }
    wrap.append(list);return wrap;
  }
  /** @param {Figure[]} figures @param {unknown} value */
  function facts(figures,value) {
    const list=element("dl");list.className="facts";
    for(const item of figures) {
      const row=element("div");const body=element("dd");body.append(figure(at(value,item.path),item));
      if(item.kind === "tree") row.className="sequence-row";
      row.append(element("dt",item.label),body);list.append(row);
    }
    return list;
  }
  /** Declared groups of a tab: heading, short explanation, then its values.
   * @param {{entries:Figure[],groups?:Group[]}} tab @param {unknown} value @returns {HTMLElement}
   */
  function grouped(tab,value) {
    const groups=tab.groups ?? [];
    if(!groups.length) return facts(tab.entries,value);
    const wrap=element("div");wrap.className="facets";
    /** @type {Set<string>} */ const placed=new Set();
    for(const group of groups) {
      /** @type {Figure[]} */ const members=[];
      for(const id of group.members) { const found=tab.entries.find(e=>e.id === id);if(found && !placed.has(id)) {members.push(found);placed.add(id);} }
      const block=element("section");block.className="facet";
      block.append(element("h3",group.label));
      if(group.note) { const note=element("p",group.note);note.className="facet-note";block.append(note); }
      const metrics=members.filter(m=>m.show === "metric"), rest=members.filter(m=>m.show !== "metric");
      if(metrics.length) { const cards=facts(metrics,value);cards.className="cards";block.append(cards); }
      if(rest.length) block.append(facts(rest,value));
      wrap.append(block);
    }
    // Never hide a declared value: anything outside the groups still appears.
    const left=tab.entries.filter(e=>!placed.has(e.id));
    if(left.length) wrap.append(facts(left,value));
    return wrap;
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
      if(pane?.tag === "ready") offer(panel,"detail",pane.value,here.key);
      report(pane,board.detail.gone);
      if(pane?.tag === "ready") {
        // The heading follows the detail read, so a renamed item is not shown stale.
        const named=board.detail.title ? at(pane.value,board.detail.title) : undefined;
        if(typeof named === "string" && named) title.textContent=named;
        tabs(here,pane.value);
      }
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
    if(access.board.guide.action) {
      const add=element("button",access.board.guide.label);add.type="button";add.className="primary";
      add.addEventListener("click",()=>go({kind:"guide",step:0}));
      const bar=element("div");bar.className="actions";bar.append(add);panel.append(bar);
    }
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
      if(tab.source === "main") { body.append(grouped(tab,main)); return; }
      if(side?.tag === "ready") { offer(body,"aside",side.value,here.key); body.append(grouped(tab,side.value)); return; }
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
  /** Declared writes offered over one reading. Locked writes stay visible, disabled.
   * @param {HTMLElement} target @param {"detail"|"aside"} where @param {unknown} base @param {string} key
   */
  function offer(target,where,base,key) {
    if(!office) return;
    const own=office.offered(where,base);if(!own.length) return;
    const bar=element("div");bar.className="actions";bar.setAttribute("role","group");
    bar.setAttribute("aria-label","Ações");
    for(const deed of own) {
      const button=element("button",deed.label);button.type="button";
      if(deed.tone === "danger") button.className="danger";
      button.disabled=office.locked();
      button.addEventListener("click",()=>office?.start(deed,base,key));
      bar.append(button);
    }
    target.append(bar);
    if(office.locked()) { const why=element("p",office.why());why.className="hint callout warn";target.append(why); }
  }
  /** @param {number} step @param {boolean} restore */
  function guide(step,restore) {
    if(access.tag !== "ready" || !panel || !notice) return;
    const spec=access.board.guide;
    if(spec.action && office) {
      // The registration wizard needs the catalog version stamp of the list reading.
      const title=element("h2",spec.label);title.tabIndex=-1;
      const banner=element("p",spec.banner);banner.className="banner";banner.setAttribute("role","note");
      const trail=element("ol");trail.className="steps";trail.setAttribute("aria-label",spec.label);
      for(const [index,item] of spec.steps.entries()) {
        const node=element("li",(index+1)+". "+item.label);if(index === step) node.setAttribute("aria-current","step");
        node.className=index === step ? "now" : "other";trail.append(node);
      }
      erase(panel);panel.append(title,banner,trail);
      if(pane?.tag !== "ready") {
        report(pane,access.board.summary.absent);
        if(pane?.tag === "loading" || pane === undefined) hint(panel,"Carregando…");
        else hint(panel,pane.tag === "absent" ? access.board.summary.absent : pane.tag === "unavailable" ? access.board.unavailable : access.board.failure,pane.tag === "absent" ? "info" : "warn");
      } else if(office.locked()) {
        notice.textContent=office.why();hint(panel,office.why(),"warn");
      } else {
        notice.textContent=spec.banner;
        const base=pane.value;
        office.wizard(panel,step,base,next=>{place={kind:"guide",step:next};guide(next,true);},(value,deed)=>{
          const key=deed.lands ? at(value,deed.lands) : undefined;
          if(typeof key === "string") go({kind:"detail",key,title:key,tab:0});
          else go({kind:"collection"});
        });
      }
      if(restore) title.focus();
      return;
    }
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
    if(access.tag === "ready" && !paused && !busy && !office?.engaged() && document.visibilityState === "visible" && (place.kind === "view" || place.kind === "summary")) timer=setTimeout(()=>{void (place.kind === "summary" ? read(false) : poll());},15000);
  }
  /** Reads the declared second-prefix call of the current place.
   * @param {boolean} focus
   */
  async function read(focus) {
    if(access.tag !== "ready") return;
    const client=access.client, board=access.board, here=place;
    const call=here.kind === "summary" ? board.summary.call : here.kind === "collection" || here.kind === "guide" ? board.collection.call : here.kind === "detail" ? board.detail.call : undefined;
    if(!call) return;
    flight?.abort(); flight=new AbortController();
    const mine=epoch, ticket=++turn;busy=true;paused=true;stopClock();
    if(!(here.kind === "summary" && pane?.tag === "ready" && !focus)) {pane={tag:"loading"};show(focus);}
    try {
      const value=await client.read(call,flight.signal,here.kind === "detail" ? here.key : undefined);
      if(mine !== epoch || ticket !== turn) return;
      pane={tag:"ready",value,time:Date.now()};paused=false;
      // A fresh successful read is the confirmation a doubtful write waits for.
      office?.settle();
    } catch(error) {
      if(mine !== epoch || ticket !== turn) return;
      if(error instanceof AccessError && error.kind === "authentication") { login("Autenticação necessária.");return; }
      pane={tag:error instanceof AccessError && error.kind === "absent" ? "absent" : error instanceof AccessError && error.kind === "unavailable" ? "unavailable" : "broken"};paused=true;
    } finally {
      if(mine === epoch && ticket === turn) {
        busy=false;show(focus);schedule();
        const said=office?.take();if(said && notice) notice.textContent=said+" "+notice.textContent;
      }
    }
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
