#!/bin/bash
# GitHub推送脚本 - 比特币监控系统
# 使用方法：先创建GitHub Personal Access Token，然后运行此脚本

echo "🚀 开始推送到GitHub..."
echo ""

# 检查是否提供了token参数
if [ -z "$1" ]; then
    echo "❌ 请提供GitHub Personal Access Token"
    echo ""
    echo "使用方式："
    echo "  bash push_to_github.sh YOUR_TOKEN"
    echo ""
    echo "如何获取Token："
    echo "1. 访问 https://github.com/settings/tokens"
    echo "2. 点击 'Generate new token (classic)'"
    echo "3. 选择 'repo' 权限"
    echo "4. 生成并复制token"
    echo ""
    exit 1
fi

TOKEN=$1
REPO_URL="https://523554166-crypto:${TOKEN}@github.com/523554166-crypto/crypto-Alex.git"

cd /Users/zengxiantao/.workbuddy/skills/bitcoin-qlib

echo "📤 推送到GitHub..."
git remote set-url origin ${REPO_URL}
git push -u origin main

echo ""
if [ $? -eq 0 ]; then
    echo "✅ 推送成功！"
    echo ""
    echo "接下来请完成以下步骤："
    echo "1. 访问 https://github.com/523554166-crypto/crypto-Alex/settings/pages"
    echo "2. 在 'Source' 下选择 'Deploy from a branch'"
    echo "3. 选择 'main' 分支和 '/docs' 目录"
    echo "4. 点击 'Save'"
    echo ""
    echo "📊 仪表盘地址将会是："
    echo "   https://523554166-crypto.github.io/crypto-Alex/"
    echo ""
    echo "⏰ 自动更新已配置："
    echo "   - 每天 09:00 (北京时间)"
    echo "   - 每天 22:00 (北京时间)"
else
    echo "❌ 推送失败，请检查token是否正确"
fi
