#!/usr/bin/env python3
"""
实时行情获取 - 黄金ETF和伦敦金
"""
import json
import time
import requests
from typing import Optional, Dict
from datetime import datetime


class GoldPriceFeed:
    """黄金价格数据源"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
    
    def get_etf_price_tencent(self, code: str = "518850") -> Optional[float]:
        """从腾讯财经获取ETF实时价格"""
        try:
            url = f"https://qt.gtimg.cn/q=sh{code}"
            resp = self.session.get(url, timeout=5)
            resp.encoding = 'gb2312'
            
            data = resp.text
            if '~' in data:
                values = data.split('~')
                if len(values) > 3:
                    return float(values[3])
            
            return None
            
        except Exception as e:
            print(f"腾讯财经获取失败: {e}")
            return None
    
    def get_etf_price_sina(self, code: str = "518850") -> Optional[float]:
        """从新浪财经获取ETF实时价格"""
        try:
            url = f"https://hq.sinajs.cn/list=sh{code}"
            resp = self.session.get(url, timeout=5)
            resp.encoding = 'gb2312'
            
            data = resp.text
            if '="' in data:
                values = data.split('="')[1].strip('";').split(',')
                if len(values) > 3:
                    return float(values[3])
            
            return None
            
        except Exception as e:
            print(f"新浪财经获取失败: {e}")
            return None
    
    def get_etf_price(self, code: str = "518850") -> Optional[float]:
        """
        获取ETF价格（多源备用）
        
        优先顺序:
        1. 腾讯财经
        2. 新浪财经
        """
        # 先尝试腾讯
        price = self.get_etf_price_tencent(code)
        if price:
            return price
        
        # 备用新浪
        price = self.get_etf_price_sina(code)
        if price:
            return price
        
        return None
    
    def get_london_gold_price(self) -> Optional[float]:
        """获取伦敦金XAUUSD价格"""
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/XAUUSD=X"
            resp = self.session.get(
                url,
                params={'interval': '1m', 'range': '1d'},
                timeout=10
            )
            data = resp.json()
            
            result = data.get('chart', {}).get('result', [{}])[0]
            meta = result.get('meta', {})
            price = meta.get('regularMarketPrice')
            
            if price:
                return float(price)
            
            closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
            if closes and len(closes) > 0:
                return float(closes[-1])
            
            return None
            
        except Exception as e:
            print(f"伦敦金获取失败: {e}")
            return None
    
    def get_all_prices(self) -> Dict:
        """获取所有黄金价格"""
        return {
            'timestamp': datetime.now().isoformat(),
            'etf_518850': self.get_etf_price("518850"),
            'london_gold': self.get_london_gold_price()
        }


if __name__ == "__main__":
    feed = GoldPriceFeed()
    
    print("获取黄金价格...")
    print("=" * 50)
    
    prices = feed.get_all_prices()
    
    if prices['etf_518850']:
        print(f"黄金ETF华夏(518850): {prices['etf_518850']:.3f} CNY")
    else:
        print("黄金ETF: 获取失败")
    
    if prices['london_gold']:
        print(f"伦敦金(XAUUSD): {prices['london_gold']:.2f} USD")
    else:
        print("伦敦金: 获取失败")
    
    print("=" * 50)
    print("\n完整数据:")
    print(json.dumps(prices, indent=2, default=str))
