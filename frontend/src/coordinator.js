import { capture, safeVersion } from "./commands.js";
import { AccessError } from "./transport.js";

/** @typedef {{value:unknown,version:number}} Snapshot */
/** @typedef {{base:Snapshot,draft:unknown,command:import("./commands.js").Command}} Editing */
/** @typedef {{tag:"authentication"} | {tag:"loading"} | {tag:"reading",snapshot:Snapshot} | {tag:"draft",edit:Editing} | {tag:"pending",edit:Editing} | {tag:"success",edit:Editing,version:number,newBase:Snapshot | undefined,message:string} | {tag:"conflict" | "busy" | "incompatible" | "unknown" | "uncertain",edit:Editing | undefined,newBase:Snapshot | undefined,message:string}} Flow */
/** @typedef {Awaited<ReturnType<typeof import("./transport.js").open>>} WriteClient */

/** Pure coordinator: no DOM control, timer, queue or implicit business operation.
 * The caller must explicitly choose a read and confirm each abstract command.
 * @param {WriteClient} client @param {string} readId
 */
export function coordinate(client,readId) {
  /** @type {Flow} */ let state={tag:"loading"};
  let generation=0, sequence=0, closed=false, occupied=false, minimum=0;
  /** @type {AbortController | undefined} */ let active;
  /** @type {Snapshot | undefined} */ let observed;
  /** @type {() => void} */ let detach=()=>{};
  function clear() {
    if(closed) return;
    closed=true;generation++;sequence++;active?.abort();active=undefined;observed=undefined;state={tag:"authentication"};occupied=false;minimum=0;detach();
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
    const mine=generation,ticket=++sequence;active?.abort();active=new AbortController();state={tag:"loading"};
    try {const value=await client.read(readId,active.signal);if(closed || mine !== generation || ticket !== sequence) return false;state={tag:"reading",snapshot:snapshot(value)};return true;}
    catch(error) {if(!closed && mine === generation && ticket === sequence && !expires(error)) state={tag:"incompatible",edit:undefined,newBase:undefined,message:"Leitura indisponível. Tente novamente."};return false;}
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
    occupied=true;const mine=generation,ticket=++sequence;active=new AbortController();
    try {
      const value=await client.read(readId,active.signal);
      if(closed || mine !== generation || ticket !== sequence) return false;
      const fresh=snapshot(value), floor=prior.tag === "success" ? prior.version : prior.edit?.base.version;
      if(fresh.version < minimum || (floor !== undefined && fresh.version < floor)) throw new Error("Request refused.");
      state={...prior,newBase:fresh,message:prior.tag === "success" ? "Salva; visualização atualizada." : prior.message};return true;
    } catch(error) {if(!closed && mine === generation && ticket === sequence) expires(error);return false;}
    finally {if(mine === generation && ticket === sequence) {occupied=false;active=undefined;}}
  }
  /** Confirmed content and its base travel as one frozen command. */
  async function confirm() {
    if(closed || occupied || (state.tag !== "draft" && state.tag !== "busy")) return false;
    const edit=state.edit;if(!edit) return false;
    client.prepare(edit.command);
    occupied=true;sequence++;active?.abort();active=new AbortController();const mine=generation,ticket=sequence;
    state={tag:"pending",edit};
    try {
      const result=await client.mutate(edit.command,active.signal);
      if(closed || mine !== generation || ticket !== sequence) return false;
      if(result.version !== undefined) safeVersion(result.version);
      minimum=result.version ?? edit.base.version;
      if(result.kind === "authentication") {close();return false;}
      if(result.kind === "success") {
        if(result.version !== edit.base.version+1) throw new Error("Request refused.");
        state={tag:"success",edit,version:result.version,newBase:undefined,message:result.message};
      } else state={tag:result.kind,edit,newBase:undefined,message:result.message};
    } catch(error) {
      if(closed || mine !== generation || ticket !== sequence || expires(error)) return false;
      state={tag:"unknown",edit,newBase:undefined,message:"Resultado desconhecido. Releia o estado antes de decidir."};
    } finally {if(mine === generation && ticket === sequence) {occupied=false;active=undefined;}}
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
  return Object.freeze({load,begin,poll,confirm,cancel,reconcile,review,finish,change,discard,close,
    getState:()=>Object.freeze(state),getObservation:()=>observed});
}
