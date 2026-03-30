#!/usr/bin/env python3
"""
K 线数据服务 - 生成专业图表数据
"""
import json
import os
import random
from datetime import datetime, timedelta
from typing import List, Dict


class KlineDataService:
    """K 线数据服务"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
    
    def generate_mock_kline(self, bank: str, days: int = 30) -> List[Dict]:
        """生成模拟 K 线数据"""
        klines = []
        base_price = 1000.0 if bank == 'zheshang' else 995.0
        
        now = datetime.now()
        
        for i in range(days * 24):  # 每小时一个数据点
            time_offset = timedelta(hours=-i)
            dt = now + time_offset
            
            # 模拟价格波动
            volatility = random.uniform(-0.005, 0.005)  # ±0.5%
            price = base_price * (1 + volatility)
            
            # 生成 OHLC 数据
            open_price = price * (1 + random.uniform(-0.002, 0.002))
            close_price = price
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.003))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.003))
            
            klines.insert(0, {
                'timestamp': int(dt.timestamp() * 1000),
                'datetime': dt.strftime('%Y-%m-%d %H:%M'),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': round(random.uniform(100, 1000), 2)
            })
            
            base_price = close_price
        
        return klines
    
    def save_kline(self, bank: str, klines: List[Dict]):
        """保存 K 线数据"""
        file_path = os.path.join(self.data_dir, f'{bank}_kline.json')
        with open(file_path, 'w') as f:
            json.dump(klines, f)
    
    def load_kline(self, bank: str) -> List[Dict]:
        """加载 K 线数据"""
        file_path = os.path.join(self.data_dir, f'{bank}_kline.json')
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return self.generate_mock_kline(bank)
    
    def get_chart_data(self, bank: str, limit: int = 50) -> Dict:
        """获取图表数据"""
        klines = self.load_kline(bank)
        
        # 取最近 limit 条数据
        recent = klines[-limit:] if len(klines) > limit else klines
        
        return {
            'labels': [k['datetime'][-5:] for k in recent],  # 只显示 HH:MM
            'open': [k['open'] for k in recent],
            'high': [k['high'] for k in recent],
            'low': [k['low'] for k in recent],
            'close': [k['close'] for k in recent],
            'volume': [k['volume'] for k in recent]
        }


if __name__ == "__main__":
    service = KlineDataService()
    
    # 生成并保存数据
    for bank in ['zheshang', 'minsheng']:
        klines = service.generate_mock_kline(bank)
        service.save_kline(bank, klines)
        print(f"✓ {bank}: 生成 {len(klines)} 条 K 线数据")
        
        chart_data = service.get_chart_data(bank, limit=10)
        print(f"  最新收盘价: {chart_data['close'][-1]}")
