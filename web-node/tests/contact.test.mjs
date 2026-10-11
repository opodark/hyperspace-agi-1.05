// SPDX-License-Identifier: Apache-2.0
// web-node/tests/contact.test.mjs
// Test del modulo di contatto (validazione e trasporto).
import assert from "node:assert/strict";

import { ContactError, validateContactForm, sendContactMessage } from "../src/contact.js";

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

console.log("== validazione form contatto ==");

await check("un form valido viene accettato", () => {
  const res = validateContactForm({
    name: "Mario Rossi",
    email: "mario@example.com",
    message: "Vorrei maggiori informazioni sulla mesh HyperSpace.",
    subject: "Richiesta info",
  });
  assert.equal(res.valid, true);
  assert.equal(Object.keys(res.errors).length, 0);
});

await check("un nome vuoto o troppo lungo viene respinto", () => {
  const emptyRes = validateContactForm({ name: "   ", email: "a@b.com", message: "Messaggio valido" });
  assert.equal(emptyRes.valid, false);
  assert.match(emptyRes.errors.name, /obbligatorio/);

  const longName = "A".repeat(101);
  const longRes = validateContactForm({ name: longName, email: "a@b.com", message: "Messaggio valido" });
  assert.equal(longRes.valid, false);
  assert.match(longRes.errors.name, /100 caratteri/);
});

await check("una email non valida viene respinta", () => {
  for (const badEmail of ["", "mario", "mario@", "mario@domain", "@domain.com", "mario domain.com"]) {
    const res = validateContactForm({ name: "Mario", email: badEmail, message: "Messaggio valido" });
    assert.equal(res.valid, false, `dovrebbe fallire per: ${badEmail}`);
    assert.match(res.errors.email, /email/);
  }
});

await check("un messaggio troppo corto (< 5 char) o vuoto viene respinto", () => {
  const shortRes = validateContactForm({ name: "Mario", email: "a@b.com", message: "Ciao" });
  assert.equal(shortRes.valid, false);
  assert.match(shortRes.errors.message, /almeno 5 caratteri/);
});

await check("la presenza del campo honeypot attiva l'errore bot", () => {
  const botRes = validateContactForm({
    name: "Spam Bot",
    email: "bot@spam.com",
    message: "Buy cheap crypto",
    honeypot: "http://spam.org",
  });
  assert.equal(botRes.valid, false);
  assert.match(botRes.errors.honeypot, /automatica/);
});

console.log("== invio messaggio (trasporto) ==");

await check("sendContactMessage invia la richiesta con successo", async () => {
  const requests = [];
  const fakeFetch = async (url, options) => {
    requests.push({ url, body: JSON.parse(options.body) });
    return {
      ok: true,
      status: 201,
      json: async () => ({ ok: true, contact_id: "cnt-12345", message: "Inviato" }),
    };
  };

  const res = await sendContactMessage({
    baseUrl: "http://mesh.example.com",
    name: "Luigi",
    email: "luigi@example.com",
    message: "Messaggio di prova",
    fetchImpl: fakeFetch,
  });

  assert.equal(res.ok, true);
  assert.equal(res.contact_id, "cnt-12345");
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, "http://mesh.example.com/web/contact");
  assert.equal(requests[0].body.name, "Luigi");
  assert.equal(requests[0].body.email, "luigi@example.com");
});

await check("sendContactMessage fallisce subito su validazione locale prima del fetch", async () => {
  let called = false;
  const fakeFetch = async () => { called = true; };
  await assert.rejects(
    () => sendContactMessage({ baseUrl: "http://mesh.example.com", name: "", email: "a@b.com", message: "test", fetchImpl: fakeFetch }),
    ContactError
  );
  assert.equal(called, false);
});

await check("sendContactMessage fa fallback se il primo endpoint non risponde", async () => {
  const endpointsTried = [];
  const fakeFetch = async (url) => {
    endpointsTried.push(url);
    if (url.includes("primary")) {
      throw new Error("Network offline");
    }
    return {
      ok: true,
      status: 201,
      json: async () => ({ ok: true, contact_id: "cnt-fallback" }),
    };
  };

  const res = await sendContactMessage({
    baseUrls: ["http://primary.example.com", "http://secondary.example.com"],
    name: "Luigi",
    email: "luigi@example.com",
    message: "Messaggio con fallback",
    fetchImpl: fakeFetch,
  });

  assert.equal(res.ok, true);
  assert.equal(res.contact_id, "cnt-fallback");
  assert.equal(endpointsTried.length, 2);
  assert.match(endpointsTried[0], /primary/);
  assert.match(endpointsTried[1], /secondary/);
});

console.log(`\nPASS contact: ${passed} check su validazione e invio form`);
