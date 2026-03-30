#!/usr/bin/env python3
"""
积存金 OpenClaw 服务
定时监控价格，发送微信通知
"""
import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jijin_trader import find_working_proxy
from app.openclaw_integration import JijinOpenClaw


def send_wechat_notification(title: str, message: str):
    """
    发送微信通知
    通过OpenClaw的message工具
    """
    # 这里会调用OpenClaw的消息发送功能
    # 实际使用时需要通过OpenClaw的API
    print(f"\n[微信通知]")
    print(f"标题: {title}")
    print(f"内容: {message}")
    print("-" * 40)


class JijinService:
    """
    积存金服务
    
    功能:
    - 定时价格监控
    - 微信通知
    - 交易提醒
    """
    
    def __init__(self, proxy: str = None):
        self.proxy = proxy or find_working_proxy()
        self.oc = JijinOpenClaw(proxy=self.proxy)
        
        # 设置回调
        self.oc.set_alert_callback(self._on_price_alert)
        self.oc.set_trade_callback(self._on_trade)
        
        # 配置
        self.config = {
            'price_alert_threshold': 0.5,  # 价格预警阈值 %
            'profit_alert_threshold': 100,  # 盈利预警阈值 元
            'daily_report_time': '21:00',   # 日报时间
        }
    
    def _on_price_alert(self, alert: dict):
        """价格预警回调"""
        title = f"积存金价格{alert['direction']=='up' and '上涨' or '下跌'}预警"
        message = alert['message']
        send_wechat_notification(title, message)
    
    def _on_trade(self, notification: dict):
        """交易通知回调"""
        action = notification['action']
        title = f"积存金{'买入' if action=='buy' else '卖出'}成功"
        message = notification['message']
        send_wechat_notification(title, message)
    
    def check_prices(self):
        """检查价格"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 检查价格...")
        
        for bank in ['zheshang', 'minsheng']:
            alert = self.oc.check_price_change(bank)
            if alert:
                print(f"  ⚠️ {alert['bank_name']}: {alert['change_pct']:+.2f}%")
            else:
                quote = self.oc.price_feed.get_price(bank)
                if quote:
                    print(f"  ✓ {quote['name']}: {quote['price']:.2f}元/克 {quote['change_rate']}")
    
    def get_daily_report(self) -> str:
        """生成日报"""
        report = []
        report.append("📊 积存金交易日报")
        report.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        for bank in ['zheshang', 'minsheng']:
            trader = self.oc.traders[bank]
            quote = trader.get_quote()
            summary = trader.get_summary()
            
            if quote:
                report.append(f"【{quote['name']}】")
                report.append(f"  价格: {quote['price']:.2f}元/克 {quote['change_rate']}")
                report.append(f"  持仓: {summary['position']:.2f}克")
                report.append(f"  市值: {summary['position_value']:.2f}元")
                report.append(f"  浮动盈亏: {summary['unrealized_pnl']:+.2f}元")
                report.append(f"  累计盈亏: {summary['realized_pnl']:+.2f}元")
                report.append("")
        
        return "\n".join(report)
    
    def send_daily_report(self):
        """发送日报"""
        report = self.get_daily_report()
        send_wechat_notification("积存金交易日报", report)
    
    def run_once(self):
        """运行一次检查"""
        self.check_prices()
    
    def run_service(self):
        """运行服务（用于定时任务）"""
        import time
        
        print("积存金服务启动")
        print("=" * 60)
        
        while True:
            now = datetime.now()
            
            # 每小时检查价格
            if now.minute == 0:
                self.check_prices()
            
            # 每日21:00发送日报
            if now.hour == 21 and now.minute == 0:
                self.send_daily_report()
            
            time.sleep(60)


def main():
    """主程序"""
    parser = argparse.ArgumentParser(description='积存金 OpenClaw 服务')
    parser.add_argument(
        '--mode',
        choices=['once', 'report', 'service'],
        default='once',
        help='once=单次检查, report=打印日报, service=持续运行'
    )
    args = parser.parse_args()

    proxy = find_working_proxy()
    service = JijinService(proxy=proxy)

    if args.mode == 'once':
        print("积存金 OpenClaw 服务 - 单次检查")
        print("=" * 60)
        service.run_once()
    elif args.mode == 'report':
        print(service.get_daily_report())
    else:
        service.run_service()


if __name__ == "__main__":
    main()
