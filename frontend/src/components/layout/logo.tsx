/** Logo aus „Vorlagen › Briefkopf und Logo“ – je Firma (11.10.2026). Ohne Upload das mitgelieferte Logo der Firma:
 *  Stiftungslogo der DSKM bzw. Logo der Regeneration Clinic (in „Dunkel“ hell gezeichnet). */
import { useState } from "react";
import type { CSSProperties } from "react";
import stiftungLogo from "@/logo-stiftung.png";
import rgcLogo from "@/logo-rgc.png";
import rgcLogoHell from "@/logo-rgc-hell.png";

export const LOGO_URL = "/api/briefkopf/logo/";

const MITGELIEFERT: Record<string, { hell: string; dunkel?: string; name: string }> = {
  dskm: { hell: stiftungLogo, name: "Deutsche Stiftung Krankheitsbedingte Mangelernährung" },
  rg: { hell: rgcLogo, dunkel: rgcLogoHell, name: "Regeneration Clinic" },
};

export function Logo({ className, style, version, firma, name }: {
  className?: string; style?: CSSProperties; version?: string;
  /** Kürzel der Firma; ohne Angabe das Logo der aktiven Firma bzw. der DSKM */
  firma?: string; name?: string;
}) {
  const [fehlt, setFehlt] = useState<string | null>(null);
  const eigen = MITGELIEFERT[firma ?? "dskm"] ?? MITGELIEFERT.dskm;
  const stil = { objectFit: "contain" as const, objectPosition: "left center", ...style };
  const alt = name ?? eigen.name;
  if (fehlt === (firma ?? "")) {
    // mitgeliefertes Logo; das der RGC gibt es hell (Schema „Dunkel“) und dunkel
    return eigen.dunkel ? <>
      <img src={eigen.hell} alt={alt} className={`${className ?? ""} logo-hell`} style={stil} />
      <img src={eigen.dunkel} alt="" aria-hidden="true" className={`${className ?? ""} logo-dunkel`} style={stil} />
    </> : <img src={eigen.hell} alt={alt} className={className} style={stil} />;
  }
  // leer=1: ohne Upload antwortet der Server mit 204 (onError, kein 404 in der Konsole)
  const teile = [firma ? `firma=${encodeURIComponent(firma)}` : "", version ? `v=${version.slice(0, 12)}` : "", "leer=1"].filter(Boolean);
  return (
    <img
      key={firma ?? ""}
      src={`${LOGO_URL}${teile.length ? `?${teile.join("&")}` : ""}`}
      onError={() => setFehlt(firma ?? "")}
      alt={alt}
      className={className}
      style={stil}
    />
  );
}
