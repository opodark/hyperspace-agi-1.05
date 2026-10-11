// SPDX-License-Identifier: Apache-2.0
// web-node/src/contact.js
// Validazione e invio messaggi dal form di contatto della landing page
// verso l'endpoint /web/contact del federation-gateway o del control-plane.

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export class ContactError extends Error {
  constructor(message, { status = 0, field = "" } = {}) {
    super(message);
    this.name = "ContactError";
    this.status = status;
    this.field = field;
  }
}

/**
 * Valida i campi del form di contatto prima dell'invio.
 * Restituisce { valid: boolean, errors: Record<string, string> }.
 */
export function validateContactForm({
  name = "",
  email = "",
  message = "",
  subject = "",
  honeypot = "",
} = {}) {
  const errors = {};
  const trimmedName = String(name || "").trim();
  const trimmedEmail = String(email || "").trim();
  const trimmedMessage = String(message || "").trim();
  const trimmedSubject = String(subject || "").trim();
  const trimmedHoneypot = String(honeypot || "").trim();

  if (trimmedHoneypot) {
    errors.honeypot = "Attività automatica rilevata";
  }

  if (!trimmedName) {
    errors.name = "Il nome è obbligatorio";
  } else if (trimmedName.length > 100) {
    errors.name = "Il nome non può superare i 100 caratteri";
  }

  if (!trimmedEmail) {
    errors.email = "L'indirizzo email è obbligatorio";
  } else if (trimmedEmail.length > 255 || !EMAIL_RE.test(trimmedEmail)) {
    errors.email = "Inserisci un indirizzo email valido (es. nome@dominio.it)";
  }

  if (!trimmedMessage) {
    errors.message = "Il messaggio è obbligatorio";
  } else if (trimmedMessage.length < 5) {
    errors.message = "Il messaggio deve contenere almeno 5 caratteri";
  } else if (trimmedMessage.length > 4000) {
    errors.message = "Il messaggio non può superare i 4000 caratteri";
  }

  if (trimmedSubject.length > 200) {
    errors.subject = "L'oggetto non può superare i 200 caratteri";
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Invia un messaggio al backend /web/contact con supporto al fallback multi-endpoint.
 */
export async function sendContactMessage({
  baseUrl,
  baseUrls,
  name,
  email,
  message,
  subject = "",
  honeypot = "",
  fetchImpl = globalThis.fetch,
  timeoutMs = 15000,
} = {}) {
  if (typeof fetchImpl !== "function") {
    throw new ContactError("fetch non disponibile");
  }

  const validation = validateContactForm({ name, email, message, subject, honeypot });
  if (!validation.valid) {
    const firstField = Object.keys(validation.errors)[0];
    throw new ContactError(validation.errors[firstField], { field: firstField });
  }

  const list = Array.isArray(baseUrls) && baseUrls.length ? baseUrls : (baseUrl ? [baseUrl] : []);
  const endpoints = list.map((u) => String(u || "").trim().replace(/\/+$/, "")).filter(Boolean);
  if (!endpoints.length) {
    throw new ContactError("Nessun endpoint di rete specificato per l'invio");
  }

  const payload = {
    name: String(name || "").trim(),
    email: String(email || "").trim(),
    message: String(message || "").trim(),
    subject: String(subject || "").trim(),
    honeypot: String(honeypot || "").trim(),
  };

  const fetchFn = fetchImpl.bind(globalThis);
  let lastError = null;

  for (const base of endpoints) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), Math.max(1000, Number(timeoutMs) || 15000));
    try {
      const response = await fetchFn(`${base}/web/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const errorMsg = (body && body.error) || `Errore HTTP ${response.status}`;
        throw new ContactError(errorMsg, { status: response.status });
      }

      return body || { ok: true, message: "Messaggio inviato con successo" };
    } catch (error) {
      lastError = error;
      if (error instanceof ContactError && error.status > 0) {
        // Il server ha risposto (es. 400 Bad Request): non fare fallback su un altro endpoint
        throw error;
      }
    } finally {
      clearTimeout(timer);
    }
  }

  throw new ContactError(
    `Impossibile inviare il messaggio: rete non raggiungibile (${lastError?.message || lastError})`
  );
}
