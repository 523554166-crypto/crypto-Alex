# Bitcoin Qlib 量化策略参考指南

## Microsoft Qlib 简介

Qlib 是微软亚洲研究院开源的 AI 量化投资平台，支持：
- 数据处理与清洗
- 因子计算与 IC 分析
- 模型训练与预测
- 回测与性能评估

## 核心概念

### 1. 因子（Factor）
从价格、成交量等原始数据计算出的特征，用于预测未来收益。

**示例因子**：
- `return_5`：5日收益率（动量因子）
- `vol_20`：20日波动率
- `rsi_14`：14日 RSI 指标
- `ma_ratio_20`：价格与20日均线比值

### 2. IC（Information Coefficient）
衡量因子预测能力的指标，取值范围 [-1, 1]：
- `IC > 0.1`：强预测能力（绿色）
- `0 < IC < 0.1`：弱预测能力（黄色）
- `IC < 0`：反向预测或无预测能力（红色）

### 3. Walk-Forward 回测
滚动窗口回测方法，避免过拟合：
1. 用前 N 天数据训练/优化策略
2. 用接下来的 M 天数据测试
3. 滚动窗口，重复步骤1-2

**优势**：更接近实盘，避免"看后视镜开车"

## 脚本使用流程

```bash
# 1. 安装依赖
pip install pyqlib yfinance pandas numpy matplotlib

# 2. 下载数据
python3 scripts/prepare_data.py --start 2020-01-01

# 3. 计算因子
python3 scripts/calc_factors.py --start 2020-01-01

# 4. IC 测试（验证因子有效性）
python3 scripts/ic_test.py --topk 20

# 5. 生成交易信号
python3 scripts/gen_signals.py --method ic_weighted --topk 10

# 6. Walk-Forward 回测
python3 scripts/backtest_wf.py --train-window 90 --test-window 30
```

## 输出文件

所有输出保存在 `~/.workbuddy/skills/bitcoin-qlib/output/`：

| 文件 | 说明 |
|------|------|
| `btc_data.csv` | 原始价格数据 |
| `btc_factors.csv` | 因子计算结果 |
| `ic_test_detail.csv` | IC 测试详细结果 |
| `ic_test_avg.csv` | 因子平均 IC |
| `ic_heatmap.png` | IC 热力图 |
| `btc_signals.csv` | 交易信号 |
| `backtest_detail.csv` | 回测详细记录 |
| `backtest_summary.txt` | 回测指标汇总 |
| `equity_curve.png` | 资金曲线图 |

## 回测指标解读

| 指标 | 说明 | 优秀值 |
|------|------|--------|
| 总收益率 | 回测期间累计收益 | > 50% |
| 年化收益率 | 折算为年度收益 | > 20% |
| 夏普比率 | 收益/风险比 | > 1.5 |
| 最大回撤 | 从高点到低点的最大亏损 | < 20% |
| 胜率 | 盈利交易占比 | > 50% |

## 风险提示

⚠️ **本工具仅供学习研究，不构成投资建议**

- 回测结果不代表未来收益
- 加密货币波动极大，谨慎投资
- 建议配合止损策略使用
- 不要投入无法承受损失的资金

## 进阶使用

### 自定义因子
编辑 `scripts/calc_factors.py`，在 `calc_factors()` 函数中添加自定义因子计算逻辑。

### 调整信号阈值
编辑 `scripts/gen_signals.py`，修改 `factor_score_norm` 的阈值（默认 >1 买入，< -1 卖出）。

### 优化回测参数
```bash
# 更长的训练窗口（捕捉长期规律）
python3 scripts/backtest_wf.py --train-window 180 --test-window 60
```

## 常见问题

**Q: 数据下载失败？**
A: 检查网络连接，或使用国内镜像源：
```bash
pip install yfinance -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**Q: IC 值全部接近 0？**
A: 比特币市场有效性较高，因子预测难度大是正常现象。可尝试：
1. 缩短预测周期（1-3天）
2. 使用高频数据
3. 结合链上数据

**Q: 回测收益过高？**
A: 检查是否过拟合，或是否有未来函数（使用未来数据预测过去）。

## 参考资源

- Qlib 官方文档：https://qlib.readthedocs.io/
- yfinance 文档：https://pypi.org/project/yfinance/
- 因子投资入门：https://www.quantopian.com/lectures/factor-analysis
