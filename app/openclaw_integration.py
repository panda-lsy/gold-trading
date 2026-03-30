#!/usr/bin/env python3
"""
积存金 OpenClaw 集成模块
实现:
- 价格波动监控
- 交易通知
- OpenClaw介入
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jijin_trader import JijinTrader, JijinPriceFeed, find_working_proxy


class JijinOpenClaw:
    """积存金 OpenClaw 集成"""
    
    def __init__(self, proxy: str = None):
        self.proxy = proxy or find_working_proxy()
        self.price_feed = JijinPriceFeed(proxy=self.proxy)
        
        self.traders = {
            'zheshang': JijinTrader(bank='zheshang', proxy=self.proxy),
            'minsheng': JijinTrader(bank='minsheng', proxy=self.proxy)
        }
        
        self.price_history = {'zheshang': [], 'minsheng': []}
        
        self.alert_config = {
            'price_change_threshold': 0.5,
            'check_interval': 60,
            'enable_auto_trade': False,
        }
        
        self.on_price_alert: Optional[Callable] = None
        self.on_trade: Optional[Callable] = None
        self.notifications = []
    
    def set_alert_callback(self, callback: Callable):
        self.on_price_alert = callback
    
    def set_trade_callback(self, callback: Callable):
        self.on_trade = callback
    
    def check_price_change(self, bank: str) -> Optional[Dict]:
        """检查价格变化"""
        quote = self.price_feed.get_price(bank)
        if not quote:
            return None
        
        current_price = quote['price']
        
        self.price_history[bank].append({
            'timestamp': datetime.now().isoformat(),
            'price': current_price
        })
        
        self.price_history[bank] = self.price_history[bank][-20:]
        
        if len(self.price_history[bank]) < 2:
            return None
        
        old_price = self.price_history[bank][0]['price']
        change_pct = (current_price - old_price) / old_price * 100
        
        threshold = self.alert_config['price_change_threshold']
        
        if abs(change_pct) >= threshold:
            alert = {
                'type': 'price_alert',
                'bank': bank,
                'bank_name': quote['name'],
                'current_price': current_price,
                'change_pct': change_pct,
                'direction': 'up' if change_pct > 0 else 'down',
                'timestamp': datetime.now().isoformat(),
                'message': self._format_alert(quote['name'], current_price, change_pct)
            }
            
            self.notifications.append(alert)
            
            if self.on_price_alert:
                self.on_price_alert(alert)
            
            return alert
        
        return None
    
    def _format_alert(self, name: str, price: float, change_pct: float) -> str:
        emoji = "📈" if change_pct > 0 else "📉"
        direction = "上涨" if change_pct > 0 else "下跌"
        return f"{emoji} {name} 价格{direction} {change_pct:+.2f}%\n当前: {price:.2f}元/克"
    
    def notify_trade(self, bank: str, action: str, grams: float, price: float, profit: float = 0):
        """交易通知"""
        trader = self.traders[bank]
        summary = trader.get_summary()
        
        if action == 'buy':
            message = f"买入 {grams:.2f}克 @ {price:.2f}元/克"
        else:
            message = f"卖出 {grams:.2f}克 @ {price:.2f}元/克, 盈亏: {profit:+.2f}元"
        
        notification = {
            'type': 'trade',
            'bank': bank,
            'action': action,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        self.notifications.append(notification)
        
        if self.on_trade:
            self.on_trade(notification)
        
        return notification


if __name__ == "__main__":
    print("积存金 OpenClaw 集成测试")
    print("=" * 60)
    
    proxy = find_working_proxy()
    oc = JijinOpenClaw(proxy=proxy)
    
    # 设置回调
    def on_alert(alert):
        print(f"\n🔔 预警: {alert['message']}")
    
    def on_trade(notification):
        print(f"\n💰 交易: {notification['message']}")
    
    oc.set_alert_callback(on_alert)
    oc.set_trade_callback(on_trade)
    
    # 测试价格检查
    print("\n测试价格监控...")
    for bank in ['zheshang', 'minsheng']:
        alert = oc.check_price_change(bank)
        if alert:
            print(f"✓ {bank}: 触发预警")
        else:
            print(f"✓ {bank}: 价格正常")
    
    print("\n✓ OpenClaw集成测试完成")
