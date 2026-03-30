#!/usr/bin/env python3
"""
积存金交易策略
针对浙商/民生积存金的特点设计

特点:
- 价格接近实时 (与现货金价挂钩)
- 卖出手续费 0.4%
- 交易时间 9:00-22:00
- 适合波段操作
"""
from typing import Dict, List, Optional
from datetime import datetime
import json
import os


class JijinStrategy:
    """
    积存金交易策略
    
    策略1: 网格交易
    - 在价格区间内低买高卖
    - 考虑0.4%卖出手续费
    
    策略2: 趋势跟踪
    - 突破均线买入
    - 跌破均线卖出
    
    策略3: 定投策略
    - 定期定额买入
    - 平摊成本
    """
    
    def __init__(self, trader, strategy_type: str = 'grid'):
        """
        初始化
        
        Args:
            trader: JijinTrader实例
            strategy_type: 'grid', 'trend', 'dca'
        """
        self.trader = trader
        self.strategy_type = strategy_type
        
        # 策略参数
        self.params = self._default_params()
        
        # 信号历史
        self.signals = []
    
    def _default_params(self) -> Dict:
        """默认策略参数"""
        if self.strategy_type == 'grid':
            return {
                'grid_size': 5.0,        # 网格大小 (元)
                'grid_count': 5,          # 网格数量
                'base_position': 10.0,    # 基础持仓 (克)
                'min_trade': 1.0,         # 最小交易量
            }
        elif self.strategy_type == 'trend':
            return {
                'ma_period': 20,          # 均线周期
                'buy_threshold': 0.005,   # 买入阈值 (突破均线0.5%)
                'sell_threshold': -0.005, # 卖出阈值 (跌破均线0.5%)
                'position_size': 10.0,    # 单次交易数量
            }
        elif self.strategy_type == 'dca':
            return {
                'amount_per_trade': 1000, # 每次投入金额
                'interval_days': 7,       # 定投间隔 (天)
                'last_trade_date': None,  # 上次交易日期
            }
        return {}
    
    def analyze(self, price_history: List[Dict]) -> Dict:
        """
        分析当前市场状态
        
        Args:
            price_history: 价格历史 [{timestamp, price}, ...]
        
        Returns:
            分析结果
        """
        if not price_history or len(price_history) < 2:
            return {'signal': 'hold', 'reason': '数据不足'}
        
        current_price = price_history[-1]['price']
        
        if self.strategy_type == 'grid':
            return self._analyze_grid(current_price, price_history)
        elif self.strategy_type == 'trend':
            return self._analyze_trend(current_price, price_history)
        elif self.strategy_type == 'dca':
            return self._analyze_dca(current_price)
        
        return {'signal': 'hold', 'reason': '未知策略'}
    
    def _analyze_grid(self, current_price: float, history: List[Dict]) -> Dict:
        """网格策略分析"""
        params = self.params
        grid_size = params['grid_size']
        
        # 计算网格位置
        base_price = history[0]['price']
        grid_levels = []
        
        for i in range(-params['grid_count'], params['grid_count'] + 1):
            level = base_price + i * grid_size
            grid_levels.append(level)
        
        # 找到当前价格所在网格
        current_grid = None
        for i, level in enumerate(grid_levels[:-1]):
            if level <= current_price < grid_levels[i + 1]:
                current_grid = i
                break
        
        if current_grid is None:
            return {'signal': 'hold', 'reason': '价格超出网格范围'}
        
        # 计算网格中点
        grid_low = grid_levels[current_grid]
        grid_high = grid_levels[current_grid + 1]
        grid_mid = (grid_low + grid_high) / 2
        
        # 判断信号
        # 考虑0.4%手续费，需要价格差 > 0.4%才有利润
        min_profit = current_price * 0.004
        
        position = self.trader.position
        avg_price = self.trader.avg_price
        
        signal = 'hold'
        reason = f'当前网格: {current_grid}, 范围: {grid_low:.2f}-{grid_high:.2f}'
        
        # 低于网格中点，考虑买入
        if current_price < grid_mid - grid_size * 0.3:
            if self.trader.balance > current_price * params['min_trade']:
                signal = 'buy'
                reason = f'价格低于网格中点，建议买入'
        
        # 高于网格中点且有持仓，考虑卖出
        elif current_price > grid_mid + grid_size * 0.3:
            if position > 0 and (current_price - avg_price) > min_profit:
                signal = 'sell'
                reason = f'价格高于网格中点且有利润，建议卖出'
        
        return {
            'signal': signal,
            'reason': reason,
            'current_price': current_price,
            'grid_low': grid_low,
            'grid_high': grid_high,
            'grid_mid': grid_mid,
            'position': position,
            'avg_price': avg_price
        }
    
    def _analyze_trend(self, current_price: float, history: List[Dict]) -> Dict:
        """趋势策略分析"""
        params = self.params
        ma_period = min(params['ma_period'], len(history))
        
        # 计算均线
        prices = [h['price'] for h in history[-ma_period:]]
        ma = sum(prices) / len(prices)
        
        # 计算偏离度
        deviation = (current_price - ma) / ma
        
        position = self.trader.position
        
        signal = 'hold'
        reason = f'均线: {ma:.2f}, 偏离: {deviation*100:.2f}%'
        
        # 突破买入
        if deviation > params['buy_threshold']:
            if position == 0 and self.trader.balance > current_price * params['position_size']:
                signal = 'buy'
                reason = f'价格突破均线{params["buy_threshold"]*100:.1f}%，建议买入'
        
        # 跌破卖出
        elif deviation < params['sell_threshold']:
            if position > 0:
                signal = 'sell'
                reason = f'价格跌破均线{abs(params["sell_threshold"])*100:.1f}%，建议卖出'
        
        return {
            'signal': signal,
            'reason': reason,
            'current_price': current_price,
            'ma': ma,
            'deviation': deviation,
            'position': position
        }
    
    def _analyze_dca(self, current_price: float) -> Dict:
        """定投策略分析"""
        params = self.params
        last_date = params.get('last_trade_date')
        today = datetime.now().date()
        
        signal = 'hold'
        reason = '未到定投时间'
        
        if last_date is None:
            signal = 'buy'
            reason = '首次定投'
        else:
            days_since = (today - datetime.fromisoformat(last_date).date()).days
            if days_since >= params['interval_days']:
                signal = 'buy'
                reason = f'距离上次定投已{days_since}天，建议定投'
        
        return {
            'signal': signal,
            'reason': reason,
            'current_price': current_price,
            'amount': params['amount_per_trade']
        }
    
    def execute(self, analysis: Dict) -> bool:
        """
        执行交易信号
        
        Args:
            analysis: analyze()返回的分析结果
        
        Returns:
            是否执行成功
        """
        signal = analysis.get('signal', 'hold')
        
        if signal == 'buy':
            if self.strategy_type == 'dca':
                amount = analysis.get('amount', 1000)
                grams = amount / analysis['current_price']
                return self.trader.buy(round(grams, 2))
            else:
                return self.trader.buy(self.params.get('min_trade', 1.0))
        
        elif signal == 'sell':
            return self.trader.sell(self.params.get('min_trade', 1.0))
        
        return False
    
    def run(self, price_history: List[Dict], auto_execute: bool = False) -> Dict:
        """
        运行策略
        
        Args:
            price_history: 价格历史
            auto_execute: 是否自动执行交易
        
        Returns:
            分析结果和执行状态
        """
        analysis = self.analyze(price_history)
        executed = False
        
        if auto_execute and analysis['signal'] in ['buy', 'sell']:
            executed = self.execute(analysis)
        
        # 记录信号
        self.signals.append({
            'time': datetime.now().isoformat(),
            'signal': analysis['signal'],
            'reason': analysis['reason'],
            'executed': executed
        })
        
        return {
            **analysis,
            'auto_executed': executed,
            'strategy': self.strategy_type
        }


if __name__ == "__main__":
    print("积存金策略测试")
    print("=" * 60)
    
    from jijin_trader import JijinTrader, find_working_proxy
    
    proxy = find_working_proxy()
    trader = JijinTrader(bank='zheshang', initial_balance=100000, proxy=proxy)
    
    # 模拟价格历史
    base_price = trader.get_price() or 990.0
    price_history = []
    import random
    
    for i in range(30):
        price = base_price * (1 + random.uniform(-0.01, 0.01))
        price_history.append({
            'timestamp': datetime.now().isoformat(),
            'price': price
        })
    
    print(f"\n当前价格: {price_history[-1]['price']:.2f}元/克")
    print(f"持仓: {trader.position:.2f}克")
    print(f"余额: {trader.balance:.2f}元")
    
    # 测试网格策略
    print("\n" + "-" * 40)
    print("网格策略分析:")
    strategy_grid = JijinStrategy(trader, 'grid')
    result = strategy_grid.run(price_history, auto_execute=False)
    print(f"  信号: {result['signal']}")
    print(f"  原因: {result['reason']}")
    if 'grid_low' in result:
        print(f"  网格范围: {result['grid_low']:.2f} - {result['grid_high']:.2f}")
    
    # 测试趋势策略
    print("\n" + "-" * 40)
    print("趋势策略分析:")
    strategy_trend = JijinStrategy(trader, 'trend')
    result = strategy_trend.run(price_history, auto_execute=False)
    print(f"  信号: {result['signal']}")
    print(f"  原因: {result['reason']}")
    if 'ma' in result:
        print(f"  均线: {result['ma']:.2f}, 偏离: {result['deviation']*100:.2f}%")
    
    # 测试定投策略
    print("\n" + "-" * 40)
    print("定投策略分析:")
    strategy_dca = JijinStrategy(trader, 'dca')
    result = strategy_dca.run(price_history, auto_execute=False)
    print(f"  信号: {result['signal']}")
    print(f"  原因: {result['reason']}")
    if 'amount' in result:
        print(f"  定投金额: {result['amount']}元")
