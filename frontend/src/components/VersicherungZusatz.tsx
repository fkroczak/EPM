/** Zur Versicherungsart (Wunsch RGC 16.11.2026): „mit Beihilfe“ und „stationäre Zusatzversicherung“ – auch zusammen. */
export function VersicherungZusatz({ beihilfe, zusatz, onAenderung }: {
  beihilfe: boolean; zusatz: boolean; onAenderung: (w: { beihilfe?: boolean; zusatz_stationaer?: boolean }) => void;
}) {
  return (
    <div className="col-span-2 flex gap-x-5 gap-y-1.5 flex-wrap text-sm" data-testid="versicherung-zusatz">
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={beihilfe} onChange={(e) => onAenderung({ beihilfe: e.target.checked })} /> mit Beihilfe
      </label>
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={zusatz} onChange={(e) => onAenderung({ zusatz_stationaer: e.target.checked })} /> Stationäre Zusatzversicherung
      </label>
    </div>
  );
}
