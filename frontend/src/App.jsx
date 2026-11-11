import { useEffect, useMemo, useRef, useState } from "react";

const TYPE = { litter: "Litter", debris: "Debris", bag: "Garbage bag", overflow: "Overflowing bin" };
const PRI = { High: 0, Medium: 1, Low: 2 };
const act = (t) => t.status === "Open" || t.status === "Assigned";
const band = (i) => (i >= 85 ? "Clean" : i >= 60 ? "Fair" : "Poor");
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const clock = (ts) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const ago = (s) => (s < 60 ? `${Math.max(0, Math.floor(s))} s ago` : `${Math.floor(s / 60)} min ago`);
const post = (url, body) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))));

function useTween(v, ms = 700) {
  const [o, setO] = useState(v), cur = useRef(v);
  useEffect(() => {
    const a = cur.current, t0 = performance.now(), d = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : ms;
    let f;
    const step = (n) => {
      const k = d ? Math.min(1, (n - t0) / d) : 1, x = a + (v - a) * (1 - Math.pow(1 - k, 3));
      cur.current = x; setO(Math.round(x));
      if (k < 1) f = requestAnimationFrame(step);
    };
    f = requestAnimationFrame(step);
    return () => cancelAnimationFrame(f);
  }, [v, ms]);
  return o;
}

function useSweep() {
  const [s, set] = useState({ up: false, zones: [], tickets: [], staff: [], hist: {}, fps: 0, toasts: [], resets: 0 });
  useEffect(() => {
    let ws, timer, stop = false, last = 0;
    const seen = {};
    const toast = (text, tone) => {
      const id = Math.random();
      set((x) => ({ ...x, toasts: [...x.toasts.slice(-2), { id, text, tone }] }));
      setTimeout(() => set((x) => ({ ...x, toasts: x.toasts.filter((t) => t.id !== id) })), 6500);
    };
    const open = () => {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
      ws.onopen = () => set((x) => ({ ...x, up: true }));
      ws.onclose = () => { set((x) => ({ ...x, up: false })); if (!stop) timer = setTimeout(open, 1500); };
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
        if (m.t === "hello") { m.tickets.forEach((t) => (seen[t.id] = t.status)); set((x) => ({ ...x, zones: m.zones, tickets: m.tickets, staff: m.staff, hist: m.history })); }
        else if (m.t === "stats") {
          const now = Date.now(), push = now - last > 2000;
          if (push) last = now;
          set((x) => {
            const hist = { ...x.hist };
            if (push) m.zones.forEach((z) => (hist[z.id] = [...(hist[z.id] || []), z.index].slice(-150)));
            return { ...x, zones: m.zones, fps: m.fps, hist };
          });
        } else if (m.t === "ticket") {
          const t = m.ticket, was = seen[t.id];
          if (!was) toast(`${t.id} opened: ${TYPE[t.type] || t.type} in ${t.zone}`, t.priority);
          else if (was !== t.status && t.status === "Cleaned") toast(`${t.id} cleaned in ${t.zone}`, "Clean");
          seen[t.id] = t.status;
          set((x) => ({ ...x, tickets: [t, ...x.tickets.filter((k) => k.id !== t.id)] }));
        } else if (m.t === "reset") { Object.keys(seen).forEach((k) => delete seen[k]); set((x) => ({ ...x, tickets: m.tickets, hist: {}, resets: x.resets + 1 })); }
      };
    };
    open();
    return () => { stop = true; clearTimeout(timer); ws && ws.close(); };
  }, []);
  return s;
}

function useConfig() {
  const [c, setC] = useState(null);
  useEffect(() => {
    let t, dead = false;
    const go = () => fetch("/api/config").then((r) => r.json()).then((j) => (j.size ? !dead && setC(j) : (t = setTimeout(go, 1000)))).catch(() => (t = setTimeout(go, 2000)));
    go();
    return () => { dead = true; clearTimeout(t); };
  }, []);
  return c;
}

function Spark({ data = [] }) {
  if (data.length < 2) return <div className="sp2" />;
  const y = (v) => (24 - Math.max(0, Math.min(60, v - 40)) * 0.4).toFixed(1);
  return (
    <svg className="sp2" viewBox="0 0 150 26" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={data.map((v, i) => `${((i * 150) / (data.length - 1)).toFixed(1)},${y(v)}`).join(" ")} />
    </svg>
  );
}

function ZoneCard({ z, data }) {
  const n = useTween(z.index);
  return (
    <div className={`zc ${z.band}`}>
      <div className="zn">{z.name}<small>{z.band}</small></div>
      <div className="n">{n}</div>
      <div className="g"><i style={{ width: `${z.index}%` }} /></div>
      <div className="zs">{z.items} {z.items === 1 ? "item" : "items"} on the floor, oldest {mmss(z.oldest)}</div>
      <Spark data={data} />
    </div>
  );
}

function Compare({ t }) {
  const [p, setP] = useState(50);
  return (
    <div className="cmp">
      {t.after_url ? <>
        <img src={t.after_url} alt="After cleanup" />
        <img src={t.before_url} alt="Before cleanup" style={{ clipPath: `inset(0 ${100 - p}% 0 0)` }} />
        <i style={{ left: `${p}%` }} /><input type="range" min="0" max="100" value={p} onChange={(e) => setP(+e.target.value)} aria-label="Drag to compare before and after" />
        <span className="l">Before</span><span className="r">After</span></> : <>
        <img src={t.before_url} alt="Before cleanup" /><span className="l">Before</span><em>Waiting for cleanup</em></>}
    </div>
  );
}

export default function App() {
  const S = useSweep(), cfg = useConfig();
  const [tid, setTid] = useState(null), [tab, setTab] = useState("All"), [layers, setLayers] = useState({ boxes: true, zones: true });
  const [old, setOld] = useState([]), [pick, setPick] = useState({}), [now, setNow] = useState(Date.now() / 1000), [err, setErr] = useState("");
  useEffect(() => { const i = setInterval(() => setNow(Date.now() / 1000), 1000); return () => clearInterval(i); }, []);
  useEffect(() => { fetch("/api/history").then((r) => r.json()).then(setOld).catch(() => {}); }, [S.resets, tab]);
  const run = (url, body) => post(url, body).then(() => setErr("")).catch(() => setErr("That action failed. Check that the backend is still running."));
  const tickets = useMemo(() => [...S.tickets].sort((a, b) => act(b) - act(a) || (act(a) ? PRI[a.priority] - PRI[b.priority] : 0) || b.created - a.created), [S.tickets]);
  const count = (st) => tickets.filter((t) => t.status === st).length;
  const shown = tab === "History" ? old : tickets.filter((t) => tab === "All" || t.status === tab);
  const cur = tickets.find((t) => t.id === tid) || old.find((t) => t.id === tid);
  const overall = S.zones.length ? Math.round(S.zones.reduce((a, z) => a + z.index, 0) / S.zones.length) : 0;
  const big = useTween(overall), ob = band(overall);
  const toggle = (k) => { const v = { ...layers, [k]: !layers[k] }; setLayers(v); run("/api/layers", v); };

  return (
    <>
      <header>
        <span className="brand">Sweep</span><span className="mu">Block C, ground floor</span><span className="sp" />
        <span className="kv"><i className={`dot${S.up ? " up" : ""}`} />{S.up ? "Connected" : "Offline"}</span>
        <span className="kv">Open tickets<b>{count("Open") + count("Assigned")}</b></span>
        <span className="kv">Processing<b>{S.fps}</b> fps</span>
      </header>
      {!S.up && <div className="warn">The backend isn’t reachable. Start it with <code>uvicorn main:app --port 8000</code> in the backend folder.</div>}
      {err && <div className="warn">{err}</div>}
      <main>
        <section>
          <div className="frame" style={{ aspectRatio: cfg ? `${cfg.size[0]} / ${cfg.size[1]}` : "16 / 9" }}>
            <img src="/video" alt="Camera 01 with detected litter marked" /><div className="shade" />
            <div className={`hud tl ${ob}`}><div className="big">{big}</div><div><b>{ob}</b><span>Site cleanliness</span></div></div>
            <div className="hud tr">
              <button className="t" aria-pressed={layers.boxes} onClick={() => toggle("boxes")}>Item boxes</button>
              <button className="t" aria-pressed={layers.zones} onClick={() => toggle("zones")}>Zones</button>
              <button className="t" onClick={() => run("/api/replay")}>Replay clip</button>
            </div>
            {cfg && S.zones.map((z) => {
              const d = cfg.zones.find((c) => c.id === z.id); if (!d) return null;
              const x = Math.min(...d.poly.map((p) => p[0])), y = Math.max(...d.poly.map((p) => p[1]));
              return <div key={z.id} className={`badge ${z.band}`} style={{ left: `${(x / cfg.size[0]) * 100 + 1}%`, top: `${(y / cfg.size[1]) * 100 - 9}%` }}>{z.name}<b>{z.index}</b></div>;
            })}
            <div className="toasts" aria-live="polite">{S.toasts.map((t) => <div key={t.id} className={`toast ${t.tone}`}>{t.text}</div>)}</div>
          </div>
          <div className="meta"><span>Camera 01, fixed view</span><span>Litter counts after 3 s, a ticket opens after 15 s</span></div>
        </section>
        <aside className="rail">
          {cur ? (
            <div className="sec">
              <button className="back" onClick={() => setTid(null)}>Back to all tickets</button>
              <h2>{cur.id}, {TYPE[cur.type] || cur.type}</h2>
              <p className="mu" style={{ margin: "0 0 12px" }}>{cur.zone}, {cur.priority} priority{cur.status === "Archived" ? ", from an earlier run" : ""}</p>
              <Compare t={cur} />
              <ul className="steps">
                <li className="done">Opened<small>{clock(cur.created)}</small></li>
                <li className={cur.assigned ? "done" : ""}>Assigned{cur.staff ? `: ${cur.staff}` : ""}<small>{cur.assigned ? clock(cur.assigned) : "Not yet"}</small></li>
                <li className={cur.cleaned ? "done" : ""}>Cleaned<small>{cur.cleaned ? `${clock(cur.cleaned)}, ${mmss(cur.cleaned - cur.created)} after opening` : "Waiting"}</small></li>
              </ul>
              {cur.note && <p className="mu">{cur.note}</p>}
              {act(cur) && <div className="act">
                {cur.status === "Open" && <>
                  <select aria-label="Staff member" value={pick[cur.id] || S.staff[0] || ""} onChange={(e) => setPick({ ...pick, [cur.id]: e.target.value })}>{S.staff.map((n) => <option key={n}>{n}</option>)}</select>
                  <button className="pri" onClick={() => run(`/api/tickets/${cur.id}/assign`, { staff: pick[cur.id] || S.staff[0] })}>Assign</button></>}
                <button className="ghost" onClick={() => run(`/api/tickets/${cur.id}/clean`)}>Mark cleaned</button>
              </div>}
            </div>
          ) : <>
            <div className="sec"><h2>Zones</h2>
              {S.zones.length === 0 && <p className="em">Waiting for the first scores.</p>}
              {S.zones.map((z) => <ZoneCard key={z.id} z={z} data={S.hist[z.id]} />)}</div>
            <div className="sec"><h2>Housekeeping tracker</h2>
              <div className="tabs">{["All", "Open", "Assigned", "Cleaned", "History"].map((n) => <button key={n} className={`tab${tab === n ? " on" : ""}`} onClick={() => setTab(n)}>{n}{n === "All" ? "" : ` ${n === "History" ? old.length : count(n)}`}</button>)}</div>
              <div className="list">
                {shown.length === 0 && <p className="em">{tab === "History" ? "No earlier runs yet. Tickets move here when the clip restarts." : "Nothing here yet. A ticket opens when litter stays put."}</p>}
                {shown.map((t) => (
                  <button key={t.id} className={`tk ${t.priority}${act(t) || t.status === "Archived" ? "" : " off"}`} onClick={() => setTid(t.id)}>
                    <b>{t.id} {TYPE[t.type] || t.type}</b><small>{ago(now - t.created)}</small>
                    <small style={{ gridColumn: 2 }}>{t.zone}, {t.priority}</small><small>{t.status === "Archived" ? (t.cleaned ? "Cleaned, earlier run" : "Left open, earlier run") : t.status}{t.staff ? `, ${t.staff}` : ""}</small>
                  </button>))}
              </div></div>
          </>}
        </aside>
      </main>
    </>
  );
}
