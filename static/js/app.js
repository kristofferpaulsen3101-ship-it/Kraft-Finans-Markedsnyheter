/* ══════════════════════════════════════════════════════════════════════════
   Kraft Finans – Markedsportal JS
   ══════════════════════════════════════════════════════════════════════════ */

// ── Klokke ──────────────────────────────────────────────────────────────────
function updateClock() {
  const el = document.getElementById("clockDisplay");
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleTimeString("nb-NO", {
    hour:   "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}
setInterval(updateClock, 1000);
updateClock();

// ── Ticker bar ───────────────────────────────────────────────────────────────
const TICKER_TICKERS = ["^GSPC", "^GDAXI", "^OSEBX", "^N225", "^FTSE", "URTH", "^IXIC", "^STOXX50E"];

async function loadTicker() {
  const el = document.getElementById("tickerContent");
  if (!el) return;
  try {
    const res  = await fetch("/api/indices");
    const json = await res.json();
    const map  = {};
    json.data.forEach(d => { map[d.ticker] = d; });

    const items = json.data.filter(d => d.price).slice(0, 14);
    if (!items.length) return;

    // Double the items for seamless loop
    const buildItems = (arr) => arr.map(d => {
      const up   = d.change_pct >= 0;
      const sign = up ? "+" : "";
      return `<span class="ticker-item">
        <span class="ticker-name">${d.name}</span>
        <span class="ticker-price">${fmtNum(d.price)}</span>
        <span class="ticker-chg ${up ? 'up' : 'down'}">${sign}${d.change_pct.toFixed(2)}%</span>
      </span>`;
    }).join("");

    el.innerHTML = buildItems(items) + buildItems(items);
  } catch (e) {
    // silently fail
  }
}

loadTicker();
setInterval(loadTicker, 120000);

// ── Hjelp-funksjoner ─────────────────────────────────────────────────────────
function fmtNum(n, decimals) {
  if (n == null || isNaN(n)) return "—";
  const d = decimals !== undefined ? decimals : (n >= 1000 ? 0 : n >= 100 ? 2 : 2);
  return new Intl.NumberFormat("nb-NO", {
    minimumFractionDigits: d,
    maximumFractionDigits: d
  }).format(n);
}
