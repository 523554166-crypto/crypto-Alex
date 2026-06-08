#!/usr/bin/env python3
"""
比特币底部监控脚本（终极版）
包含14个基础信号 + 4个高级趋势指标
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
import time
import json

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 数据保存目录
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
MONITOR_DIR = os.path.join(os.path.dirname(__file__), '..', 'monitor')
STATE_FILE = os.path.join(MONITOR_DIR, 'monitor_state.json')

# 底部信号阈值
THRESHOLDS = {
    'rsi_oversold': 30,              # RSI超卖阈值
    'rsi_extreme': 20,               # RSI极度超卖
    'ma200_severe_dip': -20,         # 200日均线严重超跌
    'bb_position_low': 0.2,          # 布林带下轨
    'drawdown_severe': -50,           # 严重回撤
    'stoch_oversold': 20,            # 随机指标超卖
    'stoch_extreme': 10,             # 随机指标极度超卖
    'fear_greed_extreme_fear': 20,   # 恐慌贪婪指数极度恐慌
    'volume_surge_multiplier': 1.5,  # 放量倍数（相对20日均量）
    'support_distance': 0.02,         # 支撑位距离（2%）
    # 高级指标阈值
    'adx_strong_trend': 25,         # ADX强趋势阈值
    'supertrend_buy': True,           # 超级趋势买入信号
    'fib_support_distance': 0.02,     # 斐波那契支撑位距离（2%）
}

# ========== 数据下载 ==========

def download_bitcoin_data(start_date='2019-01-01', end_date=None):
    """下载比特币数据（使用具体日期范围）"""
    print(f"正在下载比特币数据 ({start_date} 至今)...")
    
    import requests
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            btc = yf.Ticker("BTC-USD", session=session)
            df = btc.history(start=start_date, end=end_date, interval='1d', timeout=60)
            if len(df) > 0:
                print(f"数据下载完成，共 {len(df)} 天")
                return df
        except Exception as e:
            print(f"尝试 {attempt+1}/{max_retries} 失败: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
    
    raise Exception("下载失败，请稍后重试或检查网络连接")

# ========== 技术指标计算 ==========

def calculate_indicators(df):
    """计算所有技术指标（含4个高级指标）"""
    
    # 移除时区信息
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # 1. 移动平均线
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # 2. RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 3. MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    # 4. 布林带
    df['BB_middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
    df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
    df['BB_position'] = (df['Close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
    
    # 5. 回撤
    df['Cummax'] = df['Close'].cummax()
    df['Drawdown_from_high'] = (df['Close'] - df['Cummax']) / df['Cummax'] * 100
    
    # 6. 价格相对均线
    df['Price_vs_MA20'] = (df['Close'] - df['MA20']) / df['MA20'] * 100
    df['Price_vs_MA50'] = (df['Close'] - df['MA50']) / df['MA50'] * 100
    df['Price_vs_MA200'] = (df['Close'] - df['MA200']) / df['MA200'] * 100
    
    # 7. 成交量比
    df['Volume_ma20'] = df['Volume'].rolling(window=20).mean()
    df['Volume_ratio'] = df['Volume'] / df['Volume_ma20']
    
    # 8. 随机指标 Stochastic
    low_14 = df['Low'].rolling(window=14).min()
    high_14 = df['High'].rolling(window=14).max()
    df['Stoch_K'] = (df['Close'] - low_14) / (high_14 - low_14) * 100
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
    
    # 9. 恐慌贪婪指数（简化版，基于30天波动率）
    returns = df['Close'].pct_change()
    volatility = returns.rolling(window=30).std() * np.sqrt(365)
    df['Fear_Greed_Index'] = 100 - (volatility * 100).clip(0, 100)
    
    # 10. 支撑位检测（过去180天低点）
    df['Support_180'] = df['Low'].rolling(window=180, min_periods=1).min()
    df['Near_support'] = abs(df['Close'] - df['Support_180']) / df['Support_180'] < THRESHOLDS['support_distance']
    
    # 11. K线形态检测
    df['Hammer'] = detect_hammer(df)
    df['Morning_star'] = detect_morning_star(df)
    df['Bullish_engulfing'] = detect_bullish_engulfing(df)
    
    # 12. 双底形态检测
    df['Double_bottom'] = detect_double_bottom(df)
    
    # ========= 高级趋势指标 =========
    
    # 13. ADX (平均趋向指数)
    df['ADX'] = calculate_adx(df)
    df['DI_plus'] = calculate_di_plus(df)
    df['DI_minus'] = calculate_di_minus(df)
    
    # 14. Ichimoku Cloud (一目均衡表)
    df['Ichimoku_A'] = calculate_ichimoku_a(df)
    df['Ichimoku_B'] = calculate_ichimoku_b(df)
    df['Ichimoku_base'] = calculate_ichimoku_base(df)
    df['Ichimoku_conversion'] = calculate_ichimoku_conversion(df)
    df['Ichimoku_span'] = calculate_ichimoku_span(df)
    df['Ichimoku_bullish'] = calculate_ichimoku_bullish(df)
    
    # 15. Supertrend (超级趋势)
    supertrend, direction = calculate_supertrend(df)
    df['Supertrend'] = supertrend
    df['Supertrend_direction'] = direction
    df['Supertrend_buy'] = detect_supertrend_buy(df)
    
    # 16. Fibonacci Retracement (斐波那契回撤)
    fib_levels = calculate_fibonacci_levels(df)
    df['Fib_236'] = fib_levels[0]
    df['Fib_382'] = fib_levels[1]
    df['Fib_50'] = fib_levels[2]
    df['Fib_618'] = fib_levels[3]
    df['Near_fib_support'] = detect_fib_support(df)
    
    return df

# ========== K线形态检测 ==========

def detect_hammer(df):
    """检测锤子线形态"""
    hammer = pd.Series(False, index=df.index)
    
    for i in range(1, len(df)):
        open_price = df['Open'].iloc[i]
        close_price = df['Close'].iloc[i]
        high_price = df['High'].iloc[i]
        low_price = df['Low'].iloc[i]
        
        body = abs(close_price - open_price)
        total_range = high_price - low_price
        lower_shadow = min(open_price, close_price) - low_price
        
        # 锤子线特征：下影线长度 > 实体2倍，实体在上方
        if body > 0 and total_range > 0:
            if lower_shadow > body * 2 and close_price < df['Close'].iloc[i-1]:
                hammer.iloc[i] = True
    
    return hammer

def detect_morning_star(df):
    """检测启明星形态（3根K线）"""
    morning_star = pd.Series(False, index=df.index)
    
    for i in range(2, len(df)):
        # 第1根：长阴线
        candle1_bearish = df['Close'].iloc[i-2] < df['Open'].iloc[i-2]
        candle1_long = abs(df['Close'].iloc[i-2] - df['Open'].iloc[i-2]) > 0
        
        # 第2根：小实体（阴或阳）
        candle2_small = abs(df['Close'].iloc[i-1] - df['Open'].iloc[i-1]) < \
                       abs(df['Close'].iloc[i-2] - df['Open'].iloc[i-2]) * 0.3
        
        # 第3根：长阳线，收盘在第1根阴线实体的50%以上
        candle3_bullish = df['Close'].iloc[i] > df['Open'].iloc[i]
        candle3_strong = df['Close'].iloc[i] > (df['Open'].iloc[i-2] + df['Close'].iloc[i-2]) / 2
        
        if candle1_bearish and candle2_small and candle3_bullish and candle3_strong:
            morning_star.iloc[i] = True
    
    return morning_star

def detect_bullish_engulfing(df):
    """检测看涨吞没形态"""
    engulfing = pd.Series(False, index=df.index)
    
    for i in range(1, len(df)):
        # 前一根是阴线
        prev_bearish = df['Close'].iloc[i-1] < df['Open'].iloc[i-1]
        
        # 当前是阳线，且实体完全吞没前一根阴线
        curr_bullish = df['Close'].iloc[i] > df['Open'].iloc[i]
        engulf = (df['Open'].iloc[i] <= df['Close'].iloc[i-1] and 
                  df['Close'].iloc[i] >= df['Open'].iloc[i-1])
        
        if prev_bearish and curr_bullish and engulf:
            engulfing.iloc[i] = True
    
    return engulfing

def detect_double_bottom(df, window=60):
    """检测双底形态（W底）"""
    double_bottom = pd.Series(False, index=df.index)
    
    for i in range(window, len(df) - 10):
        # 找到第一个低点
        price_window = df['Low'].iloc[i-window:i]
        first_bottom_idx = price_window.idxmin()
        first_bottom_price = price_window.min()
        
        # 找到第二个低点（在第一个低点之后10-60天）
        second_window_start = first_bottom_idx + pd.Timedelta(days=10)
        second_window_end = first_bottom_idx + pd.Timedelta(days=60)
        
        if second_window_end in df.index:
            second_window = df.loc[second_window_start:second_window_end]['Low']
            if len(second_window) > 0:
                second_bottom_price = second_window.min()
                
                # 双底条件：两个低点价格相近（相差<3%），且中间有反弹
                price_diff = abs(first_bottom_price - second_bottom_price) / first_bottom_price
                mid_high = df.loc[first_bottom_idx:second_window.idxmin()]['High'].max()
                
                if price_diff < 0.03 and mid_high > first_bottom_price * 1.05:
                    double_bottom.loc[second_window.idxmin()] = True
    
    return double_bottom

# ========== RSI背离检测 ==========

def detect_rsi_divergence(df, window=20):
    """检测RSI背离（价格创新低但RSI不创新低）"""
    divergence = pd.Series(False, index=df.index)
    
    for i in range(window, len(df)):
        # 当前价格是否是过去window天的低点
        current_price = df['Close'].iloc[i]
        past_prices = df['Close'].iloc[i-window:i+1]
        is_price_low = current_price <= past_prices.min() * 1.01  # 允许1%误差
        
        # 当前RSI是否高于过去window天的最低RSI（背离）
        current_rsi = df['RSI'].iloc[i]
        past_rsi = df['RSI'].iloc[i-window:i+1]
        is_rsi_higher = current_rsi > past_rsi.min() * 1.01
        
        if is_price_low and is_rsi_higher:
            divergence.iloc[i] = True
    
    return divergence

# ========== 高级指标计算 ==========

def calculate_true_range(df):
    """计算真实波幅"""
    tr1 = df['High'] - df['Low']
    tr2 = abs(df['High'] - df['Close'].shift(1))
    tr3 = abs(df['Low'] - df['Close'].shift(1))
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

def calculate_di_plus(df, period=14):
    """计算+DI"""
    up_move = df['High'].diff()
    down_move = df['Low'].diff(-1).abs()
    
    # 修复：使用where而非布尔索引赋值
    pos_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
    
    tr = calculate_true_range(df)
    di_plus = 100 * (pos_dm.rolling(window=period).sum() / tr.rolling(window=period).sum())
    return di_plus

def calculate_di_minus(df, period=14):
    """计算-DI"""
    up_move = df['High'].diff()
    down_move = df['Low'].diff(-1).abs()
    
    # 修复：使用where而非布尔索引赋值
    neg_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
    
    tr = calculate_true_range(df)
    di_minus = 100 * (neg_dm.rolling(window=period).sum() / tr.rolling(window=period).sum())
    return di_minus

def calculate_adx(df, period=14):
    """计算ADX（平均趋向指数）"""
    di_plus = calculate_di_plus(df, period)
    di_minus = calculate_di_minus(df, period)
    
    # 计算DX
    dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
    
    # 计算ADX（DX的平滑平均）
    adx = dx.rolling(window=period).mean()
    return adx

def calculate_ichimoku_a(df):
    """计算Ichimoku转换线（Tenkan-sen）"""
    high_9 = df['High'].rolling(window=9).max()
    low_9 = df['Low'].rolling(window=9).min()
    return (high_9 + low_9) / 2

def calculate_ichimoku_b(df):
    """计算Ichimoku基准线（Kijun-sen）"""
    high_26 = df['High'].rolling(window=26).max()
    low_26 = df['Low'].rolling(window=26).min()
    return (high_26 + low_26) / 2

def calculate_ichimoku_base(df):
    """计算Ichimoku基准线（Kijun-sen）- 另一种算法"""
    return calculate_ichimoku_b(df)

def calculate_ichimoku_conversion(df):
    """计算Ichimoku转换线（Tenkan-sen）"""
    return calculate_ichimoku_a(df)

def calculate_ichimoku_span(df):
    """计算Ichimoku先行跨度A（Senkou Span A）"""
    conversion = calculate_ichimoku_a(df)
    base = calculate_ichimoku_b(df)
    return ((conversion + base) / 2).shift(26)

def calculate_ichimoku_bullish(df):
    """判断Ichimoku看涨信号（价格在云图之上）"""
    span_a = calculate_ichimoku_span(df)
    span_b = (df['High'].rolling(window=52).max() + df['Low'].rolling(window=52).min()) / 2
    span_b = span_b.shift(26)
    
    # 价格在云图之上 = 看涨
    bullish = (df['Close'] > span_a) & (df['Close'] > span_b)
    return bullish

def calculate_supertrend(df, period=10, multiplier=3):
    """计算Supertrend（超级趋势）"""
    # 计算ATR
    tr = calculate_true_range(df)
    atr = tr.rolling(window=period).mean()
    
    # 计算基本上下轨
    basic_upper = (df['High'] + df['Low']) / 2 + (multiplier * atr)
    basic_lower = (df['High'] + df['Low']) / 2 - (multiplier * atr)
    
    # 计算最终上下轨（考虑前一个值）
    final_upper = pd.Series(index=df.index, dtype=float)
    final_lower = pd.Series(index=df.index, dtype=float)
    
    # 找到第一个非NaN的索引
    first_valid = atr.first_valid_index()
    if first_valid is None:
        # 没有有效值，返回空序列
        return pd.Series(index=df.index, dtype=float), pd.Series(index=df.index, dtype=int)
    
    first_idx = df.index.get_loc(first_valid)
    
    # 初始化第一个有效值
    final_upper.iloc[first_idx] = basic_upper.iloc[first_idx]
    final_lower.iloc[first_idx] = basic_lower.iloc[first_idx]
    
    # 从第first_idx+1开始计算
    for i in range(first_idx + 1, len(df)):
        # 上轨：如果当前basic_upper < 前一个final_upper 或 前一个close > 前一个final_upper
        if basic_upper.iloc[i] < final_upper.iloc[i-1] or df['Close'].iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]
        
        # 下轨：如果当前basic_lower > 前一个final_lower 或 前一个close < 前一个final_lower
        if basic_lower.iloc[i] > final_lower.iloc[i-1] or df['Close'].iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]
    
    # Supertrend方向和值
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)
    
    # 初始化第一个有效值
    if df['Close'].iloc[first_idx] <= basic_upper.iloc[first_idx]:
        direction.iloc[first_idx] = -1
        supertrend.iloc[first_idx] = final_upper.iloc[first_idx]
    else:
        direction.iloc[first_idx] = 1
        supertrend.iloc[first_idx] = final_lower.iloc[first_idx]
    
    # 从第first_idx+1开始计算
    for i in range(first_idx + 1, len(df)):
        if supertrend.iloc[i-1] == final_upper.iloc[i-1]:  # 前一个看跌
            if df['Close'].iloc[i] <= final_upper.iloc[i]:  # 仍然看跌
                direction.iloc[i] = -1
                supertrend.iloc[i] = final_upper.iloc[i]
            else:  # 转为看涨
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower.iloc[i]
        else:  # 前一个看涨
            if df['Close'].iloc[i] >= final_lower.iloc[i]:  # 仍然看涨
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower.iloc[i]
            else:  # 转为看跌
                direction.iloc[i] = -1
                supertrend.iloc[i] = final_upper.iloc[i]
    
    # 返回Supertrend值和方向
    return supertrend, direction

def detect_supertrend_buy(df):
    """检测Supertrend买入信号（方向由-1转为1）"""
    # 使用已计算的结果
    if 'Supertrend' not in df.columns or 'Supertrend_direction' not in df.columns:
        supertrend, direction = calculate_supertrend(df)
        df['Supertrend'] = supertrend
        df['Supertrend_direction'] = direction
    else:
        direction = df['Supertrend_direction']
    
    # 买入信号：方向由-1转为1
    buy_signal = pd.Series(False, index=df.index)
    for i in range(1, len(df)):
        if direction.iloc[i-1] == -1 and direction.iloc[i] == 1:
            buy_signal.iloc[i] = True
    
    return buy_signal

def calculate_fibonacci_levels(df, lookback=180):
    """计算斐波那契回撤位"""
    # 找到过去lookback天的高点和低点
    high = df['High'].rolling(window=lookback).max()
    low = df['Low'].rolling(window=lookback).min()
    
    diff = high - low
    
    fib_236 = high - diff * 0.236
    fib_382 = high - diff * 0.382
    fib_50 = high - diff * 0.5
    fib_618 = high - diff * 0.618
    
    return fib_236, fib_382, fib_50, fib_618

def detect_fib_support(df, distance=0.02):
    """检测价格是否接近斐波那契支撑位"""
    fib_236, fib_382, fib_50, fib_618 = calculate_fibonacci_levels(df)
    
    latest = df.iloc[-1]
    price = latest['Close']
    
    # 检查是否接近任何斐波那契位（2%范围内）
    near_236 = abs(price - fib_236.iloc[-1]) / fib_236.iloc[-1] < distance if pd.notna(fib_236.iloc[-1]) else False
    near_382 = abs(price - fib_382.iloc[-1]) / fib_382.iloc[-1] < distance if pd.notna(fib_382.iloc[-1]) else False
    near_50 = abs(price - fib_50.iloc[-1]) / fib_50.iloc[-1] < distance if pd.notna(fib_50.iloc[-1]) else False
    near_618 = abs(price - fib_618.iloc[-1]) / fib_618.iloc[-1] < distance if pd.notna(fib_618.iloc[-1]) else False
    
    return near_236 or near_382 or near_50 or near_618

# ========== 信号检测 ==========

def detect_signals(df):
    """检测底部信号（含高级指标）"""
    signals = []
    latest = df.iloc[-1]
    
    # ========== 原有信号 ==========
    
    # 1. RSI信号
    rsi = latest['RSI']
    if pd.notna(rsi):
        if rsi < THRESHOLDS['rsi_extreme']:
            signals.append({
                'type': 'RSI极度超卖',
                'value': float(rsi),
                'message': f'RSI = {rsi:.2f} (极度超卖，<20)',
                'severity': 'high'
            })
        elif rsi < THRESHOLDS['rsi_oversold']:
            signals.append({
                'type': 'RSI超卖',
                'value': float(rsi),
                'message': f'RSI = {rsi:.2f} (超卖，<30)',
                'severity': 'medium'
            })
    
    # 2. 200日均线信号
    ma200_dev = latest['Price_vs_MA200']
    if pd.notna(ma200_dev) and ma200_dev < THRESHOLDS['ma200_severe_dip']:
        signals.append({
            'type': '严重超跌',
            'value': float(ma200_dev),
            'message': f'低于200日均线 {abs(ma200_dev):.2f}% (严重超跌，<-20%)',
            'severity': 'high'
        })
    
    # 3. 布林带信号
    bb_pos = latest['BB_position']
    if pd.notna(bb_pos) and bb_pos < THRESHOLDS['bb_position_low']:
        signals.append({
            'type': '接近布林带下轨',
            'value': float(bb_pos),
            'message': f'布林带位置 = {bb_pos:.2%} (接近下轨，<20%)',
            'severity': 'medium'
        })
    
    # 4. MACD金叉检测
    if len(df) >= 2:
        curr_hist = latest['MACD_hist']
        prev_hist = df.iloc[-2]['MACD_hist']
        
        if pd.notna(curr_hist) and pd.notna(prev_hist):
            # 金叉：柱状图由负转正
            if prev_hist < 0 and curr_hist > 0:
                signals.append({
                    'type': 'MACD金叉',
                    'value': float(curr_hist),
                    'message': f'MACD柱状图由负转正 ({prev_hist:.2f} -> {curr_hist:.2f})',
                    'severity': 'high'
                })
            # 柱状图收敛（可能即将金叉）
            elif prev_hist < curr_hist and curr_hist < 0:
                signals.append({
                    'type': 'MACD柱状图收敛',
                    'value': float(curr_hist),
                    'message': f'MACD柱状图收敛 ({prev_hist:.2f} -> {curr_hist:.2f})',
                    'severity': 'low'
                })
    
    # 5. 回撤信号
    drawdown = latest['Drawdown_from_high']
    if pd.notna(drawdown) and drawdown < THRESHOLDS['drawdown_severe']:
        signals.append({
            'type': '严重回撤',
            'value': float(drawdown),
            'message': f'距离高点回撤 {abs(drawdown):.2f}% (严重回撤，>50%)',
            'severity': 'high'
        })
    
    # 6. 价格突破MA20
    if len(df) >= 2:
        curr_price = latest['Close']
        prev_price = df.iloc[-2]['Close']
        ma20 = latest['MA20']
        
        if pd.notna(ma20) and pd.notna(prev_price):
            if prev_price < ma20 and curr_price > ma20:
                signals.append({
                    'type': '价格突破MA20',
                    'value': float(curr_price),
                    'message': f'价格突破MA20 (${ma20:.2f})',
                    'severity': 'medium'
                })
    
    # ========== 新增信号 ==========
    
    # 7. 成交量信号：放量下跌后缩量企稳
    if len(df) >= 5:
        recent_volume = df['Volume_ratio'].iloc[-5:]
        if recent_volume.iloc[-1] < 0.8 and recent_volume.iloc[-5:-1].mean() > 1.5:
            signals.append({
                'type': '缩量企稳',
                'value': float(recent_volume.iloc[-1]),
                'message': f'成交量缩至20日均量的{recent_volume.iloc[-1]:.2%} (放量下跌后企稳)',
                'severity': 'medium'
            })
    
    # 8. RSI背离
    rsi_div = detect_rsi_divergence(df)
    if rsi_div.iloc[-1]:
        signals.append({
            'type': 'RSI底背离',
            'value': float(latest['RSI']),
            'message': f'RSI底背离：价格新低但RSI未创新低 (RSI={latest["RSI"]:.2f})',
            'severity': 'high'
        })
    
    # 9. 均线金叉（MA20上穿MA50）
    if len(df) >= 2:
        curr_ma20 = latest['MA20']
        curr_ma50 = latest['MA50']
        prev_ma20 = df.iloc[-2]['MA20']
        prev_ma50 = df.iloc[-2]['MA50']
        
        if pd.notna(curr_ma20) and pd.notna(curr_ma50) and pd.notna(prev_ma20) and pd.notna(prev_ma50):
            if prev_ma20 < prev_ma50 and curr_ma20 > curr_ma50:
                signals.append({
                    'type': '均线金叉',
                    'value': float(curr_ma20),
                    'message': f'MA20上穿MA50 (MA20=${curr_ma20:.2f}, MA50=${curr_ma50:.2f})',
                    'severity': 'high'
                })
    
    # 10. 随机指标Stochastic信号
    stoch_k = latest['Stoch_K']
    stoch_d = latest['Stoch_D']
    if pd.notna(stoch_k) and pd.notna(stoch_d):
        # 超卖
        if stoch_k < THRESHOLDS['stoch_extreme']:
            signals.append({
                'type': '随机指标极度超卖',
                'value': float(stoch_k),
                'message': f'Stochastic %K = {stoch_k:.2f} (极度超卖，<10)',
                'severity': 'high'
            })
        elif stoch_k < THRESHOLDS['stoch_oversold']:
            signals.append({
                'type': '随机指标超卖',
                'value': float(stoch_k),
                'message': f'Stochastic %K = {stoch_k:.2f} (超卖，<20)',
                'severity': 'medium'
            })
        
        # 金叉
        if len(df) >= 2:
            prev_k = df.iloc[-2]['Stoch_K']
            prev_d = df.iloc[-2]['Stoch_D']
            if pd.notna(prev_k) and pd.notna(prev_d):
                if prev_k < prev_d and stoch_k > stoch_d:
                    signals.append({
                        'type': '随机指标金叉',
                        'value': float(stoch_k),
                        'message': f'Stochastic金叉 (%K上穿%D)',
                        'severity': 'high'
                    })
    
    # 11. 恐慌贪婪指数
    fgi = latest['Fear_Greed_Index']
    if pd.notna(fgi) and fgi < THRESHOLDS['fear_greed_extreme_fear']:
        signals.append({
            'type': '极度恐慌',
            'value': float(fgi),
            'message': f'恐慌贪婪指数 = {fgi:.2f} (极度恐慌，<20)',
            'severity': 'high'
        })
    
    # 12. 支撑位反弹
    if latest['Near_support']:
        signals.append({
            'type': '接近支撑位',
            'value': float(latest['Close']),
            'message': f'价格接近历史支撑位 (${latest["Close"]:.2f})',
            'severity': 'medium'
        })
    
    # 13. K线形态
    if latest['Hammer']:
        signals.append({
            'type': '锤子线',
            'value': float(latest['Close']),
            'message': f'出现锤子线形态 (${latest["Close"]:.2f})',
            'severity': 'medium'
        })
    
    if latest['Morning_star']:
        signals.append({
            'type': '启明星',
            'value': float(latest['Close']),
            'message': f'出现启明星形态 (${latest["Close"]:.2f})',
            'severity': 'high'
        })
    
    if latest['Bullish_engulfing']:
        signals.append({
            'type': '看涨吞没',
            'value': float(latest['Close']),
            'message': f'出现看涨吞没形态 (${latest["Close"]:.2f})',
            'severity': 'high'
        })
    
    # 14. 双底形态
    if latest['Double_bottom']:
        signals.append({
            'type': '双底形态',
            'value': float(latest['Close']),
            'message': f'出现双底形态 (W底) (${latest["Close"]:.2f})',
            'severity': 'high'
        })
    
    # ========== 高级指标信号 ==========
    
    # 15. ADX信号（趋势强度）
    adx = latest['ADX']
    di_plus = latest['DI_plus']
    di_minus = latest['DI_minus']
    
    if pd.notna(adx) and pd.notna(di_plus) and pd.notna(di_minus):
        if adx > THRESHOLDS['adx_strong_trend'] and di_plus > di_minus:
            signals.append({
                'type': 'ADX强趋势',
                'value': float(adx),
                'message': f'ADX = {adx:.2f} (强趋势，且+DI > -DI，看涨)',
                'severity': 'high'
            })
        elif adx > THRESHOLDS['adx_strong_trend'] and di_plus < di_minus:
            signals.append({
                'type': 'ADX强趋势',
                'value': float(adx),
                'message': f'ADX = {adx:.2f} (强趋势，但+DI < -DI，看跌)',
                'severity': 'medium'
            })
    
    # 16. Ichimoku信号
    if latest['Ichimoku_bullish']:
        signals.append({
            'type': 'Ichimoku看涨',
            'value': float(latest['Close']),
            'message': f'Ichimoku云图看涨（价格在云图之上）',
            'severity': 'high'
        })
    
    # 17. Supertrend信号
    if latest['Supertrend_buy']:
        signals.append({
            'type': 'Supertrend买入',
            'value': float(latest['Close']),
            'message': f'Supertrend买入信号（趋势反转向上）',
            'severity': 'high'
        })
    
    # 18. 斐波那契支撑信号
    if latest['Near_fib_support']:
        signals.append({
            'type': '斐波那契支撑',
            'value': float(latest['Close']),
            'message': f'价格接近斐波那契支撑位 (${latest["Close"]:.2f})',
            'severity': 'medium'
        })
    
    return signals

# ========== 报告生成 ==========

def generate_report(df, signals, state):
    """生成监控报告（含突出价格显示和购买建议）"""
    latest = df.iloc[-1]
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    current_price = float(latest['Close'])
    
    report = []
    report.append("=" * 80)
    report.append(f"比特币监控报告（终极版） - {current_time}")
    report.append("=" * 80)
    
    # ========= 突出显示当前价格 =========
    report.append("\n" + "💰" * 40)
    report.append(f"【当前价格】${current_price:,.2f}")
    
    # 价格变化
    if state['last_price']:
        change = ((current_price - state['last_price']) / state['last_price']) * 100
        change_icon = "📈" if change > 0 else "📉"
        report.append(f"{change_icon} 【价格变化】  {change:+.2f}%  (上次检查: ${state['last_price']:,.2f})")
    else:
        report.append("【价格变化】  (首次检查)")
    
    # 添加价格评估
    rsi = float(latest['RSI']) if pd.notna(latest['RSI']) else None
    ma200_dev = float(latest['Price_vs_MA200']) if pd.notna(latest['Price_vs_MA200']) else None
    
    if rsi is not None and rsi < 20:
        report.append(f"💡 【价格评估】  RSI={rsi:.2f} 极度超卖，可能接近底部")
    elif rsi is not None and rsi < 30:
        report.append(f"💡 【价格评估】  RSI={rsi:.2f} 超卖，关注反弹机会")
    
    if ma200_dev is not None and ma200_dev < -20:
        report.append(f"💡 【价格评估】  低于200日均线 {abs(ma200_dev):.2f}%，严重超跌")
    
    report.append("💰" * 40)
    
    # ========= 关键指标 =========
    report.append(f"\n【关键指标】")
    report.append(f"  RSI: {latest['RSI']:.2f}" if pd.notna(latest['RSI']) else "  RSI: N/A")
    report.append(f"  随机指标 %K: {latest['Stoch_K']:.2f}" if pd.notna(latest['Stoch_K']) else "  随机指标 %K: N/A")
    report.append(f"  恐慌贪婪指数: {latest['Fear_Greed_Index']:.2f}" if pd.notna(latest['Fear_Greed_Index']) else "  恐慌贪婪指数: N/A")
    report.append(f"  相对200日均线: {latest['Price_vs_MA200']:.2f}%" if pd.notna(latest['Price_vs_MA200']) else "  相对200日均线: N/A")
    report.append(f"  布林带位置: {latest['BB_position']:.2%}" if pd.notna(latest['BB_position']) else "  布林带位置: N/A")
    report.append(f"  MACD柱状图: {latest['MACD_hist']:.2f}" if pd.notna(latest['MACD_hist']) else "  MACD柱状图: N/A")
    report.append(f"  距离高点回撤: {latest['Drawdown_from_high']:.2f}%" if pd.notna(latest['Drawdown_from_high']) else "  距离高点回撤: N/A")
    report.append(f"  成交量比: {latest['Volume_ratio']:.2f}x" if pd.notna(latest['Volume_ratio']) else "  成交量比: N/A")
    
    # 高级指标
    report.append(f"\n【高级趋势指标】")
    report.append(f"  ADX: {latest['ADX']:.2f}" if pd.notna(latest['ADX']) else "  ADX: N/A")
    report.append(f"  +DI: {latest['DI_plus']:.2f}" if pd.notna(latest['DI_plus']) else "  +DI: N/A")
    report.append(f"  -DI: {latest['DI_minus']:.2f}" if pd.notna(latest['DI_minus']) else "  -DI: N/A")
    report.append(f"  Ichimoku看涨: {latest['Ichimoku_bullish']}" if pd.notna(latest['Ichimoku_bullish']) else "  Ichimoku看涨: N/A")
    report.append(f"  Supertrend: {latest['Supertrend']:.2f}" if pd.notna(latest['Supertrend']) else "  Supertrend: N/A")
    report.append(f"  斐波那契支撑: {latest['Near_fib_support']}" if pd.notna(latest['Near_fib_support']) else "  斐波那契支撑: N/A")
    
    # ========= 检测到的信号 =========
    report.append(f"\n【检测到的信号】({len(signals)}个)")
    if signals:
        # 按优先级排序
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        sorted_signals = sorted(signals, key=lambda x: severity_order[x['severity']])
        
        for i, signal in enumerate(sorted_signals, 1):
            severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}[signal['severity']]
            report.append(f"  {i}. {severity_icon} {signal['message']}")
    else:
        report.append("  (无新信号)")
    
    # ========= 综合判断 + 购买建议 =========
    high_signals = sum(1 for s in signals if s['severity'] == 'high')
    medium_signals = sum(1 for s in signals if s['severity'] == 'medium')
    low_signals = sum(1 for s in signals if s['severity'] == 'low')
    
    report.append(f"\n【综合判断】")
    report.append(f"  高优先级信号: {high_signals}")
    report.append(f"  中优先级信号: {medium_signals}")
    report.append(f"  低优先级信号: {low_signals}")
    
    # ========= 购买建议 =========
    report.append(f"\n{'=' * 80}")
    report.append(f"【购买建议】")
    
    if high_signals >= 3:
        report.append(f"\n  🔥🔥🔥 强烈建议买入！")
        report.append(f"  理由: 出现 {high_signals} 个高优先级信号，多重指标确认底部")
        report.append(f"  建议操作:")
        report.append(f"    - 可以大仓位买入（50-70%仓位）")
        report.append(f"    - 建议分批建仓：第一次买30%，回调5%再加20%，再回调5%再加20%")
        report.append(f"    - 止损位: ${current_price * 0.9:,.2f} (下跌10%止损)")
        report.append(f"    - 目标位: ${current_price * 1.3:,.2f} (上涨30%分批止盈)")
    elif high_signals >= 2:
        report.append(f"\n  ✅✅ 建议买入")
        report.append(f"  理由: 出现 {high_signals} 个高优先级信号，可能接近底部")
        report.append(f"  建议操作:")
        report.append(f"    - 可以中等仓位买入（30-50%仓位）")
        report.append(f"    - 建议分批建仓：第一次买20%，回调3%再加15%，再回调3%再加15%")
        report.append(f"    - 止损位: ${current_price * 0.92:,.2f} (下跌8%止损)")
        report.append(f"    - 目标位: ${current_price * 1.2:,.2f} (上涨20%分批止盈)")
    elif high_signals >= 1 or medium_signals >= 3:
        report.append(f"\n  ⚠️⚠️ 建议小仓位试探")
        report.append(f"  理由: 出现部分底部信号，但尚未完全确认")
        report.append(f"  建议操作:")
        report.append(f"    - 小仓位试探（10-20%仓位）")
        report.append(f"    - 等待更多确认信号后再加仓")
        report.append(f"    - 止损位: ${current_price * 0.95:,.2f} (下跌5%止损)")
        report.append(f"    - 目标位: ${current_price * 1.1:,.2f} (上涨10%减仓)")
    elif medium_signals >= 1:
        report.append(f"\n  👀 建议观望")
        report.append(f"  理由: 出现部分中性信号，可观察但暂不入场")
        report.append(f"  建议操作:")
        report.append(f"    - 保持观望，等待更强信号")
        report.append(f"    - 可以开始关注，准备资金")
        report.append(f"    - 建议设置价格提醒: ${current_price * 0.95:,.2f} (下跌5%) 和 ${current_price * 1.05:,.2f} (上涨5%)")
    else:
        report.append(f"\n  ❌ 暂不建议买入")
        report.append(f"  理由: 暂无明确底部信号")
        report.append(f"  建议操作:")
        report.append(f"    - 继续观望，等待信号出现")
        report.append(f"    - 建议设置价格提醒: ${current_price * 0.9:,.2f} (下跌10%)")
    
    report.append(f"{'=' * 80}")
    
    # ========= 风险提示 =========
    report.append(f"\n【风险提示】")
    report.append(f"  ⚠️  以上建议仅供参考，不构成投资建议")
    report.append(f"  ⚠️  加密货币市场波动巨大，请控制仓位")
    report.append(f"  ⚠️  建议止损位严格执行，避免大额亏损")
    report.append(f"  ⚠️  建议同时关注宏观环境（美联储政策、监管消息等）")
    
    report.append("=" * 80)
    
    return "\n".join(report)

# ========== 状态管理 ==========

def load_state():
    """加载监控状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            # 确保包含所有键
            if 'signal_history' not in state:
                state['signal_history'] = []
            return state
    return {
        'last_check_time': None,
        'last_price': None,
        'last_signals': [],
        'signal_history': []
    }

def save_state(state):
    """保存监控状态"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# ========== 主函数 ==========

def main():
    """主函数"""
    print("=" * 80)
    print("比特币底部监控脚本（终极版）")
    print("=" * 80)
    print()
    
    # 1. 下载数据
    try:
        df = download_bitcoin_data(start_date='2019-01-01')
    except Exception as e:
        print(f"❌ 数据下载失败: {e}")
        return 2
    
    # 2. 计算指标
    print("\n正在计算技术指标...")
    df = calculate_indicators(df)
    print("指标计算完成")
    
    # 3. 检测信号
    print("\n正在检测底部信号...")
    signals = detect_signals(df)
    print(f"检测完成，发现 {len(signals)} 个信号")
    
    # 4. 加载状态
    state = load_state()
    
    # 5. 判断是否有新信号
    new_signals = []
    for signal in signals:
        if signal['type'] not in state.get('last_signals', []):
            new_signals.append(signal)
    
    # 6. 生成报告
    report = generate_report(df, new_signals if new_signals else signals, state)
    
    # 7. 保存报告
    os.makedirs(MONITOR_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = os.path.join(MONITOR_DIR, f"report_{timestamp}.txt")
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📊 报告已保存: {report_file}")
    
    # 8. 输出报告
    print("\n" + report)
    
    # 9. 更新状态
    state['last_check_time'] = datetime.now().isoformat()
    state['last_price'] = float(df['Close'].iloc[-1])
    state['last_signals'] = [s['type'] for s in signals]
    state['signal_history'].append({
        'time': datetime.now().isoformat(),
        'price': float(df['Close'].iloc[-1]),
        'signals': [s['type'] for s in signals]
    })
    # 只保留最近100条历史
    state['signal_history'] = state['signal_history'][-100:]
    save_state(state)
    
    # 10. 返回码
    if len(new_signals) > 0:
        print(f"\n🚨 发现 {len(new_signals)} 个新信号！")
        return 1  # 有新信号
    else:
        print(f"\n✅ 无新信号")
        return 0  # 无新信号

if __name__ == '__main__':
    exit_code = main()
    exit(exit_code)
