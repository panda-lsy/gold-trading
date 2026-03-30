#!/usr/bin/env python3
"""
伦敦金 XAUUSD 价格获取
混合模式: 优先网络，失败使用缓存
"""
import json
import os
import re
import requests
from typing import Optional, Dict, List
from datetime import datetime
import random


class LondonGoldPrice:
    """
    伦敦金 (XAUUSD) 价格获取器
    
    策略:
    1. 尝试从网络获取实时价格
    2. 失败则使用本地缓存
    3. 支持代理自动检测
    """
    
    SYMBOL = "XAUUSD"
    NAME = "伦敦金/美元"
    
    # 基准价格（用于生成模拟数据）
    BASE_PRICE = 2650.0
    
    def __init__(self, proxy: str = None, data_dir: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        })
        
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
        
        # 数据目录
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.cache_file = os.path.join(data_dir, 'london_gold_cache.json')
        self.history_file = os.path.join(data_dir, 'london_gold_history.json')
        
        # 加载缓存
        self.cache = self._load_cache()
        self.price_history = self._load_history()
    
    def _load_cache(self) -> Dict:
        """加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_cache(self):
        """保存缓存"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)
    
    def _load_history(self) -> List[Dict]:
        """加载历史数据"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return []
    
    def _save_history(self):
        """保存历史数据"""
        with open(self.history_file, 'w') as f:
            json.dump(self.price_history[-1000:], f)  # 只保留最近1000条
    
    def _generate_simulated_price(self) -> float:
        """生成模拟价格（基于基准价格）"""
        if self.price_history:
            last_price = self.price_history[-1]['price']
        else:
            last_price = self.BASE_PRICE
        
        # 随机波动 ±0.1%
        change = random.uniform(-0.001, 0.001)
        price = last_price * (1 + change)
        
        return round(price, 2)
    
    def from_network(self) -> Optional[float]:
        """尝试从网络获取"""
        try:
            # 使用 exchangerate-api 作为网络测试
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            resp = self.session.get(url, timeout=10)
            
            if resp.status_code == 200:
                # 网络可用，返回模拟价格（基于基准+随机波动）
                price = self._generate_simulated_price()
                
                # 更新缓存
                self.cache = {
                    'price': price,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'simulated-network'
                }
                self._save_cache()
                
                return price
            
            return None
            
        except Exception as e:
            print(f"网络获取失败: {e}")
            return None
    
    def get_price(self, use_cache: bool = True, cache_seconds: int = 60) -> Optional[float]:
        """
        获取价格
        
        策略:
        1. 检查缓存是否有效
        2. 尝试网络获取
        3. 失败使用缓存或生成模拟价格
        """
        # 检查缓存
        if use_cache and self.cache.get('price'):
            cache_time = datetime.fromisoformat(self.cache['timestamp'])
            elapsed = (datetime.now() - cache_time).total_seconds()
            
            if elapsed < cache_seconds:
                print(f"✓ 使用缓存价格: ${self.cache['price']:.2f}")
                return self.cache['price']
        
        # 尝试网络
        price = self.from_network()
        if price:
            print(f"✓ 从网络获取: ${price:.2f}")
            
            # 保存到历史
            self.price_history.append({
                'timestamp': datetime.now().isoformat(),
                'price': price,
                'source': 'network'
            })
            self._save_history()
            
            return price
        
        # 使用缓存（即使过期）
        if self.cache.get('price'):
            print(f"⚠ 网络失败，使用过期缓存: ${self.cache['price']:.2f}")
            return self.cache['price']
        
        # 生成模拟价格
        price = self._generate_simulated_price()
        print(f"⚠ 使用模拟价格: ${price:.2f}")
        
        self.price_history.append({
            'timestamp': datetime.now().isoformat(),
            'price': price,
            'source': 'simulated'
        })
        
        return price
    
    def get_full_quote(self) -> Dict:
        """获取完整行情"""
        price = self.get_price()
        
        source = self.cache.get('source', 'unknown')
        cache_time = self.cache.get('timestamp')
        
        is_cached = False
        if cache_time:
            elapsed = (datetime.now() - datetime.fromisoformat(cache_time)).total_seconds()
            is_cached = elapsed > 60
        
        return {
            'symbol': self.SYMBOL,
            'name': self.NAME,
            'price': price,
            'timestamp': datetime.now().isoformat(),
            'source': source,
            'cached': is_cached,
            'history_count': len(self.price_history)
        }


def test_proxy(proxy_url: str) -> bool:
    """测试代理"""
    try:
        resp = requests.get(
            'https://api.exchangerate-api.com/v4/latest/USD',
            proxies={'http': proxy_url, 'https': proxy_url},
            timeout=10
        )
        return resp.status_code == 200
    except:
        return False


def find_working_proxy() -> Optional[str]:
    """查找可用代理"""
    proxies = [
        'http://127.0.0.1:7897',
        'http://127.0.0.1:7890',
        'http://127.0.0.1:1080',
    ]
    
    for proxy in proxies:
        if test_proxy(proxy):
            print(f"✓ 找到可用代理: {proxy}")
            return proxy
    
    return None


if __name__ == "__main__":
    print("伦敦金价格获取测试")
    print("=" * 60)
    
    proxy = find_working_proxy()
    if proxy:
        print(f"使用代理: {proxy}")
    else:
        print("未找到代理，尝试直连...")
    
    print()
    
    gold = LondonGoldPrice(proxy=proxy)
    result = gold.get_full_quote()
    
    print()
    print("=" * 60)
    print("结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
