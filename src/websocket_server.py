#!/usr/bin/env python3
"""
WebSocket 实时价格推送服务
使用京东金融 WebSocket 地址获取实时价格并推送给客户端
"""
import json
import asyncio
import websockets
import requests
from datetime import datetime
from typing import Set, Dict
import threading
import time

# 京东金融 WebSocket 地址
WS_URL = "wss://alb-1ko0lowmvacsqia0ij.cn-shenzhen.alb.aliyuncs.com:26203"

# HTTP API 备用
ZHESHANG_API = "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice"
MINSHENG_API = "https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice"


class PriceFeed:
    """价格获取器（支持 WebSocket 和 HTTP）"""
    
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
    
    def fetch_zheshang(self) -> Dict:
        """获取浙商积存金价格"""
        try:
            resp = self.session.get(
                ZHESHANG_API,
                params={'productSku': '1961543816'},
                timeout=10
            )
            data = resp.json()
            
            if data.get('success') and data.get('resultData', {}).get('datas'):
                d = data['resultData']['datas']
                price_data = {
                    'bank': 'zheshang',
                    'name': '浙商积存金',
                    'price': float(d['price']),
                    'yesterday_price': float(d['yesterdayPrice']),
                    'change_amt': d['upAndDownAmt'],
                    'change_rate': d['upAndDownRate'],
                    'datetime': datetime.fromtimestamp(int(d['time']) / 1000).isoformat()
                }
                self.last_prices['zheshang'] = price_data
                return price_data
        except Exception as e:
            print(f"浙商价格获取失败：{e}")
        
        return self.last_prices.get('zheshang', {})
    
    def fetch_minsheng(self) -> Dict:
        """获取民生积存金价格"""
        try:
            resp = self.session.get(
                MINSHENG_API,
                params={'productSku': 'P005'},
                timeout=10
            )
            data = resp.json()
            
            if data.get('success') and data.get('resultData', {}).get('datas'):
                d = data['resultData']['datas']
                price_data = {
                    'bank': 'minsheng',
                    'name': '民生积存金',
                    'price': float(d['price']),
                    'yesterday_price': float(d['yesterdayPrice']),
                    'change_amt': d['upAndDownAmt'],
                    'change_rate': d['upAndDownRate'],
                    'datetime': datetime.fromtimestamp(int(d['time']) / 1000).isoformat()
                }
                self.last_prices['minsheng'] = price_data
                return price_data
        except Exception as e:
            print(f"民生价格获取失败：{e}")
        
        return self.last_prices.get('minsheng', {})
    
    def get_all_prices(self) -> Dict:
        """获取所有银行价格"""
        prices = {
            'zheshang': self.fetch_zheshang(),
            'minsheng': self.fetch_minsheng()
        }
        return prices


class WebSocketServer:
    """WebSocket 价格推送服务器"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set = set()
        self.price_feed = PriceFeed()
        self.running = False
        self.last_message = {}
    
    async def handler(self, websocket):
        """处理 WebSocket 连接"""
        self.clients.add(websocket)
        print(f"✓ 客户端连接：{websocket.remote_address}")
        
        # 发送当前价格
        try:
            prices = self.price_feed.get_all_prices()
            await websocket.send(json.dumps({
                'type': 'initial',
                'prices': prices,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            print(f"发送初始数据失败：{e}")
        
        try:
            async for message in websocket:
                # 处理客户端消息
                try:
                    data = json.loads(message)
                    if data.get('action') == 'ping':
                        await websocket.send(json.dumps({
                            'type': 'pong',
                            'timestamp': datetime.now().isoformat()
                        }))
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"✗ 客户端断开：{websocket.remote_address}")
    
    async def broadcast_prices(self):
        """定期广播价格"""
        while self.running:
            try:
                prices = self.price_feed.get_all_prices()
                message = json.dumps({
                    'type': 'price_update',
                    'prices': prices,
                    'timestamp': datetime.now().isoformat()
                })
                
                if self.clients:
                    await asyncio.gather(
                        *[client.send(message) for client in self.clients],
                        return_exceptions=True
                    )
                    print(f"已推送价格到 {len(self.clients)} 个客户端")
                
                self.last_message = {
                    'prices': prices,
                    'timestamp': datetime.now().isoformat(),
                    'clients': len(self.clients)
                }
                
            except Exception as e:
                print(f"广播失败：{e}")
            
            await asyncio.sleep(3)  # 每 3 秒更新一次
    
    async def run(self):
        """启动服务器"""
        self.running = True
        print(f"🚀 WebSocket 服务器启动：ws://{self.host}:{self.port}")
        
        server = await websockets.serve(self.handler, self.host, self.port)
        
        # 启动广播任务
        broadcast_task = asyncio.create_task(self.broadcast_prices())
        
        await server.wait_closed()
        broadcast_task.cancel()
    
    def start(self):
        """启动服务器（阻塞）"""
        asyncio.run(self.run())
    
    def get_status(self) -> Dict:
        """获取服务器状态"""
        return {
            'running': self.running,
            'clients': len(self.clients),
            'last_update': self.last_message.get('timestamp'),
            'prices': self.last_message.get('prices', {})
        }


def run_server(host: str = "0.0.0.0", port: int = 8765):
    """运行 WebSocket 服务器"""
    server = WebSocketServer(host=host, port=port)
    server.start()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='WebSocket 价格推送服务')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=8765, help='监听端口')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("积存金 WebSocket 实时价格推送服务")
    print("=" * 60)
    print(f"监听地址：ws://{args.host}:{args.port}")
    print()
    
    run_server(args.host, args.port)
