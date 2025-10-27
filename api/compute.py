import os, json, math
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
from fredapi import Fred
import yfinance as yf

KV_URL = os.getenv("KV_REST_API_URL")
KV_TOKEN = os.getenv("KV_REST_API_TOKEN")
FRED_KEY = os.getenv("FRED_API_KEY")

TELEGRAM_BOT = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

KV_KEY = "macro:latest"   # KV record for latest snapshot
ALERT_THRESHOLD = int(os.getenv("ALERT_THRESHOLD", "6"))

def kv_set(key: str, value: dict) -> None:
    assert KV_URL and KV_TOKEN, "Vercel KV env vars not set"
    r = requests.post(
        f"{KV_URL}/set",
        headers={"Authorization": f"Bearer {KV_TOKEN}"},
        json={"key": key, "value": json.dumps(value)}
    )
    r.raise_for_status()

def kv_get(key: str):
    assert KV_URL and KV_TOKEN
    r = requests.post(
        f"{KV_URL}/get",
        headers={"Authorization": f"Bearer {KV_TOKEN}"},
        json={"key": key}
    )
    r.raise_for_status()
    data = r.json()
    return json.loads(data["result"]) if data.get("result") else None

def tg_alert(text: str):
    if not (TELEGRAM_BOT and TELEGRAM_CHAT):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "Markdown"},
            timeout=15
        )
    except Exception as e:
        print("Telegram alert failed:", e)

def handler(request):
    # 1) Fetch FRED
    fred = Fred(api_key=FRED_KEY) if FRED_KEY else Fred()
    def fred_series(code):
        s = fred.get_series(code)
        s.index = pd.to_datetime(s.index)
        return s

    fedfunds   = fred_series("FEDFUNDS").resample("M").last()
    pce_core   = fred_series("PCEPILFE").resample("M").last()
    hy_oas     = fred_series("BAMLH0A0HYM2").last("1D")
    ig_oas     = fred_series("BAMLC0A0CM").last("1D")
    t5yie      = fred_series("T5YIE").last("1D")
    dgs10      = fred_series("DGS10")
    dgs2       = fred_series("DGS2")
    nfib       = fred_series("NFIBSBOIX").last("1D")

    # 2) Fetch Yahoo data (≈ last 800 days)
    end = datetime.utcnow()
    start = end - timedelta(days=800)
    tickers = ["^VIX", "^VXV", "SPY", "RSP", "GC=F", "SI=F", "DX=F", "DX-Y.NYB"]
    yf_data = yf.download(tickers, start=start, end=end, progress=False)["Adj Close"]

    # 3) Compute indicators
    core_yoy = 100 * (pce_core / pce_core.shift(12) - 1.0)
    real_ffr = float(fedfunds.iloc[-1] - core_yoy.iloc[-1])

    def last_val(s):
        s = s.dropna()
        return float(s.iloc[-1]) if len(s) else np.nan

    hy = last_val(hy_oas); ig = last_val(ig_oas); be5 = last_val(t5yie); nf = last_val(nfib)

    vix = yf_data["^VIX"].dropna(); vxv = yf_data["^VXV"].dropna()
    common_v = vix.index.intersection(vxv.index)
    vix_term = float((vix.loc[common_v] - vxv.loc[common_v]).iloc[-1])

    dxy = yf_data["DX=F"].dropna()
    if dxy.empty and "DX-Y.NYB" in yf_data.columns:
        dxy = yf_data["DX-Y.NYB"].dropna()
    dxy_level = float(dxy.iloc[-1]) if not dxy.empty else np.nan

    gold = yf_data["GC=F"].dropna(); silver = yf_data["SI=F"].dropna()
    gs = float((gold.iloc[-1] / silver.iloc[-1])) if (len(gold) and len(silver)) else np.nan

    rsp = yf_data["RSP"].dropna(); spy = yf_data["SPY"].dropna()
    rel = (rsp / spy).dropna()
    ma50 = rel.rolling(50).mean(); ma200 = rel.rolling(200).mean()
    breadth_spread = float(ma50.iloc[-1] - ma200.iloc[-1]) if len(ma200.dropna()) else np.nan
    breadth_slope  = float(ma50.diff(20).iloc[-1]) if len(ma50.dropna()) else np.nan

    curve = (dgs10 - dgs2).dropna()
    curve_latest = float(curve.iloc[-1]) if len(curve) else np.nan
    curve_90 = (dgs10 - dgs2).dropna().last("90D")
    resteepen = bool(len(curve_90) > 20 and curve_90.iloc[0] < 0 and curve_90.iloc[-1] > 0 and curve_90.iloc[-1] > curve_90.iloc[-20])

    # 4) Breaches
    breaches = {
        "real_ffr_gt_2pct": real_ffr > 2.0,
        "hy_spread_gt_5pct": hy > 5.0,
        "ig_spread_gt_1_5pct": ig > 1.5,
        "vix_term_inverted": vix_term < 0.0,
        "dxy_gt_115": (dxy_level > 115.0) if not math.isnan(dxy_level) else False,
        "gs_ratio_lt_60": (gs < 60.0) if not math.isnan(gs) else False,
        "breakeven5y_gt_3pct": be5 > 3.0,
        "breadth_trend_bad": (breadth_spread < 0) and (breadth_slope < 0),
        "curve_resteepening": resteepen,
        "nfib_lt_90": nf < 90.0
    }
    breach_count = int(sum(breaches.values()))

    snapshot = {
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "values": {
            "real_ffr": real_ffr,
            "hy_spread_pct": hy,
            "ig_spread_pct": ig,
            "vix_term_spread": vix_term,
            "dxy_level": dxy_level,
            "gold_silver_ratio": gs,
            "breakeven_5y_pct": be5,
            "breadth_ma50_minus_ma200": breadth_spread,
            "breadth_ma50_slope_20d": breadth_slope,
            "curve_10y_2y_bps": curve_latest,
            "nfib_index": nf
        },
        "breaches": breaches,
        "breach_count": breach_count
    }

    # 5) Persist to KV, maybe alert
    kv_set(KV_KEY, snapshot)
    if breach_count >= ALERT_THRESHOLD:
        tg_alert(f"*ALERT* Macro Stress {breach_count} (>= {ALERT_THRESHOLD})")

    # 6) Respond JSON (useful for manual runs)
    return (json.dumps(snapshot), 200, {"Content-Type": "application/json"})

# Vercel Python entrypoint
def handler_wrapper(request):
    return handler(request)

# Alias for Vercel
handler = handler_wrapper
