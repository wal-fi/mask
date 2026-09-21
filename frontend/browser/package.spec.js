import {test} from "@playwright/test";
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {scenario,requireTrue} from "./harness.js";
import {inspectPublic} from "../tools/inspect.js";

test("installed HTTP bytes equal approved full inventories and public vocabulary",async({},info)=>{
  const name=info.project.name;if(name!=="chromium" && name!=="firefox" && name!=="webkit") throw new Error("Engine refused.");
  await scenario(name,async(page,origin,token)=>{
    /** @type {unknown} */ const raw=JSON.parse(readFileSync(new URL("../private/vocabulary.json",import.meta.url),"utf8"));
    if(!Array.isArray(raw)||!raw.every(v=>typeof v==="string")) throw new Error("Vocabulary refused.");
    requireTrue(raw.length===193);
    const paths=["/admin/ui","/admin/ui/assets/ui.js","/admin/ui/assets/ui.css","/admin/ui/presentation.json"];
    const files=["index.html","ui.js","ui.css","presentation.json"];
    const types=["text/html; charset=utf-8","text/javascript; charset=utf-8","text/css; charset=utf-8","application/json"];
    for(let i=0;i<paths.length;i++) {
      const path=paths[i],file=files[i];if(!path||!file) throw new Error("Resource refused.");
      if(i===3) {const denied=await page.request.get(origin+path);requireTrue(denied.status()===401);}
      const response=await page.request.get(origin+path,{headers:i===3?{Authorization:"Bearer "+token}:{}});
      const bytes=await response.body(), approved=readFileSync(new URL("../../src/maskgw/admin/ui/assets/"+file,import.meta.url));
      requireTrue(response.status()===200 && bytes.equals(approved) && response.headers()["content-type"]===types[i]);
      requireTrue(response.headers()["cache-control"]==="no-store" && !bytes.includes(token));
      if(i<3) inspectPublic(bytes.toString("utf8"),raw,i===1);
      else requireTrue(createHash("sha256").update(bytes).digest("hex")==="0ee31f73edd994ac98694ecfac36197e7bac3690879e28c7e459ce11accc9a43");
    }
  });
});
