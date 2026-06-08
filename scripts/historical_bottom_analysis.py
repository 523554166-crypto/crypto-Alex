#!/usr/bin/env python3
"""
比特币历史底部对比分析
对比当前市场（2026）与历史底部（2022年11月）
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
import time

plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

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
            # 使用 start 和 end 参数代替 period
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

def calculate_indicators(df):
    """计算技术指标"""
    
    # 移除时区信息（避免日期切片问题）
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # 移动平均线
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    # 布林带
    df['BB_middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
    df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
    df['BB_position'] = (df['Close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
    
    # 价格相对200日均线
    df['Price_vs_MA200'] = ((df['Close'] - df['MA200']) / df['MA200'] * 100)
    
    # 52周最低/最高
    df['52w_low'] = df['Close'].rolling(window=365).min()
    df['52w_high'] = df['Close'].rolling(window=365).max()
    df['Drawdown_from_high'] = ((df['Close'] - df['52w_high']) / df['52w_high'] * 100)
    
    return df

def find_bottom_periods(df):
    """识别历史底部时期"""
    # 找到RSI < 30的点
    oversold = df[df['RSI'] < 30].copy()
    
    # 找到价格相对200日均线 < -20%的点
    deep_dip = df[df['Price_vs_MA200'] < -20].copy()
    
    # 2022年底部（已知）
    bottom_2022_start = '2022-06-01'
    bottom_2022_end = '2022-12-31'
    bottom_2022 = df[bottom_2022_start:bottom_2022_end].copy()
    
    return oversold, deep_dip, bottom_2022

def analyze_specific_bottom(df, start_date, end_date, label):
    """分析特定时期的底部特征"""
    try:
        period_data = df[start_date:end_date].copy()
        
        if len(period_data) == 0:
            print(f"  ⚠️  未找到 {label} 的数据 ({start_date} 到 {end_date})")
            return None
        
        # 找到期间的最低点
        lowest_idx = period_data['Close'].idxmin()
        lowest_price = period_data['Close'].min()
        
        print(f"  📍 {label} 最低点: ${lowest_price:,.2f} ({lowest_idx.strftime('%Y-%m-%d')})")
        
        # 获取最低点前后的数据（前后30天）
        lowest_date = pd.to_datetime(lowest_idx)
        start_range = (lowest_date - pd.Timedelta(days=30)).strftime('%Y-%m-%d')
        end_range = (lowest_date + pd.Timedelta(days=30)).strftime('%Y-%m-%d')
        
        analysis_window = df[start_range:end_range].copy()
        
        if len(analysis_window) == 0:
            print(f"  ⚠️  未找到 {lowest_idx.strftime('%Y-%m-%d')} 前后30天的数据")
            return None
        
        # 最低点的指标
        bottom_data = analysis_window.loc[lowest_idx]
        
        result = {
            'label': label,
            'date': lowest_idx.strftime('%Y-%m-%d'),
            'price': float(lowest_price),
            'rsi': float(bottom_data['RSI']),
            'price_vs_ma200': float(bottom_data['Price_vs_MA200']),
            'bb_position': float(bottom_data['BB_position']),
            'macd_hist': float(bottom_data['MACD_hist']),
            'drawdown': float(bottom_data['Drawdown_from_high']),
            'ma20': float(bottom_data['MA20']),
            'ma50': float(bottom_data['MA50']),
            'ma200': float(bottom_data['MA200'])
        }
        
        return result
    except Exception as e:
        print(f"  ❌ 分析 {label} 时出错: {e}")
        return None

def compare_bottoms(current, historical):
    """对比当前与历史底部"""
    print("\n" + "="*80)
    print("比特币历史底部对比分析")
    print("="*80)
    
    comparisons = []
    
    # 当前数据
    print(f"\n【当前市场】({current['date']})")
    print(f"  价格: ${current['price']:,.2f}")
    print(f"  RSI: {current['rsi']:.2f}")
    print(f"  相对200日均线: {current['price_vs_ma200']:.2f}%")
    print(f"  布林带位置: {current['bb_position']:.2%}")
    print(f"  MACD柱状图: {current['macd_hist']:.2f}")
    print(f"  距离高点回撤: {current['drawdown']:.2f}%")
    
    for hist in historical:
        if hist is None:
            continue
            
        print(f"\n【{hist['label']}】({hist['date']})")
        print(f"  价格: ${hist['price']:,.2f}")
        print(f"  RSI: {hist['rsi']:.2f}")
        print(f"  相对200日均线: {hist['price_vs_ma200']:.2f}%")
        print(f"  布林带位置: {hist['bb_position']:.2%}")
        print(f"  MACD柱状图: {hist['macd_hist']:.2f}")
        print(f"  距离高点回撤: {hist['drawdown']:.2f}%")
        
        # 对比分析
        print(f"\n  📊 与当前对比:")
        
        # RSI对比
        rsi_diff = current['rsi'] - hist['rsi']
        if abs(rsi_diff) < 5:
            print(f"    ✅ RSI 相近 (差 {rsi_diff:.2f})")
        elif current['rsi'] < hist['rsi']:
            print(f"    ⚠️  当前RSI更低 (低 {abs(rsi_diff):.2f}) - 更超卖")
        else:
            print(f"    ⚠️  当前RSI更高 (高 {rsi_diff:.2f}) - 超卖程度不及历史底部")
        
        # 200日均线对比
        ma200_diff = current['price_vs_ma200'] - hist['price_vs_ma200']
        if current['price_vs_ma200'] < -20:
            print(f"    ✅ 价格严重超跌 (低于200日均线 {abs(current['price_vs_ma200']):.2f}%)")
        else:
            print(f"    ⚠️  价格未达严重超跌标准")
        
        # 布林带对比
        if current['bb_position'] < 0.2:
            print(f"    ✅ 接近布林带下轨 ({current['bb_position']:.2%})")
        else:
            print(f"    ⚠️  布林带位置偏高 ({current['bb_position']:.2%})")
        
        # 回撤对比
        drawdown_diff = current['drawdown'] - hist['drawdown']
        print(f"    📉 回撤对比: 当前 {current['drawdown']:.2f}% vs 历史 {hist['drawdown']:.2f}%")
        
        comparisons.append({
            'current': current,
            'historical': hist,
            'rsi_diff': rsi_diff,
            'ma200_diff': ma200_diff
        })
    
    # 综合判断
    print("\n" + "="*80)
    print("【综合判断：当前是否类似历史底部】")
    
    similar_score = 0
    total_checks = 0
    
    # 检查1: RSI
    if current['rsi'] < 20:
        print(f"  ✅ RSI < 20 (极度超卖) - 类似2022底部")
        similar_score += 1
    else:
        print(f"  ⚠️  RSI = {current['rsi']:.2f} - 不及2022底部超卖")
    total_checks += 1
    
    # 检查2: 200日均线
    if current['price_vs_ma200'] < -20:
        print(f"  ✅ 低于200日均线 >20% - 类似2022底部")
        similar_score += 1
    else:
        print(f"  ⚠️  相对200日均线 = {current['price_vs_ma200']:.2f}% - 不及2022底部")
    total_checks += 1
    
    # 检查3: 布林带
    if current['bb_position'] < 0.2:
        print(f"  ✅ 布林带位置 < 20% - 接近下轨")
        similar_score += 1
    else:
        print(f"  ⚠️  布林带位置 = {current['bb_position']:.2%}")
    total_checks += 1
    
    # 检查4: 回撤
    if current['drawdown'] < -70:
        print(f"  ✅ 回撤 >70% - 类似2022底部")
        similar_score += 1
    else:
        print(f"  ⚠️  回撤 = {abs(current['drawdown']):.2f}% - 不及2022底部")
    total_checks += 1
    
    # 最终评分
    similarity = similar_score / total_checks * 100
    
    print(f"\n  📊 相似度评分: {similar_score}/{total_checks} ({similarity:.0f}%)")
    
    if similarity >= 75:
        print(f"\n  ✅✅✅ 结论: 当前市场特征与历史底部高度相似！可能已接近底部")
    elif similarity >= 50:
        print(f"\n  ⚠️⚠️⚠️  结论: 部分特征相似，但需更多确认信号")
    else:
        print(f"\n  ❌❌❌ 结论: 当前市场与历史底部特征差异较大，可能尚未见底")
    
    print("="*80)
    
    return comparisons

def plot_comparison(df, current, historical, output_dir):
    """绘制对比图表"""
    # 获取过去3年数据（兼容不同pandas版本）
    from datetime import datetime, timedelta
    three_years_ago = datetime.now() - timedelta(days=3*365)
    last_3y = df[df.index >= three_years_ago].copy()
    
    if len(last_3y) == 0:
        # 如果3年数据为空，使用全部数据
        last_3y = df.copy()
    
    fig, axes = plt.subplots(4, 1, figsize=(16, 12))
    fig.suptitle('Bitcoin Historical Bottoms Comparison (比特币历史底部对比)', fontsize=16)
    
    # 过滤掉None值
    valid_historical = [h for h in historical if h is not None]
    
    # 图1: 价格走势 + 关键底部标记
    ax1 = axes[0]
    ax1.plot(last_3y.index, last_3y['Close'], label='BTC Price', linewidth=2)
    ax1.plot(last_3y.index, last_3y['MA200'], label='MA200', alpha=0.7, linestyle='--')
    
    # 标记历史底部
    for hist in historical:
        if hist:
            ax1.axvline(pd.to_datetime(hist['date']), color='red', linestyle=':', alpha=0.7, 
                        label=f"{hist['label']} Bottom")
            ax1.scatter(pd.to_datetime(hist['date']), hist['price'], color='red', s=100, zorder=5)
    
    # 标记当前
    ax1.axvline(pd.to_datetime(current['date']), color='blue', linestyle=':', alpha=0.7, 
                label='Current')
    ax1.scatter(pd.to_datetime(current['date']), current['price'], color='blue', s=100, zorder=5)
    
    ax1.set_title('Price History & Bottom Markers (3 Years)')
    ax1.set_ylabel('Price (USD)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_yscale('log')
    
    # 图2: RSI对比
    ax2 = axes[1]
    ax2.plot(last_3y.index, last_3y['RSI'], label='RSI', linewidth=2)
    ax2.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='Oversold (30)')
    ax2.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='Overbought (70)')
    
    for hist in historical:
        if hist:
            ax2.axvline(pd.to_datetime(hist['date']), color='red', linestyle=':', alpha=0.5)
            ax2.scatter(pd.to_datetime(hist['date']), hist['rsi'], color='red', s=100, zorder=5)
    
    ax2.axvline(pd.to_datetime(current['date']), color='blue', linestyle=':', alpha=0.5)
    ax2.scatter(pd.to_datetime(current['date']), current['rsi'], color='blue', s=100, zorder=5)
    
    ax2.set_title('RSI Comparison')
    ax2.set_ylabel('RSI')
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 图3: 价格相对200日均线
    ax3 = axes[2]
    ax3.plot(last_3y.index, last_3y['Price_vs_MA200'], label='Price vs MA200 (%)', linewidth=2)
    ax3.axhline(y=-20, color='red', linestyle='--', alpha=0.7, label='Severe Dip (-20%)')
    ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    
    for hist in historical:
        if hist:
            ax3.axvline(pd.to_datetime(hist['date']), color='red', linestyle=':', alpha=0.5)
            ax3.scatter(pd.to_datetime(hist['date']), hist['price_vs_ma200'], color='red', s=100, zorder=5)
    
    ax3.axvline(pd.to_datetime(current['date']), color='blue', linestyle=':', alpha=0.5)
    ax3.scatter(pd.to_datetime(current['date']), current['price_vs_ma200'], color='blue', s=100, zorder=5)
    
    ax3.set_title('Price vs MA200 (%)')
    ax3.set_ylabel('Deviation (%)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 图4: 回撤
    ax4 = axes[3]
    ax4.plot(last_3y.index, last_3y['Drawdown_from_high'], label='Drawdown from High (%)', 
             linewidth=2, color='red')
    ax4.axhline(y=-70, color='darkred', linestyle='--', alpha=0.7, label='Severe Drawdown (-70%)')
    ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    
    for hist in historical:
        if hist:
            ax4.axvline(pd.to_datetime(hist['date']), color='red', linestyle=':', alpha=0.5)
            ax4.scatter(pd.to_datetime(hist['date']), hist['drawdown'], color='red', s=100, zorder=5)
    
    ax4.axvline(pd.to_datetime(current['date']), color='blue', linestyle=':', alpha=0.5)
    ax4.scatter(pd.to_datetime(current['date']), current['drawdown'], color='blue', s=100, zorder=5)
    
    ax4.set_title('Drawdown from 52-Week High')
    ax4.set_ylabel('Drawdown (%)')
    ax4.set_xlabel('Date')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    output_path = os.path.join(output_dir, 'bitcoin_historical_bottom_comparison.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n对比图表已保存到: {output_path}")
    plt.close()
    
    return output_path

def main():
    """主函数"""
    # 下载数据（从2019年开始，确保包含2022年底部）
    df = download_bitcoin_data(start_date='2019-01-01')
    
    # 计算指标
    df = calculate_indicators(df)
    
    # 分析当前市场
    current_date = df.index[-1].strftime('%Y-%m-%d')
    current = {
        'label': '当前市场',
        'date': current_date,
        'price': df['Close'].iloc[-1],
        'rsi': df['RSI'].iloc[-1],
        'price_vs_ma200': df['Price_vs_MA200'].iloc[-1],
        'bb_position': df['BB_position'].iloc[-1],
        'macd_hist': df['MACD_hist'].iloc[-1],
        'drawdown': df['Drawdown_from_high'].iloc[-1],
        'ma20': df['MA20'].iloc[-1],
        'ma50': df['MA50'].iloc[-1],
        'ma200': df['MA200'].iloc[-1]
    }
    
    # 分析2022年底部
    print("\n正在分析2022年底部...")
    bottom_2022 = analyze_specific_bottom(df, '2022-06-01', '2023-01-31', '2022年底部')
    
    # 分析2020年3月疫情底部（供参考）
    print("正在分析2020年疫情底部...")
    bottom_2020 = analyze_specific_bottom(df, '2020-01-01', '2020-12-31', '2020年疫情底部')
    
    # 对比分析
    historical = [bottom_2022, bottom_2020]
    comparisons = compare_bottoms(current, historical)
    
    # 绘制对比图表
    output_dir = os.path.expanduser('~/.workbuddy/skills/bitcoin-qlib/output')
    os.makedirs(output_dir, exist_ok=True)
    plot_path = plot_comparison(df, current, historical, output_dir)
    
    # 保存详细数据
    output_data = {
        'current': current,
        '2022_bottom': bottom_2022,
        '2020_bottom': bottom_2020
    }
    
    import json
    json_path = os.path.join(output_dir, 'bottom_comparison.json')
    with open(json_path, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)
    print(f"详细数据已保存到: {json_path}")
    
    return plot_path, json_path

if __name__ == '__main__':
    main()
