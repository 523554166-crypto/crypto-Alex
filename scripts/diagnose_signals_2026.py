#!/usr/bin/env python3
"""
诊断脚本：分析 2026 年信号来源（IC 信号 vs RSI 修正）
"""
import os
import sys
import pandas as pd
import numpy as np

OUTPUT_DIR = os.path.expanduser("~/.workbuddy/skills/bitcoin-qlib/output")
SIGNAL_CSV = os.path.join(OUTPUT_DIR, "btc_signals.csv")

def diagnose_signals():
    if not os.path.exists(SIGNAL_CSV):
        print("❌ 信号文件不存在，请先运行 gen_signals.py")
        sys.exit(1)

    df = pd.read_csv(SIGNAL_CSV)
    df['date'] = pd.to_datetime(df['date'])

    # 只取 2026 年
    df_2026 = df[df['date'].dt.year == 2026].copy()
    if len(df_2026) == 0:
        print("⚠️ 2026 年无数据")
        return

    print(f"📊 2026 年信号诊断（共 {len(df_2026)} 条）")
    print(f"   日期范围：{df_2026['date'].min().strftime('%Y-%m-%d')} ~ {df_2026['date'].max().strftime('%Y-%m-%d')}")

    sig = df_2026['signal']
    rsi = df_2026['rsi_14']

    # 统计信号分布
    print(f"\n📊 信号分布：")
    for v, label in [(-1, '卖出'), (0, '持有'), (1, '买入')]:
        cnt = (sig == v).sum()
        print(f"   {label}: {cnt} 次 ({cnt/len(df_2026)*100:.1f}%)")

    # 分析 RSI 极端值覆盖情况
    print(f"\n🔧 RSI 极端值分析：")
    rsi_buy = (rsi < 15).sum()
    rsi_sell = (rsi > 85).sum()
    rsi_nosell = ((rsi < 25) & (sig == -1)).sum()
    rsi_nobuy = ((rsi > 75) & (sig == 1)).sum()
    print(f"   RSI < 15（强制买入）: {rsi_buy} 天")
    print(f"   RSI > 85（强制卖出）: {rsi_sell} 天")
    print(f"   RSI < 25 且信号=-1（阻止卖出）: {rsi_nosell} 天")
    print(f"   RSI > 75 且信号=+1（阻止买入）: {rsi_nobuy} 天")

    # 关键问题：有多少信号是纯 IC 信号（非 RSI 修正）？
    # 重新生成 IC 信号（不做 RSI 修正），对比差异
    print(f"\n🔬 重新生成无 RSI 修正的 IC 信号进行对比...")

    # 加载因子和 IC
    factor_path = os.path.join(OUTPUT_DIR, "btc_factors.csv")
    ic_path = os.path.join(OUTPUT_DIR, "ic_test_signal.csv")
    df_full = pd.read_csv(factor_path)
    df_full['date'] = pd.to_datetime(df_full['date'])
    ic_df = pd.read_csv(ic_path)
    ic_weights = dict(zip(ic_df.iloc[:, 0], ic_df.iloc[:, 1]))

    # 只取 2026 年且有因子的数据
    df_2026_factors = df_full[df_full['date'].dt.year == 2026].copy()
    if len(df_2026_factors) == 0:
        print("⚠️ 2026 年因子数据不存在")
        return

    # 取 top 12 因子
    sorted_factors = sorted(ic_weights.items(), key=lambda x: abs(x[1]), reverse=True)[:12]
    top_factors = [(f[0], f[1]) for f in sorted_factors if f[0] in df_2026_factors.columns]

    # 计算 IC 加权得分
    valid_mask = df_2026_factors.index >= 60  # 跳过前 60 天（因子 NaN）
    df_norm = pd.DataFrame(index=df_2026_factors.index)
    for name, ic in top_factors:
        col = df_2026_factors[name]
        valid = col[valid_mask]
        mean_v, std_v = valid.mean(), valid.std()
        if std_v > 0:
            df_norm[name] = ((col - mean_v) / std_v).fillna(0)
        else:
            df_norm[name] = 0

    score = np.zeros(len(df_2026_factors))
    for name, ic in top_factors:
        score += ic * df_norm[name].values

    valid_scores = score[valid_mask]
    buy_threshold = np.percentile(valid_scores, 80)
    sell_threshold = np.percentile(valid_scores, 20)

    # 生成纯 IC 信号
    ic_signal = np.zeros(len(df_2026_factors), dtype=int)
    ic_signal[valid_mask & (score > buy_threshold)] = 1
    ic_signal[valid_mask & (score < sell_threshold)] = -1

    # 对比：实际信号 vs 纯 IC 信号
    actual_signal = df_2026['signal'].values
    ic_signal_aligned = ic_signal[df_2026_factors.index.isin(df_2026.index)]

    # 对齐索引
    df_cmp = pd.DataFrame({
        'date': df_2026['date'].values,
        'rsi': rsi.values,
        'ic_signal': ic_signal[:len(df_2026)],
        'actual_signal': actual_signal,
    })
    df_cmp['rsi_forced_buy'] = df_cmp['rsi'] < 15
    df_cmp['rsi_forced_sell'] = df_cmp['rsi'] > 85

    # 统计：纯 IC 信号有多少
    n_ic_buy = (df_cmp['ic_signal'] == 1).sum()
    n_ic_sell = (df_cmp['ic_signal'] == -1).sum()
    n_ic_hold = (df_cmp['ic_signal'] == 0).sum()
    print(f"\n📊 纯 IC 信号分布（无 RSI 修正）：")
    print(f"   买入: {n_ic_buy} 次, 卖出: {n_ic_sell} 次, 持有: {n_ic_hold} 次")

    # 统计：实际信号中有多少与纯 IC 信号一致
    agree = (df_cmp['ic_signal'] == df_cmp['actual_signal']).sum()
    print(f"\n📊 实际信号与纯 IC 信号一致: {agree}/{len(df_cmp)} ({agree/len(df_cmp)*100:.1f}%)")

    # 显示不一致的案例
    disagree = df_cmp[df_cmp['ic_signal'] != df_cmp['actual_signal']]
    if len(disagree) > 0:
        print(f"\n⚠️ 信号不一致（RSI 修正覆盖 IC 信号），共 {len(disagree)} 天：")
        for _, row in disagree.head(10).iterrows():
            print(f"   {row['date'].strftime('%Y-%m-%d')}: "
                  f"IC信号={row['ic_signal']:>2}, "
                  f"实际信号={row['actual_signal']:>2}, "
                  f"RSI={row['rsi']:.1f}, "
                  f"RSI强制买入={row['rsi_forced_buy']}, "
                  f"RSI强制卖出={row['rsi_forced_sell']}")

    # 关键诊断：IC 得分分布
    print(f"\n📊 IC 得分分布（2026 年）：")
    print(f"   最小值: {valid_scores.min():.4f}")
    print(f"   最大值: {valid_scores.max():.4f}")
    print(f"   均值: {valid_scores.mean():.4f}")
    print(f"   标准差: {valid_scores.std():.4f}")
    print(f"   买入阈值 (P80): {buy_threshold:.4f}")
    print(f"   卖出阈值 (P20): {sell_threshold:.4f}")

    # 显示具体的买入/卖出信号日期
    buy_dates = df_cmp[df_cmp['actual_signal'] == 1]['date']
    sell_dates = df_cmp[df_cmp['actual_signal'] == -1]['date']
    print(f"\n🟢 买入信号日期（共 {len(buy_dates)} 天）：")
    for d in buy_dates.dt.strftime('%Y-%m-%d'):
        print(f"   {d}")
    print(f"\n🔴 卖出信号日期（共 {len(sell_dates)} 天）：")
    for d in sell_dates.dt.strftime('%Y-%m-%d'):
        print(f"   {d}")

if __name__ == "__main__":
    diagnose_signals()
