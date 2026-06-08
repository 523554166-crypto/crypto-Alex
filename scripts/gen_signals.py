#!/usr/bin/env python3
"""
生成交易信号（基于因子 IC 加权 + RSI 修正）
支持两种模式：
1. 全样本归一化（有未来函数，Qlib 标准做法）
2. 滚动窗口归一化（无未来函数，只用历史数据）
"""
import os
import sys
import argparse
import pandas as pd
import numpy as np

OUTPUT_DIR = os.path.expanduser("~/.workbuddy/skills/bitcoin-qlib/output")


def load_factors_and_ic():
    """加载因子数据和 IC 结果"""
    factor_path = os.path.join(OUTPUT_DIR, "btc_factors.csv")
    ic_signal_path = os.path.join(OUTPUT_DIR, "ic_test_signal.csv")
    ic_avg_path = os.path.join(OUTPUT_DIR, "ic_test_avg.csv")

    if not os.path.exists(factor_path):
        print("❌ 因子数据不存在，请先运行 calc_factors.py")
        sys.exit(1)

    df = pd.read_csv(factor_path)
    df['date'] = pd.to_datetime(df['date'])

    ic_weights = None
    if os.path.exists(ic_signal_path):
        ic_df = pd.read_csv(ic_signal_path)
        ic_weights = dict(zip(ic_df.iloc[:, 0], ic_df.iloc[:, 1]))
        print(f"✅ 加载信号周期 IC，共 {len(ic_weights)} 个因子")
    elif os.path.exists(ic_avg_path):
        ic_df = pd.read_csv(ic_avg_path)
        ic_weights = dict(zip(ic_df.iloc[:, 0], ic_df.iloc[:, 1]))
        print(f"⚠️ 使用平均 IC（请重新运行 ic_test.py）")

    if ic_weights:
        sorted_ic = sorted(ic_weights.items(), key=lambda x: abs(x[1]), reverse=True)
        for name, ic in sorted_ic[:8]:
            print(f"   {name}: IC={ic:+.4f}")

    return df, ic_weights


def find_first_valid_idx(df, factor_cols):
    """找到第一个所有因子都有效的行"""
    for i in range(len(df)):
        all_valid = True
        for col in factor_cols:
            val = df.iloc[i].get(col)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                all_valid = False
                break
        if all_valid:
            return i
    return 0


def generate_signal_ic_weighted(df, ic_weights, top_n=12,
                                no_lookahead=False, roll_window=252):
    """
    IC 加权信号生成

    Parameters:
    - no_lookahead=False: 全样本归一化（有未来函数）
    - no_lookahead=True:  滚动窗口归一化（无未来函数）
    """
    if ic_weights is None:
        print("⚠️ 无 IC 权重，回退到简单信号")
        return generate_signal_simple(df)

    sorted_factors = sorted(ic_weights.items(), key=lambda x: abs(x[1]), reverse=True)
    top_factors = [(f[0], f[1]) for f in sorted_factors[:top_n] if f[0] in df.columns]

    print(f"\n📊 Top {len(top_factors)} 因子及方向：")
    for name, ic in top_factors:
        direction = "📈 正向(高→多)" if ic > 0 else "📉 负向(高→空)"
        print(f"   {name:20s} IC={ic:+.4f}  {direction}")

    factor_names = [f[0] for f in top_factors]
    first_valid = find_first_valid_idx(df, factor_names)
    valid_mask = df.index >= first_valid
    print(f"\n📍 首个有效数据行: {first_valid} ({df.iloc[first_valid]['date'].strftime('%Y-%m-%d')})")

    n = len(df)
    score = np.zeros(n)
    signals = np.zeros(n, dtype=int)

    if no_lookahead:
        # ═══ 无未来函数：滚动窗口归一化 ═══
        print(f"📊 滚动窗口归一化（窗口={roll_window}天，无未来函数）...\n")

        for i in range(first_valid, n):
            start = max(first_valid, i - roll_window + 1)
            hist = df.iloc[start:i+1]

            s = 0.0
            for name, ic_val in top_factors:
                hist_vals = hist[name].values
                mean_v = np.mean(hist_vals)
                std_v = np.std(hist_vals)
                if std_v > 0:
                    z = (df[name].values[i] - mean_v) / std_v
                else:
                    z = 0
                s += ic_val * np.sign(z)

            score[i] = s

            # 用过去得分的 P60/P40 做阈值（更宽松）
            if i - first_valid >= 20:
                hist_scores = score[first_valid:i]
                valid_hist = hist_scores[hist_scores != 0]
                if len(valid_hist) >= 20:
                    buy_thr = np.percentile(valid_hist, 60)  # 原来是 70
                    sell_thr = np.percentile(valid_hist, 40)  # 原来是 30
                    if s > buy_thr:
                        signals[i] = 1
                    elif s < sell_thr:
                        signals[i] = -1

        print(f"   滚动阈值：P70（买入）/ P30（卖出）")

    else:
        # ═══ 有未来函数：全样本归一化 ═══
        print(f"📊 全样本归一化（含未来函数）...\n")

        df_norm = pd.DataFrame(index=df.index)
        for name, ic_val in top_factors:
            col = df[name]
            valid = col[valid_mask]
            mean_v, std_v = valid.mean(), valid.std()
            if std_v > 0:
                df_norm[name] = ((col - mean_v) / std_v).fillna(0)
            else:
                df_norm[name] = 0

        for j in range(n):
            s = 0.0
            for name, ic_val in top_factors:
                s += ic_val * np.sign(df_norm[name].values[j])
            score[j] = s

        valid_scores = score[valid_mask]
        buy_threshold = np.percentile(valid_scores, 80)
        sell_threshold = np.percentile(valid_scores, 20)
        print(f"   买入阈值 (P80): {buy_threshold:.4f}")
        print(f"   卖出阈值 (P20): {sell_threshold:.4f}")
        print(f"   得分范围: [{valid_scores.min():.4f}, {valid_scores.max():.4f}]\n")

        signals[valid_mask & (score > buy_threshold)] = 1
        signals[valid_mask & (score < sell_threshold)] = -1

    df['score'] = score
    df['signal'] = signals

    # ── 趋势过滤（MA200 长期趋势）──
    if 'ma_200' in df.columns:
        # 价格 > MA200 时才允许买入（只在牛市/复苏中买入）
        bear_market = df['close'] < df['ma_200']
        block_buy = valid_mask & bear_market & (df['signal'] == 1)
        df.loc[block_buy, 'signal'] = 0
        n_block = block_buy.sum()
        if n_block > 0:
            print(f"🔧 趋势过滤(MA200): 熊市中阻止 {n_block:.0f} 次买入")

    # ── RSI 修正（只保留阻止逻辑）──
    if 'rsi_14' in df.columns:
        rsi = df['rsi_14'].values
        valid_idx = df.index[valid_mask]

        # 去掉强制买入（<20），避免"接飞刀"
        # 只保留：RSI<30 时阻止卖出
        no_sell = (rsi < 30) & (df['signal'] == -1)
        df.loc[valid_idx & no_sell, 'signal'] = 0

        # RSI>80 时强制卖出（保留）
        extreme_sell = rsi > 80
        df.loc[valid_idx, 'signal'] = np.where(
            extreme_sell[valid_idx], -1, df.loc[valid_idx, 'signal']
        )

        # RSI>70 时阻止买入（保留）
        no_buy = (rsi > 70) & (df['signal'] == 1)
        df.loc[valid_idx & no_buy, 'signal'] = 0

        n_cb = (extreme_sell[valid_mask]).sum()
        n_bs = (no_sell[valid_mask]).sum()
        n_bb = (no_buy[valid_mask]).sum()
        if any([n_cb > 0, n_bs > 0, n_bb > 0]):
            print(f"🔧 RSI 修正: 强制卖出{n_cb:.0f}次, "
                  f"阻止卖出{n_bs:.0f}次, 阻止买入{n_bb:.0f}次")

    df['signal'] = df['signal'].astype(int)
    return df


def generate_signal_simple(df):
    """简单信号生成（RSI + MACD + 布林带）"""
    print("📊 使用简单信号方法（RSI + MACD + 布林带）")
    signals = np.zeros(len(df), dtype=int)

    for i in range(len(df)):
        rsi = df.iloc[i].get('rsi_14', np.nan)
        if np.isnan(rsi):
            continue

        signal = 0
        macd = df.iloc[i].get('macd', 0)
        macd_sig = df.iloc[i].get('macd_signal', 0)
        close = df.iloc[i].get('close', 0)
        bb_lower = df.iloc[i].get('bb_lower', 0)
        bb_upper = df.iloc[i].get('bb_upper', 0)

        if rsi < 20:
            signal = 1
        elif rsi > 85:
            signal = -1
        elif rsi < 35 and macd > macd_sig:
            signal = 1
        elif rsi > 65 and macd < macd_sig:
            signal = -1
        elif bb_lower > 0 and close <= bb_lower * 1.02:
            signal = 1
        elif bb_upper > 0 and close >= bb_upper * 0.98:
            signal = -1
        elif i > 0:
            prev_macd = df.iloc[i - 1].get('macd', 0)
            prev_sig = df.iloc[i - 1].get('macd_signal', 0)
            if prev_macd <= prev_sig and macd > macd_sig:
                signal = 1
            elif prev_macd >= prev_sig and macd < macd_sig:
                signal = -1

        signals[i] = signal

    df['signal'] = signals
    return df


def save_signals(df, output_suffix=""):
    """保存信号数据"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUTPUT_DIR, f"btc_signals{output_suffix}.csv")

    save_cols = ['date', 'close', 'rsi_14', 'macd', 'macd_signal', 'score', 'signal']
    save_cols = [c for c in save_cols if c in df.columns]
    df[save_cols].to_csv(csv_path, index=False)
    print(f"\n💾 信号数据已保存：{csv_path}")

    sig = df['signal']
    total = len(df)
    print(f"\n📊 信号分布 (共 {total} 条)：")
    for v, label in [(-1, '🔴 卖出'), (0, '⚪ 持有'), (1, '🟢 买入')]:
        cnt = (sig == v).sum()
        print(f"   {label} ({v:>2}): {cnt:>5} 次 ({cnt/total*100:5.1f}%)")

    switches = (sig.diff() != 0).sum()
    avg = total / max(switches, 1)
    print(f"\n🔄 信号切换次数: {switches} (平均每 {avg:.0f} 天切换一次)")
    return csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成比特币交易信号")
    parser.add_argument("--method", choices=['simple', 'ic_weighted'],
                        default='ic_weighted', help="信号生成方法")
    parser.add_argument("--topk", type=int, default=12,
                        help="IC 加权方法使用的因子数量")
    parser.add_argument("--no-lookahead", action="store_true",
                        help="无未来函数模式（滚动窗口归一化）")
    parser.add_argument("--roll-window", type=int, default=252,
                        help="滚动窗口大小（交易日天数，默认 252=1年）")
    parser.add_argument("--year", type=str, default=None,
                        help="只生成指定年份的信号（如 2025），保存为 btc_signals_2025.csv")
    args = parser.parse_args()

    df, ic_weights = load_factors_and_ic()

    # 如果指定了年份，只取该年份数据
    if args.year:
        year_int = int(args.year)
        df = df[df['date'].dt.year == year_int].copy().reset_index(drop=True)
        if len(df) == 0:
            print(f"❌ {args.year} 年无数据")
            sys.exit(1)
        print(f"\n📅 只生成 {args.year} 年的信号（共 {len(df)} 个交易日）")

    if args.method == 'simple':
        df = generate_signal_simple(df)
    else:
        df = generate_signal_ic_weighted(
            df, ic_weights,
            top_n=args.topk,
            no_lookahead=args.no_lookahead,
            roll_window=args.roll_window
        )

    suffix = ""
    if args.year:
        suffix += f"_{args.year}"
    if args.no_lookahead:
        suffix += "_no_lookahead"

    save_signals(df, output_suffix=suffix)
