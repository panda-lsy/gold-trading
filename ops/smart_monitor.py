#!/usr/bin/env python3
"""
智能监控系统 - 考虑开市状态
- 休市时跳过交易相关检查
- 交易日报在非交易日自动切换为热点新闻
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jijin_trader import JijinTrader, JijinPriceFeed, find_working_proxy


class SmartMonitor:
    """智能监控系统"""
    
    def __init__(self, proxy: str = None):
        self.proxy = proxy or find_working_proxy()
        self.price_feed = JijinPriceFeed(proxy=self.proxy)
        self.traders = {
            'zheshang': JijinTrader(bank='zheshang', proxy=self.proxy),
            'minsheng': JijinTrader(bank='minsheng', proxy=self.proxy)
        }
    
    def is_market_open(self, bank: str = None) -> bool:
        """检查是否开市（任一银行开市即认为市场开放）"""
        if bank:
            return self.traders[bank].is_trading_time()
        
        # 检查是否有任一银行开市
        for b in ['zheshang', 'minsheng']:
            if self.traders[b].is_trading_time():
                return True
        return False
    
    def get_market_status(self) -> Dict:
        """获取市场状态"""
        now = datetime.now()
        weekday = now.weekday()
        
        status = {
            'timestamp': now.isoformat(),
            'weekday': weekday,
            'is_trading_day': weekday < 6,  # 周日休市
            'banks': {}
        }
        
        for bank in ['zheshang', 'minsheng']:
            trader = self.traders[bank]
            quote = trader.get_quote()
            status['banks'][bank] = {
                'is_trading': trader.is_trading_time(),
                'price': quote['price'] if quote else None,
                'change_rate': quote['change_rate'] if quote else None
            }
        
        status['is_any_open'] = any(b['is_trading'] for b in status['banks'].values())
        return status
    
    def check_price_alert(self) -> Optional[str]:
        """检查价格波动（仅开市时）"""
        if not self.is_market_open():
            return None
        
        alerts = []
        for bank in ['zheshang', 'minsheng']:
            quote = self.price_feed.get_price(bank)
            if not quote:
                continue
            
            change_rate = quote['change_rate']
            if change_rate:
                try:
                    rate = float(change_rate.replace('%', ''))
                    if abs(rate) >= 0.5:
                        direction = "上涨" if rate > 0 else "下跌"
                        alerts.append(
                            f"🚨 {quote['name']} 价格{direction} {rate:+.2f}%\n"
                            f"当前: {quote['price']:.2f}元/克"
                        )
                except:
                    pass
        
        return "\n\n".join(alerts) if alerts else None
    
    def generate_report(self) -> str:
        """生成报告（根据市场状态自动切换）"""
        market_status = self.get_market_status()
        
        if market_status['is_any_open']:
            return self._generate_trading_report()
        else:
            return self._generate_news_report()
    
    def _generate_trading_report(self) -> str:
        """生成交易日报"""
        lines = [
            "📊 积存金交易日报",
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "【市场状态】✅ 交易中",
            ""
        ]
        
        for bank in ['zheshang', 'minsheng']:
            trader = self.traders[bank]
            quote = trader.get_quote()
            summary = trader.get_summary()
            
            if not quote:
                continue
            
            lines.append(f"【{quote['name']}】")
            lines.append(f"价格: {quote['price']:.2f}元/克 ({quote['change_rate']})")
            
            if summary['position'] > 0:
                lines.append(f"持仓: {summary['position']:.2f}克")
                lines.append(f"均价: {summary['avg_price']:.2f}元/克")
                lines.append(f"市值: {summary['position_value']:.2f}元")
                lines.append(f"浮动盈亏: {summary['unrealized_pnl']:+.2f}元")
                
                # 计算净利润
                if summary['avg_price'] > 0:
                    gross = (quote['price'] - summary['avg_price']) / summary['avg_price'] * 100
                    net = gross - 0.4
                    if net > 0.5:
                        lines.append(f"🔴 建议: SELL (净利润{net:.2f}% > 0.5%)")
                    elif net < -1:
                        lines.append(f"🟡 建议: SELL 止损 (净利润{net:.2f}% < -1%)")
                    else:
                        lines.append(f"🟢 建议: HOLD (净利润{net:.2f}%)")
            else:
                lines.append("持仓: 空仓")
                lines.append("🟢 建议: 观望，等待买入机会")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_news_report(self) -> str:
        """生成热点新闻报告（休市时）"""
        lines = [
            "📰 积存金市场热点",
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "【市场状态】⏸️ 休市中",
            ""
        ]
        
        # 获取最新价格
        for bank in ['zheshang', 'minsheng']:
            quote = self.price_feed.get_price(bank)
            trader = self.traders[bank]
            summary = trader.get_summary()
            
            if not quote:
                continue
            
            lines.append(f"【{quote['name']}】")
            lines.append(f"最新价: {quote['price']:.2f}元/克")
            lines.append(f"涨跌: {quote['change_amt']} ({quote['change_rate']})")
            
            if summary['position'] > 0:
                lines.append(f"持仓: {summary['position']:.2f}克")
                lines.append(f"浮动盈亏: {summary['unrealized_pnl']:+.2f}元")
            
            lines.append("")
        
        # 添加市场分析
        lines.append("【市场分析】")
        lines.append("• 当前市场休市，建议关注国际金价走势")
        lines.append("• 周一开盘前可关注周末国际市场动态")
        lines.append("• 持仓用户请留意开盘后的价格波动")
        lines.append("")
        
        lines.append("【明日关注点】")
        lines.append("• 国际市场金价走势")
        lines.append("• 人民币汇率变化")
        lines.append("• 宏观经济数据发布")
        
        return "\n".join(lines)
    
    def hourly_check(self) -> str:
        """每小时检查（仅开市时执行交易检查）"""
        if not self.is_market_open():
            status = self.get_market_status()
            return f"⏸️ 市场休市中 ({status['timestamp'][:10]})\n跳过交易检查，仅监控价格..."
        
        return self.generate_report()
    
    def price_alert_check(self) -> Optional[str]:
        """价格波动预警（仅开市时）"""
        if not self.is_market_open():
            return None
        
        return self.check_price_alert()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='积存金智能监控')
    parser.add_argument('action', choices=['report', 'alert', 'hourly', 'status'])
    args = parser.parse_args()
    
    monitor = SmartMonitor()
    
    if args.action == 'report':
        print(monitor.generate_report())
    elif args.action == 'alert':
        alert = monitor.price_alert_check()
        if alert:
            print(alert)
        else:
            print("✓ 价格波动正常")
    elif args.action == 'hourly':
        print(monitor.hourly_check())
    elif args.action == 'status':
        status = monitor.get_market_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
