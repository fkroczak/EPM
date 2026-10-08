/** Strichsymbole wie im Entwurf (24er-Raster, 1,8 px Linie). */
import type { ReactNode, SVGProps } from "react";

const PFADE: Record<string, ReactNode> = {
  start: (<><path d="M3 10.5L12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /><path d="M10 21v-6h4v6" /></>),
  patienten: (<><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></>),
  versorger: (<><rect x="1" y="6" width="14" height="11" rx="1" /><path d="M15 10h4l3 3v4h-7" /><circle cx="6" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>),
  backup: (<><rect x="2" y="3" width="20" height="5" rx="1" /><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" /><path d="M10 12h4" /></>),
  benutzer: (<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></>),
  vorlagen: (<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M8 13h8" /><path d="M8 17h5" /></>),
  uhr: (<><path d="M12 8v4l3 2" /><circle cx="12" cy="12" r="9" /></>),
  konto: (<><circle cx="12" cy="8" r="4" /><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1" /></>),
  abmelden: (<><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" /></>),
  suche: (<><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>),
  plus: (<><path d="M12 5v14" /><path d="M5 12h14" /></>),
  haken: (<><path d="M20 6L9 17l-5-5" /></>),
  x: (<><path d="M18 6L6 18" /><path d="M6 6l12 12" /></>),
  mehr: (<><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>),
  telefon: (<><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z" /></>),
  warnung: (<><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4" /><path d="M12 17h.01" /></>),
  schloss: (<><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>),
  hochladen: (<><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M17 8l-5-5-5 5" /><path d="M12 3v12" /></>),
  herunterladen: (<><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M7 10l5 5 5-5" /><path d="M12 15V3" /></>),
  bild: (<><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" /></>),
  dokument: (<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></>),
  stift: (<><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></>),
  pfeilRechts: (<><path d="M5 12h14" /><path d="M12 5l7 7-7 7" /></>),
  pfeilLinks: (<><path d="M19 12H5" /><path d="M12 19l-7-7 7-7" /></>),
  hoch: (<><path d="M12 19V5" /><path d="M5 12l7-7 7 7" /></>),
  runter: (<><path d="M12 5v14" /><path d="M19 12l-7 7-7-7" /></>),
  kalender: (<><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4" /><path d="M8 2v4" /><path d="M3 10h18" /></>),
  waage: (<><path d="M12 3v18" /><path d="M5 7h14" /><path d="M5 7l-3 7a4 4 0 0 0 6 0z" /><path d="M19 7l-3 7a4 4 0 0 0 6 0z" /></>),
  tropfen: (<><path d="M12 2.7l5.7 5.7a8 8 0 1 1-11.4 0z" /></>),
  sprechblase: (<><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></>),
  auge: (<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></>),
  griff: (<><circle cx="9" cy="6" r="1" /><circle cx="15" cy="6" r="1" /><circle cx="9" cy="12" r="1" /><circle cx="15" cy="12" r="1" /><circle cx="9" cy="18" r="1" /><circle cx="15" cy="18" r="1" /></>),
  info: (<><circle cx="12" cy="12" r="9" /><path d="M12 16v-4" /><path d="M12 8h.01" /></>),
  arzt: (<><path d="M5 3v5a5 5 0 0 0 10 0V3" /><path d="M10 13v2a5 5 0 0 0 10 0v-2" /><circle cx="20" cy="11" r="2" /><path d="M4 3h2" /><path d="M14 3h2" /></>),
  minus: (<><path d="M5 12h14" /></>),
  server: (<><rect x="3" y="3" width="18" height="7" rx="1.5" /><rect x="3" y="14" width="18" height="7" rx="1.5" /><path d="M7 6.5h.01" /><path d="M7 17.5h.01" /><path d="M11 6.5h6" /><path d="M11 17.5h6" /></>),
  neustart: (<><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" /></>),
  aktivitaet: (<><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></>),
  sanduhr: (<><path d="M6 2h12" /><path d="M6 22h12" /><path d="M6 2c0 6 6 6 6 10s-6 4-6 10" /><path d="M18 2c0 6-6 6-6 10s6 4 6 10" /></>),
  hilfe: (<><circle cx="12" cy="12" r="9" /><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3" /><path d="M12 17h.01" /></>),
  stern: (<><path d="M12 2.5l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.3l-5.8 3.1 1.1-6.5L2.6 9.3l6.5-.9z" /></>),
  auge_zu: (<><path d="M17.9 17.9A10 10 0 0 1 12 20c-6.5 0-10-8-10-8a18 18 0 0 1 5.1-5.9" /><path d="M9.9 4.2A9 9 0 0 1 12 4c6.5 0 10 8 10 8a18 18 0 0 1-2.2 3.2" /><path d="M14.1 14.1a3 3 0 1 1-4.2-4.2" /><path d="M2 2l20 20" /></>),
  design: (<><path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.6-.9 1.2-1.8-.4-.9.1-2.2 1.3-2.2H17a4 4 0 0 0 4-4c0-5.5-4-10-9-10z" /><circle cx="7.5" cy="11" r="1" /><circle cx="10" cy="7" r="1" /><circle cx="15" cy="7.5" r="1" /></>),
  ecke: (<><path d="M21 11v10H11" /><path d="M21 16v5h-5" /></>),
  zurueck: (<><path d="M15 18l-6-6 6-6" /></>),
  menue: (<><path d="M4 6h16" /><path d="M4 12h16" /><path d="M4 18h16" /></>),
  passkey: (<><circle cx="8" cy="9" r="4" /><path d="M2 21v-1a5 5 0 0 1 5-5h2" /><circle cx="17" cy="15" r="2.5" /><path d="M17 17.5V22" /><path d="M17 20h2" /></>),
  // Scans (F158): Blatt mit Leselinie, Kopieren, Drehen
  scan: (<><path d="M4 7V5a2 2 0 0 1 2-2h2" /><path d="M16 3h2a2 2 0 0 1 2 2v2" /><path d="M20 17v2a2 2 0 0 1-2 2h-2" /><path d="M8 21H6a2 2 0 0 1-2-2v-2" /><path d="M3 12h18" /><path d="M8 8h8" /><path d="M8 16h5" /></>),
  kopieren: (<><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></>),
  drehen_links: (<><path d="M3 12a9 9 0 1 0 2.64-6.36" /><path d="M3 3v6h6" /></>),
  drehen_rechts: (<><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" /></>),
  rahmen: (<><path d="M3 8V5a2 2 0 0 1 2-2h3" /><path d="M16 3h3a2 2 0 0 1 2 2v3" /><path d="M21 16v3a2 2 0 0 1-2 2h-3" /><path d="M8 21H5a2 2 0 0 1-2-2v-3" /></>),
  kamera: (<><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></>),
  buch: (<><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></>),
};

export type IconName = keyof typeof PFADE;

export function Icon({ name, groesse = 16, ...rest }: { name: string; groesse?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg width={groesse} height={groesse} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...rest}>
      {PFADE[name] ?? null}
    </svg>
  );
}
