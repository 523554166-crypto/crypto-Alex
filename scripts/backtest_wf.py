#!/usr/bin/env python3
"""
Walk-Forward 回测 - 避免过拟合的滚动窗口回测
"""
import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

OUTPUT_DIR = os.path.expanduser("~/.workbuddy/skills/bitcoin-qlib/output")

def load_signals():
    """加载信号数据"""
    csv_path = os.path.join(OUTPUT_DIR, "btc_signals.csv")
    if not os.path.exists(csv_path):
        print("❌ 信号数据不存在，请先运行 gen_signals.py")
        sys.exit(1)
    
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df

def backtest_single_period(df, start_idx, end_idx, initial_capital=10000):
    """回测单个时间段"""
    portfolio = initial_capital
    btc_holdings = 0
    cash = initial_capital
    trades = []
    
    for i in range(start_idx, min(end_idx, len(df) - 1)):
        price = df.iloc[i]['close']
        signal = df.iloc[i]['signal']
        
        if signal == 1 and cash > 0:  # 买入信号
            btc_bought = cash / price
            btc_holdings += btc_bought
            cash = 0
            trades.append({
                'date': df.iloc[i]['date'],
                'action': 'buy',
                'price': price,
                'amount': btc_bought
            })
        
        elif signal == -1 and btc_holdings > 0:  # 卖出信号
            cash = btc_holdings * price
            trades.append({
                'date': df.iloc[i]['date'],
                'action': 'sell',
                'price': price,
                'amount': btc_holdings,
                'value': cash
            })
            btc_holdings = 0
    
    # 最终市值
    final_value = cash + btc_holdings * df.iloc[min(end_idx, len(df)-1)]['close']
    return_ratio = (final_value - initial_capital) / initial_capital
    
    return {
        'initial': initial_capital,
        'final': final_value,
        'return': return_ratio,
        'trades': trades
    }

def walk_forward_backtest(df, train_window=90, test_window=30):
    """Walk-Forward 回测"""
    print(f"🔄 开始 Walk-Forward 回测...")
    print(f"  训练窗口：{train_window} 天")
    print(f"  测试窗口：{test_window} 天")
    
    results = []
    total_days = len(df)
    
    current_idx = train_window  # 跳过初始训练期
    
    while current_idx + test_window < total_days:
        # 测试期
        test_start = current_idx
        test_end = current_idx + test_window
        
        result = backtest_single_period(df, test_start, test_end)
        result['start_date'] = df.iloc[test_start]['date']
        result['end_date'] = df.iloc[test_end]['date']
        result['period_return'] = result['return']
        
        results.append(result)
        
        # 滚动窗口
        current_idx += test_window
    
    return results

def calculate_metrics(results):
    """计算回测指标"""
    if not results:
        return {}
    
    total_return = np.prod([1 + r['return'] for r in results]) - 1
    returns = [r['return'] for r in results]
    
    # 年化收益率：基于实际跨度天数计算
    start_dt = pd.Timestamp(results[0]['start_date'])
    end_dt = pd.Timestamp(results[-1]['end_date'])
    years = (end_dt - start_dt).days / 365.25
    if years > 0:
        annual_return = (1 + total_return) ** (1 / years) - 1
    else:
        annual_return = total_return
    
    # 夏普：使用每周期收益率（不做年化，更保守）
    sharpe = np.mean(returns) / (np.std(returns) + 1e-6) * np.sqrt(252 / 30)
    
    max_dd = 0
    peak = 1
    equity = [1]
    
    for r in returns:
        equity.append(equity[-1] * (1 + r))
        if equity[-1] > peak:
            peak = equity[-1]
        dd = (peak - equity[-1]) / peak
        if dd > max_dd:
            max_dd = dd
    
    win_rate = len([r for r in returns if r > 0]) / len(returns)
    
    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'win_rate': win_rate,
        'num_periods': len(results),
        'years': years
    }

def plot_equity_curve(results, save_path):
    """绘制资金曲线"""
    # 尝试加载中文字体
    try:
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
    except Exception:
        pass

    equity = [1]
    for r in results:
        equity.append(equity[-1] * (1 + r['return']))

    plt.figure(figsize=(12, 6))
    plt.plot(equity, label='Strategy Equity', linewidth=2)
    plt.axhline(y=1, color='r', linestyle='--', label='Benchmark')
    plt.xlabel('Period')
    plt.ylabel('Equity (Normalized)')
    plt.title('Walk-Forward Backtest Equity Curve')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(save_path, dpi=100)
    plt.close()
    print(f"📈 资金曲线已保存：{save_path}")

def save_backtest_results(results, metrics):
    """保存回测结果"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 保存详细结果
    detail_path = os.path.join(OUTPUT_DIR, "backtest_detail.csv")
    df_results = pd.DataFrame(results)
    df_results.to_csv(detail_path, index=False)
    
    # 保存指标汇总
    summary_path = os.path.join(OUTPUT_DIR, "backtest_summary.txt")
    with open(summary_path, 'w') as f:
        f.write("=== Walk-Forward 回测汇总 ===\n\n")
        f.write(f"回测跨度：{metrics.get('years', 0):.1f} 年\n")
        f.write(f"总收益率：{metrics['total_return']:.2%}\n")
        f.write(f"年化收益率：{metrics['annual_return']:.2%}\n")
        f.write(f"夏普比率：{metrics['sharpe_ratio']:.2f}\n")
        f.write(f"最大回撤：{metrics['max_drawdown']:.2%}\n")
        f.write(f"胜率：{metrics['win_rate']:.2%}\n")
        f.write(f"回测周期数：{metrics['num_periods']}\n")
    
    print(f"\n💾 回测结果已保存：")
    print(f"  - 详细：{detail_path}")
    print(f"  - 汇总：{summary_path}")
    
    # 计算 BTC 买入持有基准
    btc_start = df_results.iloc[0]['initial']
    btc_end = df_results.iloc[-1]['final'] if len(df_results) > 0 else btc_start
    btc_prices = pd.read_csv(os.path.join(OUTPUT_DIR, "btc_signals.csv"))
    if 'close' in btc_prices.columns:
        first_price = btc_prices['close'].iloc[0] if len(btc_prices) > 0 else 1
        last_price = btc_prices['close'].iloc[-1] if len(btc_prices) > 0 else 1
        btc_return = (last_price - first_price) / first_price
        years = metrics.get('years', 1)
        btc_annual = (1 + btc_return) ** (1 / years) - 1 if years > 0 else 0
        print(f"\n📊 BTC 买入持有基准 (相同区间)：")
        print(f"   总收益：{btc_return:.2%}")
        print(f"   年化：{btc_annual:.2%}")
    else:
        btc_return = 0
        btc_annual = 0
    
    # 绘制资金曲线
    plot_path = os.path.join(OUTPUT_DIR, "equity_curve.png")
    plot_equity_curve(results, plot_path)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Walk-Forward 回测")
    parser.add_argument("--start", default="2023-01-01", help="开始日期")
    parser.add_argument("--end", default=None, help="结束日期")
    parser.add_argument("--train-window", type=int, default=90, help="训练窗口（天）")
    parser.add_argument("--test-window", type=int, default=30, help="测试窗口（天）")
    args = parser.parse_args()
    
    df = load_signals()
    
    # 筛选日期
    if args.start:
        df = df[df['date'] >= pd.Timestamp(args.start)]
    if args.end:
        df = df[df['date'] <= pd.Timestamp(args.end)]
    
    print(f"📊 回测数据：{len(df)} 条记录")
    print(f"   日期范围：{df['date'].min()} 到 {df['date'].max()}")
    
    # 执行 Walk-Forward 回测
    results = walk_forward_backtest(df, train_window=args.train_window, test_window=args.test_window)
    
    if not results:
        print("❌ 无回测结果，请检查数据")
        sys.exit(1)
    
    # 计算指标
    metrics = calculate_metrics(results)
    
    print(f"\n📊 回测结果：")
    print(f"  总收益率：{metrics['total_return']:.2%}")
    print(f"  年化收益率：{metrics['annual_return']:.2%}")
    print(f"  夏普比率：{metrics['sharpe_ratio']:.2f}")
    print(f"  最大回撤：{metrics['max_drawdown']:.2%}")
    print(f"  胜率：{metrics['win_rate']:.2%}")
    
    save_backtest_results(results, metrics)
