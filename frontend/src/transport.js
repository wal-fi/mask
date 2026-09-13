import { reader } from "./reader.js";
import { check, digest } from "../../src/maskgw/admin/ui/assets/ui.js";

/** @param {unknown} value @returns {value is Record<string, unknown>} */
function object(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** @param {string} path @param {boolean} first */
function destination(path, first) {
  if (first ? path !== "/admin/ui/presentation.json" : !path.startsWith("/admin/v1/")) throw new Error("Request refused.");
  if (/[?#%\\{}]|\/\//.test(path) || path.split("/").some(v => v === "." || v === "..")) throw new Error("Request refused.");
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin || url.pathname !== path) throw new Error("Request refused.");
  return url;
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
  /** @type {Map<string, {path:string, method:"GET" | "POST", operation:string, output:string}>} */ const calls = new Map();
  /** @type {ReturnType<typeof reader> | undefined} */ let lens;
  function close() { ended=true; token=""; calls.clear(); lens=undefined; stop.abort(); signal?.removeEventListener("abort",close); }
  signal?.addEventListener("abort",close,{once:true});
  if(signal?.aborted) close();
  /** @param {string} path @param {"GET" | "POST"} method @param {string | undefined} body @param {boolean} first @param {AbortSignal | undefined} extra */
  async function send(path, method, body, first, extra=undefined) {
    if(ended) throw new AccessError("authentication");
    const url = destination(path, first);
    if (body !== undefined && body.includes(token)) throw new Error("Request refused.");
    const headers = new Headers();
    headers.set("Authorization", "Bearer " + token);
    if (body !== undefined) headers.set("Content-Type", "application/json");
    const response = await fetch(url, {
      signal:AbortSignal.any([stop.signal,AbortSignal.timeout(30000),...(extra ? [extra] : [])]), method, headers, ...(body === undefined ? {} : {body}), mode: "cors",
      credentials: "omit", redirect: "error", cache: "no-store", referrerPolicy: "no-referrer",
    });
    if(ended) throw new AccessError("authentication");
    if(response.status === 401) { close(); expired(); throw new AccessError("authentication"); }
    if (!response.ok || response.headers.get("Content-Type") !== "application/json") throw new AccessError("unknown");
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
    lens=reader(data);
    /** @type {unknown[]} */ const entries = data.calls;
    for (const item of entries) {
      if (object(item) && typeof item.id === "string" && typeof item.path === "string" && typeof item.output === "string" && item.identity === null
        && ((item.method === "GET" && item.operation === "read") || (item.method === "POST" && item.operation === "check"))) {
        calls.set(item.id, {path:item.path, method:item.method, operation:item.operation, output:item.output});
      }
    }
    /** @param {string} id @param {"GET" | "POST"} method @param {unknown} body @param {AbortSignal | undefined} extra */
    async function run(id, method, body, extra=undefined) {
      try {
        const call = calls.get(id);
        if (!call || call.method !== method) throw new Error("Request refused.");
        const response = await send(call.path, method, method === "GET" ? undefined : JSON.stringify(body), false, extra);
        /** @type {unknown} */ const value = await response.json();
        if(ended || extra?.aborted || !lens) throw new AccessError("authentication");
        if(JSON.stringify(value).includes(JSON.stringify(token).slice(1,-1))) throw new AccessError("incompatible");
        lens.inspectData(call.output,value);
        return value;
      } catch (error) { if(ended) throw new AccessError("authentication"); if(error instanceof AccessError) throw error; throw new AccessError("unknown"); }
    }
    if(ended) throw new AccessError("authentication");
    return Object.freeze({
      close,
      describe: () => { if(ended || !lens) throw new AccessError("authentication"); return lens; },
      /** @param {string} id @param {AbortSignal | undefined} extra */ read: (id, extra=undefined) => run(id, "GET", undefined,extra),
      /** @param {string} id @param {unknown} body */ check: (id, body) => run(id, "POST", body),
    });
  } catch (error) { close(); if(error instanceof AccessError) throw error; throw new AccessError("unknown"); }
}


export class AccessError extends Error {
  /** @param {"authentication" | "incompatible" | "unknown"} kind */
  constructor(kind) { super("Request failed."); this.kind=kind; }
}
