#!/usr/bin/env python3
"""
比特币时间维度分析脚本
分析比特币是否已跌到位（底部判断）
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

# 设置中文字体（如果需要）
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def download_bitcoin_data(period='1y'):
    """下载比特币数据（带重试机制）"""
    print("正在下载比特币数据...")
    
    # 设置更长的超时时间
    import requests
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            btc = yf.Ticker("BTC-USD", session=session)
            df = btc.history(period=period, interval='1d', timeout=60)
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

def calculate_indicators(df):
    """计算技术指标"""
    
    # 1. 移动平均线 (MA)
    df['MA20'] = df['Close'].rolling(window=20).mean()  # 短期
    df['MA50'] = df['Close'].rolling(window=50).mean()  # 中期
    df['MA200'] = df['Close'].rolling(window=200).mean()  # 长期
    
    # 2. RSI (相对强弱指标)
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
    
    # 4. 布林带 (Bollinger Bands)
    df['BB_middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
    df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
    
    # 5. 价格位置（相对于200日均线）
    df['Price_vs_MA200'] = ((df['Close'] - df['MA200']) / df['MA200'] * 100)
    
    # 6. 波动率
    df['Volatility'] = df['Close'].pct_change().rolling(window=20).std() * np.sqrt(365) * 100
    
    return df

def analyze_bottom_signals(df):
    """分析底部信号"""
    latest = df.iloc[-1]
    results = []
    
    print("\n" + "="*60)
    print("比特币底部分析报告中止")
    print("="*60)
    
    # 1. RSI 分析
    rsi = latest['RSI']
    print(f"\n【1. RSI 指标】")
    print(f"  当前 RSI: {rsi:.2f}")
    if rsi < 30:
        print(f"  ✅ 超卖区域 (RSI < 30) - 可能见底")
        results.append(("RSI", "看涨", rsi))
    elif rsi < 50:
        print(f"  ⚠️  弱势区域 (RSI < 50)")
        results.append(("RSI", "中性", rsi))
    else:
        print(f"  ❌ 强势/超买区域 (RSI >= 50)")
        results.append(("RSI", "看跌", rsi))
    
    # 2. 价格 vs 200日均线
    price_vs_ma200 = latest['Price_vs_MA200']
    print(f"\n【2. 长期趋势 (200日均线)】")
    print(f"  当前价格相对200日均线: {price_vs_ma200:.2f}%")
    if price_vs_ma200 < -20:
        print(f"  ✅ 严重超跌 (低于200日均线20%以上) - 长期底部区域")
        results.append(("长期趋势", "看涨", price_vs_ma200))
    elif price_vs_ma200 < -10:
        print(f"  ⚠️  超跌区域 (低于200日均线10-20%)")
        results.append(("长期趋势", "中性", price_vs_ma200))
    else:
        print(f"  ❌ 未超跌 (低于200日均线不足10%)")
        results.append(("长期趋势", "看跌", price_vs_ma200))
    
    # 3. 布林带分析
    bb_position = (latest['Close'] - latest['BB_lower']) / (latest['BB_upper'] - latest['BB_lower'])
    print(f"\n【3. 布林带位置】")
    print(f"  当前价格布林带位置: {bb_position:.2%}")
    if bb_position < 0.1:
        print(f"  ✅ 接近下轨 - 可能反弹")
        results.append(("布林带", "看涨", bb_position))
    elif bb_position < 0.5:
        print(f"  ⚠️  中下部区域")
        results.append(("布林带", "中性", bb_position))
    else:
        print(f"  ❌ 中上部/接近上轨")
        results.append(("布林带", "看跌", bb_position))
    
    # 4. MACD 分析
    macd = latest['MACD']
    macd_signal = latest['MACD_signal']
    macd_hist = latest['MACD_hist']
    print(f"\n【4. MACD 指标】")
    print(f"  MACD: {macd:.2f}")
    print(f"  Signal: {macd_signal:.2f}")
    print(f"  Histogram: {macd_hist:.2f}")
    if macd_hist > 0 and macd_hist > macd_hist:
        print(f"  ✅ MACD 金叉 - 看涨信号")
        results.append(("MACD", "看涨", macd_hist))
    elif macd_hist < 0:
        print(f"  ⚠️  MACD 死叉 - 继续观察")
        results.append(("MACD", "中性", macd_hist))
    else:
        print(f"  ❌ MACD 柱状图未确认底部")
        results.append(("MACD", "看跌", macd_hist))
    
    # 5. 移动平均线排列
    print(f"\n【5. 均线排列】")
    ma20 = latest['MA20']
    ma50 = latest['MA50']
    ma200 = latest['MA200']
    close = latest['Close']
    print(f"  当前价格: ${close:.2f}")
    print(f"  MA20: ${ma20:.2f}")
    print(f"  MA50: ${ma50:.2f}")
    print(f"  MA200: ${ma200:.2f}")
    
    if close < ma20 < ma50 < ma200:
        print(f"  ❌ 空头排列 - 下跌趋势")
        results.append(("均线", "看跌", 0))
    elif ma20 > ma50 > ma200 and close > ma20:
        print(f"  ✅ 多头排列 - 上涨趋势")
        results.append(("均线", "看涨", 1))
    else:
        print(f"  ⚠️  均线纠缠 - 趋势不明")
        results.append(("均线", "中性", 0.5))
    
    # 总结
    print("\n" + "="*60)
    print("【综合判断】")
    bullish = sum(1 for _, signal, _ in results if signal == "看涨")
    neutral = sum(1 for _, signal, _ in results if signal == "中性")
    bearish = sum(1 for _, signal, _ in results if signal == "看跌")
    
    print(f"  看涨信号: {bullish}/5")
    print(f"  中性信号: {neutral}/5")
    print(f"  看跌信号: {bearish}/5")
    
    if bullish >= 3:
        print(f"\n  ✅✅✅ 结论: 比特币可能已跌到位，出现较多底部信号")
    elif bullish >= 2:
        print(f"\n  ⚠️⚠️⚠️  结论: 部分底部信号出现，但需谨慎观察")
    else:
        print(f"\n  ❌❌❌ 结论: 尚未出现明显底部信号，可能还有下跌空间")
    
    print("="*60)
    
    return results

def plot_analysis(df, output_dir):
    """绘制分析图表"""
    # 创建图表
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle('Bitcoin Technical Analysis (Bitcoin Time Dimension Analysis)', fontsize=16)
    
    # 图1: 价格 + 均线 + 布林带
    ax1 = axes[0]
    ax1.plot(df.index[-200:], df['Close'].iloc[-200:], label='Close Price', linewidth=2)
    ax1.plot(df.index[-200:], df['MA20'].iloc[-200:], label='MA20', alpha=0.7)
    ax1.plot(df.index[-200:], df['MA50'].iloc[-200:], label='MA50', alpha=0.7)
    ax1.plot(df.index[-200:], df['MA200'].iloc[-200:], label='MA200', alpha=0.7)
    ax1.fill_between(df.index[-200:], df['BB_lower'].iloc[-200:], df['BB_upper'].iloc[-200:], 
                     alpha=0.2, label='Bollinger Bands')
    ax1.set_title('Price & Moving Averages (Past 200 Days)')
    ax1.set_ylabel('Price (USD)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 图2: RSI
    ax2 = axes[1]
    ax2.plot(df.index[-200:], df['RSI'].iloc[-200:], label='RSI', color='orange', linewidth=2)
    ax2.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='Oversold (30)')
    ax2.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='Overbought (70)')
    ax2.fill_between(df.index[-200:], 30, 70, alpha=0.1, color='gray')
    ax2.set_title('RSI (Relative Strength Index)')
    ax2.set_ylabel('RSI')
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 图3: MACD
    ax3 = axes[2]
    ax3.plot(df.index[-200:], df['MACD'].iloc[-200:], label='MACD', linewidth=2)
    ax3.plot(df.index[-200:], df['MACD_signal'].iloc[-200:], label='Signal', linewidth=2)
    ax3.bar(df.index[-200:], df['MACD_hist'].iloc[-200:], label='Histogram', alpha=0.5)
    ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    ax3.set_title('MACD')
    ax3.set_ylabel('MACD')
    ax3.set_xlabel('Date')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # 保存图表
    output_path = os.path.join(output_dir, 'bitcoin_analysis.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n图表已保存到: {output_path}")
    plt.close()
    
    return output_path

def main():
    """主函数"""
    # 下载数据
    df = download_bitcoin_data(period='1y')
    
    # 计算指标
    df = calculate_indicators(df)
    
    # 分析底部信号
    results = analyze_bottom_signals(df)
    
    # 绘制图表
    output_dir = os.path.expanduser('~/.workbuddy/skills/bitcoin-qlib/output')
    os.makedirs(output_dir, exist_ok=True)
    plot_path = plot_analysis(df, output_dir)
    
    # 保存数据到 CSV
    csv_path = os.path.join(output_dir, 'btc_analysis.csv')
    df.to_csv(csv_path)
    print(f"数据已保存到: {csv_path}")
    
    return plot_path, csv_path

if __name__ == '__main__':
    main()
