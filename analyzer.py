"""
Coal Capital Club — Swing Trading Engine v1.1
Fix: Yahoo Finance block pada GitHub Actions (curl_cffi + retry + stale fallback)
"""
import json
import os
import sys
import time
from datetime import datetime

import yfinance as yf
import pandas as pd
import numpy as np

# --- Anti-blokir: impersonate browser via curl_cffi ---
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL = True
except ImportError:
    HAS_CURL = False

with open("config.json") as f:
    CFG = json.load(f)

STOCKS = CFG["stocks"]
IND = CFG["indicators"]
RISK = CFG["risk_management"]
THRESH = CFG["scoring_thresholds"]

# ============================================================
# DATA FETCHING (ROBUST)
# ============================================================
def make_session():
    return curl_requests.Session(impersonate="chrome") if HAS_CURL else None

def fetch_history(symbol, session, period="1y", interval="1d", retries=4):
    """Ambil history dengan retry + backoff. Return (df, error)."""
    last_err = None
    for attempt in range(retries):
        try:
            t = yf.Ticker(symbol, session=session) if session else yf.Ticker(symbol)
            df = t.history(period=period, interval=interval)
            if df is not None and len(df) > 60:
                return df, None
            last_err = f"history terlalu pendek ({0 if df is None else len(df)} baris)"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(2 * (attempt + 1))
    return None, last_err

def safe_info(symbol, session):
    try:
        t = yf.Ticker(symbol, session=session) if session else yf.Ticker(symbol)
        return t.info or {}
    except Exception:
        return {}

# ============================================================
# INDIKATOR
# ============================================================
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def bollinger(series, period=20, std=2):
    sma = series.rolling(period).mean()
    sd = series.rolling(period).std()
    upper = sma + sd * std
    lower = sma - sd * std
    pct_b = (series - lower) / (upper - lower)
    return upper, sma, lower, pct_b

def macd(series, fast=12, slow=26, signal=9):
    line = series.ewm(span=fast, adjust=False).mean() - series.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig

def atr(df, period=14):
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low'] - df['Close'].shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(period).mean()

def detect_accumulation(df, window=20):
    recent = df.tail(window)
    obv = (np.sign(recent['Close'].diff()) * recent['Volume']).cumsum()
    obv_trend = obv.iloc[-1] > obv.iloc[-window // 2]
    price_change = (recent['Close'].iloc[-1] / recent['Close'].iloc[0]) - 1
    vol_recent = recent['Volume'].tail(5).mean()
    vol_prev = recent['Volume'].iloc[:window - 5].mean()
    vol_r = vol_recent / vol_prev if vol_prev > 0 else 1
    is_sideways = (recent['High'].max() - recent['Low'].min()) / recent['Close'].mean() < 0.08
    score, reasons = 0, []
    if obv_trend:
        score += 40
        reasons.append("OBV uptrend (indikasi akumulasi)")
    if vol_r > 1.3 and price_change > -0.03:
        score += 35
        reasons.append(f"Volume {vol_r:.1f}x, harga stabil")
    if is_sideways and vol_r > 1.2:
        score += 25
        reasons.append("Sideways + volume tinggi")
    return {"score": score, "reasons": reasons, "vol_ratio": round(vol_r, 2)}

def detect_rsi_divergence(df, lookback=30):
    if len(df) < lookback:
        return False
    recent = df.tail(lookback)
    r = rsi(recent['Close'], IND["rsi_period"]).values
    lows = recent['Low'].values
    i1 = np.argmin(lows[:lookback // 2])
    i2 = lookback // 2 + np.argmin(lows[lookback // 2:])
    return lows[i2] < lows[i1] and r[i2] > r[i1]

def score_stock(df, df_weekly):
    price = df['Close'].iloc[-1]
    signals, reasons, total = {}, [], 0

    # 1. RSI
    v = rsi(df['Close'], IND["rsi_period"]).iloc[-1]
    if v < 25:
        signals['rsi'] = 12
        reasons.append(f"RSI sangat oversold ({v:.1f})")
    elif v < IND["rsi_oversold"]:
        signals['rsi'] = 8
        reasons.append(f"RSI oversold ({v:.1f})")
    elif v < 40:
        signals['rsi'] = 4
    else:
        signals['rsi'] = 0
    total += signals['rsi']

    # 2. Divergence
    signals['divergence'] = 10 if detect_rsi_divergence(df) else 0
    if signals['divergence']:
        reasons.append("Bullish RSI divergence")
    total += signals['divergence']

    # 3. Bollinger
    _, _, _, pct_b = bollinger(df['Close'], IND["bb_period"], IND["bb_std"])
    b = pct_b.iloc[-1]
    if b < 0:
        signals['bb'] = 12
        reasons.append("Harga di bawah lower BB")
    elif b < 0.15:
        signals['bb'] = 8
        reasons.append(f"Harga dekat lower BB (%B={b:.2f})")
    else:
        signals['bb'] = 0
    total += signals['bb']

    # 4. MACD
    _, _, hist = macd(df['Close'], IND["macd_fast"], IND["macd_slow"], IND["macd_signal"])
    h_now, h_prev = hist.iloc[-1], hist.iloc[-2]
    if h_prev < 0 and h_now > 0:
        signals['macd'] = 10
        reasons.append("MACD histogram baru crossover bullish")
    elif h_now > h_prev and h_now > 0:
        signals['macd'] = 6
        reasons.append("MACD momentum meningkat")
    elif h_now > h_prev:
        signals['macd'] = 3
    else:
        signals['macd'] = 0
    total += signals['macd']

    # 5. Accumulation
    accum = detect_accumulation(df)
    if accum['score'] >= 70:
        signals['accumulation'] = 15
        reasons.extend(accum['reasons'])
    elif accum['score'] >= 40:
        signals['accumulation'] = 9
        reasons.append("Indikasi akumulasi ringan")
    else:
        signals['accumulation'] = 0
    total += signals['accumulation']

    # 6. ATR Squeeze
    a_now = atr(df, IND["atr_period"]).iloc[-1]
    a_avg = atr(df, IND["atr_period"]).rolling(50).mean().iloc[-1]
    if a_now < a_avg * 0.7:
        signals['atr_squeeze'] = 8
        reasons.append("ATR squeeze — volatilitas rendah, siap meledak")
    elif a_now < a_avg * 0.9:
        signals['atr_squeeze'] = 4
    else:
        signals['atr_squeeze'] = 0
    total += signals['atr_squeeze']

    # 7. MA Ribbon
    ma_score = 0
    for p in IND["ma_periods"]:
        mv = df['Close'].rolling(p).mean().iloc[-1]
        if abs(price - mv) / price < 0.02:
            ma_score = 10 if p in [50, 200] else 6
            reasons.append(f"Dekat MA{p} (dynamic support)")
            break
    signals['ma'] = ma_score
    total += ma_score

    # 8. Pivot Support
    w = IND["pivot_window"]
    pivots = []
    for i in range(w, len(df) - w):
        window_slice = df['Low'].iloc[i - w:i + w + 1]
        if df['Low'].iloc[i] == window_slice.min() and df['Low'].iloc[i] < price:
            pivots.append(df['Low'].iloc[i])
    near = min(pivots, key=lambda x: price - x) if pivots else None
    if near and (price - near) / price < 0.03:
        signals['pivot'] = 10
        reasons.append(f"Dekat pivot support Rp{near:,.0f}")
    else:
        signals['pivot'] = 0
    total += signals['pivot']

    # 9. Fibonacci
    hi, lo = df['High'].tail(252).max(), df['Low'].tail(252).min()
    fibs = [hi - (hi - lo) * r for r in [0.236, 0.382, 0.5, 0.618, 0.786]]
    nf = min(fibs, key=lambda x: abs(x - price))
    if abs(price - nf) / price < 0.02:
        signals['fib'] = 8
        reasons.append(f"Dekat Fibonacci level Rp{nf:,.0f}")
    else:
        signals['fib'] = 0
    total += signals['fib']

    # 10. Weekly
    signals['weekly'] = 0
    if df_weekly is not None and len(df_weekly) > 20:
        wma = df_weekly['Close'].rolling(20).mean().iloc[-1]
        wr = rsi(df_weekly['Close'], 14).iloc[-1]
        if price > wma * 0.97 and wr < 50:
            signals['weekly'] = 5
            reasons.append("Weekly trend mendukung")
    total += signals['weekly']

    return {
        "total": min(total, 100),
        "signals": signals,
        "reasons": reasons,
        "accumulation": accum
    }

def generate_plan(df, score_data):
    price = df['Close'].iloc[-1]
    a = atr(df, IND["atr_period"]).iloc[-1]
    e_lo = round(price - a * 0.5, 0)
    e_hi = round(price, 0)
    stop = round(e_lo - a * RISK["atr_stop_multiplier"], 0)
    risk = e_lo - stop
    t1 = round(e_lo + risk * RISK["risk_reward_1"], 0)
    t2 = round(e_lo + risk * RISK["risk_reward_2"], 0)
    t3 = round(e_lo + risk * RISK["risk_reward_3"], 0)
    s = score_data['total']
    if s >= THRESH["strong_buy"]:
        rec, color = "STRONG BUY", "#00d26a"
    elif s >= THRESH["buy"]:
        rec, color = "BUY", "#ffc107"
    elif s >= THRESH["watchlist"]:
        rec, color = "WATCHLIST", "#ff9800"
    else:
        rec, color = "WAIT", "#f44336"
    return {
        "recommendation": rec,
        "color": color,
        "entry_zone": {"low": e_lo, "high": e_hi},
        "stop_loss": stop,
        "targets": {
            "T1": {"price": t1, "pct": round((t1 / e_lo - 1) * 100, 2)},
            "T2": {"price": t2, "pct": round((t2 / e_lo - 1) * 100, 2)},
            "T3": {"price": t3, "pct": round((t3 / e_lo - 1) * 100, 2)},
        },
        "risk_reward": round((t2 - e_lo) / risk, 2),
        "max_loss_pct": round(risk / e_lo * 100, 2),
        "atr": round(a, 2)
    }

# ============================================================
# MAIN
# ============================================================
def analyze(stock_cfg, session):
    symbol = stock_cfg["symbol"]
    print(f"  🔍 Fetching {symbol}...")
    df, err = fetch_history(symbol, session, "1y", "1d")
    if df is None:
        return None, f"{symbol}: GAGAL fetch — {err}"
    df_w, _ = fetch_history(symbol, session, "2y", "1wk")

    info = safe_info(symbol, session)
    sc = score_stock(df, df_w)
    pl = generate_plan(df, sc)
    last, prev = df.iloc[-1], df.iloc[-2]

    return {
        "symbol": stock_cfg["display"],
        "full_symbol": symbol,
        "name": info.get("shortName", stock_cfg["name"]),
        "sector": info.get("sector", "Materials"),
        "industry": info.get("industry", "Coal"),
        "price": round(float(last['Close']), 2),
        "prev_close": round(float(prev['Close']), 2),
        "change_pct": round((float(last['Close']) / float(prev['Close']) - 1) * 100, 2),
        "volume": int(last['Volume']),
        "avg_volume_20d": int(df['Volume'].tail(20).mean()),
        "high_52w": round(float(df['High'].tail(252).max()), 2),
        "low_52w": round(float(df['Low'].tail(252).min()), 2),
        "score": sc['total'],
        "signals": sc['signals'],
        "reasons": sc['reasons'],
        "accumulation": sc['accumulation'],
        "plan": pl,
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M WIB"),
        "disclaimer": "⚠️ Bukan nasihat keuangan. Riset mandiri & kelola risiko."
    }, None

def load_previous():
    p = "data/result.json"
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            return None
    return None

def main():
    session = make_session()
    print(f"🏭 Coal Capital Club | curl_cffi: {'ON ✅' if HAS_CURL else 'OFF ⚠️'}")
    print(f"📊 Menganalisis {len(STOCKS)} saham...\n")

    results = {
        "project": CFG["project"],
        "generated_at": datetime.now().isoformat(),
        "stocks": [],
        "errors": [],
        "stale": False
    }

    for stock in STOCKS:
        data, err = analyze(stock, session)
        if data:
            results["stocks"].append(data)
            print(f"  ✅ {stock['display']} — Score: {data['score']}/100 — {data['plan']['recommendation']}")
        else:
            results["errors"].append(err)
            print(f"  ❌ {err}")

    # FALLBACK: kalau semua gagal, pakai data lama + tandai stale
    if not results["stocks"]:
        prev = load_previous()
        if prev and prev.get("stocks"):
            results["stocks"] = prev["stocks"]
            results["generated_at"] = prev["generated_at"]
            results["stale"] = True
            print("\n♻️  Menggunakan data lama (stale) karena fetch gagal.")
        else:
            print("\n⚠️  Tidak ada data lama untuk fallback.")

    os.makedirs("data", exist_ok=True)
    with open("data/result.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n📦 Saved: {len(results['stocks'])} stocks | {len(results['errors'])} errors | stale={results['stale']}")

    if not results["stocks"] and not results["stale"]:
        print("\n💥 GAGAL TOTAL. Workflow akan ditandai failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
