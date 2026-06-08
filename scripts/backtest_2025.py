#!/usr/bin/env python3
"""
2025 年回测（无未来函数版本）
用法: python backtest_2025.py
"""
import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

def backtest_2025(signals_file, start="2025-01-01", end="2025-12-31"):
    """回测 2025 年策略表现（无未来函数）"""
    df = pd.read_csv(signals_file)
    df['date'] = pd.to_datetime(df['date'])
    df_2025 = df[(df['date'] >= start) & (df['date'] <= end)].copy()
    
    if len(df_2025) == 0:
        print(f"❌ {start}~{end} 无数据")
        return
    
    print(f"\n{'='*60}")
    print(f"📊 2025 年回测（无未来函数）")
    print(f"{'='*60}")
    print(f"数据区间: {df_2025['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df_2025['date'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"总交易日: {len(df_2025)}\n")
    
    # 统计信号分布
    sig_counts = df_2025['signal'].value_counts().sort_index()
    print(f"信号分布:")
    print(f"  买入(1):  {sig_counts.get(1, 0):4d} 天 ({sig_counts.get(1, 0)/len(df_2025)*100:.1f}%)")
    print(f"  持有(0):  {sig_counts.get(0, 0):4d} 天 ({sig_counts.get(0, 0)/len(df_2025)*100:.1f}%)")
    print(f"  卖出(-1): {sig_counts.get(-1, 0):4d} 天 ({sig_counts.get(-1, 0)/len(df_2025)*100:.1f}%)")
    
    # 模拟交易
    cash = 10000.0
    btc_holdings = 0.0
    in_position = False
    entry_price = 0.0
    trades = []
    equity = [cash]
    dates = [df_2025.iloc[0]['date']]
    
    for i in range(len(df_2025)):
        row = df_2025.iloc[i]
        price = row['close']
        signal = row['signal']
        date = row['date']
        
        # ── 止损检查（优先于信号）──
        if in_position:
            unrealized_ret = (price - entry_price) / entry_price * 100
            if unrealized_ret < -12.0:  # 止损 -12%（BTC 波动大）
                fee = btc_holdings * price * 0.001
                cash = btc_holdings * price - fee
                trades.append({
                    'date': date,
                    'type': 'SELL',
                    'price': price,
                    'cash': cash,
                    'return': unrealized_ret,
                    'fee': fee,
                    'note': f'止损 {-unrealized_ret:.1f}%'
                })
                btc_holdings = 0.0
                in_position = False
                entry_price = 0.0
                # 记录净值后继续
                equity.append(cash)
                dates.append(date)
                continue
        
        if signal == 1 and not in_position:
            # 买入
            fee = cash * 0.001
            btc_holdings = (cash - fee) / price
            entry_price = price
            in_position = True
            trades.append({
                'date': date,
                'type': 'BUY',
                'price': price,
                'cash': cash,
                'fee': fee
            })
        
        elif signal == -1 and in_position:
            # 卖出
            fee = btc_holdings * price * 0.001
            cash = btc_holdings * price - fee
            ret = (price - entry_price) / entry_price * 100
            trades.append({
                'date': date,
                'type': 'SELL',
                'price': price,
                'cash': cash,
                'return': ret,
                'fee': fee
            })
            btc_holdings = 0.0
            in_position = False
            entry_price = 0.0
        
        # 记录净值
        if in_position:
            equity.append(btc_holdings * price)
        else:
            equity.append(cash)
        dates.append(date)
    
    # 年末强制平仓
    if in_position:
        last_price = df_2025.iloc[-1]['close']
        fee = btc_holdings * last_price * 0.001
        cash = btc_holdings * last_price - fee
        ret = (last_price - entry_price) / entry_price * 100
        trades.append({
            'date': df_2025.iloc[-1]['date'],
            'type': 'SELL',
            'price': last_price,
            'cash': cash,
            'return': ret,
            'fee': fee,
            'note': '年末强制平仓'
        })
        btc_holdings = 0.0
        in_position = False
    
    final_value = cash
    btc_buyhold = 10000 * (df_2025.iloc[-1]['close'] / df_2025.iloc[0]['close'])
    strategy_ret = (final_value - 10000) / 10000 * 100
    btc_ret = (df_2025.iloc[-1]['close'] / df_2025.iloc[0]['close'] - 1) * 100
    
    # 计算最大回撤
    equity_arr = np.array(equity)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = (equity_arr - peak) / peak * 100
    max_dd = drawdown.min()
    
    # 计算胜率
    sell_trades = [t for t in trades if t['type'] == 'SELL']
    win_trades = [t for t in sell_trades if t.get('return', 0) > 0]
    win_rate = len(win_trades) / len(sell_trades) * 100 if sell_trades else 0
    
    print(f"\n{'='*60}")
    print(f"📊 2025 年回测结果")
    print(f"{'='*60}")
    print(f"初始资金:     $10,000")
    print(f"最终资金:     ${final_value:,.2f}")
    print(f"策略收益率:   {strategy_ret:+.2f}%")
    print(f"BTC 买入持有: {btc_ret:+.2f}%  (净值 ${btc_buyhold:,.2f})")
    print(f"超额收益:     {strategy_ret - btc_ret:+.2f}%")
    print(f"最大回撤:     {max_dd:.2f}%")
    print(f"交易次数:     {len(sell_trades)} 笔")
    print(f"胜率:         {win_rate:.1f}%")
    
    print(f"\n📋 交易明细:")
    print(f"{'='*60}")
    for t in trades:
        if t['type'] == 'BUY':
            print(f"  {t['date'].strftime('%Y-%m-%d')}  BUY  ${t['price']:,.0f}  "
                  f"资金 ${t['cash']:,.0f} 手续费 ${t['fee']:.2f}")
        else:
            print(f"  {t['date'].strftime('%Y-%m-%d')}  SELL ${t['price']:,.0f}  "
                  f"资金 ${t['cash']:,.0f}  收益 {t.get('return', 0):+.2f}%  "
                  f"(手续费 ${t.get('fee', 0):.2f}) {'⚠️ '+t.get('note','') if t.get('note') else ''}")
    
    # 按月统计
    df_2025['month'] = df_2025['date'].dt.to_period('M')
    monthly = []
    for month, group in df_2025.groupby('month'):
        month_signals = group['signal'].value_counts()
        buy_count = month_signals.get(1, 0)
        sell_count = month_signals.get(-1, 0)
        monthly.append({
            'month': str(month),
            'buy': buy_count,
            'sell': sell_count,
            'close': group.iloc[-1]['close']
        })
    
    print(f"\n📅 按月信号统计:")
    print(f"{'='*60}")
    prev_close = df_2025.iloc[0]['close']
    for m in monthly:
        ret = (m['close'] / prev_close - 1) * 100
        print(f"  {m['month']}  买入{m['buy']:2d}次  卖出{m['sell']:2d}次  "
              f"收盘价 ${m['close']:,.0f}  月涨跌 {ret:+.1f}%")
        prev_close = m['close']
    
    # 绘制资金曲线
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    # 上图：资金曲线 vs BTC 买入持有
    dates_array = dates[1:]
    equity_array = equity[1:]
    btc_equity = [10000 * (df_2025.iloc[min(i, len(df_2025)-1)]['close'] / df_2025.iloc[0]['close']) 
                  for i in range(len(dates_array))]
    
    ax1.plot(dates_array, equity_array, label='策略净值', linewidth=2, color='#1f77b4')
    ax1.plot(dates_array, btc_equity, label='BTC 买入持有', linewidth=2, alpha=0.7, color='orange')
    ax1.axhline(y=10000, color='gray', linestyle='--', alpha=0.5)
    ax1.set_ylabel('净值 (USD)', fontsize=12)
    ax1.set_title('2025 年回测 - 资金曲线（无未来函数）', fontsize=14)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 标记买卖点
    for t in trades:
        if t['type'] == 'BUY':
            ax1.scatter(t['date'], equity[dates.index(t['date'])], 
                       color='green', marker='^', s=100, zorder=5)
        else:
            ax1.scatter(t['date'], equity[dates.index(t['date'])], 
                       color='red', marker='v', s=100, zorder=5)
    
    # 下图：BTC 价格 + 信号
    ax2.plot(df_2025['date'], df_2025['close'], label='BTC 价格', color='black', linewidth=1.5)
    buy_dates = df_2025[df_2025['signal'] == 1]['date']
    buy_prices = df_2025[df_2025['signal'] == 1]['close']
    sell_dates = df_2025[df_2025['signal'] == -1]['date']
    sell_prices = df_2025[df_2025['signal'] == -1]['close']
    ax2.scatter(buy_dates, buy_prices, color='green', marker='^', s=80, label='买入', zorder=5)
    ax2.scatter(sell_dates, sell_prices, color='red', marker='v', s=80, label='卖出', zorder=5)
    ax2.set_ylabel('BTC 价格 (USD)', fontsize=12)
    ax2.set_xlabel('日期', fontsize=12)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "backtest_2025_no_lookahead.png")
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n💾 资金曲线已保存: {plot_path}")
    
    return final_value, strategy_ret, btc_ret

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="2025 年回测（无未来函数）")
    parser.add_argument("--file", default=None, help="信号文件路径（默认自动查找 btc_signals_2025*.csv）")
    args = parser.parse_args()

    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

    if args.file:
        signals_file = args.file
    else:
        # 自动查找信号文件
        import glob
        pattern = os.path.join(OUTPUT_DIR, "btc_signals_2025*.csv")
        matches = glob.glob(pattern)
        if matches:
            signals_file = matches[-1]  # 取最新的
        else:
            signals_file = os.path.join(OUTPUT_DIR, "btc_signals_2025.csv")

    if not os.path.exists(signals_file):
        print(f"❌ 信号文件不存在: {signals_file}")
        print(f"请先运行: python gen_signals.py --no-lookahead --year 2025")
        sys.exit(1)

    print(f"📂 使用信号文件: {os.path.basename(signals_file)}")
    backtest_2025(signals_file)
