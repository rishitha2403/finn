import { useEffect, useRef, useState } from "react";
import { Bars, Line, PairBars } from "../components/Charts.jsx";
import { getJSON, research } from "../lib/data.js";
import { cr, pct, plain, price, tone, day } from "../lib/fmt.js";

const GOOD = ["met", "beat", "on track", "ahead", "delivered"];
const BAD = ["missed", "behind", "slipping"];

function verdictClass(v) {
  if (!v) return "v-none";
  if (GOOD.includes(v)) return "v-good";
  if (BAD.includes(v)) return "v-bad";
  return "v-none";
}

function Flags({ signals, area }) {
  const s = (signals || []).filter((x) => x.area === area || (Array.isArray(area) && area.includes(x.area)));
  if (!s.length) return null;
  return (
    <ul className="flags">
      {s.map((x) => <li key={x.text} className={`flag ${x.kind}`}><span className="flag-mark" aria-label={x.kind === "good" ? "positive" : x.kind === "bad" ? "concern" : "neutral"} />{x.text}</li>)}
    </ul>
  );
}

function Stat({ k, v, sub }) {
  return (
    <div className="stat">
      <span className="stat-k">{k}</span>
      <span className="stat-v num">{v}</span>
      {sub ? <span className={`stat-sub num ${sub.cls || ""}`}>{sub.text}</span> : null}
    </div>
  );
}

function Promises({ g, syn }) {
  if (!g) return null;
  const qual = Object.fromEntries((syn?.qualitative || []).map((q) => [q.id, q]));
  const items = g.track.map((t) => ({ ...t, v: t.verdict || qual[t.id]?.verdict || null, why: qual[t.id]?.why }));
  const checked = items.filter((i) => i.v && i.v !== "too early");
  const good = checked.filter((i) => GOOD.includes(i.v)).length;
  const bad = checked.filter((i) => BAD.includes(i.v)).length;
  const byCall = {};
  for (const i of items) (byCall[i.said_on || "Undated"] ||= []).push(i);
  return (
    <section id="promises" className="memo-sec">
      <h2>Promised vs delivered</h2>
      {items.length ? (
        <p className="tally">
          Across {g.calls.length} call{g.calls.length === 1 ? "" : "s"}, management made <strong className="num">{items.length}</strong> specific commitment{items.length === 1 ? "" : "s"}.{" "}
          {checked.length ? <>Of the {checked.length} we could check, <strong className="num good-t">{good}</strong> held up and <strong className="num bad-t">{bad}</strong> {bad === 1 ? "is" : "are"} slipping or missed.</> : "None can be checked against reported numbers yet."}
        </p>
      ) : (
        <p className="empty">No explicit guidance in the last {g.calls.length || 0} transcripts. Management here talks direction, not numbers.</p>
      )}
      {syn?.credibility ? <p className={`cred cred-${syn.credibility.score}`}><strong>Credibility: {syn.credibility.score}.</strong> {syn.credibility.why}</p> : null}
      {Object.entries(byCall).map(([when, list]) => (
        <div key={when} className="call-group">
          <h3>Said in {when}</h3>
          <ul className="promises">
            {list.map((p) => (
              <li key={p.id}>
                <div className="p-top">
                  <span className="p-what">{p.statement}</span>
                  <span className={`pill ${verdictClass(p.v)}`}>{p.v || "can't check yet"}</span>
                </div>
                <div className="p-meta fine">
                  <span>For {p.period || "unspecified period"}</span>
                  {p.actual ? <span>Actual {plain(p.actual.value)}{p.unit === "%" ? "%" : ""} ({p.actual.basis})</span> : null}
                  {p.speaker ? <span>{p.speaker}</span> : null}
                </div>
                {p.why ? <p className="fine">{p.why}</p> : null}
                {p.quote ? (
                  <details>
                    <summary>Their words</summary>
                    <blockquote>{p.quote}</blockquote>
                    {p.source ? <a href={p.source} target="_blank" rel="noreferrer" className="quiet-link">Open transcript</a> : null}
                  </details>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {syn?.narrative_vs_numbers?.length ? (
        <div className="nvn">
          <h3>Story vs financials</h3>
          <ul>
            {syn.narrative_vs_numbers.map((n) => (
              <li key={n.claim} className={`nvn-${n.verdict}`}>
                <p><span className="nvn-label">They say</span> {n.claim}</p>
                <p><span className="nvn-label">Numbers show</span> {n.numbers}</p>
                <span className={`pill ${n.verdict === "agrees" ? "v-good" : n.verdict === "diverges" ? "v-bad" : "v-none"}`}>{n.verdict}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function Numbers({ n }) {
  const s = n.snapshot;
  const l = s.latest || {};
  const q = n.quarters.filter((x) => x.revenue !== null);
  return (
    <section id="numbers" className="memo-sec">
      <h2>Where it stands</h2>
      <div className="stats">
        <Stat k={`Revenue, ${s.latest_quarter}`} v={cr(l.revenue)} sub={{ text: `${pct(l.revenue_yoy)} YoY`, cls: tone(l.revenue_yoy) }} />
        <Stat k={n.lender ? "Financing margin" : "Operating margin"} v={`${plain(l.opm, 0)}%`} sub={{ text: `TTM ${plain(s.ttm_opm)}%` }} />
        <Stat k={`PAT, ${s.latest_quarter}`} v={cr(l.pat)} sub={{ text: `${pct(l.pat_yoy)} YoY`, cls: tone(l.pat_yoy) }} />
        <Stat k="TTM revenue" v={cr(s.ttm_revenue)} sub={{ text: `PAT ${cr(s.ttm_pat)}` }} />
        <Stat k="ROCE / ROE" v={`${plain(s.roce, 0)}% / ${plain(s.roe, 0)}%`} />
        <Stat k="P/E" v={plain(s.pe)} sub={{ text: `M-cap ${cr(s.market_cap)}` }} />
      </div>
      <h3>Quarterly revenue</h3>
      <Bars data={q.map((x) => ({ label: x.label.replace(" FY", "'"), value: x.revenue }))} fmt={cr} label="Quarterly revenue" />
      <h3>{n.lender ? "Financing margin" : "Operating margin"} by quarter</h3>
      <Line data={q.map((x) => ({ label: x.label.replace(" FY", "'"), value: x.opm }))} fmt={(v) => `${plain(v, 0)}%`} label="Operating margin by quarter" />
      <Flags signals={n.signals} area="growth" />
    </section>
  );
}

function Trajectory({ n }) {
  const t = n.trajectory;
  const ys = t.years || [];
  return (
    <section id="trajectory" className="memo-sec">
      <h2>Trajectory</h2>
      <div className="stats three">
        <Stat k="Revenue CAGR, 3 yr" v={pct(t.rev_cagr_3y)} />
        <Stat k="PAT CAGR, 3 yr" v={pct(t.pat_cagr_3y)} />
        <Stat k="Margin change, 3 yr" v={t.opm_change_3y === undefined || t.opm_change_3y === null ? "–" : `${t.opm_change_3y > 0 ? "+" : ""}${t.opm_change_3y} pts`} />
      </div>
      <PairBars data={ys.map((y) => ({ label: y.label, rev: y.revenue, pat: y.pat }))} a={{ key: "rev", name: "Revenue" }} b={{ key: "pat", name: "PAT" }} fmt={cr} label="Annual revenue and profit" />
      <Flags signals={n.signals} area="trajectory" />
    </section>
  );
}

function Balance({ n }) {
  const b = n.balance || {};
  const h = (b.history || []).filter((x) => x.label);
  return (
    <section id="balance" className="memo-sec">
      <h2>Balance sheet</h2>
      <div className="stats">
        <Stat k={`Borrowings, ${b.as_of || ""}`} v={cr(b.borrowings)} sub={b.borrowings_x_3y ? { text: `${b.borrowings_x_3y}× three years ago` } : null} />
        <Stat k="Net worth" v={cr(b.equity)} />
        {!n.lender ? <Stat k="Debt / equity" v={b.de === null || b.de === undefined ? "–" : `${b.de.toFixed(2)}×`} /> : null}
        {!n.lender ? <Stat k="Cash conversion cycle" v={b.ccc === null || b.ccc === undefined ? "–" : `${Math.round(b.ccc)} days`} sub={b.debtor_days ? { text: `Receivables ${Math.round(b.debtor_days)}d, inventory ${Math.round(b.inventory_days || 0)}d` } : null} /> : null}
      </div>
      {!n.lender && h.some((x) => x.ccc !== null) ? (
        <>
          <h3>Cash conversion cycle, days</h3>
          <Line data={h.map((x) => ({ label: x.label, value: x.ccc }))} fmt={(v) => `${Math.round(v)} days`} label="Cash conversion cycle" />
        </>
      ) : null}
      {n.lender ? <p className="fine">For a lender, borrowings are raw material, so debt-to-equity and working-capital days don't apply.</p> : null}
      <Flags signals={n.signals} area={["balance", "ownership"]} />
    </section>
  );
}

function Cash({ n }) {
  const c = n.cash || {};
  if (!c.history) return null;
  return (
    <section id="cash" className="memo-sec">
      <h2>Do profits become cash?</h2>
      <div className="stats three">
        <Stat k={`Operating cash ÷ PAT, ${c.window}`} v={c.conversion === null || c.conversion === undefined ? "–" : `${Math.round(c.conversion * 100)}%`} />
        <Stat k="Operating cash, total" v={cr(c.cfo_sum)} />
        <Stat k="Free cash flow, est." v={cr(c.fcf_sum)} />
      </div>
      <PairBars data={c.history.map((y) => ({ label: y.label, cfo: y.cfo, pat: y.pat }))} a={{ key: "cfo", name: "Operating cash" }} b={{ key: "pat", name: "PAT" }} fmt={cr} label="Operating cash flow versus profit" />
      <p className="fine">Free cash flow is estimated as operating cash minus capex, where capex is the change in net block and capital work in progress plus depreciation.</p>
      <Flags signals={n.signals} area="cash" />
    </section>
  );
}

function BullBear({ syn }) {
  if (!syn?.bull) return null;
  return (
    <section id="case" className="memo-sec">
      <h2>The case each way</h2>
      <div className="case">
        <div className="bull">
          <h3>Bull</h3>
          <ul>{syn.bull.map((b) => <li key={b}>{b}</li>)}</ul>
        </div>
        <div className="bear">
          <h3>Bear</h3>
          <ul>{syn.bear.map((b) => <li key={b}>{b}</li>)}</ul>
        </div>
      </div>
      {syn.watch_next?.length ? (
        <>
          <h3>Ask on the next call</h3>
          <ul className="plain-list">{syn.watch_next.map((w) => <li key={w}>{w}</li>)}</ul>
        </>
      ) : null}
    </section>
  );
}

function Business({ n, g }) {
  const b = g?.business;
  const segs = (b?.segments || []).filter((s) => s.name);
  const total = segs.reduce((s, x) => s + (x.share_pct || 0), 0);
  return (
    <section id="business" className="memo-sec">
      <h2>The business</h2>
      <p>{b?.what || n.about || "No description available."}</p>
      {segs.length ? (
        <ul className="segments">
          {segs.map((s) => (
            <li key={s.name}>
              <div className="seg-top"><span>{s.name}</span><span className="num">{s.share_pct ? `${s.share_pct}%` : ""}</span></div>
              {s.share_pct && total ? <div className="seg-bar"><i style={{ width: `${Math.min(100, s.share_pct)}%` }} /></div> : null}
              {s.comment ? <span className="fine">{s.comment}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {b?.what ? <p className="fine">As management describes it on the latest call.</p> : n.about ? <p className="fine">From the company profile on screener.in.</p> : null}
    </section>
  );
}

function Sources({ n, g }) {
  return (
    <section className="memo-sec sources">
      <h2>Sources</h2>
      <ul className="plain-list">
        <li><a href={n.source_url} target="_blank" rel="noreferrer">{n.basis === "standalone" ? "Standalone" : "Consolidated"} financials on screener.in</a></li>
        {(g?.calls || []).map((c) => <li key={c.url}><a href={c.url} target="_blank" rel="noreferrer">Earnings call transcript, {c.date}</a></li>)}
        {(n.documents?.annual_reports || []).slice(0, 2).map((a) => <li key={a.url}><a href={a.url} target="_blank" rel="noreferrer">{a.title.replace(/\s*from bse.*/i, "")} annual report</a></li>)}
      </ul>
      <p className="fine">Numbers are computed in code from reported financials. The model only reads transcripts and writes the words; it is told not to use anything else it knows.</p>
    </section>
  );
}

const NAV = [
  ["promises", "Promises"],
  ["numbers", "Numbers"],
  ["trajectory", "Trajectory"],
  ["balance", "Balance sheet"],
  ["cash", "Cash"],
  ["case", "Bull & bear"],
  ["business", "Business"],
];

function Memo({ n, g, syn, stage, errors, prepared, onLive }) {
  const s = n.snapshot;
  return (
    <article className="memo">
      <header className="memo-head">
        <div>
          <h1>{n.name}</h1>
          <p className="fine">{n.symbol} on NSE{prepared ? `, prepared ${day(new Date(prepared * 1000).toISOString())}` : ""}</p>
        </div>
        <div className="memo-price">
          <span className="num">{price(s.price)}</span>
          <span className="fine num">M-cap {cr(s.market_cap)}</span>
        </div>
      </header>

      <nav className="memo-nav" aria-label="Sections">
        {NAV.map(([id, label]) => <a key={id} href={`#${id}`} onClick={(e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>{label}</a>)}
      </nav>

      <section className="read">
        {syn?.read ? (
          <ul>{syn.read.map((r) => <li key={r}>{r}</li>)}</ul>
        ) : (
          <div className="pending">
            {stage === "guidance" ? <p>Reading the last four earnings call transcripts…</p> : null}
            {stage === "synthesis" ? <p>Comparing what management promised with what the numbers show…</p> : null}
            {errors.story ? <p className="err">{errors.story}</p> : null}
            {stage === "done" && !syn && !errors.story ? <p className="fine">The written analysis isn't available for this company.</p> : null}
          </div>
        )}
        {prepared ? <button className="link small" onClick={onLive}>Run again with the latest filings</button> : null}
      </section>

      {g ? <Promises g={g} syn={syn} /> : <section id="promises" className="memo-sec"><h2>Promised vs delivered</h2><p className="fine">{stage === "guidance" ? "Extracting guidance from transcripts…" : errors.story || "Waiting for transcripts."}</p></section>}
      <Numbers n={n} />
      <Trajectory n={n} />
      <Balance n={n} />
      <Cash n={n} />
      <BullBear syn={syn} />
      <Business n={n} g={g} />
      <Sources n={n} g={g} />
    </article>
  );
}

export default function Research({ symbol, data, go }) {
  const [q, setQ] = useState(symbol || "");
  const [state, setState] = useState({});
  const [prepared, setPrepared] = useState([]);
  const run = useRef(0);

  useEffect(() => {
    getJSON("/data/research/index.json").then(setPrepared).catch(() => setPrepared([]));
  }, []);

  const live = async (sym, id) => {
    setState({ stage: "numbers", errors: {} });
    let n;
    try {
      n = await research(sym, "numbers");
    } catch (e) {
      if (run.current === id) setState({ stage: "failed", errors: { numbers: e.message } });
      return;
    }
    if (run.current !== id) return;
    setState({ n, stage: "guidance", errors: {} });
    let g;
    try {
      g = await research(sym, "guidance");
    } catch (e) {
      if (run.current === id) setState({ n, stage: "done", errors: { story: e.message } });
      return;
    }
    if (run.current !== id) return;
    setState({ n, g, stage: "synthesis", errors: {} });
    try {
      const syn = await research(sym, "synthesis", g);
      if (run.current === id) setState({ n, g, syn, stage: "done", errors: {} });
    } catch (e) {
      if (run.current === id) setState({ n, g, stage: "done", errors: { story: e.message } });
    }
  };

  useEffect(() => {
    if (!symbol) return;
    setQ(symbol);
    const id = ++run.current;
    getJSON(`/data/research/${symbol}.json`)
      .then((r) => {
        if (run.current !== id) return;
        setState({ n: r.numbers, g: r.guidance, syn: r.synthesis, stage: "done", errors: r.story_error ? { story: r.story_error } : {}, prepared: r.prepared_at });
      })
      .catch(() => live(symbol, id));
  }, [symbol]);

  const submit = (e) => {
    e.preventDefault();
    const s = q.trim().toUpperCase().replace(/\.(NS|BO)$/, "");
    if (s) go(`#/research/${s}`);
  };

  const suggestions = [...new Set([...(data?.meta?.research_demo || []), ...prepared])].filter(Boolean);

  return (
    <div className="research">
      <form className="search" onSubmit={submit} role="search">
        <label htmlFor="sym" className="sr">NSE symbol</label>
        <input id="sym" value={q} onChange={(e) => setQ(e.target.value.toUpperCase())} placeholder="Any NSE symbol, like TCS or KEI" autoCapitalize="characters" autoComplete="off" spellCheck="false" />
        <button type="submit">Analyse</button>
      </form>

      {!symbol ? (
        <div className="research-empty">
          <p className="lede">Pick any listed company. FINN reads its last four earnings calls, pulls ten years of reported financials, and checks what management promised against what it delivered.</p>
          {suggestions.length ? (
            <>
              <h2>Prepared for the demo</h2>
              <div className="cats">{suggestions.map((s) => <button key={s} className="chip" onClick={() => go(`#/research/${s}`)}>{s}</button>)}</div>
            </>
          ) : null}
          <h2>Your holdings</h2>
          <div className="cats">{(data?.meta?.portfolio || []).map((p) => <button key={p.symbol} className="chip" onClick={() => go(`#/research/${p.symbol}`)}>{p.symbol}</button>)}</div>
        </div>
      ) : null}

      {symbol && state.stage === "numbers" ? <p className="pending">Pulling reported financials for {symbol}…</p> : null}
      {symbol && state.errors?.numbers ? <p className="err">{state.errors.numbers}</p> : null}
      {symbol && state.n ? (
        <Memo n={state.n} g={state.g} syn={state.syn} stage={state.stage} errors={state.errors || {}} prepared={state.prepared} onLive={() => { const id = ++run.current; live(symbol, id); }} />
      ) : null}
    </div>
  );
}
