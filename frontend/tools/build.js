import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { inspectArtifacts } from "./inspect.js";
const root=fileURLToPath(new URL("../../",import.meta.url));
const python=fileURLToPath(new URL(process.platform === "win32" ? "../../.venv/Scripts/python.exe" : "../../.venv/bin/python",import.meta.url));
/** @param {string[]} args */
function py(args) { execFileSync(python,args,{cwd:root,env:{...process.env,PYTHONPATH:"src"},stdio:"inherit"}); }
/** @param {string | Buffer} value */
function hash(value) { return createHash("sha256").update(value).digest("hex"); }
/** @param {string} file @param {string} value */
function write(file,value) { writeFileSync(new URL("../../src/maskgw/admin/ui/"+file,import.meta.url),value); }
if (process.version !== "v24.20.0") throw new Error("Node version mismatch.");
py(["frontend/tools/generate.py"]);
execFileSync(process.execPath,["node_modules/typescript/bin/tsc","-p","tsconfig.source.json"],{stdio:"inherit"});
py(["frontend/tools/presentation.py"]);
const presentation=readFileSync(new URL("../private/presentation.json",import.meta.url));
const schema=readFileSync(new URL("../private/protocol-schema.json",import.meta.url),"utf8").trim();
const core=readFileSync(new URL("../src/protocol.js",import.meta.url),"utf8");
const js=core+"\n/** @type {unknown} */\nconst layout="+schema+";\nexport const digest="+JSON.stringify(hash(presentation))+";\n/** @param {unknown} value */\nexport function check(value) { return inspect(value,layout); }\n";
const html='<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Administração local</title><link rel="stylesheet" href="/admin/ui/assets/ui.css"><script type="module" src="/admin/ui/assets/ui.js"></script></head><body><main><h1>Administração local</h1></main></body></html>\n';
const css=':root{font-family:system-ui,sans-serif;color:#18212b;background:#fff}body{margin:0}main{max-width:60rem;margin:auto;padding:1rem}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #164dc5;outline-offset:3px}\n';
const resources=[
  {id:"h",path:"index.html",mime:"text/html; charset=utf-8",data:Buffer.from(html),limit:16384},
  {id:"j",path:"ui.js",mime:"text/javascript; charset=utf-8",data:Buffer.from(js),limit:524288},
  {id:"s",path:"ui.css",mime:"text/css; charset=utf-8",data:Buffer.from(css),limit:65536},
  {id:"p",path:"presentation.json",mime:"application/json",data:presentation,limit:262144},
];
for (const item of resources) {
  if (item.data.length > item.limit) throw new Error("Resource size exceeded.");
  write("assets/"+item.path,item.data.toString("utf8"));
}
inspectArtifacts();
execFileSync(process.execPath,["node_modules/typescript/bin/tsc","-p","tsconfig.json"],{stdio:"inherit"});
execFileSync(process.execPath,["node_modules/typescript/bin/tsc","--allowJs","--checkJs","--strict","--noEmit","--noUncheckedIndexedAccess","--exactOptionalPropertyTypes","--skipLibCheck","false","--target","ES2022","--module","NodeNext","../src/maskgw/admin/ui/assets/ui.js"],{stdio:"inherit"});
const manifest=JSON.stringify({format:1,entries:resources.map(({id,path,mime,data})=>({id,path,mime,size:data.length,sha256:hash(data)}))})+"\n";
if (Buffer.byteLength(manifest)>16384) throw new Error("Manifest size exceeded.");
write("assets/manifest.json",manifest);
write("_anchor.py",'"""Generated integrity anchor; no installation data."""\n\nMANIFEST_SHA256 = "'+hash(manifest)+'"\n');
py(["frontend/tools/catalog.py"]);
py(["-m","ruff","format","src/maskgw/admin/ui/_catalog.py","src/maskgw/admin/ui/_anchor.py"]);
py(["-c","from maskgw.admin.ui.resources import load_resources; print('Verified resources:', len(load_resources()))"]);
console.log("Build deterministic resources:",resources.map(v=>v.path+"="+v.data.length).join(", "));
