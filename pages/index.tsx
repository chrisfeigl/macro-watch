import { useEffect, useState } from "react";

type Snapshot = {
  generated_utc: string;
  values: Record<string, number>;
  breaches: Record<string, boolean>;
  breach_count: number;
};

export default function Home() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch("/api/status", { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setSnap(await r.json());
      } catch (e: any) {
        setErr(e?.message || "Failed to load");
      }
    })();
  }, []);

  if (err) return <main style={{padding:20}}>Error: {err}</main>;
  if (!snap) return <main style={{padding:20}}>Loading… (first run: open <code>/api/compute</code>)</main>;

  const valueRows = Object.entries(snap.values).map(([k,v]) => [k, Number.isFinite(v) ? v.toFixed(3) : String(v)]);
  const breachRows = Object.entries(snap.breaches).map(([k,v]) => [k, v ? "TRUE" : "FALSE"]);

  return (
    <main style={{padding:20, fontFamily:"system-ui"}}>
      <h2>Macro Early Warning Dashboard</h2>
      <p>Generated: {snap.generated_utc}</p>
      <div style={{fontSize:24, fontWeight:700, margin:"12px 0"}}>Macro Stress Breaches: {snap.breach_count}</div>

      <h3>Latest Values</h3>
      <table style={{borderCollapse:"collapse", width:"100%", marginBottom:20}}>
        <thead><tr><th style={{textAlign:"left"}}>Indicator</th><th>Latest</th></tr></thead>
        <tbody>
          {valueRows.map(([k,v]) => (
            <tr key={k}>
              <td style={{padding:"6px 4px", borderBottom:"1px solid #eee"}}>{k}</td>
              <td style={{padding:"6px 4px", borderBottom:"1px solid #eee"}}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Breaches</h3>
      <table style={{borderCollapse:"collapse", width:"100%"}}>
        <thead><tr><th style={{textAlign:"left"}}>Rule</th><th>Triggered?</th></tr></thead>
        <tbody>
          {breachRows.map(([k,v]) => (
            <tr key={k}>
              <td style={{padding:"6px 4px", borderBottom:"1px solid #eee"}}>{k}</td>
              <td style={{padding:"6px 4px", borderBottom:"1px solid #eee", color: v==="TRUE" ? "#b00020" : "#2e7d32"}}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
