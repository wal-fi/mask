import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import ts from "typescript";
/** @param {unknown} value @returns {value is string[]} */
function strings(value) { return Array.isArray(value) && value.every(v=>typeof v === "string"); }
/** @param {string} text @param {string[]} words */
function scan(text,words) {
  if (words.some(word=>text.includes(word))) throw new Error("Private vocabulary in public resource.");
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
/** @param {string} text @param {string[]} words @param {boolean} javascript */
export function inspectPublic(text,words,javascript=false) {
  scan(text,words);
  scan(text.replace(/&#(?:x([a-f0-9]+)|(\d+));/gi,(_whole,hex,decimal)=>String.fromCodePoint(Number.parseInt(hex ?? decimal,hex ? 16 : 10)))
    .replace(/\\([a-f0-9]{1,6})\s?/gi,(_whole,digits)=>String.fromCodePoint(Number.parseInt(digits,16))),words);
  if (!javascript) return;
  const tree=ts.createSourceFile("ui.js",text,ts.ScriptTarget.ES2022,true,ts.ScriptKind.JS);
  /** @param {ts.Node} node */
  function visit(node) {
    if (ts.isStringLiteralLike(node) || ts.isIdentifier(node)) scan(node.text,words);
    if (ts.isStringLiteralLike(node) || ts.isBinaryExpression(node) || ts.isParenthesizedExpression(node)) {
      const value=folded(node);
      if (value !== undefined) scan(value,words);
    }
    if (ts.isIdentifier(node) && ["eval","atob","btoa","fromCharCode","fromCodePoint","Function","innerHTML","localStorage","sessionStorage","indexedDB","outerHTML","insertAdjacentHTML","write","serviceWorker","BroadcastChannel"].includes(node.text)) throw new Error("Executable reconstruction or runtime feature in bootstrap.");
    ts.forEachChild(node,visit);
  }
  visit(tree);
}
export function inspectArtifacts() {
  /** @type {unknown} */ const words=JSON.parse(readFileSync(new URL("../private/vocabulary.json",import.meta.url),"utf8"));
  if (!strings(words)) throw new Error("Invalid vocabulary.");
  for (const name of ["index.html","ui.js","ui.css"]) {
    const text=readFileSync(new URL("../../src/maskgw/admin/ui/assets/"+name,import.meta.url),"utf8");
    inspectPublic(text,words,name === "ui.js");
  }
}
if (process.argv[1] === fileURLToPath(import.meta.url)) { inspectArtifacts(); console.log("Public artifacts: clean."); }
