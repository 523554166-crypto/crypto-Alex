#!/usr/bin/env python3
"""
比特币监控Web服务 - CloudStudio云端版本
提供Web界面和API接口
"""

from flask import Flask, jsonify
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'dashboard', 'dashboard_data.json')
MONITOR_SCRIPT = os.path.join(BASE_DIR, 'monitor_bitcoin_ultimate.py')
DASHBOARD_GEN_SCRIPT = os.path.join(BASE_DIR, 'generate_dashboard.py')
LOG_FILE = os.path.join(BASE_DIR, 'logs', 'monitor.log')

# 确保目录存在
os.makedirs(os.path.join(BASE_DIR, 'dashboard'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'monitor'), exist_ok=True)

@app.route('/')
def index():
    """显示仪表盘"""
    dashboard_file = os.path.join(BASE_DIR, 'dashboard', 'dashboard.html')
    if os.path.exists(dashboard_file):
        with open(dashboard_file, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return '''
        <html>
        <head><meta charset="UTF-8"><title>比特币监控</title>
        <style>body{background:#0a0e17;color:#e1e5ee;font-family:Arial;padding:50px;text-align:center;}</style></head>
        <body>
            <h1>🚀 比特币监控系统</h1>
            <p>仪表盘未生成，请先运行监控脚本</p>
            <button onclick="location.href='/run'" style="background:#f7931a;color:white;border:none;padding:15px 30px;font-size:16px;border-radius:8px;cursor:pointer;margin:10px;">🔄 运行监控脚本</button>
        </body>
        </html>
        '''

@app.route('/api/data')
def get_data():
    """API: 获取最新数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    else:
        return jsonify({'error': '数据未生成', 'status': 'no_data'}), 404

@app.route('/api/status')
def get_status():
    """API: 获取系统状态"""
    status = {
        'timestamp': datetime.now().isoformat(),
        'data_exists': os.path.exists(DATA_FILE),
        'last_update': None,
        'next_update': None
    }
    
    if os.path.exists(DATA_FILE):
        mtime = os.path.getmtime(DATA_FILE)
        status['last_update'] = datetime.fromtimestamp(mtime).isoformat()
        status['next_update'] = (datetime.fromtimestamp(mtime) + timedelta(hours=12)).isoformat()
    
    return jsonify(status)

@app.route('/run')
def run_monitor():
    """手动触发监控"""
    def run_in_background():
        try:
            log("开始运行监控脚本...")
            
            # 运行监控脚本
            result = subprocess.run(
                ['python3', MONITOR_SCRIPT],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=300
            )
            log("监控脚本完成")
            
            # 运行仪表盘生成脚本
            result2 = subprocess.run(
                ['python3', DASHBOARD_GEN_SCRIPT],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=300
            )
            log("仪表盘生成完成")
            
        except Exception as e:
            log(f"❌ 运行失败: {str(e)}")
    
    thread = threading.Thread(target=run_in_background)
    thread.start()
    
    return '''
    <html>
    <head>
        <meta charset="UTF-8">
        <title>正在运行...</title>
        <meta http-equiv="refresh" content="3;url=/">
        <style>body{background:#0a0e17;color:#e1e5ee;font-family:Arial;padding:50px;text-align:center;}</style>
    </head>
    <body>
        <h1>⏳ 正在运行监控脚本...</h1>
        <p>请等待，这可能需要2-3分钟...</p>
        <div style="margin:20px auto;width:40px;height:40px;border:4px solid #2d3548;border-top:4px solid #f7931a;border-radius:50%;animation:spin 1s linear infinite;"></div>
        <p style="color:#8a94a6;">页面将在3秒后自动刷新</p>
        <button onclick="location.href='/'" style="background:#f7931a;color:white;border:none;padding:15px 30px;font-size:16px;border-radius:8px;cursor:pointer;margin:10px;">立即返回</button>
        <style>@keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}</style>
    </body>
    </html>
    '''

def log(message):
    """写入日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line)
    print(log_line.strip())

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

# 后台定时任务
def background_scheduler():
    """后台调度器：每12小时运行一次"""
    while True:
        try:
            log("⏰ 定时任务触发：开始运行监控...")
            run_in_background_sync()
            log("✅ 定时任务完成")
        except Exception as e:
            log(f"❌ 定时任务失败: {e}")
        
        # 等待12小时
        log("💤 进入休眠，12小时后再次运行...")
        time.sleep(12 * 60 * 60)

def run_in_background_sync():
    """同步运行监控脚本"""
    try:
        # 运行监控脚本
        result = subprocess.run(
            ['python3', MONITOR_SCRIPT],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=300
        )
        log("监控脚本完成")
        
        # 运行仪表盘生成脚本
        result2 = subprocess.run(
            ['python3', DASHBOARD_GEN_SCRIPT],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=300
        )
        log("仪表盘生成完成")
    except Exception as e:
        log(f"运行失败: {e}")

if __name__ == '__main__':
    # 启动后台调度器
    scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
    scheduler_thread.start()
    log("🚀 后台调度器已启动")
    
    # 启动Flask应用
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
