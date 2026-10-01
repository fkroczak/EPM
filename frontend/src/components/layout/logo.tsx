/** Logo aus „Vorlagen › Briefkopf und Logo“; ohne Upload das mitgelieferte Stiftungslogo. */
import { useState } from "react";
import type { CSSProperties } from "react";
import stiftungLogo from "@/logo-stiftung.png";

export const LOGO_URL = "/api/briefkopf/logo/";

export function Logo({ className, style, version }: { className?: string; style?: CSSProperties; version?: string }) {
  const [fehlt, setFehlt] = useState(false);
  const quelle = fehlt ? stiftungLogo : `${LOGO_URL}${version ? `?v=${version.slice(0, 12)}` : ""}`;
  return (
    <img
      src={quelle}
      onError={() => setFehlt(true)}
      alt="Deutsche Stiftung Krankheitsbedingte Mangelernährung"
      className={className}
      style={{ objectFit: "contain", objectPosition: "left center", ...style }}
    />
  );
}
