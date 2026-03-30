#!/usr/bin/env python3
"""
国内黄金积存金交易 - 浙商银行 & 民生银行
"""
import json
import os
import requests
from typing import Optional, Dict, List
from datetime import datetime
from json_store import load_json_file, save_json_file
from sqlite_store import SQLiteStore


class JijinPriceFeed:
    """积存金价格获取器"""
    
    ZHESHANG_API = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice"
    MINSHENG_API = "https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice"
    
    def __init__(self, proxy: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
            'Accept': 'application/json',
            'Origin': 'https://www.jdjygold.com',
            'Referer': 'https://www.jdjygold.com/'
        })
        
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
        
        self.last_prices = {}
    
    def fetch_zheshang(self) -> Optional[Dict]:
        """获取浙商积存金价格"""
        try:
            resp = self.session.get(
                self.ZHESHANG_API,
                params={'productSku': '1961543816'},
                timeout=10
            )
            data = resp.json()
            
            if data.get('success') and data.get('resultData', {}).get('datas'):
                d = data['resultData']['datas']
                return {
                    'bank': 'zheshang',
                    'name': '浙商积存金',
                    'price': float(d['price']),
                    'yesterday_price': float(d['yesterdayPrice']),
                    'change_amt': d['upAndDownAmt'],
                    'change_rate': d['upAndDownRate'],
                    'datetime': datetime.fromtimestamp(int(d['time']) / 1000).isoformat()
                }
            return None
        except Exception as e:
            print(f"浙商价格获取失败: {e}")
            return None
    
    def fetch_minsheng(self) -> Optional[Dict]:
        """获取民生积存金价格"""
        try:
            resp = self.session.get(
                self.MINSHENG_API,
                params={'productSku': 'P005'},
                timeout=10
            )
            data = resp.json()
            
            if data.get('success') and data.get('resultData', {}).get('datas'):
                d = data['resultData']['datas']
                return {
                    'bank': 'minsheng',
                    'name': '民生积存金',
                    'price': float(d['price']),
                    'yesterday_price': float(d['yesterdayPrice']),
                    'change_amt': d['upAndDownAmt'],
                    'change_rate': d['upAndDownRate'],
                    'datetime': datetime.fromtimestamp(int(d['time']) / 1000).isoformat()
                }
            return None
        except Exception as e:
            print(f"民生价格获取失败: {e}")
            return None
    
    def get_all_prices(self) -> Dict[str, Dict]:
        """获取所有银行价格"""
        prices = {}
        
        zheshang = self.fetch_zheshang()
        if zheshang:
            prices['zheshang'] = zheshang
            self.last_prices['zheshang'] = zheshang
        
        minsheng = self.fetch_minsheng()
        if minsheng:
            prices['minsheng'] = minsheng
            self.last_prices['minsheng'] = minsheng
        
        return prices
    
    def get_price(self, bank: str = 'zheshang') -> Optional[Dict]:
        """获取指定银行价格"""
        prices = self.get_all_prices()
        return prices.get(bank) or self.last_prices.get(bank)


class JijinTrader:
    """积存金交易模拟器"""
    
    TRADE_START_HOUR = 9
    TRADE_END_HOUR = 22
    SELL_FEE_RATE = 0.004  # 0.4%
    
    def __init__(self, bank: str = 'zheshang', initial_balance: float = 100000, proxy: str = None):
        self.bank = bank
        self.balance = initial_balance
        self.position = 0.0
        self.avg_price = 0.0
        self.trades = []
        
        self.price_feed = JijinPriceFeed(proxy=proxy)
        
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        self.sqlite_store = SQLiteStore(data_dir=data_dir)
        self.state_file = os.path.join(data_dir, f'jijin_{bank}_state.json')
        self.load_state()
    
    def is_trading_time(self) -> bool:
        """检查是否在交易时间"""
        now = datetime.now()
        weekday = now.weekday()  # 0=周一, 5=周六, 6=周日
        hour = now.hour
        minute = now.minute
        
        if self.bank == 'zheshang':
            # 浙商: 周一 9:00 - 周六 2:00
            if weekday == 0 and hour < 9:
                return False  # 周一 9点前
            if weekday == 5 and hour >= 2:
                return False  # 周六 2点后
            if weekday == 6:
                return False  # 周日全天
            return True
        else:
            # 民生: 周一-周六 9:10-02:30
            if weekday == 6:
                return False  # 周日全天休市
            
            current_minutes = hour * 60 + minute
            start_minutes = 9 * 60 + 10  # 9:10
            end_minutes = 2 * 60 + 30    # 2:30
            
            # 周六的特殊处理：周六只有凌晨 0:00-2:30 交易
            if weekday == 5:
                return current_minutes <= end_minutes
            
            # 周一到周五：9:10 - 次日 2:30
            if current_minutes >= start_minutes:
                return True
            if current_minutes <= end_minutes:
                return True
            
            return False
    
    def get_price(self) -> Optional[float]:
        """获取当前价格"""
        quote = self.price_feed.get_price(self.bank)
        if quote:
            return quote['price']
        return None
    
    def get_quote(self) -> Optional[Dict]:
        """获取完整行情"""
        return self.price_feed.get_price(self.bank)
    
    def buy(self, grams: float = 1.0) -> bool:
        """买入积存金"""
        if not self.is_trading_time():
            print(f"⚠ 非交易时间 ({self.TRADE_START_HOUR}:00-{self.TRADE_END_HOUR}:00)")
            return False
        
        quote = self.get_quote()
        if not quote:
            print("无法获取价格")
            return False
        
        price = quote['price']
        cost = price * grams
        
        if cost > self.balance:
            print(f"资金不足: 需要{cost:.2f}元, 剩余{self.balance:.2f}元")
            return False
        
        if self.position > 0:
            total_grams = self.position + grams
            total_cost = self.position * self.avg_price + grams * price
            self.avg_price = total_cost / total_grams
            self.position = total_grams
        else:
            self.position = grams
            self.avg_price = price
        
        self.balance -= cost
        
        self.trades.append({
            'time': datetime.now().isoformat(),
            'action': 'BUY',
            'bank': self.bank,
            'price': price,
            'grams': grams,
            'cost': cost,
            'fee': 0
        })
        
        print(f"[买入] {quote['name']}: {grams}克 @ {price:.2f}元/克, 成本{cost:.2f}元")
        self.save_state()
        return True
    
    def sell(self, grams: float = None) -> bool:
        """卖出积存金（含0.4%手续费）"""
        if not self.is_trading_time():
            print(f"⚠ 非交易时间 ({self.TRADE_START_HOUR}:00-{self.TRADE_END_HOUR}:00)")
            return False
        
        if self.position <= 0:
            print("没有持仓")
            return False
        
        quote = self.get_quote()
        if not quote:
            print("无法获取价格")
            return False
        
        price = quote['price']
        
        if grams is None or grams >= self.position:
            grams = self.position
        
        gross_proceeds = price * grams
        fee = gross_proceeds * self.SELL_FEE_RATE
        net_proceeds = gross_proceeds - fee
        
        cost_basis = self.avg_price * grams
        net_profit = net_proceeds - cost_basis
        
        self.balance += net_proceeds
        self.position -= grams
        
        if self.position <= 0:
            self.avg_price = 0
        
        self.trades.append({
            'time': datetime.now().isoformat(),
            'action': 'SELL',
            'bank': self.bank,
            'price': price,
            'grams': grams,
            'gross_proceeds': gross_proceeds,
            'fee': fee,
            'net_proceeds': net_proceeds,
            'profit': net_profit
        })
        
        print(f"[卖出] {quote['name']}: {grams}克 @ {price:.2f}元/克")
        print(f"       毛收入: {gross_proceeds:.2f}元, 手续费({self.SELL_FEE_RATE*100}%): {fee:.2f}元")
        print(f"       净收入: {net_proceeds:.2f}元, 净盈亏: {net_profit:.2f}元")
        
        self.save_state()
        return True
    
    def get_summary(self) -> Dict:
        """获取账户摘要"""
        price = self.get_price()
        position_value = self.position * price if price else 0
        unrealized = (price - self.avg_price) * self.position if price and self.position > 0 else 0
        realized = sum(t.get('profit', 0) for t in self.trades if t['action'] == 'SELL')
        total_fees = sum(t.get('fee', 0) for t in self.trades)
        
        return {
            'bank': self.bank,
            'balance': round(self.balance, 2),
            'position': round(self.position, 2),
            'avg_price': round(self.avg_price, 2),
            'current_price': round(price, 2) if price else None,
            'position_value': round(position_value, 2),
            'unrealized_pnl': round(unrealized, 2),
            'realized_pnl': round(realized, 2),
            'total_fees': round(total_fees, 2),
            'total_value': round(self.balance + position_value, 2),
            'trade_count': len(self.trades),
            'is_trading_time': self.is_trading_time()
        }
    
    def save_state(self):
        """保存交易状态"""
        state = {
            'bank': self.bank,
            'balance': self.balance,
            'position': self.position,
            'avg_price': self.avg_price,
            'trades': self.trades,
            'timestamp': datetime.now().isoformat()
        }
        self.sqlite_store.save_trader_state(self.bank, state)
        save_json_file(self.state_file, state, indent=2, ensure_ascii=False)
    
    def load_state(self):
        """加载交易状态"""
        try:
            state = self.sqlite_store.load_trader_state(self.bank)
            if isinstance(state, dict):
                self.balance = state.get('balance', self.balance)
                self.position = state.get('position', self.position)
                self.avg_price = state.get('avg_price', self.avg_price)
                self.trades = state.get('trades', self.trades)

                print(f"✓ 已从 SQLite 加载交易状态: 余额{self.balance:.2f}元, 持仓{self.position:.2f}克")
                return True
        except Exception as e:
            print(f"从 SQLite 加载状态失败: {e}")

        if os.path.exists(self.state_file):
            try:
                state = load_json_file(self.state_file, default={})
                if not isinstance(state, dict):
                    state = {}
                
                self.balance = state.get('balance', self.balance)
                self.position = state.get('position', self.position)
                self.avg_price = state.get('avg_price', self.avg_price)
                self.trades = state.get('trades', self.trades)

                # 首次迁移：JSON 状态回填到 SQLite
                try:
                    self.sqlite_store.save_trader_state(self.bank, {
                        'bank': self.bank,
                        'balance': self.balance,
                        'position': self.position,
                        'avg_price': self.avg_price,
                        'trades': self.trades,
                        'timestamp': state.get('timestamp', datetime.now().isoformat()),
                    })
                except Exception as db_error:
                    print(f"迁移交易状态到 SQLite 失败: {db_error}")
                
                print(f"✓ 已加载交易状态: 余额{self.balance:.2f}元, 持仓{self.position:.2f}克")
                return True
            except Exception as e:
                print(f"加载状态失败: {e}")
        return False


def find_working_proxy() -> Optional[str]:
    """查找可用代理"""
    proxies = [
        'http://127.0.0.1:7897',
        'http://127.0.0.1:7890',
        'http://127.0.0.1:1080',
    ]
    
    for proxy in proxies:
        try:
            resp = requests.get(
                'https://www.google.com',
                proxies={'http': proxy, 'https': proxy},
                timeout=5
            )
            if resp.status_code == 200:
                return proxy
        except:
            continue
    
    return None


if __name__ == "__main__":
    print("积存金交易系统测试")
    print("=" * 60)
    
    proxy = find_working_proxy()
    if proxy:
        print(f"✓ 使用代理: {proxy}")
    else:
        print("未找到代理，尝试直连...")
    
    print()
    
    # 测试浙商
    print("\n浙商积存金:")
    print("-" * 40)
    trader_zs = JijinTrader(bank='zheshang', initial_balance=100000, proxy=proxy)
    quote_zs = trader_zs.get_quote()
    if quote_zs:
        print(f"价格: {quote_zs['price']:.2f}元/克")
        print(f"涨跌: {quote_zs['change_amt']} ({quote_zs['change_rate']})")
        print(f"交易时间: {'是' if trader_zs.is_trading_time() else '否'}")
    
    # 测试民生
    print("\n民生积存金:")
    print("-" * 40)
    trader_ms = JijinTrader(bank='minsheng', initial_balance=100000, proxy=proxy)
    quote_ms = trader_ms.get_quote()
    if quote_ms:
        print(f"价格: {quote_ms['price']:.2f}元/克")
        print(f"涨跌: {quote_ms['change_amt']} ({quote_ms['change_rate']})")
        print(f"交易时间: {'是' if trader_ms.is_trading_time() else '否'}")
    
    # 模拟交易
    print("\n模拟交易 (浙商):")
    print("-" * 40)
    trader_zs.buy(10.0)  # 买入10克
    
    summary = trader_zs.get_summary()
    print(f"\n持仓状态:")
    print(f"  余额: {summary['balance']:.2f}元")
    print(f"  持仓: {summary['position']:.2f}克")
    print(f"  均价: {summary['avg_price']:.2f}元/克")
    print(f"  市值: {summary['position_value']:.2f}元")
    print(f"  浮动盈亏: {summary['unrealized_pnl']:.2f}元")
    
    trader_zs.sell(5.0)  # 卖出5克
    
    summary = trader_zs.get_summary()
    print(f"\n最终状态:")
    print(f"  余额: {summary['balance']:.2f}元")
    print(f"  持仓: {summary['position']:.2f}克")
    print(f"  已实现盈亏: {summary['realized_pnl']:.2f}元")
    print(f"  总手续费: {summary['total_fees']:.2f}元")
    print(f"  总交易次数: {summary['trade_count']}")
