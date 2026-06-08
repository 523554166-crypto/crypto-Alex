#!/usr/bin/env python3
"""
组合策略：根据 MA200 自动切换模式
- 牛市（价格 > MA200）：RSI 均值回归（跌破 20 买入）
- 熊市（价格 < MA200）：RSI 复苏（回升突破 30 买入）
- 通用卖出条件：RSI > 70
- 止损：-12%
"""
import os
import sys
import argparse
import numpy as np
import pandas as pd

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def generate_combo_strategy(df, rsi_oversold=20, rsi_recovery=30, rsi_sell=70):
    """生成组合策略信号"""
    if 'rsi_14' not in df.columns or 'ma_200' not in df.columns:
        print("❌ 需要 RSI 和 MA200 数据")
        sys.exit(1)

    rsi = df['rsi_14'].values
    ma200 = df['ma_200'].values
    price = df['close'].values
    n = len(df)
    signals = np.zeros(n, dtype=int)

    print(f"\n📊 组合策略（牛熊自动切换）")
    print(f"   牛市（价>MA200）：RSI 均值回归（跌破 {rsi_oversold} 买入）")
    print(f"   熊市（价<MA200）：RSI 复苏（回升突破 {rsi_recovery} 买入）")
    print(f"   卖出条件：RSI > {rsi_sell}")
    print(f"   止损：-12%\n")

    for i in range(1, n):
        is_bull = price[i] > ma200[i] if not np.isnan(ma200[i]) else True

        if is_bull:
            # 牛市：RSI 均值回归
            if rsi[i] < rsi_oversold and rsi[i-1] >= rsi_oversold:
                signals[i] = 1
        else:
            # 熊市：RSI 复苏（更安全）
            if rsi[i-1] <= rsi_recovery and rsi[i] > rsi_recovery:
                signals[i] = 1

        # 卖出：RSI 超买
        if rsi[i] > rsi_sell and rsi[i-1] <= rsi_sell:
            signals[i] = -1

    df['signal'] = signals

    # 统计
    sig = df['signal']
    total = len(df)
    bull_days = (df['close'] > df['ma_200']).sum() if 'ma_200' in df.columns else 0
    bear_days = total - bull_days

    print(f"📊 信号分布 (共 {total} 条）：")
    for v, label in [(1, '🟢 买入'), (-1, '🔴 卖出'), (0, '⚪ 持有')]:
        cnt = (sig == v).sum()
        print(f"   {label} ({v:>2}): {cnt:>5} 次 ({cnt/total*100:5.1f}%)")
    print(f"\n   牛市天数：{bull_days} ({bull_days/total*100:.0f}%)")
    print(f"   熊市天数：{bear_days} ({bear_days/total*100:.0f}%)")

    return df


def backtest_combo(df, start="2025-01-01", end="2026-06-07", stop_loss=-12.0):
    """回测组合策略"""
    df_test = df[(df['date'] >= start) & (df['date'] <= end)].copy()

    if len(df_test) == 0:
        print(f"❌ {start}~{end} 无数据")
        return

    print(f"\n{'='*60}")
    print(f"📊 组合策略回测")
    print(f"{'='*60}")
    print(f"数据区间: {df_test['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df_test['date'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"总交易日: {len(df_test)}\n")

    cash = 10000.0
    btc_holdings = 0.0
    in_position = False
    entry_price = 0.0
    entry_date = None
    trades = []
    equity = [cash]
    dates = [df_test.iloc[0]['date']]
    stop_loss_val = float(stop_loss)

    for i in range(len(df_test)):
        row = df_test.iloc[i]
        price = row['close']
        signal = row['signal']
        date = row['date']
        rsi = row['rsi_14']

        # 止损检查
        if in_position:
            unrealized_ret = (price - entry_price) / entry_price * 100
            if unrealized_ret < stop_loss_val:
                fee = btc_holdings * price * 0.001
                cash = btc_holdings * price - fee
                trades.append({
                    'date': date,
                    'type': 'SELL',
                    'price': price,
                    'cash': cash,
                    'return': unrealized_ret,
                    'fee': fee,
                    'note': f'止损 {unrealized_ret:.1f}%'
                })
                btc_holdings = 0.0
                in_position = False
                entry_price = 0.0

        if signal == 1 and not in_position:
            fee = cash * 0.001
            btc_holdings = (cash - fee) / price
            entry_price = price
            entry_date = date
            in_position = True
            trades.append({
                'date': date,
                'type': 'BUY',
                'price': price,
                'cash': cash,
                'fee': fee,
                'rsi': rsi
            })

        elif signal == -1 and in_position:
            fee = btc_holdings * price * 0.001
            cash = btc_holdings * price - fee
            ret = (price - entry_price) / entry_price * 100
            trades.append({
                'date': date,
                'type': 'SELL',
                'price': price,
                'cash': cash,
                'return': ret,
                'fee': fee,
                'rsi': rsi
            })
            btc_holdings = 0.0
            in_position = False
            entry_price = 0.0

        if in_position:
            equity.append(btc_holdings * price)
        else:
            equity.append(cash)
        dates.append(date)

    # 强制平仓
    if in_position:
        last_price = df_test.iloc[-1]['close']
        fee = btc_holdings * last_price * 0.001
        cash = btc_holdings * last_price - fee
        ret = (last_price - entry_price) / entry_price * 100
        trades.append({
            'date': df_test.iloc[-1]['date'],
            'type': 'SELL',
            'price': last_price,
            'cash': cash,
            'return': ret,
            'fee': fee,
            'note': '期末强制平仓'
        })
        btc_holdings = 0.0
        in_position = False

    final_value = cash
    init_price = df_test.iloc[0]['close']
    final_price = df_test.iloc[-1]['close']
    btc_buyhold = 10000 * (final_price / init_price)
    strategy_ret = (final_value - 10000) / 10000 * 100
    btc_ret = (final_price / init_price - 1) * 100

    equity_arr = np.array(equity)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = (equity_arr - peak) / peak * 100
    max_dd = drawdown.min()

    sell_trades = [t for t in trades if t['type'] == 'SELL']
    win_trades = [t for t in sell_trades if t.get('return', 0) > 0]
    win_rate = len(win_trades) / len(sell_trades) * 100 if sell_trades else 0

    print(f"\n{'='*60}")
    print(f"📊 回测结果")
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
                  f"资金 ${t['cash']:,.0f}  RSI={t.get('rsi', 0):.1f}  手续费 ${t['fee']:.2f}")
        else:
            print(f"  {t['date'].strftime('%Y-%m-%d')}  SELL ${t['price']:,.0f}  "
                  f"资金 ${t['cash']:,.0f}  收益 {t.get('return', 0):+.2f}%  "
                  f"(手续费 ${t.get('fee', 0):.2f}) {'⚠️ '+t.get('note','') if t.get('note') else ''}")

    # 绘制资金曲线
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.figure(figsize=(14, 7))

    dates_arr = dates[1:]
    equity_arr = equity[1:]
    btc_equity = [10000 * (df_test.iloc[min(i, len(df_test)-1)]['close'] / init_price)
                  for i in range(len(dates_arr))]

    plt.plot(dates_arr, equity_arr, label='策略净值', linewidth=2, color='#1f77b4')
    plt.plot(dates_arr, btc_equity, label='BTC 买入持有', linewidth=2, alpha=0.7, color='orange')
    plt.axhline(y=10000, color='gray', linestyle='--', alpha=0.5)
    plt.ylabel('净值 (USD)', fontsize=12)
    plt.title('组合策略（牛熊自动切换）- 资金曲线', fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)

    for t in trades:
        idx = dates.index(t['date'])
        if t['type'] == 'BUY':
            plt.scatter(t['date'], equity[idx],
                       color='green', marker='^', s=100, zorder=5)
        else:
            plt.scatter(t['date'], equity[idx],
                       color='red', marker='v', s=100, zorder=5)

    plt.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "backtest_combo.png")
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n💾 资金曲线已保存: {plot_path}")

    return final_value, strategy_ret, btc_ret


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="组合策略回测（牛熊自动切换）")
    parser.add_argument("--start", type=str, default="2025-01-01", help="开始日期")
    parser.add_argument("--end", type=str, default="2026-06-07", help="结束日期")
    parser.add_argument("--rsi-oversold", type=float, default=20, help="牛市 RSI 买入阈值")
    parser.add_argument("--rsi-recovery", type=float, default=30, help="熊市 RSI 买入阈值")
    parser.add_argument("--rsi-sell", type=float, default=70, help="RSI 卖出阈值")
    parser.add_argument("--stop-loss", type=float, default=-12.0, help="止损百分比")
    args = parser.parse_args()

    factor_path = os.path.join(OUTPUT_DIR, "btc_factors.csv")
    if not os.path.exists(factor_path):
        print("❌ 因子数据不存在，请先运行 calc_factors.py")
        sys.exit(1)

    df = pd.read_csv(factor_path)
    df['date'] = pd.to_datetime(df['date'])

    df = generate_combo_strategy(df, rsi_oversold=args.rsi_oversold,
                                rsi_recovery=args.rsi_recovery, rsi_sell=args.rsi_sell)

    backtest_combo(df, start=args.start, end=args.end, stop_loss=args.stop_loss)
