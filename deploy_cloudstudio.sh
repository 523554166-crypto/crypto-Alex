#!/bin/bash
# CloudStudio 部署启动脚本

echo "🚀 开始部署比特币监控系统到CloudStudio..."

# 1. 安装依赖
echo "📦 安装Python依赖..."
pip install -r requirements.txt -q

# 2. 创建必要目录
mkdir -p /workspace/monitor
mkdir -p /workspace/dashboard
mkdir -p /workspace/logs

# 3. 复制文件到工作目录
cp monitor_bitcoin_ultimate.py /workspace/
cp generate_dashboard.py /workspace/
cp app.py /workspace/
cp -r dashboard/* /workspace/dashboard/ 2>/dev/null || true

# 4. 设置定时任务（每天早9点和晚10点运行）
echo "⏰ 设置定时任务..."

# 创建cron任务脚本
cat > /workspace/run_monitor.sh << 'EOF'
#!/bin/bash
cd /workspace
echo "[$(date)] 开始运行监控脚本..." >> /workspace/logs/monitor.log

# 运行监控脚本
python3 monitor_bitcoin_ultimate.py >> /workspace/logs/monitor.log 2>&1

# 运行仪表盘生成脚本
python3 generate_dashboard.py >> /workspace/logs/monitor.log 2>&1

echo "[$(date)] 监控脚本运行完成" >> /workspace/logs/monitor.log
EOF

chmod +x /workspace/run_monitor.sh

# 添加到crontab（北京时间 早9点=UTC+8=1:00 UTC，晚10点=14:00 UTC）
(crontab -l 2>/dev/null | grep -v run_monitor.sh; echo "0 1,14 * * * /workspace/run_monitor.sh") | crontab -

echo "✅ 定时任务已设置："
echo "   - 每天 09:00 (北京时间)"
echo "   - 每天 22:00 (北京时间)"

# 5. 立即运行一次
echo "🔄 立即运行一次监控脚本..."
bash /workspace/run_monitor.sh

# 6. 启动Web服务
echo "🌐 启动Web服务..."
cd /workspace
python3 app.py &
echo $! > /workspace/web.pid

echo "✅ 部署完成！"
echo "📊 访问地址: https://你的CloudStudio地址"
echo "📋 查看日志: tail -f /workspace/logs/monitor.log"
