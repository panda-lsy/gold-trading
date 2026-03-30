#!/usr/bin/env python3
"""
交易记录管理器
提供完整的交易记录查询、统计、分析功能
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict
from dataclasses import dataclass, asdict
from sqlite_store import SQLiteStore


@dataclass
class TradeRecord:
    """交易记录"""
    time: str
    action: str  # BUY / SELL
    bank: str
    price: float
    grams: float
    cost: float = 0
    fee: float = 0
    profit: float = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TradeManager:
    """交易记录管理器"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.sqlite_store = SQLiteStore(data_dir=data_dir)
    
    def load_trades(self, bank: str) -> List[TradeRecord]:
        """加载交易记录"""
        raw_trades = self.sqlite_store.load_trader_trades(bank)
        trades: List[TradeRecord] = []
        try:
            for t in raw_trades:
                trade = TradeRecord(
                    time=t.get('time', ''),
                    action=t.get('action', ''),
                    bank=t.get('bank', bank),
                    price=t.get('price', 0),
                    grams=t.get('grams', 0),
                    cost=t.get('cost', 0) or t.get('gross_proceeds', 0),
                    fee=t.get('fee', 0),
                    profit=t.get('profit', 0)
                )
                trades.append(trade)
            return trades
        except Exception as e:
            print(f"加载交易记录失败: {e}")
            return []
    
    def get_all_trades(self, bank: str = None) -> List[TradeRecord]:
        """获取所有交易记录"""
        if bank:
            return self.load_trades(bank)
        
        all_trades = []
        for b in ['zheshang', 'minsheng']:
            all_trades.extend(self.load_trades(b))
        
        # 按时间排序
        all_trades.sort(key=lambda x: x.time)
        return all_trades
    
    def filter_trades(
        self,
        bank: str = None,
        action: str = None,  # BUY / SELL
        start_date: str = None,
        end_date: str = None,
        min_amount: float = None,
        max_amount: float = None
    ) -> List[TradeRecord]:
        """筛选交易记录"""
        trades = self.get_all_trades(bank)
        
        filtered = []
        for t in trades:
            # 动作筛选
            if action and t.action != action:
                continue
            
            # 日期筛选
            trade_date = datetime.fromisoformat(t.time)
            if start_date:
                start = datetime.fromisoformat(start_date)
                if trade_date < start:
                    continue
            if end_date:
                end = datetime.fromisoformat(end_date)
                if trade_date > end:
                    continue
            
            # 金额筛选
            amount = t.cost if t.action == 'BUY' else t.cost
            if min_amount and amount < min_amount:
                continue
            if max_amount and amount > max_amount:
                continue
            
            filtered.append(t)
        
        return filtered
    
    def get_trade_stats(self, bank: str = None) -> Dict:
        """获取交易统计"""
        trades = self.get_all_trades(bank)
        
        if not trades:
            return {
                'total_trades': 0,
                'buy_count': 0,
                'sell_count': 0,
                'total_buy_amount': 0,
                'total_sell_amount': 0,
                'total_fees': 0,
                'total_profit': 0,
                'avg_buy_price': 0,
                'avg_sell_price': 0
            }
        
        buy_trades = [t for t in trades if t.action == 'BUY']
        sell_trades = [t for t in trades if t.action == 'SELL']
        
        total_buy_amount = sum(t.cost for t in buy_trades)
        total_sell_amount = sum(t.cost for t in sell_trades)
        total_fees = sum(t.fee for t in trades)
        total_profit = sum(t.profit for t in sell_trades)
        
        avg_buy_price = sum(t.price * t.grams for t in buy_trades) / sum(t.grams for t in buy_trades) if buy_trades else 0
        avg_sell_price = sum(t.price * t.grams for t in sell_trades) / sum(t.grams for t in sell_trades) if sell_trades else 0
        
        return {
            'total_trades': len(trades),
            'buy_count': len(buy_trades),
            'sell_count': len(sell_trades),
            'total_buy_amount': round(total_buy_amount, 2),
            'total_sell_amount': round(total_sell_amount, 2),
            'total_fees': round(total_fees, 2),
            'total_profit': round(total_profit, 2),
            'avg_buy_price': round(avg_buy_price, 2),
            'avg_sell_price': round(avg_sell_price, 2),
            'win_rate': round(len([t for t in sell_trades if t.profit > 0]) / len(sell_trades) * 100, 2) if sell_trades else 0
        }
    
    def get_daily_summary(self, days: int = 30) -> List[Dict]:
        """获取每日交易汇总"""
        trades = self.get_all_trades()
        
        # 按日期分组
        daily = {}
        for t in trades:
            date = t.time[:10]  # YYYY-MM-DD
            if date not in daily:
                daily[date] = {'buys': [], 'sells': []}
            
            if t.action == 'BUY':
                daily[date]['buys'].append(t)
            else:
                daily[date]['sells'].append(t)
        
        # 生成汇总
        summary = []
        for date in sorted(daily.keys())[-days:]:
            data = daily[date]
            buy_amount = sum(t.cost for t in data['buys'])
            sell_amount = sum(t.cost for t in data['sells'])
            profit = sum(t.profit for t in data['sells'])
            fees = sum(t.fee for t in data['sells'])
            
            summary.append({
                'date': date,
                'buy_count': len(data['buys']),
                'sell_count': len(data['sells']),
                'buy_amount': round(buy_amount, 2),
                'sell_amount': round(sell_amount, 2),
                'profit': round(profit, 2),
                'fees': round(fees, 2)
            })
        
        return summary
    
    def get_trade_history_chart(self, bank: str = None, days: int = 30) -> List[Dict]:
        """获取交易历史图表数据"""
        trades = self.get_all_trades(bank)
        
        # 生成日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 按日期统计
        daily_data = {}
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            daily_data[date_str] = {
                'date': date_str,
                'price': None,
                'volume': 0,
                'profit': 0
            }
            current_date += timedelta(days=1)
        
        # 填充交易数据
        for t in trades:
            date = t.time[:10]
            if date in daily_data:
                daily_data[date]['price'] = t.price
                daily_data[date]['volume'] += t.grams
                if t.action == 'SELL':
                    daily_data[date]['profit'] += t.profit
        
        return list(daily_data.values())
    
    def export_to_csv(self, bank: str = None, filename: str = None) -> str:
        """导出交易记录到 CSV"""
        trades = self.get_all_trades(bank)
        
        if filename is None:
            filename = os.path.join(self.data_dir, f'trades_export_{datetime.now().strftime("%Y%m%d")}.csv')
        
        import csv
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['时间', '动作', '银行', '价格', '数量(克)', '金额', '手续费', '盈亏'])
            
            for t in trades:
                writer.writerow([
                    t.time,
                    '买入' if t.action == 'BUY' else '卖出',
                    '浙商' if t.bank == 'zheshang' else '民生',
                    t.price,
                    t.grams,
                    t.cost,
                    t.fee,
                    t.profit
                ])
        
        return filename


if __name__ == "__main__":
    manager = TradeManager()
    
    print("交易记录统计")
    print("=" * 60)
    
    # 总体统计
    stats = manager.get_trade_stats()
    print(f"\n总交易次数: {stats['total_trades']}")
    print(f"买入次数: {stats['buy_count']}")
    print(f"卖出次数: {stats['sell_count']}")
    print(f"总买入金额: {stats['total_buy_amount']:.2f} 元")
    print(f"总卖出金额: {stats['total_sell_amount']:.2f} 元")
    print(f"总手续费: {stats['total_fees']:.2f} 元")
    print(f"总盈亏: {stats['total_profit']:.2f} 元")
    print(f"胜率: {stats['win_rate']}%")
    
    # 每日汇总
    print("\n\n最近交易记录:")
    print("-" * 60)
    daily = manager.get_daily_summary(days=7)
    for d in daily:
        print(f"{d['date']}: 买{d['buy_count']}次 卖{d['sell_count']}次 盈亏{d['profit']:+.2f}元")
