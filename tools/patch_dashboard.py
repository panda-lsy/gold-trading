import sys

with open('app/dashboard_v3.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace X-axis time formatting
text = text.replace("k.datetime.slice(-5)", "k.datetime.substring(5, 16)")

# Replace Tab-charts and add Tab-AI
charts_old = """                <div class="card">
                    <div class="card-header">
                        <div class="card-title">📈 浙商积存金 - 专业K线</div>
                        <div style="color: #8b949e; font-size: 0.9em;">MA5/MA10/MA20 + 成交量</div>
                    </div>
                    <div class="chart-container" id="zheshangChart"></div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">📈 民生积存金 - 专业K线</div>
                        <div style="color: #8b949e; font-size: 0.9em;">MA5/MA10/MA20 + 成交量</div>
                    </div>
                    <div class="chart-container" id="minshengChart"></div>
                </div>
            </div>
        </div>
    </div>"""

charts_new = """                <div class="card">
                    <div class="card-header">
                        <div class="card-title">📈 浙商积存金 - 专业K线</div>
                        <div style="color: #8b949e; font-size: 0.9em;">MA5/MA10/MA20 + 成交量</div>
                    </div>
                    <div class="chart-container" id="zheshangChart" style="height:350px;"></div>
                    <div class="card-title" style="margin-top:20px; font-size:1em; color:#e6edf3;">⏱ 实时秒级价格走势</div>
                    <div class="chart-container" id="zheshangRt" style="height:150px; margin-top:5px; background: transparent; border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;"></div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">📈 民生积存金 - 专业K线</div>
                        <div style="color: #8b949e; font-size: 0.9em;">MA5/MA10/MA20 + 成交量</div>
                    </div>
                    <div class="chart-container" id="minshengChart" style="height:350px;"></div>
                    <div class="card-title" style="margin-top:20px; font-size:1em; color:#e6edf3;">⏱ 实时秒级价格走势</div>
                    <div class="chart-container" id="minshengRt" style="height:150px; margin-top:5px; background: transparent; border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;"></div>
                </div>
            </div>
        </div>

        <div id="tab-ai" class="tab-content" style="height: 85vh;">
            <iframe src="http://127.0.0.1:8090" style="width:100%; height:100%; border:none; border-radius: 12px; background: transparent;"></iframe>
        </div>
    </div>"""

text = text.replace(charts_old, charts_new)

# Variables
vars_old = """        let currentData = INITIAL_DATA;
        let ws = null;
        let charts = {};"""
vars_new = """        let currentData = INITIAL_DATA;
        let ws = null;
        let charts = {};
// Realtime Charts Variables
        let rtCharts = {};
        const maxPoints = 60;
        let priceHistory = {
            zheshang: Array(maxPoints).fill(null),
            minsheng: Array(maxPoints).fill(null)
        };

        function updateRealtimeCharts() {
            for(const bank of ['zheshang', 'minsheng']) {
                if(!rtCharts[bank]) {
                    const dom = document.getElementById(bank + 'Rt');
                    if(dom) {
                        rtCharts[bank] = echarts.init(dom, 'dark');
                        rtCharts[bank].setOption({
                            backgroundColor: 'transparent',
                            animation: false,
                            grid: { left: 45, right: 15, top: 10, bottom: 20 },
                            xAxis: { type: 'category', data: Array(maxPoints).fill(''), axisLabel: {show: false}, splitLine: {show: false} },
                            yAxis: { type: 'value', scale: true, axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                            series: [{ type: 'line', data: [], smooth: true, showSymbol: false, lineStyle: { color: '#FFD700', width: 2 }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: 'rgba(255, 215, 0, 0.3)'}, {offset: 1, color: 'rgba(255, 215, 0, 0.0)'}]) } }]
                        });
                        window.addEventListener('resize', () => rtCharts[bank] && rtCharts[bank].resize());
                    }
                }
                
                if (currentData.prices && currentData.prices[bank] && currentData.prices[bank].price) {
                    priceHistory[bank].push(currentData.prices[bank].price);
                    if (priceHistory[bank].length > maxPoints) {
                        priceHistory[bank].shift();
                    }
                    if(rtCharts[bank]) {
                        rtCharts[bank].setOption({
                            series: [{ data: priceHistory[bank] }]
                        });
                    }
                }
            }
        }"""
text = text.replace(vars_old, vars_new)

# ws.onmessage
ws_old = """                    currentData.timestamp = data.timestamp;
                    renderPrices();
                    document.getElementById('updateTime').textContent = '更新于:"""
ws_new = """                    currentData.timestamp = data.timestamp;
                    renderPrices();
                    updateRealtimeCharts();
                    document.getElementById('updateTime').textContent = '更新于:"""
text = text.replace(ws_old, ws_new)

# setInterval 
int_old = """                renderStats();
                renderPrices();
                renderTrades();
                document.getElementById('updateTime').textContent = '更新于: ' + formatDateTime(data.timestamp);
            }).catch(e => console.error('刷新失败:', e));
        }, 10000);"""
int_new = """                renderStats();
                renderPrices();
                renderTrades();
                updateRealtimeCharts();
                document.getElementById('updateTime').textContent = '更新于: ' + formatDateTime(data.timestamp);
            }).catch(e => console.error('刷新失败:', e));
        }, 2000);"""
text = text.replace(int_old, int_new)

# initial call
init_old = """        renderStats();
        renderPrices();
        renderTrades();
        connectWebSocket();"""
init_new = """        renderStats();
        renderPrices();
        renderTrades();
        updateRealtimeCharts();
        connectWebSocket();"""
text = text.replace(init_old, init_new)

with open('app/dashboard_v3.py', 'w', encoding='utf-8') as f:
    f.write(text)
