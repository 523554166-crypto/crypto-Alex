---
name: bitcoin-qlib
description: "基于 Microsoft Qlib 框架的比特币量化策略分析。支持因子计算、IC测试、信号生成、Walk-Forward 回测。当用户需要量化分析比特币、生成交易信号、回测策略时触发。"
agent_created: true
---

# Bitcoin Qlib 量化策略 Skill

本技能提供基于 Microsoft Qlib 框架的比特币量化分析能力，包括因子计算、信号生成、回测验证。

## 触发场景

- 用户要求"分析比特币量化策略"
- 用户要求"生成比特币交易信号"
- 用户要求"回测比特币策略"
- 用户提到"Qlib"、"因子分析"、"IC测试"

## 依赖安装

首次使用需要安装 Qlib 和依赖：

```bash
pip install pyqlib yfinance pandas numpy matplotlib
```

## 核心功能

### 1. 数据准备

下载比特币历史数据到 Qlib 格式：

```bash
python3 {baseDir}/scripts/prepare_data.py
```

### 2. 因子计算

计算 174 个专业因子（参考 Qlib 内置因子库）：

```bash
python3 {baseDir}/scripts/calc_factors.py --start 2020-01-01 --end 2026-06-07
```

### 3. IC 测试

测试因子对收益的预测能力：

```bash
python3 {baseDir}/scripts/ic_test.py --factor return_5 --period 2024-01-01:2026-06-07
```

### 4. 信号生成

基于因子组合生成买卖信号：

```bash
python3 {baseDir}/scripts/gen_signals.py --model lightgbm --topk 5
```

### 5. Walk-Forward 回测

滚动窗口回测，避免过拟合：

```bash
python3 {baseDir}/scripts/backtest_wf.py --start 2023-01-01 --end 2026-06-07
```

## 输出格式

所有脚本输出：
- **CSV 文件**：保存到 `~/.workbuddy/skills/bitcoin-qlib/output/`
- **图表**：因子 IC 热力图、回测收益曲线
- **报告**：Markdown 格式的回测报告

## 注意事项

- Qlib 数据下载需要稳定网络（建议使用国内镜像）
- 回测结果仅供参考，不构成投资建议
- Walk-Forward 回测时间较长，建议先用短时间段测试

## 参考资料

详细说明见 `references/qlib_guide.md`
