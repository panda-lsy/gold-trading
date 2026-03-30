#!/usr/bin/env python3
"""
K 线图数据服务
生成历史价格数据，支持多种时间周期
"""
import json
import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
from json_store import load_json_file, save_json_file
from sqlite_store import SQLiteStore


class KlineService:
    """K 线数据服务"""
    
    # 京东金融 API
    ZHESHANG_API = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice"
    MINSHENG_API = "https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice"
    
    def __init__(self, data_dir: str = None, proxy: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
            'Accept': 'application/json',
            'Origin': 'https://www.jdjygold.com',
            'Referer': 'https://www.jdjygold.com/'
        })
        
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
        
        self.sqlite_store = SQLiteStore(data_dir=self.data_dir)
        self.price_history = self._load_history()
    
    def _get_history_file(self, bank: str) -> str:
        """获取历史数据文件"""
        return os.path.join(self.data_dir, f'{bank}_kline.json')
    
    def _load_history(self) -> Dict[str, List]:
        """加载历史数据"""
        history = {}
        for bank in ['zheshang', 'minsheng']:
            sqlite_history = self.sqlite_store.load_kline_history(bank, limit=10000)
            if sqlite_history:
                history[bank] = sqlite_history
                continue

            file_path = self._get_history_file(bank)
            loaded = load_json_file(file_path, default=[])
            normalized = loaded if isinstance(loaded, list) else []
            history[bank] = normalized
            if normalized:
                try:
                    self.sqlite_store.replace_kline_history(bank, normalized)
                except Exception as e:
                    print(f"迁移 K 线到 SQLite 失败 ({bank}): {e}")
        return history
    
    def _save_history(self, bank: str, incremental: bool = False):
        """保存历史数据"""
        file_path = self._get_history_file(bank)
        if incremental and self.price_history[bank]:
            self.sqlite_store.append_kline(bank, self.price_history[bank][-1])
        else:
            self.sqlite_store.replace_kline_history(bank, self.price_history[bank])
        save_json_file(file_path, self.price_history[bank], ensure_ascii=False)
    
    def fetch_current_price(self, bank: str) -> Optional[Dict]:
        """获取当前价格"""
        try:
            if bank == 'zheshang':
                resp = self.session.get(
                    self.ZHESHANG_API,
                    params={'productSku': '1961543816'},
                    timeout=10
                )
            else:
                resp = self.session.get(
                    self.MINSHENG_API,
                    params={'productSku': 'P005'},
                    timeout=10
                )
            
            data = resp.json()
            
            if data.get('success') and data.get('resultData', {}).get('datas'):
                d = data['resultData']['datas']
                return {
                    'bank': bank,
                    'price': float(d['price']),
                    'open': float(d.get('openPrice', d['yesterdayPrice'])),
                    'high': float(d.get('highPrice', d['price'])),
                    'low': float(d.get('lowPrice', d['price'])),
                    'close': float(d['price']),
                    'yesterday': float(d['yesterdayPrice']),
                    'volume': float(d.get('volume', 0)),
                    'timestamp': int(d['time'])
                }
        except Exception as e:
            print(f"获取价格失败 ({bank}): {e}")
        
        return None
    
    def record_price(self, bank: str) -> bool:
        """记录当前价格"""
        price_data = self.fetch_current_price(bank)
        if not price_data:
            return False

        current_price = float(price_data['close'])
        last_close = current_price
        if self.price_history.get(bank):
            try:
                last_close = float(self.price_history[bank][-1].get('close', current_price))
            except Exception:
                last_close = current_price

        tick_open = last_close
        tick_high = max(last_close, current_price)
        tick_low = min(last_close, current_price)
        
        # 添加到历史
        self.price_history[bank].append({
            'timestamp': price_data['timestamp'],
            'datetime': datetime.fromtimestamp(price_data['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            'open': tick_open,
            'high': tick_high,
            'low': tick_low,
            'close': current_price,
            'volume': price_data['volume']
        })
        
        # 限制历史数据量（保留最近 10000 条）
        if len(self.price_history[bank]) > 10000:
            self.price_history[bank] = self.price_history[bank][-10000:]
        
        self._save_history(bank, incremental=True)
        return True
    
    def get_kline_data(
        self,
        bank: str,
        period: str = '1m',  # 1m, 5m, 15m, 1h, 4h, 1d
        limit: int = 100
    ) -> List[Dict]:
        """
        获取 K 线数据
        
        Args:
            bank: zheshang / minsheng
            period: 时间周期
            limit: 返回条数
        
        Returns:
            K 线数据列表
        """
        history = self.price_history.get(bank, [])
        if not history:
            return []
        
        # 时间周期映射（毫秒）
        period_map = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        }
        
        interval = period_map.get(period, 60 * 1000)
        
        # 按时间周期聚合
        klines = []
        current_bar = None
        
        for item in history:
            timestamp = item['timestamp']
            bar_time = (timestamp // interval) * interval
            price = float(item.get('close', 0))
            volume = float(item.get('volume', 0))
            
            if current_bar is None or current_bar['time'] != bar_time:
                if current_bar:
                    klines.append(current_bar)
                
                current_bar = {
                    'time': bar_time,
                    'datetime': datetime.fromtimestamp(bar_time / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume
                }
            else:
                # 更新当前 K 线
                current_bar['high'] = max(current_bar['high'], price)
                current_bar['low'] = min(current_bar['low'], price)
                current_bar['close'] = price
                current_bar['volume'] += volume
        
        if current_bar:
            klines.append(current_bar)
        
        # 返回最近 limit 条
        return klines[-limit:]
    
    def get_realtime_kline(self, bank: str) -> Optional[Dict]:
        """获取实时 K 线数据（当前周期）"""
        price_data = self.fetch_current_price(bank)
        if not price_data:
            return None
        
        return {
            'time': price_data['timestamp'],
            'datetime': datetime.fromtimestamp(price_data['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            'open': price_data['open'],
            'high': price_data['high'],
            'low': price_data['low'],
            'close': price_data['close'],
            'volume': price_data['volume'],
            'change': round((price_data['close'] - price_data['yesterday']) / price_data['yesterday'] * 100, 2)
        }
    
    def get_technical_indicators(self, bank: str) -> Dict:
        """获取技术指标"""
        klines = self.get_kline_data(bank, period='1d', limit=30)
        
        if len(klines) < 5:
            return {'error': '数据不足'}
        
        closes = [k['close'] for k in klines]
        
        # 计算 MA
        def ma(data, n):
            if len(data) < n:
                return None
            return sum(data[-n:]) / n
        
        # 计算 RSI
        def rsi(data, n=14):
            if len(data) < n + 1:
                return None
            gains = []
            losses = []
            for i in range(1, n + 1):
                change = data[-i] - data[-i-1]
                if change > 0:
                    gains.append(change)
                else:
                    losses.append(abs(change))
            avg_gain = sum(gains) / n if gains else 0
            avg_loss = sum(losses) / n if losses else 0
            if avg_loss == 0:
                return 100
            rs = avg_gain / avg_loss
            return 100 - (100 / (1 + rs))
        
        # 计算 MACD
        def ema(data, n):
            if len(data) < n:
                return None
            multiplier = 2 / (n + 1)
            ema_values = [sum(data[:n]) / n]
            for price in data[n:]:
                ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
            return ema_values[-1]
        
        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        macd = ema12 - ema26 if ema12 and ema26 else None
        signal = ema([ema12 - ema26] if macd else [], 9) if macd else None
        
        return {
            'ma5': round(ma(closes, 5), 2),
            'ma10': round(ma(closes, 10), 2),
            'ma20': round(ma(closes, 20), 2),
            'rsi': round(rsi(closes), 2),
            'macd': round(macd, 4) if macd else None,
            'signal': round(signal, 4) if signal else None,
            'current_price': closes[-1],
            'data_points': len(klines)
        }
    
    def generate_mock_history(self, bank: str, days: int = 30):
        """生成模拟历史数据（用于测试）"""
        base_price = 1000.0
        history = []
        
        now = datetime.now()
        
        for i in range(days * 24 * 12):  # 每 5 分钟一条
            time_offset = timedelta(minutes=-i * 5)
            dt = now + time_offset
            
            # 模拟价格波动
            import random
            change = random.uniform(-2, 2)
            price = base_price + change + random.uniform(-0.5, 0.5)
            
            timestamp = int(dt.timestamp() * 1000)
            
            history.append({
                'timestamp': timestamp,
                'datetime': dt.isoformat(),
                'open': price - random.uniform(0, 1),
                'high': price + random.uniform(0, 2),
                'low': price - random.uniform(0, 2),
                'close': price,
                'volume': random.uniform(100, 1000)
            })
            
            base_price = price
        
        # 反转顺序（从早到晚）
        history.reverse()
        
        self.price_history[bank] = history
        self._save_history(bank)
        
        return len(history)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from src.jijin_trader import find_working_proxy
    
    proxy = find_working_proxy()
    service = KlineService(proxy=proxy)
    
    print("K 线数据服务测试")
    print("=" * 60)
    
    # 记录当前价格
    print("\n记录当前价格...")
    for bank in ['zheshang', 'minsheng']:
        if service.record_price(bank):
            print(f"✓ {bank} 价格已记录")
    
    # 获取 K 线数据
    print("\n\n获取 K 线数据 (1m):")
    print("-" * 60)
    klines = service.get_kline_data('zheshang', period='1m', limit=5)
    for k in klines:
        print(f"{k['datetime']}: 开{k['open']:.2f} 高{k['high']:.2f} 低{k['low']:.2f} 收{k['close']:.2f}")
    
    # 技术指标
    print("\n\n技术指标:")
    print("-" * 60)
    indicators = service.get_technical_indicators('zheshang')
    print(f"MA5: {indicators.get('ma5')}")
    print(f"MA10: {indicators.get('ma10')}")
    print(f"MA20: {indicators.get('ma20')}")
    print(f"RSI: {indicators.get('rsi')}")
    print(f"MACD: {indicators.get('macd')}")