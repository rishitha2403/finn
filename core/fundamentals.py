import re

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def parse_period(lbl):
    m = re.match(r"([A-Za-z]{3})\w*\s+(\d{4})", lbl or "")
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    return int(m.group(2)), mon


def fy_of(year, month):
    return year if month <= 3 else year + 1


def fy_label(fy):
    return f"FY{fy % 100:02d}"


def quarter_label(year, month):
    q = ((month - 4) % 12) // 3 + 1
    return f"Q{q} {fy_label(fy_of(year, month))}"


def find_row(tbl, *names):
    if not tbl:
        return None
    rows = tbl["rows"]
    for n in names:
        nl = n.lower()
        for k, v in rows.items():
            if k.lower() == nl:
                return v
    for n in names:
        nl = n.lower()
        for k, v in rows.items():
            if k.lower().startswith(nl):
                return v
    return None


def series(tbl, *names):
    if not tbl:
        return {}
    vals = find_row(tbl, *names)
    if vals is None:
        return {}
    out = {}
    for c, v in zip(tbl["cols"], vals):
        out[c] = v
    return out


def pct(a, b):
    if a is None or b is None or b == 0:
        return None
    if b < 0:
        return None
    return round((a / b - 1) * 100, 1)


def cagr(end, start, years):
    if end is None or start is None or start <= 0 or end <= 0 or years <= 0:
        return None
    return round(((end / start) ** (1 / years) - 1) * 100, 1)


def safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def fmt_cr(v):
    if v is None:
        return "n/a"
    neg = v < 0
    v = abs(v)
    if v >= 100000:
        s = f"{v / 100000:.2f} lakh cr"
    else:
        whole = f"{v:,.0f}"
        s = f"{whole} cr"
    return ("-₹" if neg else "₹") + s


def is_lender(page):
    q = page.get("quarters") or {}
    keys = " ".join(k.lower() for k in q.get("rows", {}))
    return "financing profit" in keys or "financing margin" in keys


def quarterly(page):
    q = page.get("quarters")
    if not q:
        return []
    lender = is_lender(page)
    rev = find_row(q, "Sales", "Revenue")
    op = find_row(q, "Financing Profit") if lender else find_row(q, "Operating Profit")
    opm = find_row(q, "Financing Margin %") if lender else find_row(q, "OPM %")
    pbt = find_row(q, "Profit before tax")
    pat = find_row(q, "Net Profit")
    out = []
    for i, c in enumerate(q["cols"]):
        p = parse_period(c)
        if not p:
            continue
        g = lambda arr: arr[i] if arr and i < len(arr) else None
        out.append({
            "col": c,
            "label": quarter_label(*p),
            "year": p[0],
            "month": p[1],
            "fy": fy_of(*p),
            "revenue": g(rev),
            "op": g(op),
            "opm": g(opm),
            "pbt": g(pbt),
            "pat": g(pat),
        })
    for i, r in enumerate(out):
        prev_y = out[i - 4] if i >= 4 else None
        prev_q = out[i - 1] if i >= 1 else None
        for k in ("revenue", "op", "pat"):
            r[f"{k}_yoy"] = pct(r[k], prev_y[k]) if prev_y else None
            r[f"{k}_qoq"] = pct(r[k], prev_q[k]) if prev_q else None
    return out


def annual(page):
    a = page.get("annual")
    if not a:
        return []
    lender = is_lender(page)
    rev = series(a, "Sales", "Revenue")
    op = series(a, "Financing Profit") if lender else series(a, "Operating Profit")
    opm = series(a, "Financing Margin %") if lender else series(a, "OPM %")
    pat = series(a, "Net Profit")
    dep = series(a, "Depreciation")
    bal = page.get("balance")
    borrow = series(bal, "Borrowings")
    eqc = series(bal, "Equity Capital")
    res = series(bal, "Reserves")
    fa = series(bal, "Fixed Assets", "Net Block")
    cwip = series(bal, "CWIP")
    inv = series(bal, "Investments")
    ta = series(bal, "Total Assets")
    cf = page.get("cashflow")
    cfo = series(cf, "Cash from Operating Activity")
    cfi = series(cf, "Cash from Investing Activity")
    eff = page.get("efficiency")
    dd = series(eff, "Debtor Days")
    idays = series(eff, "Inventory Days")
    pd = series(eff, "Days Payable")
    ccc = series(eff, "Cash Conversion Cycle")
    wcd = series(eff, "Working Capital Days")
    roce = series(eff, "ROCE %")
    roe = series(eff, "ROE %")
    out = []
    for c in a["cols"]:
        p = parse_period(c)
        if not p:
            continue
        eq = None
        if eqc.get(c) is not None and res.get(c) is not None:
            eq = eqc[c] + res[c]
        out.append({
            "col": c,
            "fy": fy_of(*p),
            "label": fy_label(fy_of(*p)),
            "revenue": rev.get(c),
            "op": op.get(c),
            "opm": opm.get(c),
            "pat": pat.get(c),
            "dep": dep.get(c),
            "borrowings": borrow.get(c),
            "equity": eq,
            "fixed_assets": fa.get(c),
            "cwip": cwip.get(c),
            "investments": inv.get(c),
            "total_assets": ta.get(c),
            "cfo": cfo.get(c),
            "cfi": cfi.get(c),
            "debtor_days": dd.get(c),
            "inventory_days": idays.get(c),
            "payable_days": pd.get(c),
            "ccc": ccc.get(c),
            "wc_days": wcd.get(c),
            "roce": roce.get(c),
            "roe": roe.get(c),
        })
    for i, r in enumerate(out):
        r["de"] = round(r["borrowings"] / r["equity"], 2) if r["borrowings"] is not None and r["equity"] else None
        prev = out[i - 1] if i else None
        r["revenue_growth"] = pct(r["revenue"], prev["revenue"]) if prev else None
        r["pat_growth"] = pct(r["pat"], prev["pat"]) if prev else None
        capex = None
        if prev and None not in (r["fixed_assets"], prev["fixed_assets"], r["dep"]):
            capex = (r["fixed_assets"] - prev["fixed_assets"]) + r["dep"]
            if r["cwip"] is not None and prev["cwip"] is not None:
                capex += r["cwip"] - prev["cwip"]
            capex = round(capex, 1)
        r["capex_est"] = capex
        r["fcf_est"] = round(r["cfo"] - capex, 1) if r["cfo"] is not None and capex is not None else None
    return out


def _last(rows, key, n=1):
    vals = [r for r in rows if r.get(key) is not None]
    return vals[-n:] if vals else []


def snapshot(page, qs, ys):
    rt = page.get("ratios", {})
    last4 = [q for q in qs if q["revenue"] is not None][-4:]
    ttm_rev = sum(q["revenue"] for q in last4) if len(last4) == 4 else None
    ttm_pat = sum(q["pat"] for q in last4 if q["pat"] is not None) if len(last4) == 4 else None
    ttm_op = sum(q["op"] for q in last4 if q["op"] is not None) if len(last4) == 4 else None
    lq = qs[-1] if qs else {}
    ly = ys[-1] if ys else {}
    return {
        "price": rt.get("Current Price"),
        "market_cap": rt.get("Market Cap"),
        "pe": rt.get("Stock P/E"),
        "book_value": rt.get("Book Value"),
        "dividend_yield": rt.get("Dividend Yield"),
        "roce": rt.get("ROCE") if rt.get("ROCE") is not None else ly.get("roce"),
        "roe": rt.get("ROE") if rt.get("ROE") is not None else ly.get("roe"),
        "ttm_revenue": ttm_rev,
        "ttm_op": ttm_op,
        "ttm_opm": round(ttm_op / ttm_rev * 100, 1) if ttm_rev and ttm_op is not None else None,
        "ttm_pat": ttm_pat,
        "latest_quarter": lq.get("label"),
        "latest": {k: lq.get(k) for k in ("revenue", "op", "opm", "pbt", "pat",
                                          "revenue_yoy", "op_yoy", "pat_yoy",
                                          "revenue_qoq", "pat_qoq")},
    }


def trajectory(ys, growth):
    rows = [y for y in ys if y["revenue"] is not None]
    out = {"years": [{k: y.get(k) for k in ("label", "revenue", "op", "opm", "pat", "revenue_growth", "pat_growth")} for y in rows[-7:]]}
    if len(rows) >= 4:
        a, b = rows[-4], rows[-1]
        out["rev_cagr_3y"] = cagr(b["revenue"], a["revenue"], 3)
        out["pat_cagr_3y"] = cagr(b["pat"], a["pat"], 3)
        if a["opm"] is not None and b["opm"] is not None:
            out["opm_change_3y"] = round(b["opm"] - a["opm"], 1)
    if len(rows) >= 6:
        a, b = rows[-6], rows[-1]
        out["rev_cagr_5y"] = cagr(b["revenue"], a["revenue"], 5)
        out["pat_cagr_5y"] = cagr(b["pat"], a["pat"], 5)
    out["screener_growth"] = growth
    return out


def balance(ys, lender):
    rows = [y for y in ys if y["equity"] is not None]
    if not rows:
        return {}
    last = rows[-1]
    out = {
        "as_of": last["label"],
        "borrowings": last["borrowings"],
        "equity": last["equity"],
        "de": None if lender else last["de"],
        "cwip": last["cwip"],
        "investments": last["investments"],
        "history": [{k: y.get(k) for k in ("label", "borrowings", "equity", "de", "debtor_days",
                                            "inventory_days", "payable_days", "ccc", "wc_days")}
                    for y in rows[-6:]],
        "lender": lender,
    }
    wc = [y for y in rows if y.get("ccc") is not None or y.get("wc_days") is not None]
    if wc:
        out["ccc"] = wc[-1].get("ccc")
        out["wc_days"] = wc[-1].get("wc_days")
        out["debtor_days"] = wc[-1].get("debtor_days")
        out["inventory_days"] = wc[-1].get("inventory_days")
        out["payable_days"] = wc[-1].get("payable_days")
    if len(rows) >= 4:
        a = rows[-4]
        if a["borrowings"] and last["borrowings"] is not None:
            out["borrowings_x_3y"] = round(last["borrowings"] / a["borrowings"], 2)
    return out


def cash(ys):
    rows = [y for y in ys if y["cfo"] is not None and y["pat"] is not None]
    if not rows:
        return {}
    w = rows[-5:]
    cfo = sum(y["cfo"] for y in w)
    pat = sum(y["pat"] for y in w)
    fcf_rows = [y for y in w if y["fcf_est"] is not None]
    return {
        "window": f"{w[0]['label']}–{w[-1]['label']}",
        "years": len(w),
        "cfo_sum": round(cfo, 1),
        "pat_sum": round(pat, 1),
        "conversion": round(cfo / pat, 2) if pat > 0 else None,
        "fcf_sum": round(sum(y["fcf_est"] for y in fcf_rows), 1) if fcf_rows else None,
        "history": [{k: y.get(k) for k in ("label", "cfo", "pat", "capex_est", "fcf_est")} for y in w],
    }


def shareholding(page):
    t = page.get("shareholding")
    if not t:
        return {}
    prom = series(t, "Promoters")
    vals = [(c, v) for c, v in prom.items() if v is not None]
    if not vals:
        return {}
    out = {"promoter_latest": vals[-1][1], "as_of": vals[-1][0]}
    if len(vals) >= 5:
        out["promoter_change_4q"] = round(vals[-1][1] - vals[-5][1], 2)
    return out


def signals(snap, traj, bal, cq, shp, lender):
    s = []

    def add(kind, area, text):
        s.append({"kind": kind, "area": area, "text": text})

    lt = snap.get("latest", {})
    if lt.get("revenue_yoy") is not None:
        k = "good" if lt["revenue_yoy"] >= 12 else ("bad" if lt["revenue_yoy"] < 0 else "neutral")
        add(k, "growth", f"{snap['latest_quarter']} revenue {lt['revenue_yoy']:+.1f}% YoY")
    if lt.get("pat_yoy") is not None and lt.get("revenue_yoy") is not None:
        gap = lt["pat_yoy"] - lt["revenue_yoy"]
        if abs(gap) >= 8:
            k = "good" if gap > 0 else "bad"
            add(k, "growth", f"Profit grew {lt['pat_yoy']:+.1f}% vs revenue {lt['revenue_yoy']:+.1f}% in {snap['latest_quarter']}")
    r3 = traj.get("rev_cagr_3y")
    p3 = traj.get("pat_cagr_3y")
    if r3 is not None and p3 is not None:
        if p3 - r3 >= 5:
            add("good", "trajectory", f"3-yr profit CAGR {p3}% outpacing revenue {r3}% — operating leverage")
        elif r3 - p3 >= 5:
            add("bad", "trajectory", f"3-yr revenue CAGR {r3}% but profit only {p3}% — margins leaking")
    oc = traj.get("opm_change_3y")
    if oc is not None and abs(oc) >= 2 and not lender:
        add("good" if oc > 0 else "bad", "trajectory", f"Operating margin {oc:+.1f} pts over 3 years")
    if not lender and bal:
        de = bal.get("de")
        if de is not None:
            if de >= 1:
                add("bad", "balance", f"Debt-to-equity {de:.2f}x")
            elif bal.get("borrowings") is not None and bal.get("equity") and bal["borrowings"] < 0.05 * bal["equity"]:
                add("good", "balance", "Practically debt-free")
        bx = bal.get("borrowings_x_3y")
        if bx and bx >= 1.5 and (bal.get("borrowings") or 0) > 0.2 * (bal.get("equity") or 1):
            add("bad", "balance", f"Borrowings up {bx:.1f}x in 3 years")
        hist = [h for h in bal.get("history", []) if h.get("ccc") is not None]
        if len(hist) >= 4:
            d = hist[-1]["ccc"] - hist[-4]["ccc"]
            if abs(d) >= 15:
                add("bad" if d > 0 else "good", "balance",
                    f"Cash conversion cycle {hist[-4]['ccc']:.0f} → {hist[-1]['ccc']:.0f} days over 3 years")
        dh = [h for h in bal.get("history", []) if h.get("debtor_days") is not None]
        if len(dh) >= 4 and dh[-1]["debtor_days"] - dh[-4]["debtor_days"] >= 15:
            add("bad", "balance", f"Receivable days up {dh[-4]['debtor_days']:.0f} → {dh[-1]['debtor_days']:.0f}")
    if cq and not lender:
        c = cq.get("conversion")
        if c is not None:
            if c < 0.7:
                add("bad", "cash", f"Only {c:.0%} of {cq['years']}-yr profit turned into operating cash")
            elif c >= 0.9:
                add("good", "cash", f"{c:.0%} of {cq['years']}-yr profit converted to operating cash")
        f = cq.get("fcf_sum")
        if f is not None and f < 0:
            add("bad", "cash", f"Free cash flow negative over {cq['years']} years ({fmt_cr(f)})")
    if shp.get("promoter_change_4q") is not None and abs(shp["promoter_change_4q"]) >= 1:
        ch = shp["promoter_change_4q"]
        add("bad" if ch < 0 else "good", "ownership", f"Promoter holding {ch:+.2f} pts over 4 quarters")
    return s


def build(page):
    lender = is_lender(page)
    qs = quarterly(page)
    ys = annual(page)
    snap = snapshot(page, qs, ys)
    traj = trajectory(ys, page.get("growth", {}))
    bal = balance(ys, lender)
    cq = cash(ys)
    shp = shareholding(page)
    return {
        "symbol": page["symbol"],
        "name": page["name"],
        "basis": page.get("basis"),
        "source_url": page.get("url"),
        "bse_code": page.get("bse_code"),
        "lender": lender,
        "snapshot": snap,
        "quarters": [{k: q.get(k) for k in ("label", "revenue", "op", "opm", "pbt", "pat", "revenue_yoy", "pat_yoy", "op_yoy")} for q in qs[-8:]],
        "trajectory": traj,
        "balance": bal,
        "cash": cq,
        "ownership": shp,
        "signals": signals(snap, traj, bal, cq, shp, lender),
        "documents": page.get("documents", {}),
        "_qs": qs,
        "_ys": ys,
    }


def public(f):
    return {k: v for k, v in f.items() if not k.startswith("_")}
