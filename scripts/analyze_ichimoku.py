#!/usr/bin/env python3
"""分析Ichimoku Cloud指标"""
import sys
sys.path.insert(0, '.')

from monitor_bitcoin_ultimate import *
import pandas as pd

print('正在下载数据...')
df = download_bitcoin_data(start_date='2023-01-01')
print(f'数据下载完成，共 {len(df)} 天')

print('\n正在计算指标...')
df = calculate_indicators(df)
print('指标计算完成')

latest = df.iloc[-1]
print('\n' + '=' * 60)
print('Ichimoku Cloud (一目均衡表) 分析')
print('=' * 60)

print(f'\n【当前价格】${latest["Close"]:.2f}')

print(f'\n【Ichimoku 各线数值】')
print(f'  转换线 (Tenkan-sen/Conversion): ${latest["Ichimoku_conversion"]:.2f}')
print(f'  基准线 (Kijun-sen/Base): ${latest["Ichimoku_base"]:.2f}')
print(f'  先行跨度A (Senkou Span A): ${latest["Ichimoku_A"]:.2f}')
print(f'  先行跨度B (Senkou Span B): ${latest["Ichimoku_B"]:.2f}')

print(f'\n【云图位置】')
print(f'  云图上线 (Span A): ${latest["Ichimoku_A"]:.2f}')
print(f'  云图下线 (Span B): ${latest["Ichimoku_B"]:.2f}')

# 判断价格在云图的哪个位置
price = latest['Close']
span_a = latest['Ichimoku_A']
span_b = latest['Ichimoku_B']

print(f'\n【价格相对云图位置】')
if pd.notna(span_a) and pd.notna(span_b):
    if price > max(span_a, span_b):
        position = '价格在云图之上 (看涨)'
        signal = '🟢 看涨'
    elif price < min(span_a, span_b):
        position = '价格在云图之下 (看跌)'
        signal = '🔴 看跌'
    else:
        position = '价格在云图之内 (中性)'
        signal = '🟡 中性'
    
    print(f'  {position}')
    print(f'  信号: {signal}')
else:
    print('  数据不足，无法判断')

print(f'\n【转换线 vs 基准线】')
if pd.notna(latest['Ichimoku_conversion']) and pd.notna(latest['Ichimoku_base']):
    if latest['Ichimoku_conversion'] > latest['Ichimoku_base']:
        print(f'  转换线 > 基准线: 🟢 看涨 (金叉)')
    else:
        print(f'  转换线 < 基准线: 🔴 看跌 (死叉)')

print(f'\n【综合判断】')
print(f'  Ichimoku看涨信号: {latest["Ichimoku_bullish"]}')

# 历史表现
print(f'\n【最近10天价格 vs 云图】')
for i in range(-10, 0):
    d = df.index[i]
    p = df['Close'].iloc[i]
    a = df['Ichimoku_A'].iloc[i]
    b = df['Ichimoku_B'].iloc[i]
    
    if pd.notna(a) and pd.notna(b):
        if p > max(a, b):
            pos = '上方'
        elif p < min(a, b):
            pos = '下方'
        else:
            pos = '云内'
        print(f'  {d.date()}: ${p:.0f} ({pos})')

print('\n' + '=' * 60)

# 解释Ichimoku
print('\n【Ichimoku Cloud 指标说明】')
print('''
一目均衡表（Ichimoku Cloud）是日本最常用的技术指标之一，包含5条线：

1. 转换线 (Tenkan-sen/Conversion Line): (9日最高+9日最低)/2
   - 短期趋势指标，类似9日均线
   
2. 基准线 (Kijun-sen/Base Line): (26日最高+26日最低)/2
   - 中期趋势指标，类似26日均线
   
3. 先行跨度A (Senkou Span A): (转换线+基准线)/2，前移26天
   - 云图的上边缘
   
4. 先行跨度B (Senkou Span B): (52日最高+52日最低)/2，前移26天
   - 云图的下边缘
   
5. 滞后跨度 (Chikou Span): 当前收盘价后移26天
   - 用于确认趋势

【云图 (Cloud/Kumo)】
- 云图是先行跨度A和B之间的区域
- 价格在云图之上 = 看涨
- 价格在云图之下 = 看跌
- 价格在云图之内 = 中性

【买入信号】
1. 价格突破云图（从下往上）
2. 转换线上穿基准线（金叉）
3. 滞后跨度在价格之上

【当前比特币状态】
'''  )

print('=' * 60)
