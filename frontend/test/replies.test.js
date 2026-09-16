import test from "node:test";
import assert from "node:assert/strict";
import { PassThrough } from "node:stream";
import { replies } from "../browser/replies.js";

test("harness replies accept split and coalesced stdout without losing boundaries",async()=>{
  const input=new PassThrough(), channel=replies(input);
  const port=channel.read();input.write("12");input.write("34");input.write("5\r");input.write("\n");assert.equal(await port,"12345");
  const first=channel.read();input.write("o");input.write("k\n");assert.equal(await first,"ok");
  input.write("ok\nok\n");assert.equal(await channel.read(),"ok");assert.equal(await channel.read(),"ok");input.end();await assert.rejects(channel.read());channel.close();
});
test("harness reply EOF, explicit close and oversized lines fail closed",async()=>{
  for(const action of ["end","close","long","partial"]) {
    const input=new PassThrough(), channel=replies(input), pending=channel.read();
    if(action==="partial") input.end("ok");else if(action==="end") input.end();else if(action==="close") channel.close();else input.write("x".repeat(129)+"\n");
    await assert.rejects(pending);channel.close();input.destroy();
  }
});
