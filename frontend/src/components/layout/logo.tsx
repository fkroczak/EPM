/** Logo aus „Vorlagen › Briefkopf und Logo“ – je Firma (11.10.2026). Ohne Upload: bei der DSKM das mitgelieferte
 *  Stiftungslogo, bei weiteren Firmen der Name als Schriftzug. */
import { useState } from "react";
import type { CSSProperties } from "react";
import stiftungLogo from "@/logo-stiftung.png";

export const LOGO_URL = "/api/briefkopf/logo/";

export function Logo({ className, style, version, firma, name }: {
  className?: string; style?: CSSProperties; version?: string;
  /** Kürzel der Firma; ohne Angabe das Logo der aktiven Firma bzw. der DSKM */
  firma?: string; name?: string;
}) {
  const [fehlt, setFehlt] = useState<string | null>(null);
  const weitere = !!firma && firma !== "dskm";
  if (fehlt === (firma ?? "") && weitere) {
    return (
      <span className={className} style={{ display: "flex", alignItems: "center", ...style }} data-testid="logo-schriftzug">
        <span className="font-semibold text-[0.9375rem] leading-tight text-akzent-text">{name ?? firma}</span>
      </span>
    );
  }
  const teile = [firma ? `firma=${encodeURIComponent(firma)}` : "", version ? `v=${version.slice(0, 12)}` : ""].filter(Boolean);
  const quelle = fehlt === (firma ?? "") ? stiftungLogo : `${LOGO_URL}${teile.length ? `?${teile.join("&")}` : ""}`;
  return (
    <img
      key={firma ?? ""}
      src={quelle}
      onError={() => setFehlt(firma ?? "")}
      alt={name ?? "Deutsche Stiftung Krankheitsbedingte Mangelernährung"}
      className={className}
      style={{ objectFit: "contain", objectPosition: "left center", ...style }}
    />
  );
}
