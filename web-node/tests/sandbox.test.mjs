// SPDX-License-Identifier: Apache-2.0
import test from "node:test";
import assert from "node:assert/strict";
import { runSandboxCode, SandboxError } from "../src/sandbox.js";

test("runSandboxCode valida codice vuoto", async () => {
  await assert.rejects(
    async () => runSandboxCode({ baseUrl: "http://mock-gw:8095", code: "  " }),
    SandboxError
  );
});

test("runSandboxCode invia richiesta e mappa risposta corretta", async () => {
  const fakeFetch = async (url, options) => {
    assert.equal(url, "http://mock-gw:8095/web/sandbox/run");
    assert.equal(options.method, "POST");
    assert.equal(options.headers["Authorization"], "Bearer test-key");
    const body = JSON.parse(options.body);
    assert.equal(body.code, "print('Hello Sandbox')");
    assert.equal(body.timeout, 20);

    return {
      ok: true,
      status: 200,
      json: async () => ({
        ok: true,
        stdout: "Hello Sandbox\n",
        stderr: "",
        exit_code: 0,
        duration_ms: 45,
        backend: "docker",
      }),
    };
  };

  const res = await runSandboxCode({
    baseUrl: "http://mock-gw:8095",
    token: "test-key",
    code: "print('Hello Sandbox')",
    timeout: 20,
    fetchImpl: fakeFetch,
  });

  assert.equal(res.ok, true);
  assert.equal(res.stdout, "Hello Sandbox\n");
  assert.equal(res.exitCode, 0);
  assert.equal(res.durationMs, 45);
  assert.equal(res.backend, "docker");
});

test("runSandboxCode gestisce fallimento esecuzione ed exit code diverso da 0", async () => {
  const fakeFetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      ok: false,
      stdout: "",
      stderr: "ZeroDivisionError: division by zero",
      exit_code: 1,
      duration_ms: 32,
      backend: "docker",
    }),
  });

  const res = await runSandboxCode({
    baseUrl: "http://mock-gw:8095",
    code: "1/0",
    fetchImpl: fakeFetch,
  });

  assert.equal(res.ok, false);
  assert.equal(res.exitCode, 1);
  assert.match(res.stderr, /ZeroDivisionError/);
});

test("runSandboxCode esegue fallback su lista endpoint", async () => {
  let attempts = 0;
  const fakeFetch = async (url) => {
    attempts++;
    if (url.startsWith("http://failing:8095")) {
      throw new Error("Connessione rifiutata");
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({
        ok: true,
        stdout: "42\n",
        exit_code: 0,
      }),
    };
  };

  const res = await runSandboxCode({
    baseUrls: ["http://failing:8095", "http://working:8095"],
    code: "print(42)",
    fetchImpl: fakeFetch,
  });

  assert.equal(attempts, 2);
  assert.equal(res.stdout, "42\n");
});
