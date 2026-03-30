#!/usr/bin/env python3
"""
黄金ETF 518850 实盘交易接口
"""
import os
import sys
from datetime import datetime, time as dt_time
from typing import Dict, Optional

# Add parent path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from price_feed import GoldPriceFeed


class GoldETFTrader:
    """黄金ETF华夏 (518850) 交易接口"""
    
    CODE = "518850"
    NAME = "黄金ETF华夏"
    
    MORNING_START = dt_time(9, 30)
    MORNING_END = dt_time(11, 30)
    AFTERNOON_START = dt_time(13, 0)
    AFTERNOON_END = dt_time(15, 0)
    
    def __init__(self, trader_backend=None):
        self.backend = trader_backend
        self.min_amount = 100
        self.mock_mode = trader_backend is None
        
        # 模拟持仓
        self.mock_position = 0
        self.mock_cash = 100000
        
        # 价格数据源
        self.price_feed = GoldPriceFeed()
        
    def is_trading_time(self) -> bool:
        """检查是否在交易时间"""
        now = datetime.now().time()
        weekday = datetime.now().weekday()
        
        if weekday >= 5:
            return False
        
        if self.MORNING_START <= now <= self.MORNING_END:
            return True
        
        if self.AFTERNOON_START <= now <= self.AFTERNOON_END:
            return True
        
        return False
    
    def get_price(self) -> Optional[float]:
        """获取实时价格"""
        return self.price_feed.get_etf_price(self.CODE)
    
    def buy(self, price: float, amount: int = 100) -> bool:
        """买入"""
        if not self.is_trading_time():
            print("非交易时间，无法买入")
            return False
        
        amount = (amount // 100) * 100
        if amount < self.min_amount:
            print(f"买入数量不足{self.min_amount}股")
            return False
        
        cost = price * amount
        
        if self.mock_mode:
            if cost > self.mock_cash:
                print(f"模拟资金不足: 需要{cost:.2f}, 剩余{self.mock_cash:.2f}")
                return False
            self.mock_cash -= cost
            self.mock_position += amount
            print(f"[模拟] 买入 {self.NAME}({self.CODE}): {amount}股 @ {price:.3f}, 成本{cost:.2f}")
            return True
        
        try:
            result = self.backend.buy(self.CODE, price, amount)
            print(f"买入 {self.NAME}({self.CODE}): {amount}股 @ {price:.3f}")
            return result
        except Exception as e:
            print(f"买入失败: {e}")
            return False
    
    def sell(self, price: float, amount: int = 100) -> bool:
        """卖出"""
        if not self.is_trading_time():
            print("非交易时间，无法卖出")
            return False
        
        amount = (amount // 100) * 100
        if amount < self.min_amount:
            return False
        
        if self.mock_mode:
            if amount > self.mock_position:
                print(f"模拟持仓不足: 需要{amount}, 拥有{self.mock_position}")
                return False
            proceeds = price * amount
            self.mock_cash += proceeds
            self.mock_position -= amount
            print(f"[模拟] 卖出 {self.NAME}({self.CODE}): {amount}股 @ {price:.3f}, 收入{proceeds:.2f}")
            return True
        
        try:
            result = self.backend.sell(self.CODE, price, amount)
            print(f"卖出 {self.NAME}({self.CODE}): {amount}股 @ {price:.3f}")
            return result
        except Exception as e:
            print(f"卖出失败: {e}")
            return False
    
    def get_position(self) -> Dict:
        """获取持仓"""
        if self.mock_mode:
            return {
                'code': self.CODE,
                'name': self.NAME,
                'volume': self.mock_position,
                'available': self.mock_position
            }
        
        try:
            positions = self.backend.get_positions()
            for pos in positions:
                if pos['code'] == self.CODE or pos['code'] == f"{self.CODE}.SH":
                    return pos
            return {'code': self.CODE, 'name': self.NAME, 'volume': 0, 'available': 0}
        except Exception as e:
            print(f"获取持仓失败: {e}")
            return {'code': self.CODE, 'name': self.NAME, 'volume': 0, 'available': 0}
    
    def get_balance(self) -> Dict:
        """获取资金"""
        if self.mock_mode:
            price = self.get_price() or 5.0
            return {
                'cash': self.mock_cash,
                'market_value': self.mock_position * price,
                'total': self.mock_cash + self.mock_position * price
            }
        
        try:
            return self.backend.get_balance()
        except:
            return {'cash': 0, 'market_value': 0, 'total': 0}
    
    def close_all(self) -> bool:
        """收盘前清仓"""
        position = self.get_position()
        volume = position.get('available', 0)
        
        if volume > 0:
            price = self.get_price()
            if price:
                return self.sell(price, volume)
        
        return True
    
    def get_status(self) -> Dict:
        """获取完整状态"""
        price = self.get_price()
        position = self.get_position()
        balance = self.get_balance()
        
        return {
            'code': self.CODE,
            'name': self.NAME,
            'price': price,
            'position': position,
            'balance': balance,
            'is_trading_time': self.is_trading_time()
        }


if __name__ == "__main__":
    print("测试黄金ETF交易接口")
    print("=" * 50)
    
    trader = GoldETFTrader()
    
    # 获取状态
    status = trader.get_status()
    print(f"\n当前价格: {status['price']:.3f} CNY")
    print(f"持仓: {status['position']['volume']}股")
    print(f"现金: {status['balance']['cash']:.2f}")
    print(f"总市值: {status['balance']['total']:.2f}")
    print(f"交易时间: {'是' if status['is_trading_time'] else '否'}")
    
    # 模拟买入
    if status['price']:
        print("\n模拟买入测试:")
        trader.buy(status['price'], 100)
        
        # 查看新状态
        new_status = trader.get_status()
        print(f"\n买入后:")
        print(f"持仓: {new_status['position']['volume']}股")
        print(f"现金: {new_status['balance']['cash']:.2f}")
