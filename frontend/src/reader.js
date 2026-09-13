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
  if (!entry(book) || !entries(book.models) || !entries(book.bindings) || !entries(book.views) || !entries(book.calls)) throw new Error("Request failed.");
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
    if(!acceptsData(key,value,0,new Set(),versions,consents) || new Set(versions).size > 1 || new Set(consents).size > 1) throw new Error("Request failed.");
    const version=versions[0];
    if(version !== undefined && consents.some(c=>c !== (version > 0))) throw new Error("Request failed.");
    return version;
  }
  const calls=book.calls;
  const views=book.views.map(view=>{
    const call=calls.find(c=>c.id === view.call);
    if(typeof view.id !== "string" || typeof view.label !== "string" || !entries(view.controls)
      || !call || typeof call.id !== "string" || call.method !== "GET" || call.identity !== null) throw new Error("Request failed.");
    return {id:view.id,label:view.label,call:call.id,controls:view.controls};
  });
  /** @param {string} id @param {unknown} value */
  function inspectDataFor(id,value) {
    const call=calls.find(c=>c.id === id && c.method === "GET");
    if(!call) throw new Error("Request failed.");
    const version=inspectData(call.output,value);
    if(version === undefined) throw new Error("Request failed.");
    return version;
  }
  return {views,inspectData,inspectDataFor};
}
