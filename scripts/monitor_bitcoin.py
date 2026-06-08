#!/usr/bin/env python3
"""
比特币底部监控脚本
定期运行，检测底部信号，发现重要变化时通知用户
"""

import yfinance as yf
import pandas as pd
import numpy as np
import os
import json
import time
from datetime import datetime, timedelta

# 配置文件路径
OUTPUT_DIR = os.path.expanduser('~/.workbuddy/skills/bitcoin-qlib/monitor')
STATE_FILE = os.path.join(OUTPUT_DIR, 'monitor_state.json')

# 底部信号阈值
THRESHOLDS = {
    'rsi_oversold': 30,          # RSI超卖阈值
    'rsi_extreme': 20,            # RSI极度超卖
    'ma200_severe_dip': -20,      # 200日均线严重超跌
    'bb_position_low': 0.2,       # 布林带下轨
    'drawdown_severe': -50,        # 严重回撤
}

def ensure_output_dir():
    """确保输出目录存在"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_state():
    """加载上次监控状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        'last_check': None,
        'last_price': None,
        'last_rsi': None,
        'last_signals': [],
        'alert_sent': []
    }

def save_state(state):
    """保存监控状态"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)

def download_latest_data():
    """下载最新比特币数据"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 下载最新数据...")
    
    import requests
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            btc = yf.Ticker("BTC-USD", session=session)
            # 下载6个月数据以确保有足够数据计算200日均线
            start_date = (datetime.now() - timedelta(days=200)).strftime('%Y-%m-%d')
            df = btc.history(start=start_date, interval='1d', timeout=60)
            if len(df) > 0:
                print(f"  数据下载完成，共 {len(df)} 天")
                return df
        except Exception as e:
            print(f"  尝试 {attempt+1}/{max_retries} 失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(10 * (attempt + 1))
    
    raise Exception("下载失败")

def calculate_indicators(df):
    """计算技术指标"""
    # 移除时区信息
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # 移动平均线
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    # 布林带
    df['BB_middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
    df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
    df['BB_position'] = (df['Close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
    
    # 价格相对200日均线
    df['Price_vs_MA200'] = ((df['Close'] - df['MA200']) / df['MA200'] * 100)
    
    # 52周高低点
    df['52w_high'] = df['Close'].rolling(window=365).max()
    df['Drawdown_from_high'] = ((df['Close'] - df['52w_high']) / df['52w_high'] * 100)
    
    return df

def detect_signals(df):
    """检测底部信号"""
    latest = df.iloc[-1]
    signals = []
    
    # 1. RSI信号
    rsi = latest['RSI']
    if pd.notna(rsi):
        if rsi < THRESHOLDS['rsi_extreme']:
            signals.append({
                'type': 'RSI极度超卖',
                'value': float(rsi),
                'message': f'RSI = {rsi:.2f} (极度超卖，<20)',
                'severity': 'high'
            })
        elif rsi < THRESHOLDS['rsi_oversold']:
            signals.append({
                'type': 'RSI超卖',
                'value': float(rsi),
                'message': f'RSI = {rsi:.2f} (超卖，<30)',
                'severity': 'medium'
            })
    
    # 2. 200日均线信号
    ma200_dev = latest['Price_vs_MA200']
    if pd.notna(ma200_dev) and ma200_dev < THRESHOLDS['ma200_severe_dip']:
        signals.append({
            'type': '严重超跌',
            'value': float(ma200_dev),
            'message': f'低于200日均线 {abs(ma200_dev):.2f}% (严重超跌，<-20%)',
            'severity': 'high'
        })
    
    # 3. 布林带信号
    bb_pos = latest['BB_position']
    if pd.notna(bb_pos) and bb_pos < THRESHOLDS['bb_position_low']:
        signals.append({
            'type': '接近布林带下轨',
            'value': float(bb_pos),
            'message': f'布林带位置 = {bb_pos:.2%} (接近下轨，<20%)',
            'severity': 'medium'
        })
    
    # 4. MACD金叉检测
    if len(df) >= 2:
        curr_hist = latest['MACD_hist']
        prev_hist = df.iloc[-2]['MACD_hist']
        
        if pd.notna(curr_hist) and pd.notna(prev_hist):
            # 金叉：柱状图由负转正
            if prev_hist < 0 and curr_hist > 0:
                signals.append({
                    'type': 'MACD金叉',
                    'value': float(curr_hist),
                    'message': f'MACD柱状图由负转正 ({prev_hist:.2f} -> {curr_hist:.2f})',
                    'severity': 'high'
                })
            # 柱状图收敛（可能即将金叉）
            elif prev_hist < curr_hist and curr_hist < 0:
                signals.append({
                    'type': 'MACD柱状图收敛',
                    'value': float(curr_hist),
                    'message': f'MACD柱状图收敛 ({prev_hist:.2f} -> {curr_hist:.2f})',
                    'severity': 'low'
                })
    
    # 5. 回撤信号
    drawdown = latest['Drawdown_from_high']
    if pd.notna(drawdown) and drawdown < THRESHOLDS['drawdown_severe']:
        signals.append({
            'type': '严重回撤',
            'value': float(drawdown),
            'message': f'距离高点回撤 {abs(drawdown):.2f}% (严重回撤，>50%)',
            'severity': 'high'
        })
    
    # 6. 价格突破MA20
    if len(df) >= 2:
        curr_price = latest['Close']
        prev_price = df.iloc[-2]['Close']
        ma20 = latest['MA20']
        
        if pd.notna(ma20) and pd.notna(prev_price):
            if prev_price < ma20 and curr_price > ma20:
                signals.append({
                    'type': '价格突破MA20',
                    'value': float(curr_price),
                    'message': f'价格突破MA20 (${ma20:.2f})',
                    'severity': 'medium'
                })
    
    return signals

def generate_report(df, signals, state):
    """生成监控报告"""
    latest = df.iloc[-1]
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report = []
    report.append("=" * 80)
    report.append(f"比特币监控报告 - {current_time}")
    report.append("=" * 80)
    
    # 基本信息
    report.append(f"\n【当前价格】${latest['Close']:,.2f}")
    
    if state['last_price']:
        change = ((latest['Close'] - state['last_price']) / state['last_price'] * 100)
        report.append(f"【变化】  {change:+.2f}% (上次检查: ${state['last_price']:,.2f})")
    else:
        report.append("【变化】  (首次检查)")
    
    # 关键指标
    report.append(f"\n【关键指标】")
    report.append(f"  RSI: {latest['RSI']:.2f}" if pd.notna(latest['RSI']) else "  RSI: N/A")
    report.append(f"  相对200日均线: {latest['Price_vs_MA200']:.2f}%" if pd.notna(latest['Price_vs_MA200']) else "  相对200日均线: N/A")
    report.append(f"  布林带位置: {latest['BB_position']:.2%}" if pd.notna(latest['BB_position']) else "  布林带位置: N/A")
    report.append(f"  MACD柱状图: {latest['MACD_hist']:.2f}" if pd.notna(latest['MACD_hist']) else "  MACD柱状图: N/A")
    report.append(f"  距离高点回撤: {latest['Drawdown_from_high']:.2f}%" if pd.notna(latest['Drawdown_from_high']) else "  距离高点回撤: N/A")
    
    # 检测到的信号
    report.append(f"\n【检测到的信号】({len(signals)}个)")
    if signals:
        for i, signal in enumerate(signals, 1):
            severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}[signal['severity']]
            report.append(f"  {i}. {severity_icon} {signal['message']}")
    else:
        report.append("  (无新信号)")
    
    # 综合判断
    high_signals = sum(1 for s in signals if s['severity'] == 'high')
    medium_signals = sum(1 for s in signals if s['severity'] == 'medium')
    
    report.append(f"\n【综合判断】")
    report.append(f"  高优先级信号: {high_signals}")
    report.append(f"  中优先级信号: {medium_signals}")
    
    if high_signals >= 2:
        report.append(f"\n  🔴🔴🔴 结论: 出现多个高优先级信号，可能接近底部！")
    elif high_signals >= 1 or medium_signals >= 2:
        report.append(f"\n  🟡🟡🟡  结论: 出现部分底部信号，建议密切关注")
    else:
        report.append(f"\n  ⚪⚪⚪  结论: 暂无明确底部信号")
    
    report.append("=" * 80)
    
    return "\n".join(report)

def check_new_signals(signals, state):
    """检查是否有新信号（避免重复通知）"""
    new_signals = []
    last_signal_types = set(state.get('last_signals', []))
    
    for signal in signals:
        if signal['type'] not in last_signal_types:
            new_signals.append(signal)
    
    return new_signals

def main():
    """主函数"""
    ensure_output_dir()
    state = load_state()
    
    try:
        # 下载数据
        df = download_latest_data()
        
        # 计算指标
        df = calculate_indicators(df)
        
        # 检测信号
        signals = detect_signals(df)
        
        # 生成报告
        report = generate_report(df, signals, state)
        print("\n" + report)
        
        # 检查新信号
        new_signals = check_new_signals(signals, state)
        
        # 保存报告到文件
        report_file = os.path.join(OUTPUT_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(report_file, 'w') as f:
            f.write(report)
        
        # 更新状态
        latest = df.iloc[-1]
        state['last_check'] = datetime.now().isoformat()
        state['last_price'] = float(latest['Close'])
        state['last_rsi'] = float(latest['RSI']) if pd.notna(latest['RSI']) else None
        state['last_signals'] = [s['type'] for s in signals]
        
        # 如果有新信号，记录到alert_sent
        if new_signals:
            if 'new_signals_log' not in state:
                state['new_signals_log'] = []
            state['new_signals_log'].append({
                'time': datetime.now().isoformat(),
                'signals': [s['type'] for s in new_signals]
            })
            print(f"\n⚠️  发现 {len(new_signals)} 个新信号！")
        
        save_state(state)
        
        # 返回退出码：0=无新信号，1=有新信号
        if new_signals:
            return 1
        return 0
        
    except Exception as e:
        error_msg = f"监控脚本出错: {e}"
        print(f"\n❌ {error_msg}")
        import traceback
        traceback.print_exc()
        
        # 保存错误日志
        error_file = os.path.join(OUTPUT_DIR, f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(error_file, 'w') as f:
            f.write(error_msg + "\n\n")
            traceback.print_exc(file=f)
        
        return 2

if __name__ == '__main__':
    exit_code = main()
    exit(exit_code)
