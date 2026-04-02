#!/bin/bash
# 创建systemd服务

echo "创建systemd服务..."

# 创建服务文件
sudo tee /etc/systemd/system/jijin-monitor.service > /dev/null << 'EOF'
[Unit]
Description=积存金交易监控系统
After=network.target

[Service]
Type=simple
User=<user>
WorkingDirectory=/home/<user>/.openclaw/workspace/gold-trading
Environment="PYTHONPATH=/home/<user>/.openclaw/workspace/gold-trading/src"
ExecStart=/usr/bin/python3 /home/<user>/.openclaw/workspace/gold-trading/ops/jijin_service.py --mode service
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

echo "✓ systemd服务文件已创建"

# 创建Web服务器服务
sudo tee /etc/systemd/system/jijin-web.service > /dev/null << 'EOF'
[Unit]
Description=积存金Dashboard Web服务器
After=network.target

[Service]
Type=simple
User=<user>
WorkingDirectory=/home/<user>/.openclaw/workspace/gold-trading/web
ExecStart=/usr/bin/python3 -m http.server 8090
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Web服务器服务文件已创建"

echo ""
echo "启用服务:"
echo "  sudo systemctl enable jijin-monitor"
echo "  sudo systemctl enable jijin-web"
echo ""
echo "启动服务:"
echo "  sudo systemctl start jijin-monitor"
echo "  sudo systemctl start jijin-web"
echo ""
echo "查看状态:"
echo "  sudo systemctl status jijin-monitor"
echo "  sudo systemctl status jijin-web"

