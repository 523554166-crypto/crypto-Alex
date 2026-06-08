#!/usr/bin/env python3
"""
比特币监控Web服务 - 云端版本
提供Web界面和API接口
"""

from flask import Flask, render_template, jsonify, send_from_directory
import json
import os
import subprocess
import threading
import time
from datetime import datetime

app = Flask(__name__)

# 数据和脚本路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(BASE_DIR, '..', 'dashboard')
MONITOR_DIR = BASE_DIR
REPORT_DIR = os.path.join(BASE_DIR, '..', 'monitor')

# 确保目录存在
os.makedirs(DASHBOARD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

@app.route('/')
def index():
    """主页 - 显示仪表盘"""
    dashboard_file = os.path.join(DASHBOARD_DIR, 'dashboard.html')
    if os.path.exists(dashboard_file):
        return send_from_directory(DASHBOARD_DIR, 'dashboard.html')
    else:
        return """
        <html>
        <head><meta charset="UTF-8"><title>比特币监控</title></head>
        <body style="background:#0a0e17;color:#e1e5ee;font-family:Arial;padding:50px;text-align:center;">
            <h1>🚀 比特币监控系统</h1>
            <p>仪表盘未生成，请先运行监控脚本</p>
            <button onclick="location.href='/run_monitor'" style="background:#f7931a;color:white;border:none;padding:15px 30px;font-size:16px;border-radius:8px;cursor:pointer;margin:10px;">🔄 运行监控脚本</button>
            <button onclick="location.reload()" style="background:#1a1f2e;color:white;border:1px solid #f7931a;padding:15px 30px;font-size:16px;border-radius:8px;cursor:pointer;margin:10px;">🔄 刷新页面</button>
        </body>
        </html>
        """

@app.route('/api/data')
def get_data():
    """API: 获取最新监控数据"""
    data_file = os.path.join(DASHBOARD_DIR, 'dashboard_data.json')
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    else:
        return jsonify({'error': '数据未生成'}), 404

@app.route('/api/report/latest')
def get_latest_report():
    """API: 获取最新报告"""
    if not os.path.exists(REPORT_DIR):
        return jsonify({'error': '报告目录不存在'}), 404
    
    # 查找最新的报告文件
    report_files = [f for f in os.listdir(REPORT_DIR) if f.startswith('report_') and f.endswith('.txt')]
    if not report_files:
        return jsonify({'error': '没有报告文件'}), 404
    
    latest_report = max(report_files)
    report_path = os.path.join(REPORT_DIR, latest_report)
    
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return jsonify({
        'filename': latest_report,
        'content': content,
        'generated_at': datetime.fromtimestamp(os.path.getmtime(report_path)).isoformat()
    })

@app.route('/run_monitor')
def run_monitor():
    """手动运行监控脚本"""
    def run_script():
        try:
            # 运行监控脚本
            result = subprocess.run(
                ['python3', 'monitor_bitcoin_ultimate.py'],
                cwd=MONITOR_DIR,
                capture_output=True,
                text=True,
                timeout=300
            )
            print("监控脚本输出:", result.stdout)
            print("监控脚本错误:", result.stderr)
            
            # 运行仪表盘生成脚本
            result2 = subprocess.run(
                ['python3', 'generate_dashboard.py'],
                cwd=MONITOR_DIR,
                capture_output=True,
                text=True,
                timeout=300
            )
            print("仪表盘生成输出:", result2.stdout)
            print("仪表盘生成错误:", result2.stderr)
        except Exception as e:
            print(f"运行脚本失败: {e}")
    
    # 在后台线程中运行
    thread = threading.Thread(target=run_script)
    thread.start()
    
    return """
    <html>
    <head><meta charset="UTF-8"><title>正在运行...</title>
    <meta http-equiv="refresh" content="5;url=/" /></head>
    <body style="background:#0a0e17;color:#e1e5ee;font-family:Arial;padding:50px;text-align:center;">
        <h1>⏳ 正在运行监控脚本...</h1>
        <p>请等待，这可能需要几分钟...</p>
        <p>页面将在5秒后自动刷新</p>
        <button onclick="location.href='/'" style="background:#f7931a;color:white;border:none;padding:15px 30px;font-size:16px;border-radius:8px;cursor:pointer;">立即返回</button>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

def run_monitor_background():
    """后台定时运行监控脚本"""
    while True:
        try:
            print(f"[{datetime.now()}] 开始运行监控脚本...")
            
            # 运行监控脚本
            result = subprocess.run(
                ['python3', 'monitor_bitcoin_ultimate.py'],
                cwd=MONITOR_DIR,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # 运行仪表盘生成脚本
            result2 = subprocess.run(
                ['python3', 'generate_dashboard.py'],
                cwd=MONITOR_DIR,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            print(f"[{datetime.now()}] 监控脚本运行完成")
        except Exception as e:
            print(f"[{datetime.now()}] 运行脚本失败: {e}")
        
        # 等待12小时（43200秒）
        time.sleep(43200)

if __name__ == '__main__':
    # 启动后台监控线程
    monitor_thread = threading.Thread(target=run_monitor_background, daemon=True)
    monitor_thread.start()
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=8080, debug=False)
