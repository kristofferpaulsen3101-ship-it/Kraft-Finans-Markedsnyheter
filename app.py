from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
import yfinance as yf
import feedparser
import smtplib, ssl, re, time, threading, logging, os, math
from email.utils import parsedate_to_datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Konfigurasjon ─────────────────────────────────────────────────────────────
EMAIL_FROM     = os.getenv("EMAIL_FROM", "")
EMAIL_TO       = os.getenv("EMAIL_TO", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
SMTP_HOST      = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "587"))
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")

INDICES = [
    # Global / MSCI
    {"ticker": "URTH",       "name": "MSCI World (URTH ETF)",  "currency": "USD", "region": "Global"},
    {"ticker": "IWDA.AS",    "name": "MSCI World (IWDA ETF)",  "currency": "USD", "region": "Global"},
    # USA
    {"ticker": "^GSPC",      "name": "S&P 500",                "currency": "USD", "region": "USA"},
    {"ticker": "^DJI",       "name": "Dow Jones",              "currency": "USD", "region": "USA"},
    {"ticker": "^IXIC",      "name": "NASDAQ Composite",       "currency": "USD", "region": "USA"},
    {"ticker": "^RUT",       "name": "Russell 2000",           "currency": "USD", "region": "USA"},
    # Europa
    {"ticker": "^FTSE",      "name": "FTSE 100",               "currency": "GBP", "region": "Europa"},
    {"ticker": "^GDAXI",     "name": "DAX",                    "currency": "EUR", "region": "Europa"},
    {"ticker": "^FCHI",      "name": "CAC 40",                 "currency": "EUR", "region": "Europa"},
    {"ticker": "^STOXX50E",  "name": "Euro Stoxx 50",          "currency": "EUR", "region": "Europa"},
    {"ticker": "^SSMI",      "name": "SMI (Sveits)",           "currency": "CHF", "region": "Europa"},
    {"ticker": "^AEX",       "name": "AEX (Amsterdam)",        "currency": "EUR", "region": "Europa"},
    # Norden
    {"ticker": "OSEBX.OL",   "name": "Oslo Børs OSEBX",        "currency": "NOK", "region": "Norden"},
    {"ticker": "^OMX",       "name": "OMX Stockholm",          "currency": "SEK", "region": "Norden"},
    {"ticker": "^OMXC25",    "name": "OMX Copenhagen 25",      "currency": "DKK", "region": "Norden"},
    {"ticker": "^OMXHPI",    "name": "OMX Helsinki",           "currency": "EUR", "region": "Norden"},
    # Asia / Pacific
    {"ticker": "^N225",      "name": "Nikkei 225",             "currency": "JPY", "region": "Asia"},
    {"ticker": "^HSI",       "name": "Hang Seng",              "currency": "HKD", "region": "Asia"},
    {"ticker": "000001.SS",  "name": "Shanghai Composite",     "currency": "CNY", "region": "Asia"},
    {"ticker": "^AXJO",      "name": "ASX 200",                "currency": "AUD", "region": "Asia/Pacific"},
    {"ticker": "^STI",       "name": "Straits Times (SG)",     "currency": "SGD", "region": "Asia"},
]

COMMODITIES = [
    # Edelmetaller
    {"ticker": "GC=F",   "name": "Gull",            "unit": "USD/oz",    "category": "Edelmetaller"},
    {"ticker": "SI=F",   "name": "Sølv",            "unit": "USD/oz",    "category": "Edelmetaller"},
    {"ticker": "PL=F",   "name": "Platina",         "unit": "USD/oz",    "category": "Edelmetaller"},
    {"ticker": "PA=F",   "name": "Palladium",       "unit": "USD/oz",    "category": "Edelmetaller"},
    # Energi
    {"ticker": "CL=F",   "name": "Råolje WTI",      "unit": "USD/fat",   "category": "Energi"},
    {"ticker": "BZ=F",   "name": "Råolje Brent",    "unit": "USD/fat",   "category": "Energi"},
    {"ticker": "NG=F",   "name": "Naturgass",       "unit": "USD/MMBtu", "category": "Energi"},
    {"ticker": "RB=F",   "name": "Bensin (RBOB)",   "unit": "USD/gal",   "category": "Energi"},
    # Industri-/basismetaller
    {"ticker": "HG=F",   "name": "Kobber",          "unit": "USD/lb",    "category": "Industri"},
    {"ticker": "ALI=F",  "name": "Aluminium",       "unit": "USD/lb",    "category": "Industri"},
    # Jordbruk
    {"ticker": "ZW=F",   "name": "Hvete",           "unit": "USc/bu",    "category": "Jordbruk"},
    {"ticker": "ZC=F",   "name": "Mais",            "unit": "USc/bu",    "category": "Jordbruk"},
    {"ticker": "ZS=F",   "name": "Soya",            "unit": "USc/bu",    "category": "Jordbruk"},
    {"ticker": "KC=F",   "name": "Kaffe",           "unit": "USc/lb",    "category": "Jordbruk"},
]

FX_PAIRS = [
    # NOK-par (viktigst for norsk investor)
    {"ticker": "USDNOK=X", "name": "USD/NOK", "group": "NOK-par"},
    {"ticker": "EURNOK=X", "name": "EUR/NOK", "group": "NOK-par"},
    {"ticker": "GBPNOK=X", "name": "GBP/NOK", "group": "NOK-par"},
    {"ticker": "SEKNOK=X", "name": "SEK/NOK", "group": "NOK-par"},
    {"ticker": "DKKNOK=X", "name": "DKK/NOK", "group": "NOK-par"},
    {"ticker": "CHFNOK=X", "name": "CHF/NOK", "group": "NOK-par"},
    {"ticker": "JPYNOK=X", "name": "JPY/NOK", "group": "NOK-par"},
    # Kryssrater
    {"ticker": "EURUSD=X", "name": "EUR/USD", "group": "Major"},
    {"ticker": "GBPUSD=X", "name": "GBP/USD", "group": "Major"},
    {"ticker": "USDJPY=X", "name": "USD/JPY", "group": "Major"},
    {"ticker": "USDCHF=X", "name": "USD/CHF", "group": "Major"},
    {"ticker": "EURSEK=X", "name": "EUR/SEK", "group": "Norden"},
    {"ticker": "EURDKK=X", "name": "EUR/DKK", "group": "Norden"},
    {"ticker": "USDSEK=X", "name": "USD/SEK", "group": "Norden"},
]

# FX til NOK for konvertering av indekser og råvarer
FX_MAP = {
    "USD": "USDNOK=X", "EUR": "EURNOK=X", "GBP": "GBPNOK=X",
    "JPY": "JPYNOK=X", "HKD": "HKDNOK=X", "CNY": None,
    "AUD": "AUDNOK=X", "SEK": "SEKNOK=X", "DKK": "DKKNOK=X",
    "CHF": "CHFNOK=X", "SGD": "SGDNOK=X", "NOK": None,
}

NEWS_FEEDS = [
    {"name": "E24 Økonomi",      "url": "https://e24.no/rss/",                                       "flag": "🇳🇴"},
    {"name": "DN Næringsliv",    "url": "https://www.dn.no/rss",                                      "flag": "🇳🇴"},
    {"name": "CNBC Finance",     "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",       "flag": "🇺🇸"},
    {"name": "MarketWatch",      "url": "https://feeds.marketwatch.com/marketwatch/topstories/",      "flag": "🇺🇸"},
    {"name": "BBC Business",     "url": "https://feeds.bbci.co.uk/news/business/rss.xml",             "flag": "🌍"},
    {"name": "Investing.com",    "url": "https://www.investing.com/rss/news.rss",                     "flag": "🌍"},
]

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: dict = {}

def get_cached(key, fn, ttl=300):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < ttl:
        return _cache[key]["data"]
    data = fn()
    _cache[key] = {"data": data, "ts": now}
    return data

# ── FX-henting med daglig endring ─────────────────────────────────────────────
def _fetch_fx():
    """Returnerer dict: ccy -> {rate, prev, change_pct}"""
    fx = {"NOK": {"rate": 1.0, "prev": 1.0, "change_pct": 0.0}}
    fx_list = [v for v in FX_MAP.values() if v]
    try:
        dl = yf.download(fx_list, period="5d", progress=False, auto_adjust=True)
        close = dl["Close"]
        if not hasattr(close, "columns"):
            close = close.to_frame(name=fx_list[0])
        for ccy, tkr in FX_MAP.items():
            if tkr and tkr in close.columns:
                s = close[tkr].dropna()
                if len(s) >= 1:
                    today = float(s.iloc[-1])
                    prev  = float(s.iloc[-2]) if len(s) >= 2 else today
                    fx[ccy] = {
                        "rate":       today,
                        "prev":       prev,
                        "change_pct": (today / prev - 1) * 100 if prev else 0.0,
                    }
    except Exception as e:
        log.error(f"FX fetch: {e}")
    return fx

def _nok_return(local_pct: float, ccy: str, fx: dict) -> tuple[float, float]:
    """
    Beregn avkastning i NOK og FX-effekten.
    Returnerer (nok_pct, fx_effect_pct)
    """
    if ccy == "NOK":
        return local_pct, 0.0
    fx_pct = fx.get(ccy, {}).get("change_pct", 0.0)
    nok_pct = ((1 + local_pct / 100) * (1 + fx_pct / 100) - 1) * 100
    return round(nok_pct, 2), round(nok_pct - local_pct, 2)

# ── Indekser ──────────────────────────────────────────────────────────────────
def _fetch_indices():
    tickers = [i["ticker"] for i in INDICES]
    result  = []
    try:
        dl    = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
        fx    = _fetch_fx()
        close = dl["Close"]
        if not hasattr(close, "columns"):
            close = close.to_frame(name=tickers[0])
        for idx in INDICES:
            t = idx["ticker"]
            try:
                if t not in close.columns:
                    raise KeyError(t)
                s = close[t].dropna()
                if len(s) < 1:
                    raise ValueError("no data")
                price     = float(s.iloc[-1])
                prev      = float(s.iloc[-2]) if len(s) >= 2 else price
                chg       = price - prev
                local_pct = chg / prev * 100 if prev else 0.0
                rate      = fx.get(idx["currency"], {"rate": 1.0})["rate"]
                nok_pct, fx_eff = _nok_return(local_pct, idx["currency"], fx)
                result.append({
                    **idx,
                    "price":      round(price, 2),
                    "price_nok":  round(price * rate, 2),
                    "change":     round(chg, 2),
                    "change_pct": round(local_pct, 2),   # % i lokal valuta
                    "nok_pct":    nok_pct,                # % i NOK
                    "fx_effect":  fx_eff,                 # valuta-bidrag
                    "fx_rate":    round(rate, 4),
                    "error":      None,
                })
            except Exception as e:
                result.append({**idx, "price": None, "price_nok": None,
                               "change": None, "change_pct": None,
                               "nok_pct": None, "fx_effect": None,
                               "fx_rate": None, "error": str(e)})
    except Exception as e:
        log.error(f"Index fetch: {e}")
        result = [{**i, "price": None, "price_nok": None, "change": None,
                   "change_pct": None, "nok_pct": None, "fx_effect": None,
                   "fx_rate": None, "error": "Feil"} for i in INDICES]
    return result

# ── Råvarer ───────────────────────────────────────────────────────────────────
def _fetch_commodities():
    tickers = [c["ticker"] for c in COMMODITIES]
    result  = []
    try:
        dl    = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
        fx    = _fetch_fx()
        close = dl["Close"]
        if not hasattr(close, "columns"):
            close = close.to_frame(name=tickers[0])
        for com in COMMODITIES:
            t = com["ticker"]
            try:
                if t not in close.columns:
                    raise KeyError(t)
                s = close[t].dropna()
                if len(s) < 1:
                    raise ValueError("no data")
                price     = float(s.iloc[-1])
                prev      = float(s.iloc[-2]) if len(s) >= 2 else price
                chg       = price - prev
                usd_pct   = chg / prev * 100 if prev else 0.0
                usd_rate  = fx.get("USD", {"rate": 1.0})["rate"]
                nok_pct, fx_eff = _nok_return(usd_pct, "USD", fx)
                result.append({
                    **com,
                    "currency":   "USD",
                    "price":      round(price, 2),
                    "price_nok":  round(price * usd_rate, 2),
                    "change":     round(chg, 2),
                    "change_pct": round(usd_pct, 2),
                    "nok_pct":    nok_pct,
                    "fx_effect":  fx_eff,
                    "error":      None,
                })
            except Exception as e:
                result.append({**com, "currency": "USD", "price": None,
                               "price_nok": None, "change": None,
                               "change_pct": None, "nok_pct": None,
                               "fx_effect": None, "error": str(e)})
    except Exception as e:
        log.error(f"Commodity fetch: {e}")
        result = [{**c, "currency": "USD", "price": None, "price_nok": None,
                   "change": None, "change_pct": None, "nok_pct": None,
                   "fx_effect": None, "error": "Feil"} for c in COMMODITIES]
    return result

# ── Valutapar ─────────────────────────────────────────────────────────────────
def _fetch_fx_pairs():
    tickers = [p["ticker"] for p in FX_PAIRS]
    result  = []
    try:
        dl    = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
        close = dl["Close"]
        if not hasattr(close, "columns"):
            close = close.to_frame(name=tickers[0])
        for pair in FX_PAIRS:
            t = pair["ticker"]
            try:
                if t not in close.columns:
                    raise KeyError(t)
                s = close[t].dropna()
                if len(s) < 1:
                    raise ValueError("no data")
                rate  = float(s.iloc[-1])
                prev  = float(s.iloc[-2]) if len(s) >= 2 else rate
                chg   = rate - prev
                chg_p = chg / prev * 100 if prev else 0.0
                result.append({
                    **pair,
                    "rate":       round(rate, 4),
                    "prev":       round(prev, 4),
                    "change":     round(chg, 4),
                    "change_pct": round(chg_p, 2),
                    "error":      None,
                })
            except Exception as e:
                result.append({**pair, "rate": None, "prev": None,
                               "change": None, "change_pct": None, "error": str(e)})
    except Exception as e:
        log.error(f"FX pairs fetch: {e}")
        result = [{**p, "rate": None, "prev": None,
                   "change": None, "change_pct": None, "error": "Feil"} for p in FX_PAIRS]
    return result

# ── Nyheter ───────────────────────────────────────────────────────────────────
def _parse_date(published_str: str):
    """Parser RSS-dato til datetime-objekt. Returnerer None ved feil."""
    if not published_str:
        return None
    try:
        return parsedate_to_datetime(published_str)
    except Exception:
        pass
    try:
        from datetime import timezone
        import dateutil.parser
        return dateutil.parser.parse(published_str).replace(tzinfo=timezone.utc)
    except Exception:
        return None

def _fmt_date_no(published_str: str) -> str:
    """Formater dato til norsk format: 'i dag 14:32', 'i går 09:15', 'man 17. mar 08:00'"""
    dt = _parse_date(published_str)
    if not dt:
        return ""
    from datetime import timezone
    now   = datetime.now(timezone.utc)
    delta = now - dt
    time_str = dt.strftime("%H:%M")
    if delta.days == 0:
        return f"i dag {time_str}"
    elif delta.days == 1:
        return f"i går {time_str}"
    else:
        days_no = ["man","tir","ons","tor","fre","lør","søn"]
        day     = days_no[dt.weekday()]
        return f"{day} {dt.day}. {dt.strftime('%b').lower()} {time_str}"

def _fetch_news():
    items = []
    for feed_cfg in NEWS_FEEDS:
        try:
            f = feedparser.parse(feed_cfg["url"])
            for e in f.entries[:10]:
                raw   = e.get("summary", e.get("description", ""))
                clean = re.sub(r"<[^>]+>", " ", raw).strip()
                clean = re.sub(r"\s+", " ", clean)[:400]
                published = e.get("published", "")
                dt        = _parse_date(published)
                items.append({
                    "title":      e.get("title", ""),
                    "summary":    clean,
                    "link":       e.get("link", "#"),
                    "published":  published,
                    "published_fmt": _fmt_date_no(published),
                    "dt_ts":      dt.timestamp() if dt else 0,
                    "source":     feed_cfg["name"],
                    "flag":       feed_cfg["flag"],
                })
        except Exception as e:
            log.error(f"Feed {feed_cfg['name']}: {e}")

    # Sorter nyeste først, filtrer bort artikler eldre enn 7 dager
    from datetime import timezone
    cutoff = (datetime.now(timezone.utc).timestamp()) - (7 * 24 * 3600)
    items  = [a for a in items if a["dt_ts"] == 0 or a["dt_ts"] >= cutoff]
    items.sort(key=lambda x: x["dt_ts"], reverse=True)
    return items[:25]

# ── AI-oppsummering ───────────────────────────────────────────────────────────
def ai_summarize(articles: list) -> str | None:
    if not ANTHROPIC_KEY:
        return None
    try:
        import anthropic
        client    = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        headlines = "\n".join([f"• {a['title']}" for a in articles[:12]])
        resp = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content":
                f"""Du er senioranalytiker ved Kraft Finans AS. Lag en kort profesjonell markedsoppsummering på norsk:

{headlines}

Skriv 3 korte avsnitt: 1) Markedssentiment, 2) Viktigste hendelser, 3) Hva investorer bør følge med på."""
            }]
        )
        return resp.content[0].text
    except Exception as e:
        log.error(f"AI summarize: {e}")
        return None

# ── E-post ────────────────────────────────────────────────────────────────────
def send_morning_email():
    if not (EMAIL_FROM and EMAIL_TO and EMAIL_PASSWORD):
        log.warning("E-post ikke konfigurert – hopper over morgenrapport")
        return
    try:
        indices  = get_cached("indices", _fetch_indices)
        articles = get_cached("news", _fetch_news, ttl=600)
        summary  = ai_summarize(articles)
        date_str = datetime.now().strftime("%d.%m.%Y")

        ai_block = ""
        if summary:
            ai_block = f"""
            <div style="background:#003087;color:#fff;padding:20px;border-radius:8px;margin:20px 0">
              <h3 style="margin:0 0 12px;color:#C49A00">🤖 AI-Markedsanalyse</h3>
              <p style="line-height:1.7;margin:0;font-size:14px">{summary.replace(chr(10), '<br>')}</p>
            </div>"""

        reg_order = ["Global", "USA", "Europa", "Norden", "Asia", "Asia/Pacific"]
        idx_html  = ""
        for reg in reg_order:
            rows = [i for i in indices if i["region"] == reg and i["price"]]
            if not rows:
                continue
            idx_html += f"""
            <h3 style="color:#003087;margin:20px 0 8px">{reg}</h3>
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border-collapse:collapse;font-size:13px">
              <tr style="background:#003087;color:#fff">
                <th style="padding:7px 12px;text-align:left">Indeks</th>
                <th style="padding:7px 12px;text-align:right">Kurs</th>
                <th style="padding:7px 12px;text-align:right">% Lokal</th>
                <th style="padding:7px 12px;text-align:right">% i NOK</th>
                <th style="padding:7px 12px;text-align:right">FX-effekt</th>
              </tr>"""
            for r in rows:
                lc  = "#007a3d" if r["change_pct"] >= 0 else "#c00000"
                nc  = "#007a3d" if r["nok_pct"]    >= 0 else "#c00000"
                fc  = "#007a3d" if r["fx_effect"]  >= 0 else "#c00000"
                ls  = "+" if r["change_pct"] >= 0 else ""
                ns  = "+" if r["nok_pct"]    >= 0 else ""
                fs  = "+" if r["fx_effect"]  >= 0 else ""
                idx_html += f"""
              <tr style="border-bottom:1px solid #eee">
                <td style="padding:6px 12px">{r['name']}</td>
                <td style="padding:6px 12px;text-align:right">{r['price']:,.2f} {r['currency']}</td>
                <td style="padding:6px 12px;text-align:right;color:{lc};font-weight:bold">{ls}{r['change_pct']:.2f}%</td>
                <td style="padding:6px 12px;text-align:right;color:{nc};font-weight:bold">{ns}{r['nok_pct']:.2f}%</td>
                <td style="padding:6px 12px;text-align:right;color:{fc}">{fs}{r['fx_effect']:.2f}%</td>
              </tr>"""
            idx_html += "</table>"

        news_html = "".join([f"""
        <div style="margin:10px 0;padding:12px 15px;border-left:3px solid #C49A00;background:#f9f9f9">
          <strong>{a['title']}</strong><br>
          <small style="color:#888">{a['flag']} {a['source']}</small><br>
          <span style="font-size:13px;color:#444">{a['summary']}</span>
        </div>""" for a in articles[:8]])

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Calibri,Arial,sans-serif;max-width:800px;margin:0 auto;background:#fff;color:#333">
  <div style="background:#003087;padding:28px;text-align:center">
    <div><span style="font-size:26px;font-weight:900;letter-spacing:3px;color:#fff">KRAFT</span>
         <span style="font-size:26px;font-weight:300;letter-spacing:3px;color:#C49A00">FINANS</span></div>
    <p style="color:#aac4e8;margin:6px 0 0;font-size:15px">Daglig Markedsoppsummering · {date_str}</p>
  </div>
  <div style="padding:24px">
    {ai_block}
    <h2 style="color:#003087;border-bottom:2px solid #C49A00;padding-bottom:8px">📈 Markedsdata</h2>
    {idx_html}
    <h2 style="color:#003087;border-bottom:2px solid #C49A00;padding-bottom:8px;margin-top:32px">📰 Nyheter</h2>
    {news_html}
  </div>
  <div style="background:#f4f4f4;padding:14px;text-align:center;color:#999;font-size:12px">
    Kraft Finans AS · Automatisk generert · {datetime.now().strftime('%d.%m.%Y %H:%M')}
  </div>
</body></html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Kraft Finans – Markedsrapport {date_str}"
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg.attach(MIMEText(html, "html", "utf-8"))

        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
            srv.starttls(context=ctx)
            srv.login(EMAIL_FROM, EMAIL_PASSWORD)
            srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_bytes())
        log.info(f"Morgenrapport sendt → {EMAIL_TO}")
    except Exception as e:
        log.error(f"E-postsending feilet: {e}")

# ── Ruter ─────────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    try:
        indices = get_cached("indices", _fetch_indices)
        hero    = {i["ticker"]: i for i in indices if i["price"]}
    except Exception:
        hero = {}
    return render_template("home.html", hero=hero)

@app.route("/indekser")
def indekser():
    return render_template("indices.html")

@app.route("/nyheter")
def nyheter():
    return render_template("news.html")

@app.route("/api/indices")
def api_indices():
    data = get_cached("indices", _fetch_indices)
    return jsonify({"data": data, "ts": datetime.now().strftime("%H:%M:%S %d.%m.%Y")})

@app.route("/api/commodities")
def api_commodities():
    data = get_cached("commodities", _fetch_commodities)
    return jsonify({"data": data, "ts": datetime.now().strftime("%H:%M:%S %d.%m.%Y")})

@app.route("/api/currencies")
def api_currencies():
    data = get_cached("fx_pairs", _fetch_fx_pairs)
    return jsonify({"data": data, "ts": datetime.now().strftime("%H:%M:%S")})

@app.route("/api/news")
def api_news():
    articles = get_cached("news", _fetch_news, ttl=600)
    return jsonify({"articles": articles, "ts": datetime.now().strftime("%H:%M:%S")})

@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    articles = request.get_json(force=True).get("articles", [])
    return jsonify({"summary": ai_summarize(articles)})

@app.route("/api/history/<path:ticker>")
def api_history(ticker):
    period = request.args.get("period", "1y")
    ccy    = request.args.get("ccy", "NOK").upper()
    PERIOD_MAP = {
        "1d":  ("1d",  "5m"),
        "1w":  ("5d",  "1h"),
        "1m":  ("1mo", "1d"),
        "ytd": ("ytd", "1d"),
        "1y":  ("1y",  "1wk"),
        "3y":  ("3y",  "1wk"),
        "5y":  ("5y",  "1mo"),
        "10y": ("10y", "3mo"),
    }
    yf_period, interval = PERIOD_MAP.get(period, ("1y", "1wk"))
    try:
        tkr  = yf.Ticker(ticker)
        hist = (tkr.history(start=f"{date.today().year}-01-01", interval=interval)
                if yf_period == "ytd"
                else tkr.history(period=yf_period, interval=interval))
        if hist.empty:
            return jsonify({"error": "Ingen data", "labels": [], "prices": []})

        labels = []
        for dt in hist.index:
            if period == "1d":
                labels.append(dt.strftime("%H:%M"))
            elif period in ("1w", "1m", "ytd"):
                labels.append(dt.strftime("%d.%m"))
            else:
                labels.append(dt.strftime("%b %y"))

        prices = [round(float(p), 2) if not math.isnan(float(p)) else None
                  for p in hist["Close"]]
        valid  = [p for p in prices if p is not None]
        first, last = (valid[0], valid[-1]) if valid else (0, 0)
        chg    = last - first
        chg_p  = (chg / first * 100) if first else 0

        # NOK-historikk
        prices_nok     = None
        nok_change_pct = None
        if ccy != "NOK":
            fx_tkr = FX_MAP.get(ccy)
            if fx_tkr:
                try:
                    fx_hist = (yf.Ticker(fx_tkr).history(start=f"{date.today().year}-01-01", interval=interval)
                               if yf_period == "ytd"
                               else yf.Ticker(fx_tkr).history(period=yf_period, interval=interval))
                    if not fx_hist.empty:
                        fx_aligned = fx_hist["Close"].reindex(hist.index, method="ffill")
                        prices_nok = []
                        for p, fx in zip(hist["Close"], fx_aligned):
                            try:
                                val = float(p) * float(fx)
                                prices_nok.append(None if math.isnan(val) else round(val, 2))
                            except Exception:
                                prices_nok.append(None)
                        valid_nok = [p for p in prices_nok if p is not None]
                        if valid_nok:
                            f_nok, l_nok = valid_nok[0], valid_nok[-1]
                            nok_change_pct = round((l_nok / f_nok - 1) * 100, 2) if f_nok else 0
                except Exception as e:
                    log.error(f"FX history {fx_tkr}: {e}")

        return jsonify({
            "ticker": ticker, "period": period, "ccy": ccy,
            "labels": labels, "prices": prices,
            "prices_nok": prices_nok, "nok_change_pct": nok_change_pct,
            "change": round(chg, 2), "change_pct": round(chg_p, 2),
            "first": first, "last": last,
        })
    except Exception as e:
        log.error(f"History {ticker} {period}: {e}")
        return jsonify({"error": str(e), "labels": [], "prices": []})

@app.route("/api/send-test-email", methods=["POST"])
def api_test_email():
    threading.Thread(target=send_morning_email, daemon=True).start()
    return jsonify({"ok": True, "msg": "Sender e-post..."})

# ── Planlegger ────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone="Europe/Oslo")
scheduler.add_job(send_morning_email, "cron", hour=8, minute=0, id="morgenrapport")
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
