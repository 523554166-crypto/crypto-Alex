#!/usr/bin/env python3
"""
生成比特币测试数据（当 yfinance 被限流时使用）
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

OUTPUT_DIR = os.path.expanduser("~/.workbuddy/skills/bitcoin-qlib/output")

def generate_test_data(start_date="2024-01-01", end_date=None, initial_price=45000):
    """生成模拟的比特币价格数据"""
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    # 生成日期范围
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    dates = pd.date_range(start=start, end=end, freq='D')
    
    print(f"📊 生成测试数据：{len(dates)} 条记录")
    print(f"   日期范围：{start_date} 到 {end_date}")
    
    # 生成模拟价格数据（随机游走 + 趋势）
    np.random.seed(42)  # 固定随机种子，保证可重复
    n = len(dates)
    
    # 日收益率（均值 0.0005，标准差 0.03）
    returns = np.random.normal(0.0005, 0.03, n)
    
    # 添加一些趋势和周期性
    trend = np.linspace(0, 0.5, n)  # 上涨趋势
    seasonality = 0.1 * np.sin(2 * np.pi * np.arange(n) / 365)  # 年度周期
    
    # 合成价格
    price = initial_price * np.exp(np.cumsum(returns + trend / n + seasonality / n))
    
    # 生成 OHLC 数据
    data = []
    for i in range(n):
        close = price[i]
        high = close * (1 + abs(np.random.normal(0, 0.015)))
        low = close * (1 - abs(np.random.normal(0, 0.015)))
        open_price = close * (1 + np.random.normal(0, 0.01))
        volume = np.random.uniform(10000, 50000) * (1 + 0.5 * np.random.random())
        
        data.append({
            'symbol': 'BTC',
            'date': dates[i],
            'open': open_price,
            'high': max(open_price, high, close),
            'low': min(open_price, low, close),
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    return df

def save_data(df):
    """保存数据到输出目录"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    csv_path = os.path.join(OUTPUT_DIR, "btc_data.csv")
    df.to_csv(csv_path, index=False)
    print(f"✅ 测试数据已保存：{csv_path}")
    
    # 生成统计信息
    print(f"\n📊 价格统计：")
    print(df[['open', 'high', 'low', 'close']].describe())
    print(f"\n   最新价格：{df['close'].iloc[-1]:.2f}")
    print(f"   最高价：{df['high'].max():.2f}")
    print(f"   最低价：{df['low'].min():.2f}")
    
    return csv_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成比特币测试数据")
    parser.add_argument("--start", default="2024-01-01", help="开始日期")
    parser.add_argument("--end", default=None, help="结束日期")
    parser.add_argument("--initial-price", type=float, default=45000, help="初始价格")
    args = parser.parse_args()
    
    df = generate_test_data(args.start, args.end, args.initial_price)
    save_data(df)
