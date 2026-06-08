#!/usr/bin/env python3
"""
准备比特币历史数据（优先使用真实数据，失败时使用模拟数据）
支持多个数据源：yfinance、CoinGecko API
"""
import os
import sys
import time
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

OUTPUT_DIR = os.path.expanduser("~/.workbuddy/skills/bitcoin-qlib/output")

def download_btc_yfinance(start="2020-01-01", end=None, retries=3):
    """使用 yfinance 下载比特币数据（带重试）"""
    import yfinance as yf
    
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    
    print(f"📥 尝试 yfinance 下载 BTC-USD 数据: {start} 到 {end}")
    
    for attempt in range(retries):
        try:
            # 使用 Ticker.history 而不是 download（更稳定）
            ticker = yf.Ticker("BTC-USD")
            df = ticker.history(start=start, end=end, auto_adjust=True)
            
            if df.empty:
                print(f"⚠️ 第 {attempt+1} 次尝试：数据为空，等待 60 秒后重试...")
                time.sleep(60)
                continue
            
            print(f"✅ yfinance 下载完成：{len(df)} 条数据")
            
            # 重命名列为 Qlib 格式
            df = df.reset_index()
            qlib_df = pd.DataFrame({
                'symbol': 'BTC',
                'date': pd.to_datetime(df['Date']),
                'open': df['Open'],
                'high': df['High'],
                'low': df['Low'],
                'close': df['Close'],
                'volume': df['Volume'] if 'Volume' in df.columns else 0
            })
            
            return qlib_df
            
        except Exception as e:
            wait_time = 60 * (attempt + 1)
            print(f"⚠️ 第 {attempt+1} 次尝试失败：{str(e)[:100]}")
            if attempt < retries - 1:
                print(f"   等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
    
    print("❌ yfinance 下载失败（达到重试上限）")
    return None

def download_btc_coingecko(start="2020-01-01", end=None, retries=3):
    """使用 CoinGecko API 下载比特币数据（免费，无需 API key）"""
    print(f"📥 尝试 CoinGecko API 下载 BTC 数据...")
    
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    
    # 转换日期为时间戳
    start_ts = int(pd.Timestamp(start).timestamp())
    end_ts = int(pd.Timestamp(end).timestamp())
    
    # CoinGecko API 端点
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
    params = {
        'vs_currency': 'usd',
        'from': start_ts,
        'to': end_ts
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 429:  # Rate limit
                wait_time = 60 * (attempt + 1)
                print(f"⚠️ API 限流，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
                continue
            
            if response.status_code != 200:
                print(f"⚠️ API 返回错误 {response.status_code}：{response.text[:100]}")
                time.sleep(30)
                continue
            
            data = response.json()
            
            if 'prices' not in data:
                print(f"❌ API 返回数据格式错误")
                return None
            
            # 解析数据
            prices = data['prices']  # [[timestamp, price], ...]
            volumes = data.get('total_volumes', [])
            
            records = []
            for i, (ts, price) in enumerate(prices):
                date = pd.Timestamp(ts, unit='ms')
                volume = volumes[i][1] if i < len(volumes) else 0
                
                # CoinGecko 只有收盘价，需要估算 OHLC
                if i == 0:
                    open_price = price * 0.99
                    high = price * 1.01
                    low = price * 0.99
                else:
                    prev_price = prices[i-1][1]
                    open_price = prev_price
                    high = max(price, open_price) * 1.005
                    low = min(price, open_price) * 0.995
                
                records.append({
                    'symbol': 'BTC',
                    'date': date,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': price,
                    'volume': volume
                })
            
            df = pd.DataFrame(records)
            print(f"✅ CoinGecko 下载完成：{len(df)} 条数据")
            return df
            
        except Exception as e:
            print(f"⚠️ 第 {attempt+1} 次尝试失败：{str(e)[:100]}")
            if attempt < retries - 1:
                time.sleep(30)
    
    print("❌ CoinGecko 下载失败（达到重试上限）")
    return None

def download_btc_alternative(start="2020-01-01", end=None):
    """使用替代方案：从加密货币交易所公开 API 下载"""
    print(f"📥 尝试 Binance 公开 API 下载 BTC 数据...")
    
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    
    # Binance 公开 API（无需 API key）
    url = "https://api.binance.com/api/v3/klines"
    params = {
        'symbol': 'BTCUSDT',
        'interval': '1d',
        'startTime': int(pd.Timestamp(start).timestamp() * 1000),
        'endTime': int(pd.Timestamp(end).timestamp() * 1000),
        'limit': 1000
    }
    
    try:
        all_data = []
        while True:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                print(f"⚠️ Binance API 返回错误 {response.status_code}")
                return None
            
            data = response.json()
            if not data:
                break
            
            for d in data:
                all_data.append({
                    'symbol': 'BTC',
                    'date': pd.Timestamp(d[0], unit='ms'),
                    'open': float(d[1]),
                    'high': float(d[2]),
                    'low': float(d[3]),
                    'close': float(d[4]),
                    'volume': float(d[5])
                })
            
            # 更新 startTime 继续获取
            params['startTime'] = data[-1][0] + 1
            
            if len(data) < 1000:
                break
            
            time.sleep(1)  # 避免 API 限流
        
        if all_data:
            df = pd.DataFrame(all_data)
            print(f"✅ Binance 下载完成：{len(df)} 条数据")
            return df
        
    except Exception as e:
        print(f"⚠️ Binance 下载失败：{str(e)[:100]}")
        return None

def generate_test_data(start_date="2024-01-01", end_date=None, initial_price=45000):
    """生成模拟的比特币价格数据（备用方案）"""
    print(f"📥 使用模拟数据（真实数据源均失败）...")
    
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    # 生成日期范围
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    dates = pd.date_range(start=start, end=end, freq='D')
    
    print(f"📊 生成测试数据：{len(dates)} 条记录")
    
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
    print(f"✅ 模拟数据生成完成")
    return df

def save_data(df):
    """保存数据到输出目录"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    csv_path = os.path.join(OUTPUT_DIR, "btc_data.csv")
    df.to_csv(csv_path, index=False)
    print(f"💾 数据已保存：{csv_path}")
    
    # 生成统计信息
    print(f"\n📊 价格统计：")
    print(df[['open', 'high', 'low', 'close']].describe())
    print(f"\n   最新价格：{df['close'].iloc[-1]:.2f}")
    print(f"   最高价：{df['high'].max():.2f}")
    print(f"   最低价：{df['low'].min():.2f}")
    
    return csv_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="下载比特币历史数据（多数据源）")
    parser.add_argument("--start", default="2020-01-01", help="开始日期")
    parser.add_argument("--end", default=None, help="结束日期")
    parser.add_argument("--source", choices=['yfinance', 'coingecko', 'binance', 'auto'], 
                        default='auto', help="数据源（auto=自动尝试所有源）")
    parser.add_argument("--force-test", action='store_true', help="强制使用模拟数据")
    args = parser.parse_args()
    
    if args.force_test:
        print("⚠️ 强制使用模拟数据模式")
        df = generate_test_data(args.start, args.end)
        save_data(df)
        sys.exit(0)
    
    df = None
    
    if args.source in ['yfinance', 'auto']:
        df = download_btc_yfinance(args.start, args.end)
    
    if df is None and args.source in ['coingecko', 'auto']:
        df = download_btc_coingecko(args.start, args.end)
    
    if df is None and args.source in ['binance', 'auto']:
        df = download_btc_alternative(args.start, args.end)
    
    if df is None:
        print("\n⚠️ 所有真实数据源均失败，使用模拟数据...")
        df = generate_test_data(args.start, args.end)
    
    save_data(df)
