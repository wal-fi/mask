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
const reader=readFileSync(new URL("../src/reader.js",import.meta.url),"utf8");
const commands=readFileSync(new URL("../src/commands.js",import.meta.url),"utf8").split("\n").filter(line=>!line.startsWith("import ")).join("\n");
const author=readFileSync(new URL("../src/author.js",import.meta.url),"utf8").split("\n").filter(line=>!line.startsWith("import ")).join("\n");
const coordinator=readFileSync(new URL("../src/coordinator.js",import.meta.url),"utf8").split("\n").filter(line=>!line.startsWith("import ")).join("\n");
const workbench=readFileSync(new URL("../src/workbench.js",import.meta.url),"utf8").split("\n").filter(line=>!line.startsWith("import ")).join("\n");
const screen=readFileSync(new URL("../src/screen.js",import.meta.url),"utf8").split("\n").filter(line=>!line.startsWith("import ")).join("\n");
const transport=readFileSync(new URL("../src/transport.js",import.meta.url),"utf8").split("\n").filter(line=>!line.startsWith("import ")).join("\n");
const js=(core+"\n/** @type {unknown} */\nconst layout="+schema+";\nexport const digest="+JSON.stringify(hash(presentation))+";\n/** @param {unknown} value */\nexport function check(value) { return inspect(value,layout); }\n"+reader+"\n"+commands+"\n"+author+"\n"+transport+"\n"+coordinator+"\n"+workbench+"\n"+screen).replaceAll('import("./commands.js").',"").replaceAll('import("./transport.js").',"");
const html='<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Administração local</title><link rel="stylesheet" href="/admin/ui/assets/ui.css"><script type="module" src="/admin/ui/assets/ui.js"></script></head><body><main><h1>Administração local</h1></main></body></html>\n';
const baseCss=':root{font-family:system-ui,sans-serif;color:#18212b;background:#fff;line-height:1.5}*{box-sizing:border-box}body{margin:0}main{max-width:64rem;margin:auto;padding:1rem}header,nav{display:flex;flex-wrap:wrap;gap:.75rem;align-items:center}header{justify-content:space-between}nav{margin-block:1rem}button,input{font:inherit;padding:.6rem;min-height:2.75rem;max-width:100%}button{cursor:pointer;border:1px solid #164dc5;background:#fff;color:#123a80;border-radius:.25rem}button[aria-current]{background:#164dc5;color:#fff}button:disabled{cursor:wait;color:#414a55;border-color:#737c87}label{display:block}form{max-width:28rem;display:grid;gap:.75rem}a:focus-visible,button:focus-visible,input:focus-visible,h2:focus{outline:3px solid #164dc5;outline-offset:3px}section{min-width:0}dt{font-weight:600;margin-top:.5rem}dd{margin-left:1rem}ol{padding-left:1.5rem}span,dd,dt,h1,h2,h3,p,button{overflow-wrap:anywhere;white-space:pre-wrap}[role="status"]{border-left:4px solid #164dc5;padding-left:.75rem}h2{scroll-margin-top:1rem}@media(max-width:24rem){main{padding:.75rem}nav button{width:100%}dd{margin-left:.5rem}}@media(prefers-reduced-motion:reduce){*{animation:none;transition:none;scroll-behavior:auto}}\n';
const css=baseCss+'dialog{width:min(42rem,calc(100% - 1.5rem));max-height:calc(100% - 1.5rem);overflow:auto;border:2px solid #164dc5;border-radius:.4rem;padding:1rem;color:#18212b;background:#fff}dialog::backdrop{background:#0008}dialog form{max-width:none}dialog button{margin:.25rem}select{font:inherit;padding:.6rem;min-height:2.75rem;max-width:100%}textarea{font:inherit;max-width:100%;min-height:6rem}textarea:focus-visible,select:focus-visible{outline:3px solid #164dc5;outline-offset:3px}\n';
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
execFileSync(process.execPath,["--check","../src/maskgw/admin/ui/assets/ui.js"],{stdio:"inherit"});
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
