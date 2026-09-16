import { createInterface } from "node:readline";
/** Lines, not stream chunks, delimit the private harness protocol.
 * @param {import("node:stream").Readable} input */
export function replies(input) {
  let ended=false, terminated=true;
  /** @param {unknown} value */
  const data=value=>{if(Buffer.isBuffer(value) && value.length) terminated=value.at(-1)===10;else if(typeof value === "string" && value.length) terminated=value.endsWith("\n");};
  const end=()=>{ended=true;};input.on("data",data);input.on("end",end);
  const lines=createInterface({input,crlfDelay:Infinity}), iterator=lines[Symbol.asyncIterator]();
  return {
    async read() {const item=await iterator.next();if(item.done || item.value.length>128 || (ended && !terminated)) throw new Error("Harness reply refused.");return item.value;},
    close() {lines.close();input.off("data",data);input.off("end",end);},
  };
}
