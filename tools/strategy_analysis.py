#!/usr/bin/env python3
"""
交易策略分析报告
对比旧策略 vs 新策略
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jijin_trader import JijinTrader, find_working_proxy
from datetime import datetime


def analyze_old_trades():
    """分析旧交易记录的问题"""
    print("=" * 70)
    print("交易策略分析报告")
    print("=" * 70)
    
    proxy = find_working_proxy()
    trader = JijinTrader(bank='zheshang', proxy=proxy)
    
    print("\n【当前持仓状态】")
    print("-" * 70)
    quote = trader.get_quote()
    if quote:
        print(f"当前价格: {quote['price']:.2f}元/克")
        print(f"涨跌: {quote['change_amt']} ({quote['change_rate']})")
    
    summary = trader.get_summary()
    print(f"\n持仓: {summary['position']:.2f}克")
    print(f"持仓均价: {summary['avg_price']:.2f}元/克")
    print(f"浮动盈亏: {summary['unrealized_pnl']:+.2f}元")
    print(f"已实现盈亏: {summary['realized_pnl']:+.2f}元")
    print(f"累计手续费: {summary['total_fees']:.2f}元")
    
    print("\n【历史交易分析】")
    print("-" * 70)
    
    trades = trader.trades
    if not trades:
        print("无交易记录")
        return
    
    print(f"总交易笔数: {len(trades)}")
    print()
    
    for i, trade in enumerate(trades, 1):
        print(f"交易 #{i}")
        print(f"  时间: {trade['time'][:19]}")
        print(f"  操作: {'买入' if trade['action'] == 'BUY' else '卖出'}")
        print(f"  数量: {trade['grams']:.2f}克")
        print(f"  价格: {trade['price']:.2f}元/克")
        
        if trade['action'] == 'BUY':
            print(f"  成本: {trade['cost']:.2f}元")
        else:
            print(f"  毛收入: {trade.get('gross_proceeds', 0):.2f}元")
            print(f"  手续费: {trade.get('fee', 0):.2f}元")
            print(f"  净盈亏: {trade.get('profit', 0):+.2f}元")
        print()
    
    # 分析问题
    print("【问题分析】")
    print("-" * 70)
    
    # 检查频繁交易
    if len(trades) >= 2:
        from datetime import datetime
        times = [datetime.fromisoformat(t['time']) for t in trades]
        
        for i in range(1, len(times)):
            diff = (times[i] - times[i-1]).total_seconds()
            if diff < 60:
                print(f"⚠️ 问题 #{i}: 交易间隔仅{diff:.0f}秒，过于频繁！")
                print(f"   建议: 最小持仓时间30分钟，避免频繁买卖")
    
    # 检查盈利目标
    sells = [t for t in trades if t['action'] == 'SELL']
    for sell in sells:
        profit = sell.get('profit', 0)
        if profit < 0:
            print(f"⚠️ 卖出亏损: {profit:.2f}元")
            print(f"   建议: 卖出需盈利>0.5%(扣除手续费)才划算")
    
    # 计算如果不频繁交易
    print("\n【优化建议】")
    print("-" * 70)
    
    if trades:
        # 假设只买不卖
        total_bought = sum(t['grams'] for t in trades if t['action'] == 'BUY')
        total_cost = sum(t['cost'] for t in trades if t['action'] == 'BUY')
        
        if total_bought > 0:
            avg_cost = total_cost / total_bought
            current_price = quote['price'] if quote else avg_cost
            
            potential_value = total_bought * current_price
            potential_profit = potential_value - total_cost
            
            print(f"如果采用'买入持有'策略:")
            print(f"  总买入: {total_bought:.2f}克")
            print(f"  总成本: {total_cost:.2f}元")
            print(f"  当前市值: {potential_value:.2f}元")
            print(f"  浮动盈亏: {potential_profit:+.2f}元")
            print(f"  对比当前已实现: {summary['realized_pnl']:+.2f}元")
            print(f"  差异: {potential_profit - summary['realized_pnl']:+.2f}元")
    
    print("\n【新策略规则】")
    print("-" * 70)
    print("1. 最小持仓时间: 30分钟")
    print("2. 最小盈利目标: 0.5% (扣除0.4%手续费后)")
    print("3. 趋势确认: 连续3次同向价格变动才交易")
    print("4. 分批操作: 每次最多买卖5克")
    print("5. 止损线: 亏损超过1%时止损")
    
    print("\n【当前建议】")
    print("-" * 70)
    
    if summary['position'] > 0 and quote:
        current_price = quote['price']
        avg_price = summary['avg_price']
        
        # 计算净利润率
        gross_profit = (current_price - avg_price) / avg_price * 100
        net_profit = gross_profit - 0.4  # 扣除手续费
        
        print(f"当前持仓: {summary['position']:.2f}克")
        print(f"持仓均价: {avg_price:.2f}元")
        print(f"当前价格: {current_price:.2f}元")
        print(f"毛利润: {gross_profit:.2f}%")
        print(f"净利润(扣手续费): {net_profit:.2f}%")
        
        if net_profit >= 0.5:
            print(f"\n✅ 建议: 盈利达标，可考虑卖出获利")
            print(f"   预计净盈利: {net_profit:.2f}%")
        elif gross_profit < -1.0:
            print(f"\n⚠️ 建议: 亏损超过1%，考虑止损")
        else:
            print(f"\n⏸️ 建议: 继续持有，等待盈利达标")


if __name__ == "__main__":
    analyze_old_trades()
