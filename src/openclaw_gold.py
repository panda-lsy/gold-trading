#!/usr/bin/env python3
"""
OpenClaw集成 - 黄金全天候交易
"""
import os
import json
import sys
from datetime import datetime
from typing import Dict
import logging
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gold_etf_trader import GoldETFTrader
from london_gold import LondonGoldSimulator
from gold_strategy import GoldIntradayStrategy, LondonGoldStrategy


class GoldTradingSystem:
    """
    黄金全天候交易系统
    
    自动切换:
    - 9:30-15:00: 黄金ETF实盘交易
    - 其他时间: 伦敦金模拟交易
    """
    
    def __init__(self, trader_backend=None):
        self.mode = None
        
        # 组件
        self.etf_trader = GoldETFTrader(trader_backend)
        self.london_sim = LondonGoldSimulator(initial_balance=100000)
        
        # 策略
        self.etf_strategy = GoldIntradayStrategy()
        self.london_strategy = LondonGoldStrategy()
        
        # 状态
        self.last_run = None
        
    def check_market_hours(self) -> str:
        """检查当前市场时段"""
        if self.etf_trader.is_trading_time():
            return 'etf'
        elif self.london_sim.is_trading_time():
            return 'london'
        else:
            return 'closed'
    
    def run(self) -> Dict:
        """运行一次交易循环"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'mode': None,
            'actions': [],
            'status': {}
        }
        
        # 判断交易模式
        market = self.check_market_hours()
        result['mode'] = market
        
        if market == 'etf':
            result.update(self._run_etf_trading())
        elif market == 'london':
            result.update(self._run_london_trading())
        else:
            result['status'] = '市场休市'
        
        self.last_run = datetime.now()
        return result
    
    def _run_etf_trading(self) -> Dict:
        """运行黄金ETF交易"""
        result = {'actions': [], 'status': {}}
        
        # 获取价格（从yahoo或新浪）
        price = 5.0  # 模拟价格，实际应从数据源获取
        
        # 获取持仓
        position = self.etf_trader.get_position()
        self.etf_strategy.position = position.get('volume', 0)
        
        # 生成信号
        time_str = datetime.now().strftime('%H:%M')
        signals = self.etf_strategy.on_tick(price, time_str)
        
        # 执行交易
        for signal in signals:
            if signal.action == 'BUY':
                success = self.etf_trader.buy(signal.price, signal.volume)
            elif signal.action == 'SELL':
                success = self.etf_trader.sell(signal.price, signal.volume)
            else:
                success = True
            
            result['actions'].append({
                'code': signal.code, 'action': signal.action,
                'price': signal.price, 'volume': signal.volume,
                'reason': signal.reason, 'success': success
            })
        
        # 检查是否收盘
        if time_str >= '14:55':
            close_signals = self.etf_strategy.on_close(price)
            for signal in close_signals:
                success = self.etf_trader.sell(signal.price, signal.volume)
                result['actions'].append({
                    'code': signal.code, 'action': 'CLOSE',
                    'price': signal.price, 'volume': signal.volume,
                    'reason': signal.reason, 'success': success
                })
        
        result['status'] = {
            'price': price,
            'position': position,
            'balance': self.etf_trader.get_balance()
        }
        
        return result
    
    def _run_london_trading(self) -> Dict:
        """运行伦敦金模拟交易"""
        result = {'actions': [], 'status': {}}
        
        # 获取价格
        price = self.london_sim.get_price()
        if not price:
            result['error'] = '无法获取伦敦金价格'
            return result
        
        # 获取K线数据
        klines = self.london_sim.get_kline(period='1h', count=30)
        self.london_strategy.update_kline(klines)
        
        # 生成信号
        signals = self.london_strategy.on_data(price)
        
        # 执行交易
        for signal in signals:
            if signal.action == 'BUY':
                success = self.london_sim.buy(signal.volume)
            elif signal.action == 'SELL':
                success = self.london_sim.sell(signal.volume)
            else:
                success = True
            
            result['actions'].append({
                'symbol': signal.code, 'action': signal.action,
                'price': signal.price, 'volume': signal.volume,
                'reason': signal.reason, 'success': success
            })
        
        # 获取账户摘要
        result['status'] = self.london_sim.get_summary()
        
        return result
    
    def get_daily_report(self) -> str:
        """生成日报"""
        report = []
        report.append("=" * 40)
        report.append("黄金交易日报")
        report.append("=" * 40)
        report.append(f"日期: {datetime.now().strftime('%Y-%m-%d')}")
        report.append("")
        
        # ETF交易总结
        report.append("【黄金ETF 518850】")
        position = self.etf_trader.get_position()
        balance = self.etf_trader.get_balance()
        report.append(f"持仓: {position.get('volume', 0)}股")
        report.append(f"现金: {balance.get('cash', 0):.2f}")
        report.append("")
        
        # 伦敦金总结
        report.append("【伦敦金 XAUUSD】")
        summary = self.london_sim.get_summary()
        report.append(f"账户余额: ${summary['balance']:.2f}")
        report.append(f"持仓: {summary['position']:.2f}盎司")
        report.append(f"浮动盈亏: ${summary['unrealized_pnl']:.2f}")
        report.append(f"已实现盈亏: ${summary['realized_pnl']:.2f}")
        report.append(f"总交易次数: {summary['trade_count']}")
        report.append("")
        
        return "\n".join(report)


# OpenClaw入口
def run_gold_trading() -> str:
    """OpenClaw调用入口"""
    system = GoldTradingSystem()
    result = system.run()
    return json.dumps(result, ensure_ascii=False, default=str)


def get_gold_report() -> str:
    """获取日报"""
    system = GoldTradingSystem()
    return system.get_daily_report()


if __name__ == "__main__":
    print("运行黄金交易系统...")
    result = run_gold_trading()
    print(result)
