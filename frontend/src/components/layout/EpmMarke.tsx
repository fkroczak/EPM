/** Neutrale Wortmarke von EPM (Anmeldeseite, 11.10.2026): EPM wird von mehreren Einrichtungen genutzt, deshalb vor der
 *  Anmeldung kein Firmenlogo. Symbol: abgerundetes Feld mit Pulslinie. */
export function EpmSymbol({ groesse = 44, hell }: { groesse?: number; hell?: boolean }) {
  return (
    <svg width={groesse} height={groesse} viewBox="0 0 48 48" aria-hidden="true" style={{ width: `${groesse / 16}rem`, height: `${groesse / 16}rem` }}>
      <rect x="1" y="1" width="46" height="46" rx="12" fill={hell ? "rgba(255,255,255,.08)" : "#24353D"}
        stroke={hell ? "rgba(255,255,255,.28)" : "none"} />
      <path d="M8 26h8l3-7 5 15 4-11 2 3h10" fill="none" stroke={hell ? "#9CC9C1" : "#FFFFFF"} strokeWidth="2.6"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function EpmMarke({ className }: { className?: string }) {
  return (
    <div className={`flex items-center gap-3.5 ${className ?? ""}`} data-testid="epm-marke">
      <EpmSymbol />
      <div className="flex flex-col leading-tight">
        <span className="text-[1.625rem] font-semibold tracking-[.02em] text-tinte">EPM</span>
        <span className="text-[0.8125rem] gedaempft">Elektronisches Patientenmanagement</span>
      </div>
    </div>
  );
}
