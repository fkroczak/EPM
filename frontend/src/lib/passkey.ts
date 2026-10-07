/**
 * Passkeys (WebAuthn) im Browser – Festlegung 08.10.2026: zweiter Faktor statt oder neben dem Code der
 * Authenticator-App. Ohne Fremdbibliothek: Der Server liefert die Optionen als JSON (Bytes als Base64URL), hier
 * werden sie in ArrayBuffer umgesetzt und die Antwort des Browsers zurück in JSON (Format wie ``toJSON()`` der
 * WebAuthn-Spezifikation, das py_webauthn erwartet).
 *
 * Passkeys gehen nur über den eingerichteten Namen mit gültigem Zertifikat (eigene CA), nicht über eine IP-Adresse.
 */
import { api } from "./api";

export type PasskeyStand = { verfuegbar: boolean; rp_id: string; grund: string };
/** Antwort des Browsers als JSON (wird unverändert an den Server geschickt) */
export type PasskeyAntwort = Record<string, unknown>;
export type PasskeyZweck = "anmelden" | "bestaetigen" | "registrieren";

function zuBytes(b64url: string) {
  const b64 = b64url.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(b64url.length / 4) * 4, "=");
  const roh = atob(b64);
  const bytes = new Uint8Array(roh.length);
  for (let i = 0; i < roh.length; i++) bytes[i] = roh.charCodeAt(i);
  return bytes;
}

function zuText(puffer: ArrayBuffer | null | undefined): string | null {
  if (!puffer) return null;
  const bytes = new Uint8Array(puffer);
  let roh = "";
  for (let i = 0; i < bytes.length; i++) roh += String.fromCharCode(bytes[i]);
  return btoa(roh).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Kann dieser Browser Passkeys? (sicherer Kontext, WebAuthn vorhanden) */
export function browserKann(): boolean {
  return typeof window !== "undefined" && window.isSecureContext && typeof window.PublicKeyCredential === "function"
    && !!navigator.credentials;
}

function istIp(name: string) {
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(name) || name.includes(":");
}

/** Warum gerade kein Passkey geht – oder "" wenn er geht. ``stand`` kommt vom Server (/api/auth/status/). */
export function passkeyHindernis(stand: PasskeyStand | undefined): string {
  if (!stand) return "Passkeys sind auf diesem Server nicht eingerichtet.";
  if (!stand.verfuegbar) return stand.grund;
  const hier = window.location.hostname;
  if (hier !== stand.rp_id && !hier.endsWith(`.${stand.rp_id}`)) {
    return istIp(hier)
      ? `Passkeys gehen nur über den Namen, nicht über die IP-Adresse. Bitte EPM über https://${stand.rp_id}/ aufrufen.`
      : `Passkeys gehen nur über https://${stand.rp_id}/.`;
  }
  if (!browserKann()) return "Dieser Browser unterstützt keine Passkeys (oder die Verbindung gilt nicht als sicher).";
  return "";
}

type Optionen = Record<string, unknown> & { challenge: string };
type Beschreibung = { id: string; type: string; transports?: string[] };

/** Optionen vom Server holen (legt die einmalige Aufgabe in der Sitzung ab, 5 Minuten gültig). */
export function passkeyOptionen(zweck: PasskeyZweck): Promise<Optionen> {
  return api<Optionen>("auth/passkey/optionen/", { body: { zweck }, ohneAbmeldeSignal: zweck !== "bestaetigen" });
}

function fehlerText(e: unknown): Error {
  const name = e instanceof DOMException ? e.name : "";
  if (name === "NotAllowedError" || name === "AbortError") return new Error("Abgebrochen oder Zeit abgelaufen. Bitte erneut versuchen.");
  if (name === "InvalidStateError") return new Error("Dieses Gerät ist bereits als Passkey eingerichtet.");
  if (name === "SecurityError") return new Error("Der Browser lehnt Passkeys für diese Adresse ab (Name und Zertifikat prüfen).");
  return e instanceof Error ? e : new Error(String(e));
}

function anbindung(cred: PublicKeyCredential): string | undefined {
  return (cred as PublicKeyCredential & { authenticatorAttachment?: string | null }).authenticatorAttachment ?? undefined;
}

/** Passkey benutzen (Anmeldung oder Bestätigung): ``navigator.credentials.get`` mit den Optionen des Servers. */
export async function passkeyBenutzen(opt: Optionen): Promise<PasskeyAntwort> {
  const erlaubt = (opt.allowCredentials as Beschreibung[] | undefined) ?? [];
  const publicKey: PublicKeyCredentialRequestOptions = {
    challenge: zuBytes(opt.challenge),
    rpId: opt.rpId as string | undefined,
    timeout: opt.timeout as number | undefined,
    userVerification: (opt.userVerification as UserVerificationRequirement | undefined) ?? "required",
    allowCredentials: erlaubt.map((c) => ({ type: "public-key", id: zuBytes(c.id),
      transports: c.transports as AuthenticatorTransport[] | undefined })),
  };
  let cred: PublicKeyCredential | null;
  try {
    cred = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential | null;
  } catch (e) {
    throw fehlerText(e);
  }
  if (!cred) throw new Error("Kein Passkey gewählt.");
  const r = cred.response as AuthenticatorAssertionResponse;
  return {
    id: cred.id, rawId: zuText(cred.rawId), type: cred.type, clientExtensionResults: cred.getClientExtensionResults(),
    authenticatorAttachment: anbindung(cred),
    response: { clientDataJSON: zuText(r.clientDataJSON), authenticatorData: zuText(r.authenticatorData),
      signature: zuText(r.signature), userHandle: zuText(r.userHandle) },
  };
}

/** Neuen Passkey anlegen: ``navigator.credentials.create`` mit den Optionen des Servers. */
export async function passkeyErstellen(opt: Optionen): Promise<PasskeyAntwort> {
  const user = opt.user as { id: string; name: string; displayName: string };
  const rp = opt.rp as { id?: string; name: string };
  const publicKey: PublicKeyCredentialCreationOptions = {
    challenge: zuBytes(opt.challenge),
    rp,
    user: { id: zuBytes(user.id), name: user.name, displayName: user.displayName },
    pubKeyCredParams: opt.pubKeyCredParams as PublicKeyCredentialParameters[],
    timeout: opt.timeout as number | undefined,
    attestation: (opt.attestation as AttestationConveyancePreference | undefined) ?? "none",
    authenticatorSelection: opt.authenticatorSelection as AuthenticatorSelectionCriteria | undefined,
    excludeCredentials: ((opt.excludeCredentials as Beschreibung[] | undefined) ?? []).map((c) => ({
      type: "public-key", id: zuBytes(c.id), transports: c.transports as AuthenticatorTransport[] | undefined })),
  };
  let cred: PublicKeyCredential | null;
  try {
    cred = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential | null;
  } catch (e) {
    throw fehlerText(e);
  }
  if (!cred) throw new Error("Kein Passkey angelegt.");
  const r = cred.response as AuthenticatorAttestationResponse;
  return {
    id: cred.id, rawId: zuText(cred.rawId), type: cred.type, clientExtensionResults: cred.getClientExtensionResults(),
    authenticatorAttachment: anbindung(cred),
    response: { clientDataJSON: zuText(r.clientDataJSON), attestationObject: zuText(r.attestationObject),
      transports: typeof r.getTransports === "function" ? r.getTransports() : [] },
  };
}

/** Vorschlag für den Namen eines neuen Passkeys nach Gerät/Browser („iPhone“, „Windows-PC“ …) */
export function geraetename(): string {
  const ua = navigator.userAgent;
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Android/.test(ua)) return "Android-Telefon";
  if (/Windows/.test(ua)) return "Windows-PC";
  if (/Macintosh/.test(ua)) return "Mac";
  return "Passkey";
}

/**
 * Optionen vorab holen, damit der Tipp auf „Mit Passkey …“ ``navigator.credentials`` sofort aufruft – Safari verlangt
 * das direkt in der Nutzeraktion. Ältere als 4 Minuten werden beim Tippen neu geholt.
 */
export class PasskeyVorrat {
  private optionen: Optionen | null = null;
  private geholt = 0;
  constructor(private zweck: PasskeyZweck) {}

  vorbereiten() {
    passkeyOptionen(this.zweck).then((o) => { this.optionen = o; this.geholt = Date.now(); }).catch(() => undefined);
  }

  async holen(): Promise<Optionen> {
    const frisch = this.optionen && Date.now() - this.geholt < 4 * 60_000;
    const o = frisch ? this.optionen! : await passkeyOptionen(this.zweck);
    this.optionen = null;   // jede Aufgabe des Servers gilt einmal
    return o;
  }
}
