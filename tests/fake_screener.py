def _table(cols, rows):
    head = "<th class='text'></th>" + "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for name, vals in rows.items():
        cells = "".join(f"<td>{'' if v is None else (f'{v:,.0f}' if abs(v) >= 1000 else v)}</td>" for v in vals)
        body += (f"<tr><td class='text'><button class='button-plain'>{name}&nbsp;<span>+</span></button></td>{cells}</tr>")
    body += "<tr><td class='text'>Raw PDF</td></tr>"
    return f"<table class='data-table responsive-text-nowrap'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


QCOLS = ["Sep 2023", "Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025", "Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026", "Jun 2026", "Sep 2026"]
YCOLS = ["Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026", "TTM"]


def quarters():
    sales = [1000, 1040, 1080, 1100, 1150, 1190, 1240, 1260, 1320, 1360, 1420, 1450, 1520]
    op = [round(s * m) for s, m in zip(sales, [0.20, 0.20, 0.21, 0.21, 0.21, 0.22, 0.22, 0.21, 0.22, 0.22, 0.23, 0.22, 0.23])]
    opm = [round(o / s * 100) for o, s in zip(op, sales)]
    pbt = [o - 40 for o in op]
    pat = [round(p * 0.75) for p in pbt]
    return {"Sales": sales, "Expenses": [s - o for s, o in zip(sales, op)], "Operating Profit": op, "OPM %": opm,
            "Profit before tax": pbt, "Tax %": [25] * 13, "Net Profit": pat, "EPS in Rs": [1.0] * 13}


def annual():
    sales = [2800, 3000, 3400, 3900, 4400, 4900, 5600, 5970]
    op = [560, 600, 700, 820, 940, 1080, 1250, 1350]
    return {"Sales": sales, "Expenses": [s - o for s, o in zip(sales, op)], "Operating Profit": op,
            "OPM %": [round(o / s * 100) for o, s in zip(op, sales)], "Other Income": [20] * 8,
            "Interest": [30] * 8, "Depreciation": [80, 90, 100, 110, 120, 130, 140, 140],
            "Profit before tax": [o - 110 for o in op], "Net Profit": [round((o - 110) * 0.75) for o in op]}


def balance():
    return {"Equity Capital": [100] * 7, "Reserves": [1500, 1800, 2100, 2500, 2900, 3400, 4000],
            "Borrowings": [400, 380, 350, 600, 900, 1200, 1300], "Other Liabilities": [500] * 7,
            "Total Liabilities": [2500] * 7, "Fixed Assets": [1000, 1050, 1120, 1300, 1500, 1700, 1850],
            "CWIP": [50, 60, 80, 150, 200, 120, 100], "Investments": [300] * 7, "Other Assets": [1150] * 7,
            "Total Assets": [2500] * 7}


def cashflow():
    return {"Cash from Operating Activity": [350, 420, 480, 520, 560, 640, 700],
            "Cash from Investing Activity": [-200, -230, -260, -400, -450, -380, -350],
            "Cash from Financing Activity": [-100] * 7, "Net Cash Flow": [50] * 7}


def ratios():
    return {"Debtor Days": [50, 52, 55, 60, 66, 72, 75], "Inventory Days": [80] * 7, "Days Payable": [60] * 7,
            "Cash Conversion Cycle": [70, 72, 75, 80, 86, 92, 95], "Working Capital Days": [40] * 7,
            "ROCE %": [20, 21, 22, 22, 23, 23, 24]}


def page(name="Fake Industries Ltd", bse="512345", lender=False):
    q = quarters()
    if lender:
        q = {"Revenue": q["Sales"], "Interest": [400] * 13, "Expenses": [200] * 13,
             "Financing Profit": q["Operating Profit"], "Financing Margin %": q["OPM %"],
             "Profit before tax": q["Profit before tax"], "Net Profit": q["Net Profit"]}
    ycols = YCOLS[:-1]
    shp = {"Promoters": [55.0, 54.8, 54.5, 54.0, 53.2], "FIIs": [20, 21, 21, 22, 23]}
    return f"""<html><body>
<div class='company-links'><a href='https://www.bseindia.com/x'>BSE: {bse}</a> <a href='https://www.nseindia.com/x'>NSE: FAKE</a></div>
<h1 class='h2'>{name}</h1>
<div class='company-profile'><div class='about'><p>Fake Industries makes widgets for utilities.</p></div></div>
<ul id='top-ratios'>
<li><span class='name'>Market Cap</span><span class='nowrap value'>₹ <span class='number'>45,000</span> Cr.</span></li>
<li><span class='name'>Current Price</span><span class='nowrap value'>₹ <span class='number'>1,234</span></span></li>
<li><span class='name'>Stock P/E</span><span class='nowrap value'><span class='number'>42.5</span></span></li>
<li><span class='name'>ROCE</span><span class='nowrap value'><span class='number'>24.1</span> %</span></li>
<li><span class='name'>ROE</span><span class='nowrap value'><span class='number'>19.0</span> %</span></li>
<li><span class='name'>High / Low</span><span class='nowrap value'>₹ <span class='number'>1,500</span> / <span class='number'>900</span></span></li>
</ul>
<section id='quarters'>{_table(QCOLS, q)}</section>
<section id='profit-loss'>{_table(YCOLS, annual())}
<table class='ranges-table'><tr><th colspan='2'>Compounded Sales Growth</th></tr><tr><td>10 Years:</td><td>14%</td></tr><tr><td>3 Years:</td><td>13%</td></tr></table>
</section>
<section id='balance-sheet'>{_table(ycols, balance())}</section>
<section id='cash-flow'>{_table(ycols, cashflow())}</section>
<section id='ratios'>{_table(ycols, ratios())}</section>
<section id='shareholding'><div id='quarterly-shp'>{_table(['Sep 2025', 'Dec 2025', 'Mar 2026', 'Jun 2026', 'Sep 2026'], shp)}</div></section>
<section id='documents'>
<div class='documents annual-reports'><ul class='list-links'>
<li><a href='https://www.bseindia.com/bseplus/AnnualReport/512345/ar2026.pdf'>Financial Year 2026<div>from bse</div></a></li>
</ul></div>
<div class='documents concalls'><ul class='list-links'>
<li><div class='ink-600'>Oct 2026</div><a class='concall-link' href='https://www.bseindia.com/t/oct26.pdf'>Transcript</a><a class='concall-link' href='/ppt'>PPT</a><a class='concall-link' href='https://youtu.be/x'>REC</a></li>
<li><div class='ink-600'>Jul 2026</div><a class='concall-link' href='https://www.bseindia.com/t/jul26.pdf'>Transcript</a></li>
<li><div class='ink-600'>May 2026</div><a class='concall-link' href='https://www.bseindia.com/t/may26.pdf'>Transcript</a></li>
<li><div class='ink-600'>Jan 2026</div><a class='concall-link' href='https://www.bseindia.com/t/jan26.pdf'>Transcript</a></li>
<li><div class='ink-600'>Oct 2025</div><a class='concall-link' href='https://www.bseindia.com/t/oct25.pdf'>Transcript</a></li>
</ul></div>
</section>
</body></html>"""
