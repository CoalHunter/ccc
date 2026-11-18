"""
Coal Capital Club — Swing Trading Engine
10-Point Confluence System with Bandit Accumulation Detection
"""
import json
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import os

# Load config
with open("config.json") as f:
    CFG = json.load(f)

STOCKS = CFG["stocks"]
IND = CFG["indicators"]
RISK = CFG["risk_management"]
THRESH = CFG["scoring_thresholds"]

# ============================================================
# INDIKATOR CORE
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
    ema_f = series.ewm(span=fast, adjust=False).mean()
    ema_s = series.ewm(span=slow, adjust=False).mean()
    line = ema_f - ema_s
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    return line, sig, hist

def atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_cp = (df['High'] - df['Close'].shift()).abs()
    low_cp = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ============================================================
# DETEKSI AKUMULASI BANDAR
# ============================================================
def detect_accumulation(df, window=20):
    """
    Deteksi pola akumulasi:
    - Volume naik saat harga sideways/turun (absorpsi)
    - Price tidak turun signifikan meski volume besar
    - On-Balance Volume (OBV) naik
    """
    recent = df.tail(window)
    
    # 1. OBV trend
    obv = (np.sign(recent['Close'].diff()) * recent['Volume']).cumsum()
    obv_trend = obv.iloc[-1] > obv.iloc[-window//2]
    
    # 2. Volume-price divergence
    price_change = (recent['Close'].iloc[-1] / recent['Close'].iloc[0]) - 1
    vol_avg_recent = recent['Volume'].tail(5).mean()
    vol_avg_prev = recent['Volume'].iloc[:window-5].mean()
    vol_ratio = vol_avg_recent / vol_avg_prev if vol_avg_prev > 0 else 1
    
    # 3. Sideways dengan volume tinggi
    price_range = (recent['High'].max() - recent['Low'].min()) / recent['Close'].mean()
    is_sideways = price_range < 0.08  # range < 8%
    
    # Skor akumulasi 0-100
    score = 0
    reasons = []
    
    if obv_trend:
        score += 40
        reasons.append("OBV uptrend (bandar akumulasi)")
    
    if vol_ratio > 1.3 and price_change > -0.03:
        score += 35
        reasons.append(f"Volume naik {vol_ratio:.1f}x, harga stabil")
    
    if is_sideways and vol_ratio > 1.2:
        score += 25
        reasons.append("Sideways dengan volume tinggi")
    
    return {"score": score, "reasons": reasons, "vol_ratio": round(vol_ratio, 2)}

# ============================================================
# RSI DIVERGENCE
# ============================================================
def detect_rsi_divergence(df, lookback=30):
    """Bullish divergence: harga lower low, RSI higher low"""
    if len(df) < lookback:
        return False
    
    recent = df.tail(lookback)
    rsi_series = rsi(recent['Close'], IND["rsi_period"])
    
    # Cari 2 low terakhir
    lows = recent['Low'].values
    rsi_vals = rsi_series.values
    
    # Simplified: bandingkan low 15 hari lalu vs 5 hari lalu
    low1_idx = np.argmin(lows[:lookback//2])
    low2_idx = lookback//2 + np.argmin(lows[lookback//2:])
    
    if low2_idx > low1_idx:
        price_lower = lows[low2_idx] < lows[low1_idx]
        rsi_higher = rsi_vals[low2_idx] > rsi_vals[low1_idx]
        return price_lower and rsi_higher
    return False

# ============================================================
# SCORING SYSTEM (100 poin total)
# ============================================================
def score_stock(df, df_weekly):
    last = df.iloc[-1]
    price = last['Close']
    signals = {}
    reasons = []
    total = 0
    
    # 1. RSI (12 poin)
    rsi_val = rsi(df['Close'], IND["rsi_period"]).iloc[-1]
    if rsi_val < 25:
        signals['rsi'] = 12
        reasons.append(f"RSI sangat oversold ({rsi_val:.1f})")
    elif rsi_val < IND["rsi_oversold"]:
        signals['rsi'] = 8
        reasons.append(f"RSI oversold ({rsi_val:.1f})")
    elif rsi_val < 40:
        signals['rsi'] = 4
    else:
        signals['rsi'] = 0
    total += signals['rsi']
    
    # 2. RSI Divergence (10 poin)
    if detect_rsi_divergence(df):
        signals['divergence'] = 10
        reasons.append("Bullish RSI divergence terdeteksi")
    else:
        signals['divergence'] = 0
    total += signals['divergence']
    
    # 3. Bollinger %B (12 poin)
    _, _, _, pct_b = bollinger(df['Close'], IND["bb_period"], IND["bb_std"])
    pct_b_val = pct_b.iloc[-1]
    if pct_b_val < 0:
        signals['bb'] = 12
        reasons.append("Harga di bawah lower BB")
    elif pct_b_val < 0.15:
        signals['bb'] = 8
        reasons.append(f"Harga dekat lower BB (%B={pct_b_val:.2f})")
    else:
        signals['bb'] = 0
    total += signals['bb']
    
    # 4. MACD Momentum (10 poin)
    _, _, hist = macd(df['Close'], IND["macd_fast"], IND["macd_slow"], IND["macd_signal"])
    h_now = hist.iloc[-1]
    h_prev = hist.iloc[-2]
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
    
    # 5. Volume Accumulation (15 poin) — PALING BOBOT
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
    
    # 6. ATR Squeeze (8 poin)
    atr_val = atr(df, IND["atr_period"]).iloc[-1]
    atr_avg = atr(df, IND["atr_period"]).rolling(50).mean().iloc[-1]
    if atr_val < atr_avg * 0.7:
        signals['atr_squeeze'] = 8
        reasons.append("ATR squeeze — volatilitas rendah, siap meledak")
    elif atr_val < atr_avg * 0.9:
        signals['atr_squeeze'] = 4
    else:
        signals['atr_squeeze'] = 0
    total += signals['atr_squeeze']
    
    # 7. Multi-MA Ribbon (10 poin)
    ma_vals = {}
    for p in IND["ma_periods"]:
        ma_vals[p] = df['Close'].rolling(p).mean().iloc[-1]
    
    ma_score = 0
    for p, mv in ma_vals.items():
        dist = abs(price - mv) / price
        if dist < 0.02:
            ma_score = max(ma_score, 10 if p in [50, 200] else 6)
            reasons.append(f"Dekat MA{p} (dynamic support)")
            break
    signals['ma'] = ma_score
    total += ma_score
    
    # 8. Pivot Support (10 poin)
    pivot_lows = []
    for i in range(IND["pivot_window"], len(df) - IND["pivot_window"]):
        if df['Low'].iloc[i] == df['Low'].iloc[i-IND["pivot_window"]:i+IND["pivot_window"]+1].min():
            pivot_lows.append(df['Low'].iloc[i])
    
    pivot_support = None
    for pl in sorted(pivot_lows, reverse=True):
        if pl < price:
            pivot_support = pl
            break
    
    if pivot_support and abs(price - pivot_support) / price < 0.03:
        signals['pivot'] = 10
        reasons.append(f"Dekat pivot support Rp{pivot_support:,.0f}")
    else:
        signals['pivot'] = 0
    total += signals['pivot']
    
    # 9. Fibonacci (8 poin)
    high_52w = df['High'].tail(252).max()
    low_52w = df['Low'].tail(252).min()
    diff = high_52w - low_52w
    fib_levels = [high_52w - diff * r for r in [0.236, 0.382, 0.5, 0.618, 0.786]]
    
    nearest_fib = min(fib_levels, key=lambda x: abs(x - price))
    if abs(price - nearest_fib) / price < 0.02:
        signals['fib'] = 8
        reasons.append(f"Dekat Fibonacci level Rp{nearest_fib:,.0f}")
    else:
        signals['fib'] = 0
    total += signals['fib']
    
    # 10. Weekly Alignment (5 poin)
    if not df_weekly.empty and len(df_weekly) > 20:
        weekly_ma20 = df_weekly['Close'].rolling(20).mean().iloc[-1]
        weekly_rsi = rsi(df_weekly['Close'], 14).iloc[-1]
        if price > weekly_ma20 * 0.97 and weekly_rsi < 50:
            signals['weekly'] = 5
            reasons.append("Weekly trend mendukung (di atas MA20W, RSIW belum overbought)")
        else:
            signals['weekly'] = 0
    else:
        signals['weekly'] = 0
    total += signals['weekly']
    
    return {
        "total": min(total, 100),
        "signals": signals,
        "reasons": reasons,
        "accumulation": accum
    }

# ============================================================
# TRADING PLAN
# ============================================================
def generate_plan(df, score_data):
    price = df['Close'].iloc[-1]
    atr_val = atr(df, IND["atr_period"]).iloc[-1]
    score = score_data['total']
    
    # Entry zone: current price - 1 ATR (dynamic)
    entry_low = round(price - atr_val * 0.5, 0)
    entry_high = round(price, 0)
    
    # Stop loss: ATR-based (1.5x ATR di bawah entry)
    stop_loss = round(entry_low - atr_val * RISK["atr_stop_multiplier"], 0)
    
    # Targets berdasarkan R:R
    risk = entry_low - stop_loss
    t1 = round(entry_low + risk * RISK["risk_reward_1"], 0)
    t2 = round(entry_low + risk * RISK["risk_reward_2"], 0)
    t3 = round(entry_low + risk * RISK["risk_reward_3"], 0)
    
    # Recommendation
    if score >= THRESH["strong_buy"]:
        rec, color = "STRONG BUY", "#00d26a"
    elif score >= THRESH["buy"]:
        rec, color = "BUY", "#ffc107"
    elif score >= THRESH["watchlist"]:
        rec, color = "WATCHLIST", "#ff9800"
    else:
        rec, color = "WAIT", "#f44336"
    
    return {
        "recommendation": rec,
        "color": color,
        "entry_zone": {"low": entry_low, "high": entry_high},
        "stop_loss": stop_loss,
        "targets": {
            "T1": {"price": t1, "pct": round((t1/entry_low - 1)*100, 2)},
            "T2": {"price": t2, "pct": round((t2/entry_low - 1)*100, 2)},
            "T3": {"price": t3, "pct": round((t3/entry_low - 1)*100, 2)},
        },
        "risk_reward": round((t2 - entry_low) / risk, 2),
        "max_loss_pct": round(risk / entry_low * 100, 2),
        "atr": round(atr_val, 2)
    }

# ============================================================
# MAIN
# ============================================================
def analyze(stock_cfg):
    symbol = stock_cfg["symbol"]
    print(f"🔍 Analyzing {symbol}...")
    
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="1y")
    df_weekly = ticker.history(period="2y", interval="1wk")
    
    if df.empty:
        return None
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    info = ticker.info
    
    score_data = score_stock(df, df_weekly)
    plan = generate_plan(df, score_data)
    
    return {
        "symbol": stock_cfg["display"],
        "full_symbol": symbol,
        "name": stock_cfg["name"],
        "sector": info.get("sector", "Materials"),
        "industry": info.get("industry", "Coal"),
        "price": round(last['Close'], 2),
        "prev_close": round(prev['Close'], 2),
        "change_pct": round((last['Close']/prev['Close'] - 1) * 100, 2),
        "volume": int(last['Volume']),
        "avg_volume_20d": int(df['Volume'].tail(20).mean()),
        "high_52w": round(df['High'].tail(252).max(), 2),
        "low_52w": round(df['Low'].tail(252).min(), 2),
        "score": score_data['total'],
        "signals": score_data['signals'],
        "reasons": score_data['reasons'],
        "accumulation": score_data['accumulation'],
        "plan": plan,
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M WIB"),
        "disclaimer": "⚠️ Bukan nasihat keuangan. Riset mandiri & kelola risiko."
    }

def main():
    results = {
        "project": CFG["project"],
        "generated_at": datetime.now().isoformat(),
        "stocks": []
    }
    
    for stock in STOCKS:
        try:
            data = analyze(stock)
            if data:
                results["stocks"].append(data)
                print(f"✅ {stock['display']} — Score: {data['score']}/100 — {data['plan']['recommendation']}")
        except Exception as e:
            print(f"❌ Error {stock['symbol']}: {e}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/result.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Done. Saved to data/result.json")

if __name__ == "__main__":
    main()
