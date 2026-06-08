#!/usr/bin/env python3
"""
IC (Information Coefficient) 测试 - 验证因子预测能力
"""
import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

OUTPUT_DIR = os.path.expanduser("~/.workbuddy/skills/bitcoin-qlib/output")

def load_factors():
    """加载因子数据"""
    csv_path = os.path.join(OUTPUT_DIR, "btc_factors.csv")
    if not os.path.exists(csv_path):
        print("❌ 因子数据不存在，请先运行 calc_factors.py")
        sys.exit(1)
    
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    return df

def calc_ic(df, factor_name, forward_periods=[1, 3, 5, 10]):
    """计算指定因子的 IC 值（分周期返回，不平均）"""
    close = df['close']
    results = []
    
    for p in forward_periods:
        # 计算未来收益（用未来价格 / 当前价格 - 1）
        future_price = close.shift(-p)
        future_ret = (future_price - close) / close
        
        # 计算 IC（皮尔逊相关系数）
        factor_series = df[factor_name]
        valid_data = pd.DataFrame({
            'factor': factor_series,
            'future_ret': future_ret
        }).dropna()
        
        if len(valid_data) > 10:
            ic = valid_data['factor'].corr(valid_data['future_ret'])
        else:
            ic = np.nan
        
        results.append({
            'factor': factor_name,
            'forward_period': p,
            'ic': ic
        })
    
    return results

def batch_ic_test(df, factor_list=None, top_n=20, signal_period=5):
    """
    批量 IC 测试
    - signal_period: 用于信号生成的 forward period（默认 5 天）
    """
    # 如果没有指定因子列表，自动选择数值型因子
    if factor_list is None:
        exclude_cols = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']
        factor_list = [c for c in df.columns if c not in exclude_cols][:top_n]
    
    print(f"🔬 开始 IC 测试，共 {len(factor_list)} 个因子...")
    print(f"   📍 信号生成将使用 {signal_period} 日 IC")
    
    all_results = []
    signal_ic = {}  # factor -> IC at signal_period
    
    for factor in factor_list:
        if factor in df.columns:
            results = calc_ic(df, factor)
            all_results.extend(results)
            # 提取 signal_period 对应的 IC
            for r in results:
                if r['forward_period'] == signal_period:
                    signal_ic[factor] = r['ic']
    
    # 转换为 DataFrame
    results_df = pd.DataFrame(all_results)
    
    # 计算平均 IC（用于展示）
    avg_ic = results_df.groupby('factor')['ic'].mean().sort_values(ascending=False)
    
    # 保存 signal_period 的 IC（用于信号生成）
    signal_ic_series = pd.Series(signal_ic).dropna().sort_values(ascending=False)
    
    print(f"\n📊 Top 10 因子（按平均 IC 排序）：")
    print(avg_ic.head(10))
    print(f"\n📊 {signal_period}日 IC Top 10（用于信号生成）：")
    print(signal_ic_series.head(10))
    
    return results_df, avg_ic, signal_ic_series

def plot_ic_heatmap(results_df, save_path):
    """绘制 IC 热力图"""
    try:
        import seaborn as sns
        
        # 透视表
        pivot = results_df.pivot(index='factor', columns='forward_period', values='ic')
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(pivot, annot=True, cmap='RdYlGn', center=0, fmt='.2f')
        plt.title('因子 IC 热力图')
        plt.xlabel('预测周期')
        plt.ylabel('因子')
        plt.tight_layout()
        plt.savefig(save_path, dpi=100)
        plt.close()
        print(f"📈 IC 热力图已保存：{save_path}")
    except ImportError:
        print("⚠️ 未安装 seaborn，跳过绘图")

def save_ic_results(results_df, avg_ic, signal_ic, signal_period=5):
    """保存 IC 测试结果"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 保存详细结果（含各周期 IC）
    detail_path = os.path.join(OUTPUT_DIR, "ic_test_detail.csv")
    results_df.to_csv(detail_path, index=False)
    
    # 保存平均 IC
    avg_path = os.path.join(OUTPUT_DIR, "ic_test_avg.csv")
    avg_ic.to_csv(avg_path, header=['avg_ic'])
    
    # 保存信号周期 IC（用于 gen_signals.py）
    signal_path = os.path.join(OUTPUT_DIR, "ic_test_signal.csv")
    signal_ic.to_csv(signal_path, header=[f'ic_{signal_period}d'])
    
    print(f"💾 IC 测试结果已保存：\n  - 详细（各周期）: {detail_path}\n  - 平均: {avg_path}\n  - 信号周期({signal_period}d): {signal_path}")
    
    # 绘制热力图
    plot_path = os.path.join(OUTPUT_DIR, "ic_heatmap.png")
    plot_ic_heatmap(results_df, plot_path)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IC 测试 - 验证因子预测能力")
    parser.add_argument("--factor", default=None, help="指定单个因子（不指定则测试所有因子）")
    parser.add_argument("--topk", type=int, default=20, help="测试的因子数量上限")
    parser.add_argument("--signal-period", type=int, default=5, help="用于信号生成的 forward period（默认 5 天）")
    args = parser.parse_args()
    
    df = load_factors()
    
    if args.factor:
        # 测试单个因子
        results = calc_ic(df, args.factor)
        results_df = pd.DataFrame(results)
        avg_ic = pd.Series({args.factor: results_df['ic'].mean()})
        # 提取 signal_period 的 IC
        signal_ic_val = results_df.loc[results_df['forward_period'] == args.signal_period, 'ic'].values
        signal_ic = pd.Series({args.factor: signal_ic_val[0] if len(signal_ic_val) > 0 else np.nan})
    else:
        # 批量测试
        results_df, avg_ic, signal_ic = batch_ic_test(df, top_n=args.topk, signal_period=args.signal_period)
    
    save_ic_results(results_df, avg_ic, signal_ic, signal_period=args.signal_period)
