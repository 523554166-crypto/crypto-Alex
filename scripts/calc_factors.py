#!/usr/bin/env python3
"""
计算比特币技术指标因子（IC测试验证）
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

OUTPUT_DIR = os.path.expanduser("~/.workbuddy/skills/bitcoin-qlib/output")

def load_data():
    """加载已下载的数据"""
    csv_path = os.path.join(OUTPUT_DIR, "btc_data.csv")
    if not os.path.exists(csv_path):
        print("❌ 数据文件不存在，请先运行 prepare_data.py")
        sys.exit(1)
    
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df

def calc_momentum(df, periods=[5, 10, 20, 60]):
    """计算动量因子"""
    for p in periods:
        df[f'return_{p}'] = df['close'].pct_change(p)
    return df

def calc_volatility(df, windows=[5, 10, 20]):
    """计算波动率因子"""
    returns = df['close'].pct_change()
    for w in windows:
        df[f'vol_{w}'] = returns.rolling(w).std()
    return df

def calc_volume_signal(df, windows=[5, 10, 20]):
    """计算成交量信号因子"""
    for w in windows:
        df[f'volume_ma_{w}'] = df['volume'].rolling(w).mean()
        df[f'volume_ratio_{w}'] = df['volume'] / df[f'volume_ma_{w}']
    return df

def calc_rsi(df, periods=[14]):
    """计算 RSI 因子"""
    for p in periods:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(p).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(p).mean()
        rs = gain / loss
        df[f'rsi_{p}'] = 100 - (100 / (1 + rs))
    return df

def calc_macd(df, fast=12, slow=26, signal=9):
    """计算 MACD 因子"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df

def calc_factors(df):
    """计算所有因子"""
    print("🔢 计算因子...")
    
    # 价格因子
    df = calc_momentum(df)
    df = calc_volatility(df)
    df = calc_volume_signal(df)
    df = calc_rsi(df)
    df = calc_macd(df)
    
    # 移动平均因子
    for w in [5, 10, 20, 60, 200]:
        df[f'ma_{w}'] = df['close'].rolling(w).mean()
        df[f'ma_ratio_{w}'] = df['close'] / df[f'ma_{w}']
    
    # 布林带因子
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * bb_std
    df['bb_lower'] = df['bb_middle'] - 2 * bb_std
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    print(f"✅ 因子计算完成，共 {len([c for c in df.columns if c not in ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']])} 个因子")
    
    return df

def save_factors(df):
    """保存因子数据"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUTPUT_DIR, "btc_factors.csv")
    df.to_csv(csv_path, index=False)
    print(f"💾 因子数据已保存：{csv_path}")
    return csv_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="计算比特币技术指标因子")
    parser.add_argument("--start", default="2020-01-01", help="开始日期")
    parser.add_argument("--end", default=None, help="结束日期")
    args = parser.parse_args()
    
    df = load_data()
    
    # 筛选日期范围
    if args.start:
        df = df[df['date'] >= args.start]
    if args.end:
        df = df[df['date'] <= args.end]
    
    df = calc_factors(df)
    save_factors(df)
