#!/usr/bin/env python3
"""
直接按信号模拟交易 - 2026-01 至 2026-06
信号已预生成，直接逐日执行买卖
"""
import os
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime

OUTPUT_DIR = os.path.expanduser("~/.workbuddy/skills/bitcoin-qlib/output")

def load_signals(start_date, end_date):
    csv_path = os.path.join(OUTPUT_DIR, "btc_signals.csv")
    if not os.path.exists(csv_path):
        print("❌ 信号文件不存在，请先运行 gen_signals.py")
        sys.exit(1)
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    mask = (df['date'] >= start_date) & (df['date'] <= end_date)
    return df[mask].reset_index(drop=True)

def backtest(df, initial_capital=10000):
    """
    逐日模拟交易
    signal: 1=买入, 0=持有, -1=卖出
    """
    cash = initial_capital
    btc = 0.0
    trades = []
    equity_curve = []
    peak = initial_capital
    max_dd = 0.0
    dd_days = 0

    for i in range(len(df)):
        row = df.iloc[i]
        price = row['close']
        signal = int(row['signal'])
        date = row['date']

        if signal == 1 and cash > 10:  # 买入（留 $10 手续费）
            btc_bought = (cash - 10) / price
            # 简单手续费 0.1%
            fee = cash * 0.001
            btc_bought = (cash - fee - 10) / price
            btc += btc_bought
            cash = 0
            trades.append({'date': date, 'action': 'buy', 'price': price, 'btc': btc_bought})

        elif signal == -1 and btc > 0.00001:  # 卖出
            sell_value = btc * price
            fee = sell_value * 0.001
            cash += sell_value - fee
            trades.append({'date': date, 'action': 'sell', 'price': price, 'value': sell_value - fee})
            btc = 0.0

        # 记录当日权益
        equity = cash + btc * price
        equity_curve.append({'date': date, 'equity': equity, 'price': price})
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    # 最终权益（如果还持有 BTC）
    final_equity = cash + btc * df.iloc[-1]['close']
    return_ratio = (final_equity - initial_capital) / initial_capital

    # 计算胜率（每笔卖出交易）
    sell_trades = [t for t in trades if t['action'] == 'sell']
    buy_trades_map = [t for t in trades if t['action'] == 'buy']

    # 配对买卖交易计算盈亏
    paired_returns = []
    buy_queue = []
    for t in trades:
        if t['action'] == 'buy':
            buy_queue.append(t)
        elif t['action'] == 'sell' and buy_queue:
            buy_t = buy_queue.pop(0)
            ret = (t['value'] - (buy_t['btc'] * buy_t['price'])) / (buy_t['btc'] * buy_t['price'])
            paired_returns.append(ret)

    win_rate = sum(1 for r in paired_returns if r > 0) / len(paired_returns) if paired_returns else 0

    return {
        'initial': initial_capital,
        'final': final_equity,
        'return': return_ratio,
        'max_drawdown': max_dd,
        'win_rate': win_rate,
        'num_trades': len(trades),
        'num_buys': sum(1 for t in trades if t['action'] == 'buy'),
        'num_sells': sum(1 for t in trades if t['action'] == 'sell'),
        'equity_curve': equity_curve,
        'trades': trades,
        'paired_returns': paired_returns,
    }

def btc_buy_hold(df, initial_capital=10000):
    """BTC 买入持有基准"""
    price_start = df.iloc[0]['close']
    price_end = df.iloc[-1]['close']
    btc_bought = initial_capital / price_start
    final_value = btc_bought * price_end
    return_ratio = (final_value - initial_capital) / initial_capital
    return {
        'initial': initial_capital,
        'final': final_value,
        'return': return_ratio,
        'price_start': price_start,
        'price_end': price_end,
    }

def plot_equity(result, btc_result, save_path):
    equity = [e['equity'] for e in result['equity_curve']]
    dates = [e['date'] for e in result['equity_curve']]
    btc_equity = [result['initial'] * (e['price'] / result['equity_curve'][0]['price']) for e in result['equity_curve']]

    try:
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
    except Exception:
        pass

    plt.figure(figsize=(12, 6))
    plt.plot(dates, equity, label='Strategy', linewidth=2)
    plt.plot(dates, btc_equity, label='BTC Buy & Hold', linewidth=2, linestyle='--', alpha=0.7)
    plt.axhline(y=result['initial'], color='gray', linestyle=':', alpha=0.5)
    plt.xlabel('Date')
    plt.ylabel('Equity ($)')
    plt.title('Backtest Equity Curve (2026-01 ~ 2026-06)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=100)
    plt.close()
    print(f"📈 资金曲线已保存：{save_path}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-06-07")
    args = parser.parse_args()

    start_dt = pd.Timestamp(args.start)
    end_dt = pd.Timestamp(args.end)

    df = load_signals(start_dt, end_dt)
    print(f"📊 回测数据：{len(df)} 条")
    print(f"   日期范围：{df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}")

    # 策略回测
    result = backtest(df)
    print(f"\n📊 策略回测结果：")
    print(f"   初始资金：${result['initial']:,.0f}")
    print(f"   最终权益：${result['final']:,.0f}")
    print(f"   总收益率：{result['return']:.2%}")
    print(f"   最大回撤：{result['max_drawdown']:.2%}")
    print(f"   胜率：{result['win_rate']:.2%}")
    print(f"   交易次数：{result['num_trades']} (买{result['num_buys']}/卖{result['num_sells']})")

    # BTC 基准
    btc_result = btc_buy_hold(df)
    print(f"\n📊 BTC 买入持有基准：")
    print(f"   入场价：${btc_result['price_start']:,.0f}")
    print(f"   出场价：${btc_result['price_end']:,.0f}")
    print(f"   总收益率：{btc_result['return']:.2%}")

    # 绘制资金曲线
    plot_path = os.path.join(OUTPUT_DIR, "equity_curve_2026.png")
    plot_equity(result, btc_result, plot_path)

    # 保存结果
    detail_path = os.path.join(OUTPUT_DIR, "backtest_2026_detail.csv")
    import csv
    with open(detail_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'equity', 'price', 'action'])
        for e in result['equity_curve']:
            # 找当天是否有交易
            actions = [t['action'] for t in result['trades'] if t['date'] == e['date']]
            action_str = ','.join(actions) if actions else ''
            writer.writerow([e['date'].strftime('%Y-%m-%d'), f"{e['equity']:.2f}", f"{e['price']:.2f}", action_str])
    print(f"\n💾 详细结果已保存：{detail_path}")

    # 交易记录
    if result['trades']:
        print(f"\n📋 交易记录：")
        for t in result['trades']:
            if t['action'] == 'buy':
                print(f"   {t['date'].strftime('%Y-%m-%d')} 🟢 买入 @ ${t['price']:,.0f}")
            else:
                v = t.get('value', 0)
                print(f"   {t['date'].strftime('%Y-%m-%d')} 🔴 卖出 @ ${t['price']:,.0f} 到账 ${v:,.0f}")

if __name__ == "__main__":
    main()
