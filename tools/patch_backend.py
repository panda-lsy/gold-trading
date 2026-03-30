import re
from pathlib import Path

with open('app/dashboard_v3.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update the iframe src
text = text.replace('http://127.0.0.1:8090', '/ai_page')

# 2. Fix the split tab resize
old_switch = """        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');  
            if (tabName === 'charts') setTimeout(initKlineCharts, 100);
        }"""
new_switch = """        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');  
            if (tabName === 'charts') {
                setTimeout(() => {
                    initKlineCharts();
                    if (rtCharts.zheshang) rtCharts.zheshang.resize();
                    if (rtCharts.minsheng) rtCharts.minsheng.resize();
                }, 100);
            }
        }"""
text = text.replace(old_switch, new_switch)

# 3. Add the route
old_route = """        @app.route('/api/health')
        def health():
            return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})"""

new_route = """        @app.route('/api/health')
        def health():
            return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

        @app.route('/ai_page')
        def ai_page():
            with open(PROJECT_ROOT / 'web' / 'index.html', 'r', encoding='utf-8') as f:
                return f.read()"""
text = text.replace(old_route, new_route)

with open('app/dashboard_v3.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Backend patched successfully")
