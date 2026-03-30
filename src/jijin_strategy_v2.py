#!/usr/bin/env python3
"""
积存金交易策略 v2.0 - 改进版

改进点:
1. 避免频繁买卖 (最小持仓时间)
2. 考虑0.4%卖出手续费，设置合理盈利目标
3. 分批建仓/减仓
4. 趋势确认后再交易
"""
import json
import os
from typing import Dict, List
from datetime import datetime, timedelta


class JijinStrategyV2:
    """积存金交易策略 v2.0"""
    
    # 交易参数
    MIN_HOLD_MINUTES = 30  # 最小持仓时间
    MIN_PROFIT_PCT = 0.5   # 最小盈利目标(%)
    TRADE_UNIT = 5.0       # 每次交易单位(克)
    
    # 趋势参数
    TREND_CONFIRM_COUNT = 3
    TREND_THRESHOLD = 0.3
    
    def __init__(self, trader, strategy_type: str = 'smart'):
        self.trader = trader
        self.strategy_type = strategy_type
        self.price_history = []
        self.last_trade_time = None
        self.signals = []
    
    def can_trade(self) -> tuple:
        """检查是否可以交易"""
        if not self.trader.is_trading_time():
            return False, "非交易时间"
        
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds() / 60
            if elapsed < self.MIN_HOLD_MINUTES:
                return False, f"持仓时间不足{self.MIN_HOLD_MINUTES}分钟"
        
        return True, "可以交易"
    
    def calculate_profit_after_fee(self, buy_price: float, sell_price: float) -> float:
        """计算扣除手续费后的净利润(%)"""
        gross_profit = (sell_price - buy_price) / buy_price * 100
        fee = 0.4  # 卖出手续费
        return gross_profit - fee
    
    def analyze_trend(self, price_history: List[Dict]) -> Dict:
        """分析趋势"""
        if len(price_history) < self.TREND_CONFIRM_COUNT:
            return {'trend': 'flat', 'strength': 0}
        
        recent = price_history[-self.TREND_CONFIRM_COUNT:]
        prices = [p['price'] for p in recent]
        changes = []
        
        for i in range(1, len(prices)):
            change = (prices[i] - prices[i-1]) / prices[i-1] * 100
            changes.append(change)
        
        avg_change = sum(changes) / len(changes)
        
        if all(c > 0 for c in changes) and avg_change > self.TREND_THRESHOLD:
            return {'trend': 'up', 'strength': avg_change}
        elif all(c < 0 for c in changes) and avg_change < -self.TREND_THRESHOLD:
            return {'trend': 'down', 'strength': abs(avg_change)}
        
        return {'trend': 'flat', 'strength': 0}
    
    def smart_strategy(self, price_history: List[Dict]) -> Dict:
        """智能策略"""
        if not price_history:
            return {'signal': 'hold', 'reason': '无价格数据'}
        
        current_price = price_history[-1]['price']
        position = self.trader.position
        avg_price = self.trader.avg_price
        balance = self.trader.balance
        
        can_trade, reason = self.can_trade()
        if not can_trade:
            return {'signal': 'hold', 'reason': reason}
        
        trend = self.analyze_trend(price_history)
        
        # 有持仓时 - 考虑卖出
        if position > 0:
            net_profit = self.calculate_profit_after_fee(avg_price, current_price)
            
            if net_profit >= self.MIN_PROFIT_PCT:
                if trend['trend'] == 'down':
                    return {
                        'signal': 'sell',
                        'reason': f'盈利{net_profit:.2f}%达标且趋势向下',
                        'grams': min(position, self.TRADE_UNIT)
                    }
                else:
                    return {
                        'signal': 'hold',
                        'reason': f'盈利{net_profit:.2f}%但趋势向上，继续持有'
                    }
            else:
                # 亏损超过1%，止损
                if trend['trend'] == 'down' and net_profit < -1.0:
                    return {
                        'signal': 'sell',
                        'reason': f'亏损{abs(net_profit):.2f}%超过1%，止损',
                        'grams': min(position, self.TRADE_UNIT)
                    }
                
                return {
                    'signal': 'hold',
                    'reason': f'盈利{net_profit:.2f}%未达标，继续持有'
                }
        
        # 无持仓时 - 考虑买入
        else:
            if trend['trend'] == 'up':
                buy_grams = min(self.TRADE_UNIT, balance * 0.8 / current_price)
                if buy_grams >= 1.0:
                    strength = trend['strength']
                return {
                        'signal': 'buy',
                        'reason': f'趋势向上({strength:.2f}%)，买入{buy_grams:.1f}克',
                        'grams': buy_grams
                    }
            
            trend_name = trend['trend']
            return {
                'signal': 'hold',
                'reason': f'趋势{trend_name}，观望'
            }
    
    def execute_signal(self, signal: Dict) -> bool:
        """执行交易信号"""
        action = signal.get('signal')
        
        if action == 'buy':
            grams = signal.get('grams', self.TRADE_UNIT)
            success = self.trader.buy(grams)
            if success:
                self.last_trade_time = datetime.now()
            return success
        
        elif action == 'sell':
            grams = signal.get('grams', self.TRADE_UNIT)
            success = self.trader.sell(grams)
            if success:
                self.last_trade_time = datetime.now()
            return success
        
        return False
    
    def run(self, price_history: List[Dict], auto_execute: bool = False) -> Dict:
        """运行策略"""
        signal = self.smart_strategy(price_history)
        executed = False
        
        if auto_execute and signal['signal'] in ['buy', 'sell']:
            executed = self.execute_signal(signal)
        
        return {**signal, 'executed': executed}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from src.jijin_trader import JijinTrader, find_working_proxy
    
    print("积存金策略 v2.0 测试")
    print("=" * 60)
    
    proxy = find_working_proxy()
    trader = JijinTrader(bank='zheshang', proxy=proxy)
    strategy = JijinStrategyV2(trader, 'smart')
    
    # 模拟价格历史
    base_price = trader.get_price() or 1000.0
    price_history = []
    import random
    
    for i in range(10):
        price = base_price * (1 + random.uniform(-0.005, 0.005))
        price_history.append({'timestamp': datetime.now().isoformat(), 'price': price})
    
    print(f"\n当前持仓: {trader.position:.2f}克")
    print(f"持仓均价: {trader.avg_price:.2f}元")
    print(f"当前价格: {price_history[-1]['price']:.2f}元")
    
    # 运行策略
    result = strategy.run(price_history, auto_execute=False)
    
    print(f"\n策略信号: {result['signal']}")
    print(f"原因: {result['reason']}")
    
    if result['signal'] == 'sell' and trader.position > 0:
        profit = strategy.calculate_profit_after_fee(trader.avg_price, price_history[-1]['price'])
        print(f"预计净利润: {profit:.2f}%")
