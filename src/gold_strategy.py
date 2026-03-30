#!/usr/bin/env python3
"""
黄金超短线策略
针对518850黄金ETF设计
"""
import numpy as np
from typing import List, Dict
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)


@dataclass
class Signal:
    code: str
    action: str
    price: float
    volume: int
    reason: str


class GoldIntradayStrategy:
    """
    黄金ETF超短线策略
    
    核心逻辑:
    1. 5分钟突破前高买入
    2. 跌破前低或盈利1%卖出
    3. 严格止损-0.5%
    4. 收盘前清仓(T+0)
    """
    
    def __init__(self):
        self.name = "GoldIntraday"
        self.code = "518850"
        
        # 参数
        self.take_profit = 0.01
        self.stop_loss = 0.005
        self.lookback = 5
        
        # 状态
        self.position = 0
        self.entry_price = 0
        self.high_5min = []
        self.low_5min = []
        
    def update_kline(self, price: float):
        """更新5分钟K线数据"""
        self.high_5min.append(price)
        self.low_5min.append(price)
        
        if len(self.high_5min) > self.lookback:
            self.high_5min.pop(0)
            self.low_5min.pop(0)
    
    def on_tick(self, price: float, time_str: str) -> List[Signal]:
        """处理实时tick数据"""
        signals = []
        
        self.update_kline(price)
        
        if len(self.high_5min) < self.lookback:
            return signals
        
        prev_high = max(self.high_5min[:-1])
        prev_low = min(self.low_5min[:-1])
        
        # 有持仓，检查止盈止损
        if self.position > 0:
            profit_pct = (price - self.entry_price) / self.entry_price
            
            if profit_pct >= self.take_profit:
                signals.append(Signal(
                    code=self.code, action="SELL", price=price,
                    volume=self.position, reason=f"止盈 {profit_pct*100:.2f}%"
                ))
                self.position = 0
                return signals
            
            if profit_pct <= -self.stop_loss:
                signals.append(Signal(
                    code=self.code, action="SELL", price=price,
                    volume=self.position, reason=f"止损 {profit_pct*100:.2f}%"
                ))
                self.position = 0
                return signals
        
        # 无持仓，检查买入信号
        if self.position == 0:
            if price > prev_high * 1.001:
                volume = 100
                signals.append(Signal(
                    code=self.code, action="BUY", price=price,
                    volume=volume, reason=f"突破前高 {prev_high:.3f}"
                ))
                self.position = volume
                self.entry_price = price
                return signals
        
        return signals
    
    def on_close(self, price: float) -> List[Signal]:
        """收盘前强制清仓"""
        signals = []
        if self.position > 0:
            signals.append(Signal(
                code=self.code, action="SELL", price=price,
                volume=self.position, reason="收盘前清仓(T+0)"
            ))
            self.position = 0
        return signals
    
    def reset(self):
        """重置状态"""
        self.position = 0
        self.entry_price = 0
        self.high_5min = []
        self.low_5min = []


class LondonGoldStrategy:
    """
    伦敦金趋势策略
    
    核心逻辑:
    1. 1小时K线MA5/MA20金叉做多
    2. MA死叉平仓
    3. 追踪止损
    """
    
    def __init__(self):
        self.name = "LondonGoldTrend"
        self.symbol = "XAUUSD"
        
        self.short_ma = 5
        self.long_ma = 20
        self.trailing_stop = 0.02
        
        self.position = 0
        self.entry_price = 0
        self.highest_price = 0
        self.price_history = []
        
    def update_kline(self, klines: List[Dict]):
        """更新K线数据"""
        self.price_history = [k['close'] for k in klines]
    
    def calculate_ma(self, prices: List[float], window: int) -> float:
        """计算均线"""
        if len(prices) < window:
            return None
        return sum(prices[-window:]) / window
    
    def on_data(self, current_price: float) -> List[Signal]:
        """生成交易信号"""
        signals = []
        
        if len(self.price_history) < self.long_ma:
            return signals
        
        short = self.calculate_ma(self.price_history, self.short_ma)
        long = self.calculate_ma(self.price_history, self.long_ma)
        
        if short is None or long is None:
            return signals
        
        # 有持仓，检查平仓信号
        if self.position > 0:
            if current_price > self.highest_price:
                self.highest_price = current_price
            
            drawdown = (self.highest_price - current_price) / self.highest_price
            if drawdown >= self.trailing_stop:
                signals.append(Signal(
                    code=self.symbol, action="SELL", price=current_price,
                    volume=self.position, reason=f"追踪止损 {drawdown*100:.1f}%"
                ))
                self.position = 0
                return signals
            
            if short < long:
                signals.append(Signal(
                    code=self.symbol, action="SELL", price=current_price,
                    volume=self.position, reason=f"MA{self.short_ma}死叉MA{self.long_ma}"
                ))
                self.position = 0
                return signals
        
        # 无持仓，检查买入信号
        if self.position == 0:
            if short > long:
                signals.append(Signal(
                    code=self.symbol, action="BUY", price=current_price,
                    volume=1.0, reason=f"MA{self.short_ma}金叉MA{self.long_ma}"
                ))
                self.position = 1.0
                self.entry_price = current_price
                self.highest_price = current_price
                return signals
        
        return signals
    
    def reset(self):
        """重置状态"""
        self.position = 0
        self.entry_price = 0
        self.highest_price = 0
        self.price_history = []
