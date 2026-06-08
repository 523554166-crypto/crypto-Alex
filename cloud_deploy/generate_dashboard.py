#!/usr/bin/env python3
"""
比特币监控仪表盘数据生成器
生成JSON数据文件，供HTML仪表盘使用
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import sys
import time

# 添加主脚本到路径
sys.path.insert(0, os.path.dirname(__file__))

from monitor_bitcoin_ultimate import (
    download_bitcoin_data, calculate_indicators, detect_signals,
    load_state, generate_report, calculate_supertrend,
    calculate_adx, calculate_ichimoku_a, calculate_ichimoku_b,
    calculate_ichimoku_span, calculate_fibonacci_levels
)

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
MONITOR_DIR = os.path.join(os.path.dirname(__file__), '..', 'monitor')
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), '..', 'dashboard')
STATE_FILE = os.path.join(MONITOR_DIR, 'monitor_state.json')
DATA_FILE = os.path.join(DASHBOARD_DIR, 'dashboard_data.json')

def generate_dashboard_data():
    """生成仪表盘所需的所有数据"""
    print("=" * 80)
    print("比特币监控仪表盘数据生成器")
    print("=" * 80)
    print()
    
    # 1. 下载数据
    print("步骤1: 下载比特币数据...")
    try:
        df = download_bitcoin_data(start_date='2023-01-01')  # 最近3年数据用于图表
    except Exception as e:
        print(f"❌ 数据下载失败: {e}")
        return False
    
    # 2. 计算指标
    print("\n步骤2: 计算技术指标...")
    df = calculate_indicators(df)
    print("指标计算完成")
    
    # 3. 检测信号
    print("\n步骤3: 检测底部信号...")
    signals = detect_signals(df)
    print(f"检测到 {len(signals)} 个信号")
    
    # 4. 加载状态
    state = load_state()
    
    # 5. 准备价格数据（用于图表）
    print("\n步骤4: 准备图表数据...")
    
    # 最近90天的数据用于图表显示
    chart_days = 90
    df_chart = df.tail(chart_days).copy()
    
    # 价格数据
    price_data = []
    for i in range(len(df_chart)):
        price_data.append({
            'date': df_chart.index[i].strftime('%Y-%m-%d'),
            'open': float(df_chart['Open'].iloc[i]),
            'high': float(df_chart['High'].iloc[i]),
            'low': float(df_chart['Low'].iloc[i]),
            'close': float(df_chart['Close'].iloc[i]),
            'volume': float(df_chart['Volume'].iloc[i])
        })
    
    # 技术指标数据
    indicators_data = {
        'dates': [d['date'] for d in price_data],
        'ma20': [float(x) if pd.notna(x) else None for x in df_chart['MA20'].tail(chart_days)],
        'ma50': [float(x) if pd.notna(x) else None for x in df_chart['MA50'].tail(chart_days)],
        'ma200': [float(x) if pd.notna(x) else None for x in df_chart['MA200'].tail(chart_days)],
        'bb_upper': [float(x) if pd.notna(x) else None for x in df_chart['BB_upper'].tail(chart_days)],
        'bb_middle': [float(x) if pd.notna(x) else None for x in df_chart['BB_middle'].tail(chart_days)],
        'bb_lower': [float(x) if pd.notna(x) else None for x in df_chart['BB_lower'].tail(chart_days)],
        'supertrend': [float(x) if pd.notna(x) else None for x in df_chart['Supertrend'].tail(chart_days)],
        'supertrend_direction': [int(x) if pd.notna(x) else None for x in df_chart['Supertrend_direction'].tail(chart_days)],
        'rsi': [float(x) if pd.notna(x) else None for x in df_chart['RSI'].tail(chart_days)],
        'macd': [float(x) if pd.notna(x) else None for x in df_chart['MACD'].tail(chart_days)],
        'macd_signal': [float(x) if pd.notna(x) else None for x in df_chart['MACD_signal'].tail(chart_days)],
        'macd_hist': [float(x) if pd.notna(x) else None for x in df_chart['MACD_hist'].tail(chart_days)],
        'adx': [float(x) if pd.notna(x) else None for x in df_chart['ADX'].tail(chart_days)],
        'di_plus': [float(x) if pd.notna(x) else None for x in df_chart['DI_plus'].tail(chart_days)],
        'di_minus': [float(x) if pd.notna(x) else None for x in df_chart['DI_minus'].tail(chart_days)],
        'ichimoku_a': [float(x) if pd.notna(x) else None for x in df_chart['Ichimoku_A'].tail(chart_days)],
        'ichimoku_b': [float(x) if pd.notna(x) else None for x in df_chart['Ichimoku_B'].tail(chart_days)],
        'stoch_k': [float(x) if pd.notna(x) else None for x in df_chart['Stoch_K'].tail(chart_days)],
        'stoch_d': [float(x) if pd.notna(x) else None for x in df_chart['Stoch_D'].tail(chart_days)],
        'volume_ratio': [float(x) if pd.notna(x) else None for x in df_chart['Volume_ratio'].tail(chart_days)]
    }
    
    # 6. 当前指标值
    latest = df.iloc[-1]
    current_indicators = {
        'price': float(latest['Close']),
        'rsi': float(latest['RSI']) if pd.notna(latest['RSI']) else None,
        'stoch_k': float(latest['Stoch_K']) if pd.notna(latest['Stoch_K']) else None,
        'fear_greed': float(latest['Fear_Greed_Index']) if pd.notna(latest['Fear_Greed_Index']) else None,
        'ma200_dev': float(latest['Price_vs_MA200']) if pd.notna(latest['Price_vs_MA200']) else None,
        'bb_position': float(latest['BB_position']) if pd.notna(latest['BB_position']) else None,
        'macd_hist': float(latest['MACD_hist']) if pd.notna(latest['MACD_hist']) else None,
        'drawdown': float(latest['Drawdown_from_high']) if pd.notna(latest['Drawdown_from_high']) else None,
        'volume_ratio': float(latest['Volume_ratio']) if pd.notna(latest['Volume_ratio']) else None,
        'adx': float(latest['ADX']) if pd.notna(latest['ADX']) else None,
        'di_plus': float(latest['DI_plus']) if pd.notna(latest['DI_plus']) else None,
        'di_minus': float(latest['DI_minus']) if pd.notna(latest['DI_minus']) else None,
        'supertrend': float(latest['Supertrend']) if pd.notna(latest['Supertrend']) else None,
        'supertrend_direction': int(latest['Supertrend_direction']) if pd.notna(latest['Supertrend_direction']) else None,
        'ichimoku_bullish': bool(latest['Ichimoku_bullish']) if pd.notna(latest['Ichimoku_bullish']) else None,
        'near_fib_support': bool(latest['Near_fib_support']) if pd.notna(latest['Near_fib_support']) else None
    }
    
    # 7. 信号数据
    signals_data = []
    for signal in signals:
        signals_data.append({
            'type': signal['type'],
            'severity': signal['severity'],
            'message': signal['message'],
            'value': signal['value']
        })
    
    # 8. 购买建议
    high_signals = sum(1 for s in signals if s['severity'] == 'high')
    medium_signals = sum(1 for s in signals if s['severity'] == 'medium')
    low_signals = sum(1 for s in signals if s['severity'] == 'low')
    
    if high_signals >= 3:
        recommendation = 'strong_buy'
        recommendation_text = '强烈建议买入'
    elif high_signals >= 2:
        recommendation = 'buy'
        recommendation_text = '建议买入'
    elif high_signals >= 1 or medium_signals >= 3:
        recommendation = 'speculative'
        recommendation_text = '小仓位试探'
    elif medium_signals >= 1:
        recommendation = 'watch'
        recommendation_text = '建议观望'
    else:
        recommendation = 'no_buy'
        recommendation_text = '暂不建议买入'
    
    recommendation_data = {
        'recommendation': recommendation,
        'recommendation_text': recommendation_text,
        'high_signals': high_signals,
        'medium_signals': medium_signals,
        'low_signals': low_signals,
        'current_price': float(latest['Close'])
    }
    
    # 9. 历史信号数据
    history_data = state.get('signal_history', [])[-30:]  # 最近30条
    
    # 10. 组装完整数据
    dashboard_data = {
        'generated_at': datetime.now().isoformat(),
        'price_data': price_data,
        'indicators': indicators_data,
        'current_indicators': current_indicators,
        'signals': signals_data,
        'recommendation': recommendation_data,
        'history': history_data,
        'last_check_time': state.get('last_check_time'),
        'last_price': state.get('last_price')
    }
    
    # 11. 保存数据
    print("\n步骤5: 保存仪表盘数据...")
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 数据已保存: {DATA_FILE}")
    
    # 12. 生成HTML仪表盘
    print("\n步骤6: 生成HTML仪表盘...")
    generate_html_dashboard(dashboard_data)
    
    print("\n" + "=" * 80)
    print("✅ 仪表盘数据生成完成！")
    print("=" * 80)
    print(f"\n📊 打开以下文件查看仪表盘:")
    print(f"   {os.path.join(DASHBOARD_DIR, 'dashboard.html')}")
    
    return True

def generate_html_dashboard(data):
    """生成HTML仪表盘（将数据直接嵌入HTML）"""
    html_file = os.path.join(DASHBOARD_DIR, 'dashboard.html')
    
    # 将数据序列化为紧凑JSON字符串
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>比特币监控仪表盘 - 终极版</title>
    <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #0a0e17;
            color: #e1e5ee;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, #1a1f2e 0%, #2d3548 100%);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        
        .header h1 {{
            font-size: 32px;
            margin-bottom: 10px;
            color: #f7931a;
        }}
        
        .current-price {{
            font-size: 48px;
            font-weight: bold;
            color: #00ff88;
            margin: 20px 0;
        }}
        
        .price-change {{
            font-size: 20px;
            margin-bottom: 10px;
        }}
        
        .price-change.positive {{ color: #00ff88; }}
        .price-change.negative {{ color: #ff4976; }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .card {{
            background: #1a1f2e;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        
        .card h2 {{
            font-size: 20px;
            margin-bottom: 15px;
            color: #f7931a;
            border-bottom: 2px solid #2d3548;
            padding-bottom: 10px;
        }}
        
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #2d3548;
        }}
        
        .metric:last-child {{
            border-bottom: none;
        }}
        
        .metric-label {{
            color: #8a94a6;
        }}
        
        .metric-value {{
            font-weight: bold;
            font-size: 16px;
        }}
        
        .metric-value.positive {{ color: #00ff88; }}
        .metric-value.negative {{ color: #ff4976; }}
        .metric-value.neutral {{ color: #e1e5ee; }}
        
        .signal {{
            padding: 12px;
            margin: 8px 0;
            border-radius: 8px;
            border-left: 4px solid;
        }}
        
        .signal.high {{
            background: rgba(255, 73, 118, 0.1);
            border-color: #ff4976;
        }}
        
        .signal.medium {{
            background: rgba(255, 193, 7, 0.1);
            border-color: #ffc107;
        }}
        
        .signal.low {{
            background: rgba(0, 255, 136, 0.1);
            border-color: #00ff88;
        }}
        
        .recommendation {{
            background: linear-gradient(135deg, #1a1f2e 0%, #2d3548 100%);
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            margin-top: 20px;
        }}
        
        .recommendation.strong_buy {{ border: 3px solid #00ff88; }}
        .recommendation.buy {{ border: 3px solid #00cc6a; }}
        .recommendation.speculative {{ border: 3px solid #ffc107; }}
        .recommendation.watch {{ border: 3px solid #8a94a6; }}
        .recommendation.no_buy {{ border: 3px solid #ff4976; }}
        
        .recommendation-text {{
            font-size: 36px;
            font-weight: bold;
            margin: 20px 0;
        }}
        
        .recommendation.strong_buy .recommendation-text {{ color: #00ff88; }}
        .recommendation.buy .recommendation-text {{ color: #00cc6a; }}
        .recommendation.speculative .recommendation-text {{ color: #ffc107; }}
        .recommendation.watch .recommendation-text {{ color: #8a94a6; }}
        .recommendation.no_buy .recommendation-text {{ color: #ff4976; }}
        
        .chart-container {{
            height: 400px;
            margin-top: 15px;
        }}
        
        .update-time {{
            text-align: center;
            color: #8a94a6;
            margin-top: 20px;
            font-size: 14px;
        }}
        
        button {{
            background: #f7931a;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px 5px;
            transition: all 0.3s;
        }}
        
        button:hover {{
            background: #e8850f;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(247, 147, 26, 0.3);
        }}
        
        .loader {{
            border: 4px solid #2d3548;
            border-top: 4px solid #f7931a;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 比特币监控仪表盘（终极版）</h1>
        <div class="current-price" id="currentPrice">加载中...</div>
        <div class="price-change" id="priceChange"></div>
        <button onclick="window.location.reload()">🔄 刷新页面</button>
    </div>
    
    <div class="grid">
        <div class="card">
            <h2>📈 价格走势图</h2>
            <div id="priceChart" class="chart-container"></div>
        </div>
        
        <div class="card">
            <h2>📊 技术指标</h2>
            <div id="rsiChart" class="chart-container"></div>
        </div>
    </div>
    
    <div class="grid">
        <div class="card">
            <h2>🎯 关键指标</h2>
            <div id="keyMetrics"></div>
        </div>
        
        <div class="card">
            <h2>🚨 检测到的信号</h2>
            <div id="signalsList"></div>
        </div>
    </div>
    
    <div class="recommendation" id="recommendation">
        <h2>💡 购买建议</h2>
        <div class="recommendation-text" id="recommendationText">加载中...</div>
        <div id="recommendationDetails"></div>
    </div>
    
    <div class="update-time" id="updateTime"></div>
    
    <script>
        // 直接嵌入仪表盘数据
        const dashboardData = {data_json};
        
        // 渲染仪表盘
        function renderDashboard() {{
            renderPrice();
            renderCharts();
            renderKeyMetrics();
            renderSignals();
            renderRecommendation();
            renderUpdateTime();
        }}
        
        // 渲染价格
        function renderPrice() {{
            const price = dashboardData.current_indicators.price;
            document.getElementById('currentPrice').textContent = '$' + price.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
            
            const changeEl = document.getElementById('priceChange');
            if (dashboardData.last_price && dashboardData.last_price > 0) {{
                const change = ((price - dashboardData.last_price) / dashboardData.last_price) * 100;
                changeEl.className = 'price-change ' + (change >= 0 ? 'positive' : 'negative');
                changeEl.textContent = (change >= 0 ? '📈 ' : '📉 ') + (change >= 0 ? '+' : '') + change.toFixed(2) + '% (上次: $' + dashboardData.last_price.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}}) + ')';
            }} else {{
                changeEl.textContent = '首次检查';
                changeEl.className = 'price-change neutral';
            }}
        }}
        
        // 渲染图表
        function renderCharts() {{
            renderPriceChart();
            renderRSIChart();
        }}
        
        // 渲染价格走势图
        function renderPriceChart() {{
            const chartEl = document.getElementById('priceChart');
            chartEl.innerHTML = '';
            
            const chart = LightweightCharts.createChart(chartEl, {{
                width: chartEl.clientWidth,
                height: 350,
                layout: {{
                    background: {{ type: 'solid', color: '#1a1f2e' }},
                    textColor: '#e1e5ee',
                }},
                grid: {{
                    vertLines: {{ color: '#2d3548' }},
                    horzLines: {{ color: '#2d3548' }},
                }},
                timeScale: {{
                    timeVisible: false,
                }},
            }});
            
            //  Candlestick数据
            const candlestickData = dashboardData.price_data.map(d => ({{
                time: d.date,
                open: d.open,
                high: d.high,
                low: d.low,
                close: d.close,
            }}));
            
            const candlestickSeries = chart.addCandlestickSeries({{
                upColor: '#00ff88',
                downColor: '#ff4976',
                borderDownColor: '#ff4976',
                borderUpColor: '#00ff88',
                wickDownColor: '#ff4976',
                wickUpColor: '#00ff88',
            }});
            candlestickSeries.setData(candlestickData);
            
            // 添加Supertrend线
            const supertrendData = dashboardData.indicators.dates.map((date, i) => ({{
                time: date,
                value: dashboardData.indicators.supertrend[i],
            }})).filter(d => d.value !== null);
            
            if (supertrendData.length > 0) {{
                const supertrendSeries = chart.addLineSeries({{
                    color: '#f7931a',
                    lineWidth: 2,
                    priceLineVisible: false,
                }});
                supertrendSeries.setData(supertrendData);
            }}
            
            chart.timeScale().fitContent();
        }}
        
        // 渲染RSI图表
        function renderRSIChart() {{
            const chartEl = document.getElementById('rsiChart');
            chartEl.innerHTML = '<canvas id="rsiCanvas"></canvas>';
            const ctx = document.getElementById('rsiCanvas');
            
            const dates = dashboardData.indicators.dates;
            const rsiData = dashboardData.indicators.rsi;
            
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: dates,
                    datasets: [{{
                        label: 'RSI',
                        data: rsiData,
                        borderColor: '#f7931a',
                        backgroundColor: 'rgba(247, 147, 26, 0.1)',
                        fill: true,
                        tension: 0.4,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        x: {{ display: false }},
                        y: {{
                            min: 0,
                            max: 100,
                            grid: {{ color: '#2d3548' }},
                            ticks: {{ color: '#8a94a6' }}
                        }}
                    }}
                }}
            }});
        }}
        
        // 渲染关键指标
        function renderKeyMetrics() {{
            const indicators = dashboardData.current_indicators;
            let html = '';
            
            const metrics = [
                {{ label: 'RSI', value: indicators.rsi ? indicators.rsi.toFixed(2) : 'N/A', type: indicators.rsi < 30 ? 'negative' : indicators.rsi > 70 ? 'positive' : 'neutral' }},
                {{ label: '随机指标 %K', value: indicators.stoch_k ? indicators.stoch_k.toFixed(2) : 'N/A', type: 'neutral' }},
                {{ label: '恐慌贪婪指数', value: indicators.fear_greed ? indicators.fear_greed.toFixed(2) : 'N/A', type: 'neutral' }},
                {{ label: '相对200日均线', value: indicators.ma200_dev ? indicators.ma200_dev.toFixed(2) + '%' : 'N/A', type: indicators.ma200_dev < -20 ? 'negative' : 'positive' }},
                {{ label: '布林带位置', value: indicators.bb_position ? (indicators.bb_position * 100).toFixed(2) + '%' : 'N/A', type: 'neutral' }},
                {{ label: 'MACD柱状图', value: indicators.macd_hist ? indicators.macd_hist.toFixed(2) : 'N/A', type: indicators.macd_hist >= 0 ? 'positive' : 'negative' }},
                {{ label: '距离高点回撤', value: indicators.drawdown ? indicators.drawdown.toFixed(2) + '%' : 'N/A', type: 'negative' }},
                {{ label: 'ADX', value: indicators.adx ? indicators.adx.toFixed(2) : 'N/A', type: 'neutral' }},
                {{ label: 'Supertrend方向', value: indicators.supertrend_direction === 1 ? '看涨' : '看跌', type: indicators.supertrend_direction === 1 ? 'positive' : 'negative' }},
            ];
            
            metrics.forEach(m => {{
                html += '<div class="metric">';
                html += '<span class="metric-label">' + m.label + '</span>';
                html += '<span class="metric-value ' + m.type + '">' + m.value + '</span>';
                html += '</div>';
            }});
            
            document.getElementById('keyMetrics').innerHTML = html;
        }}
        
        // 渲染信号列表
        function renderSignals() {{
            const signals = dashboardData.signals;
            let html = '';
            
            if (signals.length === 0) {{
                html = '<p style="color: #8a94a6;">暂无检测到的信号</p>';
            }} else {{
                signals.forEach(signal => {{
                    const icon = signal.severity === 'high' ? '🔴' : signal.severity === 'medium' ? '🟡' : '🟢';
                    html += '<div class="signal ' + signal.severity + '">' + icon + ' ' + signal.message + '</div>';
                }});
            }}
            
            html += '<p style="margin-top: 15px; color: #8a94a6;">共检测到 <strong>' + signals.length + '</strong> 个信号</p>';
            
            document.getElementById('signalsList').innerHTML = html;
        }}
        
        // 渲染购买建议
        function renderRecommendation() {{
            const rec = dashboardData.recommendation;
            const recEl = document.getElementById('recommendation');
            const textEl = document.getElementById('recommendationText');
            
            recEl.className = 'recommendation ' + rec.recommendation;
            textEl.textContent = rec.recommendation_text;
            
            const detailsHtml = '<p style="margin: 15px 0; font-size: 18px;">' +
                '高优先级: <strong>' + rec.high_signals + '</strong> | ' +
                '中优先级: <strong>' + rec.medium_signals + '</strong> | ' +
                '低优先级: <strong>' + rec.low_signals + '</strong>' +
                '</p>' +
                '<p style="color: #8a94a6;">当前: $' + rec.current_price.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}}) + '</p>';
            
            document.getElementById('recommendationDetails').innerHTML = detailsHtml;
        }}
        
        // 渲染更新时间
        function renderUpdateTime() {{
            const generatedAt = new Date(dashboardData.generated_at);
            document.getElementById('updateTime').textContent = '最后更新: ' + generatedAt.toLocaleString('zh-CN');
        }}
        
        // 页面加载时自动渲染
        document.addEventListener('DOMContentLoaded', renderDashboard);
    </script>
</body>
</html>'''
    
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML仪表盘已生成: {html_file}")

if __name__ == '__main__':
    success = generate_dashboard_data()
    exit(0 if success else 1)
