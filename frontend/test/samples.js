import { readFileSync } from "node:fs";
/** @type {unknown} */ const source=JSON.parse(readFileSync(new URL("../private/presentation.json",import.meta.url),"utf8"));
/** @param {unknown} value @returns {value is Record<string,unknown>} */
function rec(value) { return typeof value === "object" && value !== null && !Array.isArray(value); }
if(!rec(source) || !Array.isArray(source.models) || !Array.isArray(source.calls)) throw new Error("Fixture failed.");
export const book=source;
const models=new Map(source.models.filter(rec).map(n=>[n.id,n.shape]));
const calls=source.calls.filter(rec);
/** @param {unknown} key @returns {unknown} */
function sample(key) {
  const n=models.get(key);if(!rec(n)) throw new Error("Fixture failed.");
  if(n.type === "nullable") return null;
  if(n.type === "list") return [];
  if(n.type === "integer") return n.min;
  if(n.type === "boolean") return false;
  if(n.type === "enum" && Array.isArray(n.choices)) return n.choices[0];
  if(n.type === "string") return typeof n.prefix === "string" ? n.prefix+"0".repeat(32) : "";
  if(n.type === "object" && Array.isArray(n.fields)) return Object.fromEntries(n.fields.filter(rec).filter(f=>f.required).map(f=>[f.name,sample(f.ref)]));
  throw new Error("Fixture failed.");
}
/** @param {string} id @returns {unknown} */
export function responseFor(id) {const call=calls.find(c=>c.id === id);if(!call)throw new Error("Fixture failed.");return sample(call.output);}
