// SPDX-License-Identifier: Apache-2.0
// web-node/tests/auth.test.mjs
// Test del modulo di autenticazione e gestione credenziali del web-node.
import assert from "node:assert/strict";

import { AuthError, AuthManager, clearStoredAuthKey, getStoredAuthKey, setStoredAuthKey, verifyAuthKey }
  from "../src/auth.js";

let passed = 0;
async function check(label, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`ok   ${label}`);
  } catch (error) {
    console.error(`FAIL ${label}: ${error.message}`);
    process.exitCode = 1;
  }
}

console.log("== storage credenziali ==");

await check("salvataggio e lettura della chiave nel mock storage", () => {
  const store = {};
  const mockStorage = {
    getItem: (k) => store[k] ?? null,
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
  };

  assert.equal(getStoredAuthKey(mockStorage), "");
  setStoredAuthKey("secret-test-key-123", mockStorage);
  assert.equal(getStoredAuthKey(mockStorage), "secret-test-key-123");
  clearStoredAuthKey(mockStorage);
  assert.equal(getStoredAuthKey(mockStorage), "");
});

console.log("== verifica chiave (endpoint /web/auth/verify) ==");

await check("verifyAuthKey accetta una chiave valida e restituisce il ruolo", async () => {
  const calls = [];
  const fakeFetch = async (url, options) => {
    calls.push({ url, headers: options.headers, body: JSON.parse(options.body) });
    return {
      ok: true,
      status: 200,
      json: async () => ({ ok: true, authenticated: true, role: "admin", label: "Admin Mesh" }),
    };
  };

  const res = await verifyAuthKey({
    key: "valid-admin-token",
    baseUrl: "http://mesh.example.com",
    fetchImpl: fakeFetch,
  });

  assert.equal(res.ok, true);
  assert.equal(res.authenticated, true);
  assert.equal(res.role, "admin");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].headers["Authorization"], "Bearer valid-admin-token");
});

await check("verifyAuthKey rifiuta una chiave errata con status 401", async () => {
  const fakeFetch = async () => ({
    ok: false,
    status: 401,
    json: async () => ({ ok: false, error: "Chiave non valida" }),
  });

  await assert.rejects(
    () => verifyAuthKey({ key: "wrong-key", baseUrl: "http://mesh.example.com", fetchImpl: fakeFetch }),
    (err) => err instanceof AuthError && err.status === 401
  );
});

await check("verifyAuthKey esegue il fallback se il primo endpoint è irraggiungibile", async () => {
  const urls = [];
  const fakeFetch = async (url) => {
    urls.push(url);
    if (url.includes("gw1")) throw new Error("Connection refused");
    return {
      ok: true,
      status: 200,
      json: async () => ({ ok: true, authenticated: true, role: "member", label: "Utente" }),
    };
  };

  const res = await verifyAuthKey({
    key: "member-token",
    baseUrls: ["http://gw1.example.com", "http://gw2.example.com"],
    fetchImpl: fakeFetch,
  });

  assert.equal(res.authenticated, true);
  assert.equal(res.role, "member");
  assert.equal(urls.length, 2);
  assert.match(urls[0], /gw1/);
  assert.match(urls[1], /gw2/);
});

console.log("== AuthManager (ciclo di vita e notifiche) ==");

await check("AuthManager gestisce login, stato e notifiche", async () => {
  const store = {};
  const mockStorage = {
    getItem: (k) => store[k] ?? null,
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
  };

  const stateChanges = [];
  const fakeFetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({ ok: true, authenticated: true, role: "member", label: "Membro Mesh" }),
  });

  const auth = new AuthManager({
    baseUrl: "http://mesh.example.com",
    storage: mockStorage,
    fetchImpl: fakeFetch,
    onStateChange: (s) => stateChanges.push(s),
  });

  assert.equal(auth.getState().authenticated, false);

  await auth.login("my-member-key");
  assert.equal(auth.getState().authenticated, true);
  assert.equal(auth.getState().role, "member");
  assert.equal(getStoredAuthKey(mockStorage), "my-member-key");

  auth.logout();
  assert.equal(auth.getState().authenticated, false);
  assert.equal(getStoredAuthKey(mockStorage), "");
  assert.ok(stateChanges.length >= 3);
});

await check("AuthManager.saveKey salva la chiave nello storage e aggiorna la proprietà key", () => {
  const store = {};
  const mockStorage = {
    getItem: (k) => store[k] ?? null,
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
  };
  let notified = 0;
  const auth = new AuthManager({ storage: mockStorage, onStateChange: () => { notified += 1; } });
  assert.equal(auth.getKey(), "");
  const returned = auth.saveKey("hs-mesh-pippo-12345");
  assert.equal(returned, "hs-mesh-pippo-12345");
  assert.equal(auth.getKey(), "hs-mesh-pippo-12345");
  assert.equal(getStoredAuthKey(mockStorage), "hs-mesh-pippo-12345");

  auth.notify();
  assert.equal(notified, 1);
});

console.log(`\nPASS auth: ${passed} check su credenziali e verifica`);
