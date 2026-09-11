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
 */
export async function open(token) {
  if (!token || /[\r\n]/.test(token)) throw new Error("Request refused.");
  /** @param {string} path @param {"GET" | "POST"} method @param {string | undefined} body @param {boolean} first */
  async function send(path, method, body, first) {
    const url = destination(path, first);
    if (body !== undefined && body.includes(token)) throw new Error("Request refused.");
    const headers = new Headers();
    headers.set("Authorization", "Bearer " + token);
    if (body !== undefined) headers.set("Content-Type", "application/json");
    const response = await fetch(url, {
      method, headers, ...(body === undefined ? {} : {body}), mode: "cors",
      credentials: "omit", redirect: "error", cache: "no-store", referrerPolicy: "no-referrer",
    });
    if (!response.ok || response.headers.get("Content-Type") !== "application/json") throw new Error("Request failed.");
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
    /** @type {Map<string, {path:string, method:"GET" | "POST", operation:string}>} */ const calls = new Map();
    /** @type {unknown[]} */ const entries = data.calls;
    for (const item of entries) {
      if (object(item) && typeof item.id === "string" && typeof item.path === "string" && item.identity === null
        && ((item.method === "GET" && item.operation === "read") || (item.method === "POST" && item.operation === "check"))) {
        calls.set(item.id, {path:item.path, method:item.method, operation:item.operation});
      }
    }
    /** @param {string} id @param {"GET" | "POST"} method @param {unknown} body */
    async function run(id, method, body) {
      try {
        const call = calls.get(id);
        if (!call || call.method !== method) throw new Error("Request refused.");
        const response = await send(call.path, method, method === "GET" ? undefined : JSON.stringify(body), false);
        /** @type {unknown} */ const value = await response.json();
        return value;
      } catch { throw new Error("Request failed."); }
    }
    return Object.freeze({
      /** @param {string} id */ read: (id) => run(id, "GET", undefined),
      /** @param {string} id @param {unknown} body */ check: (id, body) => run(id, "POST", body),
    });
  } catch { throw new Error("Request failed."); }
}
