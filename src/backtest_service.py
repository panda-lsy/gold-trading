#!/usr/bin/env python3
"""
策略回测服务
支持网格策略、趋势策略、定投策略的回测
"""
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import random


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    start_date: str
    end_date: str
    initial_balance: float
    final_balance: float
    final_position: float
    total_trades: int
    total_fees: float
    total_profit: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[Dict]
    daily_returns: List[Dict]


class BacktestService:
    """策略回测服务"""
    
    def __init__(self):
        self.trades = []
        self.daily_data = []
    
    def generate_mock_data(self, days: int = 90, start_price: float = 1000.0) -> List[Dict]:
        """生成模拟价格数据"""
        data = []
        price = start_price
        
        now = datetime.now()
        
        for i in range(days):
            date = now - timedelta(days=days - i)
            
            # 模拟日内波动
            daily_change = random.uniform(-0.02, 0.02)  # ±2%
            price = price * (1 + daily_change)
            
            # 生成 4 个时间点的价格（开盘、盘中、收盘）
            for hour in [9, 12, 15, 22]:
                point_time = date.replace(hour=hour, minute=0)
                
                # 小幅随机波动
                point_price = price * (1 + random.uniform(-0.005, 0.005))
                
                data.append({
                    'datetime': point_time.isoformat(),
                    'timestamp': int(point_time.timestamp() * 1000),
                    'price': round(point_price, 2),
                    'volume': random.uniform(1000, 5000)
                })
        
        return data
    
    def backtest_grid_strategy(
        self,
        price_data: List[Dict],
        initial_balance: float = 100000,
        grid_size: float = 5.0,  # 网格间距（元）
        grid_levels: int = 10,   # 网格层数
        trade_amount: float = 1.0  # 每次交易量（克）
    ) -> BacktestResult:
        """
        回测网格策略
        
        在价格区间内设置多个买入/卖出网格
        """
        if not price_data:
            raise ValueError("No price data provided")
        
        balance = initial_balance
        position = 0.0
        avg_price = 0.0
        trades = []
        daily_returns = []
        
        # 计算价格区间
        prices = [p['price'] for p in price_data]
        mid_price = sum(prices) / len(prices)
        
        # 设置网格
        grids = []
        for i in range(grid_levels):
            buy_price = mid_price - (i + 1) * grid_size
            sell_price = mid_price + (i + 1) * grid_size
            grids.append({
                'level': i + 1,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'buy_triggered': False,
                'sell_triggered': False
            })
        
        total_fees = 0
        max_balance = initial_balance
        min_balance = initial_balance
        
        for i, point in enumerate(price_data):
            current_price = point['price']
            current_time = point['datetime']
            
            # 检查每个网格
            for grid in grids:
                # 买入条件：价格低于买入网格且未触发
                if current_price <= grid['buy_price'] and not grid['buy_triggered']:
                    if balance >= current_price * trade_amount:
                        cost = current_price * trade_amount
                        balance -= cost
                        
                        if position > 0:
                            total_cost = position * avg_price + cost
                            position += trade_amount
                            avg_price = total_cost / position
                        else:
                            position = trade_amount
                            avg_price = current_price
                        
                        trades.append({
                            'time': current_time,
                            'action': 'BUY',
                            'price': current_price,
                            'grams': trade_amount,
                            'cost': cost,
                            'fee': 0,
                            'balance': balance,
                            'position': position
                        })
                        
                        grid['buy_triggered'] = True
                        grid['sell_triggered'] = False
                
                # 卖出条件：价格高于卖出网格且有持仓
                elif current_price >= grid['sell_price'] and position > 0 and not grid['sell_triggered']:
                    sell_grams = min(trade_amount, position)
                    gross = current_price * sell_grams
                    fee = gross * 0.004  # 0.4% 手续费
                    net = gross - fee
                    
                    profit = net - (sell_grams * avg_price)
                    
                    balance += net
                    position -= sell_grams
                    total_fees += fee
                    
                    trades.append({
                        'time': current_time,
                        'action': 'SELL',
                        'price': current_price,
                        'grams': sell_grams,
                        'gross': gross,
                        'fee': fee,
                        'net': net,
                        'profit': profit,
                        'balance': balance,
                        'position': position
                    })
                    
                    grid['sell_triggered'] = True
                    grid['buy_triggered'] = False
            
            # 计算每日收益
            if i % 4 == 0:  # 每天记录一次
                position_value = position * current_price
                total_value = balance + position_value
                daily_returns.append({
                    'date': current_time[:10],
                    'total_value': round(total_value, 2),
                    'balance': round(balance, 2),
                    'position_value': round(position_value, 2)
                })
            
            # 更新最大/最小余额
            total_value = balance + position * current_price
            max_balance = max(max_balance, total_value)
            min_balance = min(min_balance, total_value)
        
        # 计算最终收益
        final_price = price_data[-1]['price']
        final_position_value = position * final_price
        final_total = balance + final_position_value
        
        total_profit = final_total - initial_balance
        max_drawdown = (max_balance - min_balance) / max_balance * 100 if max_balance > 0 else 0
        
        # 计算夏普比率（简化版）
        if len(daily_returns) > 1:
            returns = [(daily_returns[i]['total_value'] - daily_returns[i-1]['total_value']) 
                      / daily_returns[i-1]['total_value'] * 100 
                      for i in range(1, len(daily_returns))]
            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5
            sharpe_ratio = avg_return / std_dev if std_dev > 0 else 0
        else:
            sharpe_ratio = 0
        
        return BacktestResult(
            strategy_name='网格策略',
            start_date=price_data[0]['datetime'][:10],
            end_date=price_data[-1]['datetime'][:10],
            initial_balance=initial_balance,
            final_balance=balance,
            final_position=position,
            total_trades=len(trades),
            total_fees=total_fees,
            total_profit=total_profit,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            trades=trades,
            daily_returns=daily_returns
        )
    
    def backtest_trend_strategy(
        self,
        price_data: List[Dict],
        initial_balance: float = 100000,
        ma_short: int = 5,   # 短期均线
        ma_long: int = 20,   # 长期均线
        trade_amount: float = 5.0
    ) -> BacktestResult:
        """
        回测趋势策略（均线突破）
        
        短期均线上穿长期均线买入，下穿卖出
        """
        if len(price_data) < ma_long:
            raise ValueError("Insufficient price data")
        
        balance = initial_balance
        position = 0.0
        avg_price = 0.0
        trades = []
        daily_returns = []
        total_fees = 0
        
        prices = [p['price'] for p in price_data]
        max_balance = initial_balance
        min_balance = initial_balance
        
        for i in range(ma_long, len(price_data)):
            current_price = price_data[i]['price']
            current_time = price_data[i]['datetime']
            
            # 计算均线
            ma_s = sum(prices[i-ma_short:i]) / ma_short
            ma_l = sum(prices[i-ma_long:i]) / ma_long
            
            # 前一天的均线
            prev_ma_s = sum(prices[i-ma_short-1:i-1]) / ma_short
            prev_ma_l = sum(prices[i-ma_long-1:i-1]) / ma_long
            
            # 金叉买入
            if prev_ma_s <= prev_ma_l and ma_s > ma_l:
                if balance >= current_price * trade_amount:
                    cost = current_price * trade_amount
                    balance -= cost
                    
                    if position > 0:
                        total_cost = position * avg_price + cost
                        position += trade_amount
                        avg_price = total_cost / position
                    else:
                        position = trade_amount
                        avg_price = current_price
                    
                    trades.append({
                        'time': current_time,
                        'action': 'BUY',
                        'price': current_price,
                        'grams': trade_amount,
                        'cost': cost,
                        'ma_short': ma_s,
                        'ma_long': ma_l,
                        'signal': 'golden_cross'
                    })
            
            # 死叉卖出
            elif prev_ma_s >= prev_ma_l and ma_s < ma_l and position > 0:
                sell_grams = min(trade_amount, position)
                gross = current_price * sell_grams
                fee = gross * 0.004
                net = gross - fee
                profit = net - (sell_grams * avg_price)
                
                balance += net
                position -= sell_grams
                total_fees += fee
                
                trades.append({
                    'time': current_time,
                    'action': 'SELL',
                    'price': current_price,
                    'grams': sell_grams,
                    'gross': gross,
                    'fee': fee,
                    'profit': profit,
                    'ma_short': ma_s,
                    'ma_long': ma_l,
                    'signal': 'death_cross'
                })
            
            # 记录每日收益
            if i % 4 == 0:
                position_value = position * current_price
                total_value = balance + position_value
                daily_returns.append({
                    'date': current_time[:10],
                    'total_value': round(total_value, 2),
                    'balance': round(balance, 2),
                    'position_value': round(position_value, 2)
                })
            
            total_value = balance + position * current_price
            max_balance = max(max_balance, total_value)
            min_balance = min(min_balance, total_value)
        
        final_price = price_data[-1]['price']
        final_total = balance + position * final_price
        total_profit = final_total - initial_balance
        max_drawdown = (max_balance - min_balance) / max_balance * 100 if max_balance > 0 else 0
        
        return BacktestResult(
            strategy_name='趋势策略(MA)',
            start_date=price_data[0]['datetime'][:10],
            end_date=price_data[-1]['datetime'][:10],
            initial_balance=initial_balance,
            final_balance=balance,
            final_position=position,
            total_trades=len(trades),
            total_fees=total_fees,
            total_profit=total_profit,
            max_drawdown=max_drawdown,
            sharpe_ratio=0,
            trades=trades,
            daily_returns=daily_returns
        )
    
    def backtest_dca_strategy(
        self,
        price_data: List[Dict],
        initial_balance: float = 100000,
        daily_investment: float = 1000,  # 每日定投金额
        invest_days: int = 3  # 每几天投一次
    ) -> BacktestResult:
        """
        回测定投策略
        
        定期定额投资
        """
        balance = initial_balance
        position = 0.0
        avg_price = 0.0
        trades = []
        daily_returns = []
        total_invested = 0
        
        max_balance = initial_balance
        min_balance = initial_balance
        
        for i, point in enumerate(price_data):
            current_price = point['price']
            current_time = point['datetime']
            
            # 定投逻辑
            if i % (4 * invest_days) == 0 and balance >= daily_investment:  # 每 invest_days 天
                grams = daily_investment / current_price
                cost = daily_investment
                balance -= cost
                total_invested += cost
                
                if position > 0:
                    total_cost = position * avg_price + cost
                    position += grams
                    avg_price = total_cost / position
                else:
                    position = grams
                    avg_price = current_price
                
                trades.append({
                    'time': current_time,
                    'action': 'BUY',
                    'price': current_price,
                    'grams': grams,
                    'cost': cost,
                    'balance': balance,
                    'position': position
                })
            
            # 记录每日收益
            if i % 4 == 0:
                position_value = position * current_price
                total_value = balance + position_value
                daily_returns.append({
                    'date': current_time[:10],
                    'total_value': round(total_value, 2),
                    'balance': round(balance, 2),
                    'position_value': round(position_value, 2),
                    'invested': total_invested
                })
            
            total_value = balance + position * current_price
            max_balance = max(max_balance, total_value)
            min_balance = min(min_balance, total_value)
        
        final_price = price_data[-1]['price']
        final_total = balance + position * final_price
        total_profit = final_total - initial_balance
        max_drawdown = (max_balance - min_balance) / max_balance * 100 if max_balance > 0 else 0
        
        return BacktestResult(
            strategy_name='定投策略',
            start_date=price_data[0]['datetime'][:10],
            end_date=price_data[-1]['datetime'][:10],
            initial_balance=initial_balance,
            final_balance=balance,
            final_position=position,
            total_trades=len(trades),
            total_fees=0,
            total_profit=total_profit,
            max_drawdown=max_drawdown,
            sharpe_ratio=0,
            trades=trades,
            daily_returns=daily_returns
        )
    
    def compare_strategies(self, price_data: List[Dict], initial_balance: float = 100000) -> Dict:
        """对比所有策略"""
        results = {}
        
        # 网格策略
        try:
            grid_result = self.backtest_grid_strategy(price_data, initial_balance)
            results['grid'] = {
                'name': grid_result.strategy_name,
                'total_profit': round(grid_result.total_profit, 2),
                'total_trades': grid_result.total_trades,
                'max_drawdown': round(grid_result.max_drawdown, 2),
                'final_value': round(grid_result.final_balance + grid_result.final_position * price_data[-1]['price'], 2),
                'return_rate': round(grid_result.total_profit / initial_balance * 100, 2)
            }
        except Exception as e:
            results['grid'] = {'error': str(e)}
        
        # 趋势策略
        try:
            trend_result = self.backtest_trend_strategy(price_data, initial_balance)
            results['trend'] = {
                'name': trend_result.strategy_name,
                'total_profit': round(trend_result.total_profit, 2),
                'total_trades': trend_result.total_trades,
                'max_drawdown': round(trend_result.max_drawdown, 2),
                'final_value': round(trend_result.final_balance + trend_result.final_position * price_data[-1]['price'], 2),
                'return_rate': round(trend_result.total_profit / initial_balance * 100, 2)
            }
        except Exception as e:
            results['trend'] = {'error': str(e)}
        
        # 定投策略
        try:
            dca_result = self.backtest_dca_strategy(price_data, initial_balance)
            results['dca'] = {
                'name': dca_result.strategy_name,
                'total_profit': round(dca_result.total_profit, 2),
                'total_trades': dca_result.total_trades,
                'max_drawdown': round(dca_result.max_drawdown, 2),
                'final_value': round(dca_result.final_balance + dca_result.final_position * price_data[-1]['price'], 2),
                'return_rate': round(dca_result.total_profit / initial_balance * 100, 2)
            }
        except Exception as e:
            results['dca'] = {'error': str(e)}
        
        # 基准（买入持有）
        start_price = price_data[0]['price']
        end_price = price_data[-1]['price']
        hold_return = (end_price - start_price) / start_price * initial_balance
        
        results['buy_and_hold'] = {
            'name': '买入持有',
            'total_profit': round(hold_return, 2),
            'total_trades': 1,
            'max_drawdown': 0,
            'final_value': round(initial_balance + hold_return, 2),
            'return_rate': round((end_price - start_price) / start_price * 100, 2)
        }
        
        return results


if __name__ == "__main__":
    service = BacktestService()
    
    print("策略回测服务")
    print("=" * 60)
    
    # 生成模拟数据
    print("\n生成模拟数据 (90 天)...")
    price_data = service.generate_mock_data(days=90)
    print(f"✓ 生成了 {len(price_data)} 条价格数据")
    print(f"  起始价格: {price_data[0]['price']:.2f}")
    print(f"  结束价格: {price_data[-1]['price']:.2f}")
    
    # 对比策略
    print("\n\n策略对比:")
    print("-" * 60)
    comparison = service.compare_strategies(price_data)
    
    for strategy, result in comparison.items():
        if 'error' in result:
            print(f"{strategy}: 错误 - {result['error']}")
        else:
            print(f"\n{result['name']}:")
            print(f"  总收益: {result['total_profit']:+.2f} 元")
            print(f"  收益率: {result['return_rate']:+.2f}%")
            print(f"  交易次数: {result['total_trades']}")
            print(f"  最大回撤: {result['max_drawdown']:.2f}%")
            print(f"  最终资产: {result['final_value']:.2f} 元")
