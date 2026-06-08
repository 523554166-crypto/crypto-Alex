#!/usr/bin/env python3
"""
诊断脚本 v2：用与 gen_signals.py 完全相同的逻辑计算 IC 得分，
精准定位 2026 年 IC 信号不触发的原因。
"""
import os
import sys
import pandas as pd
import numpy as np

OUTPUT_DIR = os.path.expanduser("~/.workbuddy/skills/bitcoin-qlib/output")

def diagnose():
    factor_path = os.path.join(OUTPUT_DIR, "btc_factors.csv")
    signal_csv  = os.path.join(OUTPUT_DIR, "ic_test_signal.csv")
    signals_csv = os.path.join(OUTPUT_DIR, "btc_signals.csv")

    df = pd.read_csv(factor_path)
    df['date'] = pd.to_datetime(df['date'])

    ic_df = pd.read_csv(signal_csv)
    ic_weights = dict(zip(ic_df.iloc[:, 0], ic_df.iloc[:, 1]))

    # ── 与 gen_signals.py 完全相同的逻辑 ──
    sorted_factors = sorted(ic_weights.items(), key=lambda x: abs(x[1]), reverse=True)[:12]
    top_factors = [(f[0], f[1]) for f in sorted_factors if f[0] in df.columns]

    first_valid = 60  # find_first_valid_idx 简化
    valid_mask = df.index >= first_valid

    df_norm = pd.DataFrame(index=df.index)
    for name, ic in top_factors:
        col = df[name]
        valid = col[valid_mask]
        mean_v, std_v = valid.mean(), valid.std()
        if std_v > 0:
            df_norm[name] = ((col - mean_v) / std_v).fillna(0)
        else:
            df_norm[name] = 0

    score = np.zeros(len(df))
    for name, ic in top_factors:
        score += ic * df_norm[name].values

    valid_scores = score[valid_mask]
    buy_threshold = np.percentile(valid_scores, 80)
    sell_threshold = np.percentile(valid_scores, 20)

    ic_signal = np.zeros(len(df), dtype=int)
    ic_signal[valid_mask & (score > buy_threshold)] = 1
    ic_signal[valid_mask & (score < sell_threshold)] = -1

    # ── 对齐 2026 年 ──
    df_2026 = df[df['date'].dt.year == 2026].copy().reset_index(drop=True)
    # 需要找到 2026 年在 df 中的索引位置
    idx_2026 = df[df['date'].dt.year == 2026].index

    score_2026 = score[idx_2026]
    ic_sig_2026 = ic_signal[idx_2026]
    rsi_2026 = df.loc[idx_2026, 'rsi_14'].values

    # 读取实际信号
    df_sig = pd.read_csv(signals_csv)
    df_sig['date'] = pd.to_datetime(df_sig['date'])
    actual_2026 = df_sig[df_sig['date'].dt.year == 2026]['signal'].values

    print(f"📊 2026 年 IC 信号诊断（与 gen_signals.py 完全相同的逻辑）\n")
    print(f"   得分范围（全量）: [{valid_scores.min():.4f}, {valid_scores.max():.4f}]")
    print(f"   P80 买入阈值: {buy_threshold:.4f}")
    print(f"   P20 卖出阈值: {sell_threshold:.4f}")
    print(f"   2026 年得分范围: [{score_2026.min():.4f}, {score_2026.max():.4f}]")
    print()

    # 统计 IC 信号 vs 实际信号
    n_ic_buy  = (ic_sig_2026 ==  1).sum()
    n_ic_sell = (ic_sig_2026 == -1).sum()
    n_ic_hold = (ic_sig_2026 ==  0).sum()
    print(f"📊 纯 IC 信号（2026）: 买入={n_ic_buy}, 卖出={n_ic_sell}, 持有={n_ic_hold}")

    n_act_buy  = (actual_2026 ==  1).sum()
    n_act_sell = (actual_2026 == -1).sum()
    n_act_hold = (actual_2026 ==  0).sum()
    print(f"📊 实际信号（2026）: 买入={n_act_buy}, 卖出={n_act_sell}, 持有={n_act_hold}")
    print()

    # 逐笔显示 IC 买入/卖出信号
    dates = df.loc[idx_2026, 'date'].values
    print("🟢 IC 买入信号（2026）：")
    for i in range(len(ic_sig_2026)):
        if ic_sig_2026[i] == 1:
            print(f"   {pd.Timestamp(dates[i]).strftime('%Y-%m-%d')}  "
                  f"得分={score_2026[i]:+.4f}  RSI={rsi_2026[i]:.1f}  "
                  f"实际信号={actual_2026[i]}")

    print("\n🔴 IC 卖出信号（2026）：")
    for i in range(len(ic_sig_2026)):
        if ic_sig_2026[i] == -1:
            print(f"   {pd.Timestamp(dates[i]).strftime('%Y-%m-%d')}  "
                  f"得分={score_2026[i]:+.4f}  RSI={rsi_2026[i]:.1f}  "
                  f"实际信号={actual_2026[i]}")

    # 核心问题：为什么 IC 信号这么少？
    # → 查看得分分布
    print(f"\n📈 2026 年得分分位数：")
    for p in [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99]:
        print(f"   P{p:2d}: {np.percentile(score_2026, p):+.4f}")

    # 有多少天得分 > P80 阈值？
    n_above = (score_2026 > buy_threshold).sum()
    n_below = (score_2026 < sell_threshold).sum()
    print(f"\n   得分 > P80 ({buy_threshold:+.4f}): {n_above} 天")
    print(f"   得分 < P20 ({sell_threshold:+.4f}): {n_below} 天")

    # 显示最高得分的几天
    print(f"\n📈 2026 年得分最高的 10 天：")
    top_idx = np.argsort(score_2026)[-10:][::-1]
    for i in top_idx:
        print(f"   {pd.Timestamp(dates[i]).strftime('%Y-%m-%d')}  "
              f"得分={score_2026[i]:+.4f}  RSI={rsi_2026[i]:.1f}  "
              f"IC信号={ic_sig_2026[i]:+d}  实际={actual_2026[i]:+d}")

    print(f"\n📉 2026 年得分最低的 10 天：")
    bot_idx = np.argsort(score_2026)[:10]
    for i in bot_idx:
        print(f"   {pd.Timestamp(dates[i]).strftime('%Y-%m-%d')}  "
              f"得分={score_2026[i]:+.4f}  RSI={rsi_2026[i]:.1f}  "
              f"IC信号={ic_sig_2026[i]:+d}  实际={actual_2026[i]:+d}")

if __name__ == "__main__":
    diagnose()
