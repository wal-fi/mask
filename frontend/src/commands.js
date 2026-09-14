import { at, entry, reader } from "./reader.js";

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
