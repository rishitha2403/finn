import time

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

_session = None


def session():
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": UA,
            "Accept-Language": "en-IN,en;q=0.9",
        })
        _session = s
    return _session


def get(url, tries=3, timeout=20, **kw):
    err = None
    for i in range(tries):
        try:
            r = session().get(url, timeout=timeout, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                err = RuntimeError(f"{r.status_code} from {url}")
                time.sleep(1.5 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            err = e
            time.sleep(1.0 * (i + 1))
    raise err


def get_pdf(url, max_bytes=18_000_000):
    headers = {}
    if "bseindia.com" in url:
        headers["Referer"] = "https://www.bseindia.com/"
    if "nseindia.com" in url:
        headers["Referer"] = "https://www.nseindia.com/"
    r = get(url, headers=headers, timeout=40)
    data = r.content
    if len(data) > max_bytes:
        raise ValueError(f"pdf too large ({len(data)} bytes)")
    if not data.startswith(b"%PDF"):
        raise ValueError("not a pdf")
    return data
