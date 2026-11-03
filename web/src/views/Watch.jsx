import { useMemo } from "react";
import { Spark } from "../components/Charts.jsx";
import { scan, sessions } from "../lib/rules.js";
import { useStored } from "../lib/store.js";
import { pct, price, tone, ymd } from "../lib/fmt.js";

const CATS = ["results", "M&A", "management_change", "fund_raise", "litigation", "credit_rating", "pledging", "insider_trading", "capex", "press_release", "dividend", "bonus_split", "earnings_call", "agm_egm", "postal_ballot", "investor_meetings"];

export default function Watch({ data, go }) {
  const { meta, eod, filings } = data;
  const [rules, setRules] = useStored("rules", meta.default_rules);
  const [watched, setWatched] = useStored("watch", meta.default_watch);

  const days = sessions(eod, 60);
  const from = days[0];
  const fired = useMemo(() => scan(eod, rules, from), [eod, rules, from]);
  const names = new Set(fired.map((f) => f.symbol));
  const perWeek = days.length ? (fired.length / days.length) * 5 : 0;

  const catCounts = useMemo(() => {
    const c = {};
    for (const f of filings) c[f.category] = (c[f.category] || 0) + 1;
    return c;
  }, [filings]);

  const set = (k) => (e) => setRules({ ...rules, [k]: Number(e.target.value) });
  const toggle = (c) => setWatched(watched.includes(c) ? watched.filter((x) => x !== c) : [...watched, c]);

  const holdings = meta.portfolio.map((p) => {
    const rows = eod[p.symbol] || [];
    const last = rows[rows.length - 1];
    const prev = rows[rows.length - 2];
    const ret = last && prev ? (last[1] / prev[1] - 1) * 100 : null;
    const r20 = rows.length > 21 ? (last[1] / rows[rows.length - 21][1] - 1) * 100 : null;
    const avg = rows.length > 21 ? rows.slice(-21, -1).reduce((s, r) => s + r[2], 0) / 20 : null;
    return { ...p, last: last?.[1], ret, r20, vx: avg ? last[2] / avg : null, spark: rows.slice(-30).map((r) => r[1]) };
  });

  return (
    <div className="watch">
      <section>
        <h1 className="page-title">What counts as unusual</h1>
        <p className="lede">FINN checks every holding after the close against these lines. Move them and see how noisy they would have been.</p>

        <div className="rule">
          <label htmlFor="r-price">Daily price move of at least <strong className="num">±{rules.price_pct}%</strong></label>
          <input id="r-price" type="range" min="1" max="12" step="0.5" value={rules.price_pct} onChange={set("price_pct")} />
        </div>
        <div className="rule">
          <label htmlFor="r-vol">Volume at least <strong className="num">{Number(rules.volume_x).toFixed(1)}×</strong> its 20-day average</label>
          <input id="r-vol" type="range" min="1.2" max="6" step="0.1" value={rules.volume_x} onChange={set("volume_x")} />
        </div>

        <div className="calib" aria-live="polite">
          <p>
            Over the last {days.length} sessions these lines would have fired <strong className="num">{fired.length}</strong> time{fired.length === 1 ? "" : "s"} across {names.size} holding{names.size === 1 ? "" : "s"}, about <strong className="num">{perWeek.toFixed(1)}</strong> a week.
          </p>
          <p className="fine">{perWeek > 6 ? "That's a lot. Raise a threshold if you'd ignore most of these." : perWeek < 0.5 ? "Very quiet. You may miss real moves; consider lowering a threshold." : "A workable level of noise."}</p>
          {fired.length ? (
            <ul className="fired">
              {fired.slice(0, 6).map((m) => (
                <li key={m.symbol + m.date}>
                  <span className="fine">{ymd(m.date)}</span>
                  <span className="sym">{m.symbol}</span>
                  <span className={`num ${tone(m.ret)}`}>{pct(m.ret)}</span>
                  <span className="fine">{m.vx && m.vx >= 1.5 ? `${m.vx.toFixed(1)}× vol` : ""}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </section>

      <section>
        <h2>Filings that should reach you</h2>
        <p className="fine section-note">Chosen types rise to the top of your brief and go to your phone. Others are set aside unless they're unusually large. The number is how many arrived in the last 30 days.</p>
        <div className="cats">
          {CATS.map((c) => (
            <button key={c} className={watched.includes(c) ? "chip on" : "chip"} aria-pressed={watched.includes(c)} onClick={() => toggle(c)}>
              {meta.labels[c] || c}
              <span className="chip-n num">{catCounts[c] || 0}</span>
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2>Holdings</h2>
        <ul className="holdings">
          {holdings.map((h) => (
            <li key={h.symbol}>
              <button className="hold-row" onClick={() => go(`#/research/${h.symbol}`)}>
                <span className="hold-name">
                  <span className="sym">{h.symbol}</span>
                  <span className="fine">{h.sector}</span>
                </span>
                <Spark values={h.spark} up={(h.r20 ?? 0) >= 0} />
                <span className="hold-num">
                  <span className="num">{price(h.last)}</span>
                  <span className={`num small ${tone(h.ret)}`}>{pct(h.ret)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="push-note">
        <h2>On your phone</h2>
        <p>Add FINN to your home screen from the browser's share menu. Each scheduled run also sends a Telegram message when a filing needs you or a holding moves past the server's default lines ({meta.default_rules.price_pct}% or {meta.default_rules.volume_x}× volume). The sliders above change what you see here; moving them to the server is next on the list.</p>
      </section>
    </div>
  );
}
