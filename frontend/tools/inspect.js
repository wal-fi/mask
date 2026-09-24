import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import ts from "typescript";
/** @param {unknown} value @returns {value is string[]} */
function strings(value) { return Array.isArray(value) && value.every(v=>typeof v === "string"); }
/** @param {string} text @param {string[]} words */
function scan(text,words) {
  if (words.some(word=>text.includes(word))) throw new Error("Private vocabulary in public resource.");
}
/** @param {string} word */
function boundary(word) { return new RegExp("(?<![A-Za-z0-9_])"+word.replace(/[.*+?^${}()|[\]\\/-]/g,"\\$&")+"(?![A-Za-z0-9_])"); }
/** Second-prefix vocabulary is checked on token boundaries (Phase 9, Stage 5, D-099).
 * @param {string} text @param {string[]} tokens
 */
function scanTokens(text,tokens) {
  if (tokens.some(word=>boundary(word).test(text))) throw new Error("Private vocabulary in public resource.");
}
/** @param {string} text */
function decoded(text) {
  return text.replace(/&#(?:x([a-f0-9]+)|(\d+));/gi,(_whole,hex,decimal)=>String.fromCodePoint(Number.parseInt(hex ?? decimal,hex ? 16 : 10)))
    .replace(/\\([a-f0-9]{1,6})\s?/gi,(_whole,digits)=>String.fromCodePoint(Number.parseInt(digits,16)));
}
/** @param {ts.Expression} node @returns {string | undefined} */
function folded(node) {
  if (ts.isStringLiteralLike(node)) return node.text;
  if (ts.isParenthesizedExpression(node)) return folded(node.expression);
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    const left=folded(node.left),right=folded(node.right);
    return left !== undefined && right !== undefined ? left+right : undefined;
  }
  return undefined;
}
/** @param {string} text @param {string[]} words @param {boolean} javascript @param {string[]} tokens */
export function inspectPublic(text,words,javascript=false,tokens=[]) {
  scan(text,words);
  scan(decoded(text),words);
  scanTokens(text,tokens);
  scanTokens(decoded(text),tokens);
  if (!javascript) return;
  const tree=ts.createSourceFile("ui.js",text,ts.ScriptTarget.ES2022,true,ts.ScriptKind.JS);
  /** @param {ts.Node} node */
  function visit(node) {
    if (ts.isStringLiteralLike(node) || ts.isIdentifier(node)) { scan(node.text,words); scanTokens(node.text,tokens); }
    if (ts.isStringLiteralLike(node) || ts.isBinaryExpression(node) || ts.isParenthesizedExpression(node)) {
      const value=folded(node);
      if (value !== undefined) { scan(value,words); scanTokens(value,tokens); }
    }
    if (ts.isIdentifier(node) && ["eval","atob","btoa","fromCharCode","fromCodePoint","Function","innerHTML","localStorage","sessionStorage","indexedDB","outerHTML","insertAdjacentHTML","write","serviceWorker","BroadcastChannel","postMessage","caches"].includes(node.text)) throw new Error("Executable reconstruction or runtime feature in bootstrap.");
    ts.forEachChild(node,visit);
  }
  visit(tree);
}
/** @param {string} name */
function vocabulary(name) {
  /** @type {unknown} */ const words=JSON.parse(readFileSync(new URL("../private/"+name,import.meta.url),"utf8"));
  if (!strings(words)) throw new Error("Invalid vocabulary.");
  return words;
}
export function inspectArtifacts() {
  const words=vocabulary("vocabulary.json"), tokens=vocabulary("vocabulary-tokens.json");
  for (const name of ["index.html","ui.js","ui.css"]) {
    const text=readFileSync(new URL("../../src/maskgw/admin/ui/assets/"+name,import.meta.url),"utf8");
    inspectPublic(text,words,name === "ui.js",tokens);
  }
}
/** Names the offending entries; only for local diagnosis, never in the build output. */
export function diagnose() {
  const words=vocabulary("vocabulary.json"), tokens=vocabulary("vocabulary-tokens.json");
  /** @type {string[]} */ const found=[];
  for (const name of ["index.html","ui.js","ui.css"]) {
    const text=readFileSync(new URL("../../src/maskgw/admin/ui/assets/"+name,import.meta.url),"utf8");
    for (const word of words) if (text.includes(word) || decoded(text).includes(word)) found.push(name+": "+word);
    for (const word of tokens) if (boundary(word).test(text) || boundary(word).test(decoded(text))) found.push(name+": token "+word);
  }
  return found;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (process.argv[2] === "--diagnose") { console.log(diagnose().join("\n") || "clean"); }
  else { inspectArtifacts(); console.log("Public artifacts: clean."); }
}
