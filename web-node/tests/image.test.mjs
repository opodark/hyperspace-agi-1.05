// SPDX-License-Identifier: Apache-2.0
// web-node/tests/image.test.mjs
import assert from "node:assert/strict";
import test from "node:test";
import { generateImage, ImageError } from "../src/image.js";

test("generateImage: valida prompt vuoto", async () => {
  await assert.rejects(
    () => generateImage({ prompt: "" }),
    (err) => err instanceof ImageError && err.message.includes("vuoto")
  );
});

test("generateImage: usa ComfyUI mesh quando il gateway risponde con successo", async () => {
  const fakeFetch = async (url, opts) => {
    if (url.includes("/web/image/generate")) {
      return {
        ok: true,
        json: async () => ({ ok: true, job_id: "job-comfy-123" }),
      };
    }
    if (url.includes("/web/image/status")) {
      return {
        ok: true,
        json: async () => ({ ok: true, status: "done", image_url: "/data/images/job-123.png" }),
      };
    }
    throw new Error("404");
  };

  const res = await generateImage({
    prompt: "Cyberpunk skyline",
    gatewayUrl: "https://mesh.test",
    fetchImpl: fakeFetch,
    comfyTimeoutMs: 5000,
  });

  assert.equal(res.ok, true);
  assert.equal(res.provider, "comfyui-mesh");
  assert.equal(res.imageUrl, "https://mesh.test/data/images/job-123.png");
});

test("generateImage: fa fallback trasparente su motore neurale Flux se ComfyUI e' offline", async () => {
  const failFetch = async () => {
    throw new Error("Network error / ComfyUI unreachable");
  };

  const res = await generateImage({
    prompt: "Gatto astronauta sul pianeta Marte",
    gatewayUrl: "https://mesh.test",
    fetchImpl: failFetch,
  });

  assert.equal(res.ok, true);
  assert.equal(res.provider, "flux-neural-engine");
  assert.ok(res.imageUrl.includes("pollinations.ai/prompt/"));
  assert.ok(res.imageUrl.includes("model=flux"));
});
