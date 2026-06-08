#!/bin/bash
# 一键部署脚本 - 将比特币监控系统部署到GitHub Pages + Actions
# 实现真正的24小时云端运行

echo "🚀 开始部署比特币监控系统到云端..."
echo ""

# 检查是否在Git仓库中
if [ ! -d ".git" ]; then
    echo "❌ 错误：当前目录不是Git仓库"
    echo "请先创建GitHub仓库，然后运行此脚本"
    exit 1
fi

# 1. 创建必要的目录结构
echo "📁 创建目录结构..."
mkdir -p docs
mkdir -p data
mkdir -p logs

# 2. 复制仪表盘文件到docs（GitHub Pages会从这个目录提供服务）
echo "📊 复制仪表盘文件..."
cp dashboard/dashboard.html docs/index.html
cp dashboard/dashboard_data.json data/ 2>/dev/null || echo "⚠️  dashboard_data.json不存在，稍后会自动生成"

# 3. 创建GitHub Actions工作流
echo "⚙️  创建GitHub Actions工作流..."
mkdir -p .github/workflows

cat > .github/workflows/update.yml << 'EOF'
name: 比特币监控自动更新

on:
  schedule:
    # 每天北京时间 09:00 和 22:00 运行
    - cron: '0 1 * * *'   # 北京时间 09:00 = UTC 01:00
    - cron: '0 14 * * *'  # 北京时间 22:00 = UTC 14:00
  workflow_dispatch:  # 允许手动触发

jobs:
  update:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    
    steps:
    - name: 检出代码
      uses: actions/checkout@v4
      with:
        fetch-depth: 0
        
    - name: 设置Python环境
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        
    - name: 安装依赖
      run: |
        pip install yfinance pandas numpy
        
    - name: 运行监控脚本
      run: |
        cd scripts
        python monitor_bitcoin_ultimate.py
        
    - name: 生成仪表盘
      run: |
        cd scripts
        python generate_dashboard.py
        
    - name: 复制到docs目录
      run: |
        cp dashboard/dashboard.html docs/index.html
        cp dashboard/dashboard_data.json data/ || true
        
    - name: 提交并推送
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add -A
        git diff --staged --quiet || (git commit -m "自动更新: $(date +'%Y-%m-%d %H:%M')" && git push)
        
    - name: 完成
      run: |
        echo "✅ 更新完成！"
        echo "📊 访问地址: https://$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/tree/main/docs"
EOF

echo "✅ GitHub Actions工作流已创建"

# 4. 创建README
echo "📝 创建README..."
cat > README.md << 'EOF'
# 比特币监控系统

自动化比特币技术分析系统，提供：

- 📊 实时技术指标计算（RSI、MACD、布林带、Ichimoku等）
- 🚨 底部信号检测
- 💡 智能购买建议
- 📈 可视化仪表盘

## 访问地址

- **在线仪表盘**: [点击访问](https://你的用户名.github.io/仓库名/)
- **数据API**: https://你的用户名.github.io/仓库名/data/dashboard_data.json

## 自动更新

系统每天自动运行2次（北京时间 09:00 和 22:00）：
- 下载最新比特币数据
- 计算技术指标
- 检测底部信号
- 更新仪表盘

## 本地运行

```bash
pip install yfinance pandas numpy flask
python scripts/monitor_bitcoin_ultimate.py
python scripts/generate_dashboard.py
python scripts/app.py
```

## 技术指标

- RSI（相对强弱指数）
- MACD（指数平滑移动平均线）
- 布林带（Bollinger Bands）
- 随机指标（Stochastic）
- ADX（平均趋向指数）
- Ichimoku Cloud（一目均衡表）
- Supertrend（超级趋势）
- 斐波那契回撤

## 信号检测

- 成交量确认
- RSI背离
- 均线金叉/死叉
- K线形态（锤子线、启明星、看涨吞没、双底）
- 支撑位突破
EOF

echo "✅ README已创建"

# 5. 添加到Git并推送
echo ""
echo "📤 准备推送到GitHub..."
echo ""
echo "请执行以下命令完成部署："
echo ""
echo "  git add -A"
echo "  git commit -m '初始提交：比特币监控系统'"
echo "  git branch -M main"
echo "  git remote add origin https://github.com/你的用户名/仓库名.git"
echo "  git push -u origin main"
echo ""
echo "然后："
echo "1. 在GitHub仓库设置中启用 GitHub Pages（选择 main 分支 / docs 目录）"
echo "2. 在GitHub仓库设置中启用 Actions"
echo "3. 访问 https://你的用户名.github.io/仓库名/ 查看仪表盘"
echo ""
echo "✅ 部署脚本执行完成！"
