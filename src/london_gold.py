#!/usr/bin/env python3
"""
伦敦金 XAUUSD 模拟交易
使用网络数据 + 本地缓存
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

# 导入价格获取器
try:
    from .london_price import LondonGoldPrice, find_working_proxy
except ImportError:
    from london_price import LondonGoldPrice, find_working_proxy


class LondonGoldSimulator:
    """
    伦敦金 (XAUUSD) 模拟交易
    
    特点:
    - 24小时交易 (周一6:00 - 周六4:00)
    - 优先使用网络价格，失败使用本地数据
    - 自动检测代理
    """
    
    SYMBOL = "XAUUSD"
    NAME = "伦敦金/美元"
    
    def __init__(self, initial_balance: float = 100000, proxy: str = None):
        self.balance = initial_balance
        self.position = 0
        self.avg_price = 0
        self.trades = []
        
        # 数据目录
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # 初始化价格获取器
        if proxy is None:
            proxy = find_working_proxy()
        
        self.price_feed = LondonGoldPrice(proxy=proxy, data_dir=data_dir)
        
        # 加载交易状态
        self.state_file = os.path.join(data_dir, 'london_gold_state.json')
        self.load_state()
        
    def is_trading_time(self) -> bool:
        """检查是否在交易时间"""
        now = datetime.utcnow()
        weekday = now.weekday()
        hour = now.hour
        
        # 周六4:00后 - 周一6:00前 休市
        if weekday == 5 and hour >= 4:
            return False
        if weekday == 6:
            return False
        if weekday == 0 and hour < 6:
            return False
        
        return True
    
    def get_price(self) -> Optional[float]:
        """获取当前价格"""
        return self.price_feed.get_price()
    
    def get_quote(self) -> Dict:
        """获取完整行情"""
        return self.price_feed.get_full_quote()
    
    def buy(self, ounces: float = 1.0) -> bool:
        """买入（做多）"""
        if not self.is_trading_time():
            print("⚠ 当前非交易时间")
            return False
        
        price = self.get_price()
        if not price:
            print("无法获取价格")
            return False
        
        cost = price * ounces
        spread = cost * 0.0005  # 0.05% 点差
        total_cost = cost + spread
        
        if total_cost > self.balance:
            print(f"资金不足: 需要${total_cost:.2f}, 剩余${self.balance:.2f}")
            return False
        
        # 更新持仓
        if self.position > 0:
            total_oz = self.position + ounces
            total_cost_basis = self.position * self.avg_price + ounces * price
            self.avg_price = total_cost_basis / total_oz
            self.position = total_oz
        else:
            self.position = ounces
            self.avg_price = price
        
        self.balance -= total_cost
        
        self.trades.append({
            'time': datetime.now().isoformat(),
            'action': 'BUY',
            'price': price,
            'ounces': ounces,
            'cost': total_cost
        })
        
        print(f"[买入] {ounces}盎司 @ ${price:.2f}, 成本${total_cost:.2f}")
        self.save_state()
        return True
    
    def sell(self, ounces: float = None) -> bool:
        """卖出（平仓）"""
        if not self.is_trading_time():
            print("⚠ 当前非交易时间")
            return False
        
        if self.position <= 0:
            print("没有持仓")
            return False
        
        price = self.get_price()
        if not price:
            return False
        
        if ounces is None or ounces >= self.position:
            ounces = self.position
        
        proceeds = price * ounces
        spread = proceeds * 0.0005
        total_proceeds = proceeds - spread
        profit = (price - self.avg_price) * ounces - spread
        
        self.balance += total_proceeds
        self.position -= ounces
        
        if self.position <= 0:
            self.avg_price = 0
        
        self.trades.append({
            'time': datetime.now().isoformat(),
            'action': 'SELL',
            'price': price,
            'ounces': ounces,
            'proceeds': total_proceeds,
            'profit': profit
        })
        
        print(f"[卖出] {ounces}盎司 @ ${price:.2f}, 盈亏${profit:.2f}")
        self.save_state()
        return True
    
    def get_summary(self) -> Dict:
        """获取账户摘要"""
        price = self.get_price()
        position_value = self.position * price if price else 0
        unrealized = (price - self.avg_price) * self.position if price and self.position > 0 else 0
        realized = sum(t.get('profit', 0) for t in self.trades if t['action'] == 'SELL')
        
        return {
            'symbol': self.SYMBOL,
            'balance': round(self.balance, 2),
            'position': round(self.position, 2),
            'avg_price': round(self.avg_price, 2),
            'current_price': round(price, 2) if price else None,
            'position_value': round(position_value, 2),
            'unrealized_pnl': round(unrealized, 2),
            'realized_pnl': round(realized, 2),
            'total_value': round(self.balance + position_value, 2),
            'trade_count': len(self.trades),
            'is_trading_time': self.is_trading_time()
        }
    
    def save_state(self):
        """保存交易状态"""
        state = {
            'balance': self.balance,
            'position': self.position,
            'avg_price': self.avg_price,
            'trades': self.trades,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self):
        """加载交易状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                self.balance = state.get('balance', 100000)
                self.position = state.get('position', 0)
                self.avg_price = state.get('avg_price', 0)
                self.trades = state.get('trades', [])
                
                print(f"✓ 已加载交易状态: 余额${self.balance:.2f}, 持仓{self.position:.2f}盎司")
                return True
            except Exception as e:
                print(f"加载状态失败: {e}")
        
        return False


if __name__ == "__main__":
    print("伦敦金模拟交易")
    print("=" * 60)
    
    sim = LondonGoldSimulator(initial_balance=100000)
    
    print(f"\n当前行情:")
    quote = sim.get_quote()
    print(f"  价格: ${quote['price']:.2f}")
    print(f"  来源: {quote['source']}")
    print(f"  交易时间: {'是' if sim.is_trading_time() else '否'}")
    
    print("\n模拟买入1盎司:")
    sim.buy(1.0)
    
    print("\n当前状态:")
    summary = sim.get_summary()
    print(f"  余额: ${summary['balance']:.2f}")
    print(f"  持仓: {summary['position']:.2f}盎司")
    print(f"  均价: ${summary['avg_price']:.2f}")
    print(f"  当前价: ${summary['current_price']:.2f}")
    print(f"  浮动盈亏: ${summary['unrealized_pnl']:.2f}")
    
    print("\n模拟卖出0.5盎司:")
    sim.sell(0.5)
    
    print("\n最终状态:")
    summary = sim.get_summary()
    print(f"  余额: ${summary['balance']:.2f}")
    print(f"  持仓: {summary['position']:.2f}盎司")
    print(f"  已实现盈亏: ${summary['realized_pnl']:.2f}")
    print(f"  总交易次数: {summary['trade_count']}")
