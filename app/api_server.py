#!/usr/bin/env python3
"""
积存金交易 API 服务器
提供完整的 REST API 接口
"""
import json
import os
import sys
import tempfile
import threading
import time
import logging
import uuid
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from flask import Flask, jsonify, request, send_file, g
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

# 添加 src 路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
AI_OUTPUT_DIR = PROJECT_ROOT / 'data' / 'ai_outputs'
AI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jijin_trader import JijinTrader, find_working_proxy
from trade_manager import TradeManager
from kline_service import KlineService
from alert_service import AlertService, AlertNotifier
from backtest_service import BacktestService
try:
    from app.openclaw_integration import JijinOpenClaw
except ImportError:
    try:
        from openclaw_integration import JijinOpenClaw
    except ImportError:
        JijinOpenClaw = None


logger = logging.getLogger(__name__)


MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.ogg', '.flac'}
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
ALLOWED_ARTIFACT_EXTENSIONS = ALLOWED_AUDIO_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS
SUPPORTED_BANKS = {'zheshang', 'minsheng'}
SUPPORTED_KLINE_PERIODS = {'1m', '5m', '15m', '1h', '4h', '1d'}
SUPPORTED_BACKTEST_STRATEGIES = {'grid', 'trend', 'dca', 'compare'}
SUPPORTED_BACKTEST_DETAIL_STRATEGIES = {'grid', 'trend', 'dca'}
RATE_LIMIT_EXEMPT_PATHS = {'/api/health'}
RATE_LIMIT_PATH_TIERS = [
    ('/api/ai/chat', 20),
    ('/api/ai/', 30),
    ('/api/backtest/', 20),
    ('/api/kline/', 90),
]


class AIInterfaceBridge:
    """ai_interface 运行时桥接，按需懒加载模型。"""

    def __init__(self):
        self.asr = None
        self.tts = None
        self.vlm = None
        self.image_generator = None

    def _safe_load(self, loader, model_name: str):
        try:
            model = loader()
            if model is None or getattr(model, 'model', None) is None:
                return None, f'{model_name} 模型未成功加载，请检查模型目录和依赖'
            return model, None
        except Exception as e:
            return None, f'{model_name} 加载失败: {e}'

    def get_capabilities(self):
        status = {
            'asr': {'ready': False, 'message': 'not loaded'},
            'tts': {'ready': False, 'message': 'not loaded'},
            'vlm': {'ready': False, 'message': 'not loaded'},
            'image_generation': {'ready': False, 'message': 'not loaded'},
        }

        from ai_interface import Qwen3ASR, Qwen3TTS, Qwen3VLAnalyzer, MarketImageGenerator

        asr_err = None
        if self.asr is None:
            self.asr, asr_err = self._safe_load(Qwen3ASR, 'ASR')
        status['asr']['ready'] = self.asr is not None and getattr(self.asr, 'model', None) is not None
        status['asr']['message'] = 'ready' if status['asr']['ready'] else (asr_err or 'ASR 模型未成功加载，请检查模型目录和依赖')

        tts_err = None
        if self.tts is None:
            self.tts, tts_err = self._safe_load(Qwen3TTS, 'TTS')
        status['tts']['ready'] = self.tts is not None and getattr(self.tts, 'model', None) is not None
        status['tts']['message'] = 'ready' if status['tts']['ready'] else (tts_err or 'TTS 模型未成功加载，请检查模型目录和依赖')

        vlm_err = None
        if self.vlm is None:
            self.vlm, vlm_err = self._safe_load(Qwen3VLAnalyzer, 'VLM')
        status['vlm']['ready'] = self.vlm is not None and getattr(self.vlm, 'model', None) is not None
        if status['vlm']['ready'] and getattr(self.vlm, 'backend', None) == 'fallback':
            reason = getattr(self.vlm, 'fallback_reason', '')
            status['vlm']['message'] = f'规则分析模式可用（原生VLM后端受限: {reason}）'
        else:
            status['vlm']['message'] = 'ready' if status['vlm']['ready'] else (vlm_err or 'VLM 模型未成功加载，请检查模型目录和依赖')

        if self.image_generator is None:
            try:
                self.image_generator = MarketImageGenerator(output_dir=str(AI_OUTPUT_DIR))
            except Exception as e:
                status['image_generation']['message'] = f'image generation init failed: {e}'
        status['image_generation']['ready'] = self.image_generator is not None
        if status['image_generation']['ready']:
            if self.image_generator.pipeline is not None:
                mode = 'OpenVINO' if getattr(self.image_generator, '_use_openvino', False) else 'Diffusers'
                status['image_generation']['message'] = f'{mode} 文生图可用'
            else:
                status['image_generation']['message'] = '模板渲染模式可用'

        return status

    def tts_synthesize(self, text: str):
        if not text.strip():
            return None, 'text 不能为空'

        if self.tts is None:
            from ai_interface import Qwen3TTS
            self.tts, err = self._safe_load(Qwen3TTS, 'TTS')
            if err:
                return None, err

        output_name = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        output_path = AI_OUTPUT_DIR / output_name
        result = self.tts.synthesize(text=text, output_file=str(output_path))
        if not result or not output_path.exists():
            return None, 'TTS 合成失败，请检查模型和依赖'
        return output_name, None

    def asr_recognize(self, audio_file_path: str):
        if self.asr is None:
            from ai_interface import Qwen3ASR
            self.asr, err = self._safe_load(Qwen3ASR, 'ASR')
            if err:
                return None, err

        if not audio_file_path or not Path(audio_file_path).exists():
            return None, '音频文件不存在'

        text = self.asr.recognize(audio_file_path)
        return text, None

    def vlm_analyze_image(self, image_file_path: str):
        if self.vlm is None:
            from ai_interface import Qwen3VLAnalyzer
            self.vlm, err = self._safe_load(Qwen3VLAnalyzer, 'VLM')
            if err:
                return None, err

        if not image_file_path or not Path(image_file_path).exists():
            return None, '图片文件不存在'

        result = self.vlm.analyze_kline(image_file_path)
        return result, None

    def vlm_analyze_kline(self, image_file_path: str):
        """K线图专项分析（复用VLM图像分析能力）。"""
        return self.vlm_analyze_image(image_file_path)

    def vlm_analyze_market(self, payload: dict):
        if self.vlm is None:
            from ai_interface import Qwen3VLAnalyzer
            self.vlm, err = self._safe_load(Qwen3VLAnalyzer, 'VLM')
            if err:
                return None, err

        result = self.vlm.analyze_market(payload)
        return result, None

    def generate_market_brief_image(self, market_data: Dict, news_lines: List[str], title: str = '积存金行情快报'):
        if self.image_generator is None:
            from ai_interface import MarketImageGenerator
            self.image_generator = MarketImageGenerator(output_dir=str(AI_OUTPUT_DIR))

        output_name, warn = self.image_generator.generate_market_brief(
            market_data=market_data,
            news_lines=news_lines,
            title=title,
        )
        return output_name, warn


class APIServer:
    """API 服务器"""
    
    def __init__(self):
        self.proxy = find_working_proxy()
        self.ai_bridge = AIInterfaceBridge()
        self.rate_limit_per_minute = int(os.getenv('API_RATE_LIMIT_PER_MINUTE', '120'))
        self._rate_limit_hits = {}
        self._rate_limit_lock = threading.Lock()
        self.rate_limit_ip_whitelist = self._load_rate_limit_ip_whitelist()
        
        # 初始化各服务
        self.traders = {
            'zheshang': JijinTrader(bank='zheshang', proxy=self.proxy),
            'minsheng': JijinTrader(bank='minsheng', proxy=self.proxy)
        }
        self.trade_manager = TradeManager()
        self.kline_service = KlineService(proxy=self.proxy)
        self.alert_service = AlertService()
        self.backtest_service = BacktestService()
        self.openclaw = self._init_openclaw()
        self._kline_recorder_started = False
        self.enable_internal_kline_recorder = os.getenv('ENABLE_INTERNAL_KLINE_RECORDER', '1') == '1'
        
        # 注册预警回调
        self.alert_service.register_callback(AlertNotifier.console_notify)
        
        # 创建 Flask 应用
        self.app = Flask(__name__)
        self.app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE_BYTES
        CORS(self.app)

        @self.app.errorhandler(RequestEntityTooLarge)
        def _handle_large_upload(_):
            return self._error_response(
                code='UPLOAD_TOO_LARGE',
                message='上传文件过大，限制为 20MB',
                http_status=413,
            )

        @self.app.errorhandler(Exception)
        def _handle_exception(exc):
            if isinstance(exc, HTTPException):
                return self._error_response(
                    code='HTTP_ERROR',
                    message=exc.description or '请求失败',
                    http_status=exc.code or 500,
                )

            if isinstance(exc, TimeoutError):
                return self._error_response(
                    code='RESOURCE_LOCK_TIMEOUT',
                    message='系统资源繁忙，请稍后重试',
                    http_status=503,
                )

            logger.error('unhandled exception request_id=%s error=%s\n%s', getattr(g, 'request_id', '-'), exc, traceback.format_exc())
            return self._error_response(
                code='INTERNAL_ERROR',
                message='服务器内部错误',
                http_status=500,
            )

        @self.app.before_request
        def _before_request_middleware():
            g.request_id = request.headers.get('X-Request-ID') or uuid.uuid4().hex[:12]
            g._audit_start = time.perf_counter()
            g._audit_ip = self._get_client_ip()

            retry_after = self._check_rate_limit(g._audit_ip, request.path)
            if retry_after is None:
                return None

            logger.warning(
                'rate-limit blocked request_id=%s ip=%s method=%s path=%s retry_after=%ss',
                g.request_id,
                g._audit_ip,
                request.method,
                request.path,
                retry_after,
            )
            resp, _ = self._error_response(
                code='RATE_LIMIT_EXCEEDED',
                message='请求过于频繁，请稍后重试',
                http_status=429,
                details={'retry_after_seconds': retry_after},
            )
            resp.status_code = 429
            resp.headers['Retry-After'] = str(retry_after)
            return resp

        @self.app.after_request
        def _after_request_middleware(response):
            response = self._normalize_error_response(response)
            response.headers['X-Request-ID'] = getattr(g, 'request_id', '-')

            start = getattr(g, '_audit_start', None)
            duration_ms = (time.perf_counter() - start) * 1000 if start is not None else -1
            ip = getattr(g, '_audit_ip', self._get_client_ip())
            logger.info(
                'audit request_id=%s ip=%s method=%s path=%s status=%s duration_ms=%.2f ua=%s',
                getattr(g, 'request_id', '-'),
                ip,
                request.method,
                request.path,
                response.status_code,
                duration_ms,
                (request.user_agent.string or '-'),
            )
            return response
        
        self._setup_routes()
        if self.enable_internal_kline_recorder:
            self._start_kline_recorder()
        else:
            logger.info('内部K线采集线程已禁用，请使用独立采集进程')

    def _load_rate_limit_ip_whitelist(self):
        raw = os.getenv('API_RATE_LIMIT_IP_WHITELIST', '')
        items = {x.strip() for x in raw.split(',') if x.strip()}
        items.update({'127.0.0.1', '::1', 'localhost'})
        return items

    def _error_response(self, code: str, message: str, http_status: int, details: dict = None):
        payload = {
            'success': False,
            'code': code,
            'message': message,
            'request_id': getattr(g, 'request_id', '-'),
        }
        if details:
            payload['details'] = details
        return jsonify(payload), http_status

    def _normalize_error_response(self, response):
        if response.status_code < 400:
            return response
        if not response.content_type or 'application/json' not in response.content_type.lower():
            return response

        payload = response.get_json(silent=True)
        if not isinstance(payload, dict):
            return response
        if 'code' in payload and 'message' in payload:
            return response

        message = payload.get('error') or payload.get('message') or '请求失败'
        status = response.status_code
        default_codes = {
            400: 'BAD_REQUEST',
            401: 'UNAUTHORIZED',
            403: 'FORBIDDEN',
            404: 'NOT_FOUND',
            413: 'PAYLOAD_TOO_LARGE',
            429: 'RATE_LIMIT_EXCEEDED',
            500: 'INTERNAL_ERROR',
            503: 'SERVICE_UNAVAILABLE',
        }
        code = payload.get('code') or default_codes.get(status, 'REQUEST_FAILED')
        details = {k: v for k, v in payload.items() if k not in {'error', 'message', 'code', 'success'}}
        normalized = {
            'success': False,
            'code': code,
            'message': message,
            'request_id': getattr(g, 'request_id', '-'),
        }
        if details:
            normalized['details'] = details

        rebuilt = jsonify(normalized)
        rebuilt.status_code = status
        return rebuilt

    def _get_client_ip(self):
        forwarded_for = request.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip() or 'unknown'
        return request.remote_addr or 'unknown'

    def _resolve_rate_limit_per_minute(self, path: str):
        for prefix, limit in RATE_LIMIT_PATH_TIERS:
            if path.startswith(prefix):
                return limit, prefix
        return self.rate_limit_per_minute, 'default'

    def _check_rate_limit(self, client_ip: str, path: str):
        if path in RATE_LIMIT_EXEMPT_PATHS or client_ip in self.rate_limit_ip_whitelist:
            return None

        limit_per_minute, bucket = self._resolve_rate_limit_per_minute(path)
        if limit_per_minute <= 0:
            return None

        now = time.time()
        window_start = now - 60
        key = f'{client_ip}:{bucket}'
        with self._rate_limit_lock:
            recent_hits = self._rate_limit_hits.get(key, [])
            recent_hits = [ts for ts in recent_hits if ts >= window_start]

            if len(recent_hits) >= limit_per_minute:
                earliest = min(recent_hits) if recent_hits else now
                retry_after = max(1, int(60 - (now - earliest)))
                self._rate_limit_hits[key] = recent_hits
                return retry_after

            recent_hits.append(now)
            self._rate_limit_hits[key] = recent_hits
            return None

    def _validate_suffix(self, filename: str, default_suffix: str, allowed_suffixes: set):
        suffix = Path(filename or '').suffix.lower() or default_suffix
        if suffix not in allowed_suffixes:
            return None
        return suffix

    def _save_uploaded_file(self, file_obj, prefix: str, default_suffix: str, allowed_suffixes: set):
        suffix = self._validate_suffix(getattr(file_obj, 'filename', ''), default_suffix, allowed_suffixes)
        if suffix is None:
            return None, '不支持的文件类型'

        fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        os.close(fd)
        file_obj.save(temp_path)
        return temp_path, None

    def _resolve_artifact_path(self, filename: str):
        suffix = Path(filename or '').suffix.lower()
        if suffix not in ALLOWED_ARTIFACT_EXTENSIONS:
            return None

        base_dir = AI_OUTPUT_DIR.resolve()
        candidate = (base_dir / filename).resolve()
        if candidate.parent != base_dir:
            return None
        return candidate

    def _validate_bank(self, bank: str):
        if bank not in SUPPORTED_BANKS:
            return jsonify({'error': 'Invalid bank'}), 400
        return None

    def _parse_bounded_int(self, raw_value, field_name: str, minimum: int, maximum: int, default: int):
        if raw_value is None:
            return default, None
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return None, (jsonify({'error': f'{field_name} must be an integer'}), 400)

        if value < minimum or value > maximum:
            return None, (jsonify({'error': f'{field_name} out of range [{minimum}, {maximum}]'}), 400)
        return value, None

    def _parse_bounded_float(self, raw_value, field_name: str, minimum: float, maximum: float, default: float):
        if raw_value is None:
            return default, None
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None, (jsonify({'error': f'{field_name} must be a number'}), 400)

        if value < minimum or value > maximum:
            return None, (jsonify({'error': f'{field_name} out of range [{minimum}, {maximum}]'}), 400)
        return value, None

    def _kline_recorder_loop(self):
        """后台定时记录金价，保证 K 线时间连续且实时。"""
        while True:
            for bank in ['zheshang', 'minsheng']:
                try:
                    self.kline_service.record_price(bank)
                except Exception as e:
                    logger.warning('K线记录失败(%s): %s', bank, e)
            time.sleep(30)

    def _start_kline_recorder(self):
        if self._kline_recorder_started:
            return
        t = threading.Thread(target=self._kline_recorder_loop, daemon=True)
        t.start()
        self._kline_recorder_started = True

    def _build_market_payload(self) -> Dict:
        payload = {}
        for bank in ['zheshang', 'minsheng']:
            quote = self.traders[bank].get_quote() or {}
            summary = self.traders[bank].get_summary() or {}
            payload[bank] = {
                'price': quote.get('price'),
                'change_rate': quote.get('change_rate'),
                'position': summary.get('position'),
            }
        return payload

    def _build_market_news(self, payload: Dict) -> List[str]:
        lines = []
        for bank, info in payload.items():
            name = '浙商积存金' if bank == 'zheshang' else '民生积存金'
            price = info.get('price', 'N/A')
            change = str(info.get('change_rate', 'N/A'))
            lines.append(f'{name} 当前 {price} 元/克，涨跌 {change}')

            try:
                value = float(change.replace('%', ''))
                if value >= 0.5:
                    lines.append(f'{name} 短线动能偏强，关注冲高回落风险')
                elif value <= -0.5:
                    lines.append(f'{name} 波动下行，建议控制仓位')
            except ValueError:
                pass

        lines.append('国际贵金属市场受宏观数据预期影响，波动可能放大')
        lines.append('建议结合 K 线形态与仓位情况进行分步决策')
        return lines

    def _init_openclaw(self):
        if JijinOpenClaw is None:
            logger.warning('OpenClaw 集成模块不可用，/api/ai/chat 将回退到常规行情分析')
            return None

        try:
            return JijinOpenClaw(proxy=self.proxy)
        except Exception as e:
            logger.warning('OpenClaw 初始化失败，将回退到常规行情分析: %s', e)
            return None

    def _build_openclaw_flow(self) -> Dict:
        flow = {
            'timestamp': datetime.now().isoformat(),
            'prices': {},
            'positions': {},
            'alerts': [],
            'recent_notifications': [],
            'recent_trades': [],
        }

        for bank in ['zheshang', 'minsheng']:
            quote = {}
            summary = {}

            if self.openclaw is not None:
                try:
                    quote = self.openclaw.price_feed.get_price(bank) or {}
                except Exception:
                    quote = {}

                try:
                    summary = self.openclaw.traders[bank].get_summary() or {}
                except Exception:
                    summary = {}

                try:
                    alert = self.openclaw.check_price_change(bank)
                    if alert:
                        flow['alerts'].append(alert)
                except Exception:
                    pass

            if not quote:
                quote = self.traders[bank].get_quote() or {}
            if not summary:
                summary = self.traders[bank].get_summary() or {}

            flow['prices'][bank] = {
                'name': quote.get('name') or ('浙商积存金' if bank == 'zheshang' else '民生积存金'),
                'price': quote.get('price'),
                'change_rate': quote.get('change_rate'),
                'datetime': quote.get('datetime'),
            }
            flow['positions'][bank] = {
                'position': summary.get('position'),
                'avg_price': summary.get('avg_price'),
                'unrealized_pnl': summary.get('unrealized_pnl'),
                'realized_pnl': summary.get('realized_pnl'),
            }

        if self.openclaw is not None:
            flow['recent_notifications'] = self.openclaw.notifications[-8:]

        try:
            all_trades = self.trade_manager.get_all_trades()
        except Exception:
            all_trades = []

        for t in all_trades[-5:]:
            flow['recent_trades'].append({
                'time': str(getattr(t, 'time', '')),
                'bank': getattr(t, 'bank', ''),
                'action': getattr(t, 'action', ''),
                'price': getattr(t, 'price', None),
                'grams': getattr(t, 'grams', None),
                'profit': getattr(t, 'profit', None),
            })

        return flow

    def _build_openclaw_brief(self, openclaw_flow: Dict) -> str:
        alerts = openclaw_flow.get('alerts') or []
        trades = openclaw_flow.get('recent_trades') or []
        lines = []

        if alerts:
            alert_msgs = [x.get('message', '') for x in alerts[:2] if x.get('message')]
            if alert_msgs:
                lines.append('预警: ' + ' | '.join(alert_msgs))
        if not lines:
            lines.append('预警: 暂无明显异常波动')

        if trades:
            last_trade = trades[-1]
            action_raw = str(last_trade.get('action', '')).upper()
            if action_raw == 'BUY':
                action = '买入'
            elif action_raw == 'SELL':
                action = '卖出'
            else:
                action = '未知动作'
            lines.append(
                f"最近交易: {last_trade.get('bank', '-')}/{action} {last_trade.get('grams', '-')}克 @ {last_trade.get('price', '-')}"
            )
        else:
            lines.append('最近交易: 暂无新成交记录')

        return '\n'.join(lines)
    
    def _setup_routes(self):
        """设置路由"""
        
        # ========== 健康检查 ==========
        @self.app.route('/api/health')
        def health():
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
                'version': '2.0'
            })
        
        # ========== 价格相关 ==========
        @self.app.route('/api/prices')
        def get_prices():
            """获取所有银行价格"""
            prices = {}
            for bank, trader in self.traders.items():
                quote = trader.get_quote()
                if quote:
                    prices[bank] = {
                        'bank': bank,
                        'name': quote['name'],
                        'price': quote['price'],
                        'yesterday_price': quote['yesterday_price'],
                        'change_amt': quote['change_amt'],
                        'change_rate': quote['change_rate'],
                        'datetime': quote['datetime'],
                        'is_trading': trader.is_trading_time()
                    }
            return jsonify(prices)
        
        @self.app.route('/api/prices/<bank>')
        def get_price(bank):
            """获取指定银行价格"""
            bank_error = self._validate_bank(bank)
            if bank_error:
                return bank_error
            
            trader = self.traders[bank]
            quote = trader.get_quote()
            
            if not quote:
                return jsonify({'error': 'Failed to fetch price'}), 500
            
            return jsonify({
                'bank': bank,
                'name': quote['name'],
                'price': quote['price'],
                'yesterday_price': quote['yesterday_price'],
                'change_amt': quote['change_amt'],
                'change_rate': quote['change_rate'],
                'datetime': quote['datetime'],
                'is_trading': trader.is_trading_time()
            })
        
        # ========== 持仓相关 ==========
        @self.app.route('/api/positions')
        def get_positions():
            """获取所有持仓"""
            positions = {}
            for bank, trader in self.traders.items():
                positions[bank] = trader.get_summary()
            return jsonify(positions)
        
        @self.app.route('/api/positions/<bank>')
        def get_position(bank):
            """获取指定银行持仓"""
            bank_error = self._validate_bank(bank)
            if bank_error:
                return bank_error
            return jsonify(self.traders[bank].get_summary())
        
        # ========== 交易相关 ==========
        @self.app.route('/api/trades')
        def get_trades():
            """获取交易记录"""
            bank = request.args.get('bank')
            action = request.args.get('action')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            if bank:
                bank_error = self._validate_bank(bank)
                if bank_error:
                    return bank_error
            
            trades = self.trade_manager.filter_trades(
                bank=bank,
                action=action,
                start_date=start_date,
                end_date=end_date
            )
            
            return jsonify({
                'count': len(trades),
                'trades': [t.to_dict() for t in trades]
            })
        
        @self.app.route('/api/trades/stats')
        def get_trade_stats():
            """获取交易统计"""
            bank = request.args.get('bank')
            if bank:
                bank_error = self._validate_bank(bank)
                if bank_error:
                    return bank_error
            stats = self.trade_manager.get_trade_stats(bank)
            return jsonify(stats)
        
        @self.app.route('/api/trades/daily')
        def get_daily_trades():
            """获取每日交易汇总"""
            days, parse_error = self._parse_bounded_int(
                raw_value=request.args.get('days'),
                field_name='days',
                minimum=1,
                maximum=365,
                default=30,
            )
            if parse_error:
                return parse_error
            summary = self.trade_manager.get_daily_summary(days)
            return jsonify(summary)
        
        @self.app.route('/api/trades/export', methods=['POST'])
        def export_trades():
            """导出交易记录"""
            bank = request.json.get('bank') if request.json else None
            if bank:
                bank_error = self._validate_bank(bank)
                if bank_error:
                    return bank_error
            filename = self.trade_manager.export_to_csv(bank)
            return jsonify({
                'success': True,
                'filename': filename,
                'message': f'已导出到 {filename}'
            })
        
        # ========== K 线数据 ==========
        @self.app.route('/api/kline/<bank>')
        def get_kline(bank):
            """获取 K 线数据"""
            bank_error = self._validate_bank(bank)
            if bank_error:
                return bank_error
            
            period = request.args.get('period', '1m')
            if period not in SUPPORTED_KLINE_PERIODS:
                return jsonify({'error': 'Invalid period'}), 400

            limit, parse_error = self._parse_bounded_int(
                raw_value=request.args.get('limit'),
                field_name='limit',
                minimum=1,
                maximum=1000,
                default=100,
            )
            if parse_error:
                return parse_error
            klines = self.kline_service.get_kline_data(bank, period, limit)
            if not klines:
                # 历史为空时做一次补采，避免首次查询返回空列表。
                self.kline_service.record_price(bank)
                klines = self.kline_service.get_kline_data(bank, period, limit)
            return jsonify({
                'bank': bank,
                'period': period,
                'count': len(klines),
                'data': klines
            })
        
        @self.app.route('/api/kline/<bank>/indicators')
        def get_indicators(bank):
            """获取技术指标"""
            bank_error = self._validate_bank(bank)
            if bank_error:
                return bank_error
            
            indicators = self.kline_service.get_technical_indicators(bank)
            return jsonify(indicators)
        
        @self.app.route('/api/kline/<bank>/realtime')
        def get_realtime_kline(bank):
            """获取实时 K 线"""
            bank_error = self._validate_bank(bank)
            if bank_error:
                return bank_error
            
            kline = self.kline_service.get_realtime_kline(bank)
            if not kline:
                return jsonify({'error': 'Failed to fetch data'}), 500
            
            return jsonify(kline)
        
        # ========== 预警相关 ==========
        @self.app.route('/api/alerts/rules')
        def get_alert_rules():
            """获取预警规则"""
            bank = request.args.get('bank')
            enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'

            if bank:
                bank_error = self._validate_bank(bank)
                if bank_error:
                    return bank_error
            
            rules = self.alert_service.get_rules(bank, enabled_only)
            return jsonify([{
                'id': r.id,
                'name': r.name,
                'bank': r.bank,
                'alert_type': r.alert_type,
                'threshold': r.threshold,
                'enabled': r.enabled,
                'created_at': r.created_at,
                'triggered_at': r.triggered_at,
                'triggered_count': r.triggered_count,
                'cooldown_minutes': r.cooldown_minutes
            } for r in rules])
        
        @self.app.route('/api/alerts/rules', methods=['POST'])
        def add_alert_rule():
            """添加预警规则"""
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            required = ['name', 'bank', 'alert_type', 'threshold']
            for field in required:
                if field not in data:
                    return jsonify({'error': f'Missing field: {field}'}), 400

            bank_error = self._validate_bank(data['bank'])
            if bank_error:
                return bank_error
            
            rule = self.alert_service.add_rule(
                name=data['name'],
                bank=data['bank'],
                alert_type=data['alert_type'],
                threshold=data['threshold'],
                cooldown_minutes=data.get('cooldown_minutes', 60)
            )
            
            return jsonify({
                'success': True,
                'rule': {
                    'id': rule.id,
                    'name': rule.name,
                    'bank': rule.bank,
                    'alert_type': rule.alert_type,
                    'threshold': rule.threshold,
                    'enabled': rule.enabled
                }
            })
        
        @self.app.route('/api/alerts/rules/<rule_id>', methods=['DELETE'])
        def delete_alert_rule(rule_id):
            """删除预警规则"""
            if self.alert_service.remove_rule(rule_id):
                return jsonify({'success': True})
            return jsonify({'error': 'Rule not found'}), 404
        
        @self.app.route('/api/alerts/rules/<rule_id>/toggle', methods=['POST'])
        def toggle_alert_rule(rule_id):
            """启用/禁用预警规则"""
            data = request.json or {}
            enabled = data.get('enabled', True)
            
            if self.alert_service.enable_rule(rule_id, enabled):
                return jsonify({'success': True, 'enabled': enabled})
            return jsonify({'error': 'Rule not found'}), 404
        
        @self.app.route('/api/alerts/history')
        def get_alert_history():
            """获取预警历史"""
            bank = request.args.get('bank')
            if bank:
                bank_error = self._validate_bank(bank)
                if bank_error:
                    return bank_error

            limit, parse_error = self._parse_bounded_int(
                raw_value=request.args.get('limit'),
                field_name='limit',
                minimum=1,
                maximum=500,
                default=50,
            )
            if parse_error:
                return parse_error
            
            history = self.alert_service.get_history(bank, limit)
            return jsonify(history)
        
        @self.app.route('/api/alerts/check', methods=['POST'])
        def check_alerts():
            """手动检查预警"""
            data = request.json or {}

            bank = data.get('bank', 'zheshang')
            bank_error = self._validate_bank(bank)
            if bank_error:
                return bank_error
            
            # 获取价格数据
            price_data = {
                'bank': bank,
                'price': data.get('price', 0),
                'change_rate': data.get('change_rate', 0),
                'ma5': data.get('ma5', 0),
                'ma10': data.get('ma10', 0)
            }
            
            alerts = self.alert_service.check_price_alert(price_data)
            
            if alerts:
                self.alert_service.notify(alerts)
            
            return jsonify({
                'triggered': len(alerts) > 0,
                'alerts': alerts
            })
        
        # ========== 回测相关 ==========
        @self.app.route('/api/backtest/strategies')
        def get_backtest_strategies():
            """获取支持的回测策略"""
            return jsonify({
                'strategies': [
                    {'id': 'grid', 'name': '网格策略', 'description': '低买高卖的网格交易策略'},
                    {'id': 'trend', 'name': '趋势策略', 'description': '基于均线突破的趋势跟踪'},
                    {'id': 'dca', 'name': '定投策略', 'description': '定期定额投资'},
                    {'id': 'compare', 'name': '策略对比', 'description': '对比所有策略表现'}
                ]
            })
        
        @self.app.route('/api/backtest/run', methods=['POST'])
        def run_backtest():
            """运行策略回测"""
            data = request.json or {}
            strategy = data.get('strategy', 'grid')
            if strategy not in SUPPORTED_BACKTEST_STRATEGIES:
                return jsonify({'error': 'Unknown strategy'}), 400

            days, parse_error = self._parse_bounded_int(
                raw_value=data.get('days'),
                field_name='days',
                minimum=1,
                maximum=3650,
                default=90,
            )
            if parse_error:
                return parse_error

            initial_balance, parse_error = self._parse_bounded_float(
                raw_value=data.get('initial_balance'),
                field_name='initial_balance',
                minimum=1,
                maximum=1_000_000_000,
                default=100000,
            )
            if parse_error:
                return parse_error
            
            # 生成模拟数据
            price_data = self.backtest_service.generate_mock_data(days=days)
            
            if strategy == 'compare':
                results = self.backtest_service.compare_strategies(price_data, initial_balance)
                return jsonify({
                    'strategy': 'compare',
                    'days': days,
                    'initial_balance': initial_balance,
                    'results': results
                })
            
            try:
                if strategy == 'grid':
                    result = self.backtest_service.backtest_grid_strategy(
                        price_data, initial_balance
                    )
                elif strategy == 'trend':
                    result = self.backtest_service.backtest_trend_strategy(
                        price_data, initial_balance
                    )
                elif strategy == 'dca':
                    result = self.backtest_service.backtest_dca_strategy(
                        price_data, initial_balance
                    )
                
                return jsonify({
                    'strategy': strategy,
                    'strategy_name': result.strategy_name,
                    'start_date': result.start_date,
                    'end_date': result.end_date,
                    'initial_balance': result.initial_balance,
                    'final_balance': result.final_balance,
                    'final_position': result.final_position,
                    'total_trades': result.total_trades,
                    'total_fees': result.total_fees,
                    'total_profit': result.total_profit,
                    'max_drawdown': result.max_drawdown,
                    'return_rate': round(result.total_profit / result.initial_balance * 100, 2),
                    'trades_count': len(result.trades),
                    'daily_returns_count': len(result.daily_returns)
                })
            
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/backtest/result/<strategy>', methods=['POST'])
        def get_backtest_detail(strategy):
            """获取回测详细结果"""
            if strategy not in SUPPORTED_BACKTEST_DETAIL_STRATEGIES:
                return jsonify({'error': 'Unknown strategy'}), 400

            data = request.json or {}
            days, parse_error = self._parse_bounded_int(
                raw_value=data.get('days'),
                field_name='days',
                minimum=1,
                maximum=3650,
                default=90,
            )
            if parse_error:
                return parse_error

            initial_balance, parse_error = self._parse_bounded_float(
                raw_value=data.get('initial_balance'),
                field_name='initial_balance',
                minimum=1,
                maximum=1_000_000_000,
                default=100000,
            )
            if parse_error:
                return parse_error
            
            price_data = self.backtest_service.generate_mock_data(days=days)
            
            try:
                if strategy == 'grid':
                    result = self.backtest_service.backtest_grid_strategy(
                        price_data, initial_balance
                    )
                elif strategy == 'trend':
                    result = self.backtest_service.backtest_trend_strategy(
                        price_data, initial_balance
                    )
                elif strategy == 'dca':
                    result = self.backtest_service.backtest_dca_strategy(
                        price_data, initial_balance
                    )
                
                return jsonify({
                    'strategy': strategy,
                    'summary': {
                        'strategy_name': result.strategy_name,
                        'start_date': result.start_date,
                        'end_date': result.end_date,
                        'initial_balance': result.initial_balance,
                        'final_balance': result.final_balance,
                        'total_profit': result.total_profit,
                        'return_rate': round(result.total_profit / result.initial_balance * 100, 2),
                        'total_trades': result.total_trades,
                        'max_drawdown': result.max_drawdown
                    },
                    'trades': result.trades[:100],  # 限制返回数量
                    'daily_returns': result.daily_returns
                })
            
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # ========== 综合数据 ==========
        @self.app.route('/api/dashboard')
        def get_dashboard_data():
            """获取 Dashboard 综合数据"""
            data = {
                'timestamp': datetime.now().isoformat(),
                'prices': {},
                'positions': {},
                'stats': self.trade_manager.get_trade_stats()
            }
            
            for bank in ['zheshang', 'minsheng']:
                # 价格
                quote = self.traders[bank].get_quote()
                if quote:
                    data['prices'][bank] = {
                        'price': quote['price'],
                        'change_rate': quote['change_rate'],
                        'is_trading': self.traders[bank].is_trading_time()
                    }
                
                # 持仓
                data['positions'][bank] = self.traders[bank].get_summary()
            
            return jsonify(data)

        # ========== AI 多场景 ==========
        @self.app.route('/api/ai/capabilities')
        def get_ai_capabilities():
            """获取 AI 能力加载状态。"""
            try:
                caps = self.ai_bridge.get_capabilities()
                return jsonify({'success': True, 'capabilities': caps})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/ai/tts', methods=['POST'])
        def ai_tts():
            """文本转语音，返回可下载音频 URL。"""
            data = request.json or {}
            text = data.get('text', '')
            output_name, err = self.ai_bridge.tts_synthesize(text)
            if err:
                return jsonify({'success': False, 'error': err}), 400

            return jsonify({
                'success': True,
                'audio_file': output_name,
                'audio_url': f'/api/ai/artifacts/{output_name}'
            })

        @self.app.route('/api/ai/asr', methods=['POST'])
        def ai_asr():
            """语音识别，支持文件上传或本地路径。"""
            audio_file_path = None
            temp_file_path = None

            try:
                if 'audio' in request.files:
                    audio = request.files['audio']
                    temp_file_path, err = self._save_uploaded_file(
                        file_obj=audio,
                        prefix='asr_upload_',
                        default_suffix='.wav',
                        allowed_suffixes=ALLOWED_AUDIO_EXTENSIONS,
                    )
                    if err:
                        return jsonify({'success': False, 'error': err}), 400
                    audio_file_path = temp_file_path
                else:
                    data = request.json or {}
                    audio_file_path = data.get('audio_path', '')

                text, err = self.ai_bridge.asr_recognize(audio_file_path)
                if err:
                    return jsonify({'success': False, 'error': err}), 400
                return jsonify({'success': True, 'text': text})
            finally:
                if temp_file_path and Path(temp_file_path).exists():
                    try:
                        os.remove(temp_file_path)
                    except OSError:
                        pass

        @self.app.route('/api/ai/vlm/image', methods=['POST'])
        def ai_vlm_image():
            """VLM 图像分析，支持图片上传或本地路径。"""
            image_file_path = None
            temp_file_path = None

            try:
                if 'image' in request.files:
                    image = request.files['image']
                    temp_file_path, err = self._save_uploaded_file(
                        file_obj=image,
                        prefix='vlm_upload_',
                        default_suffix='.png',
                        allowed_suffixes=ALLOWED_IMAGE_EXTENSIONS,
                    )
                    if err:
                        return jsonify({'success': False, 'error': err}), 400
                    image_file_path = temp_file_path
                else:
                    data = request.json or {}
                    image_file_path = data.get('image_path', '')

                result, err = self.ai_bridge.vlm_analyze_image(image_file_path)
                if err:
                    return jsonify({'success': False, 'error': err}), 400
                return jsonify({'success': True, 'result': result})
            finally:
                if temp_file_path and Path(temp_file_path).exists():
                    try:
                        os.remove(temp_file_path)
                    except OSError:
                        pass

        @self.app.route('/api/ai/vlm/kline', methods=['POST'])
        def ai_vlm_kline():
            """K线图专项理解接口。"""
            image_file_path = None
            temp_file_path = None

            try:
                if 'image' in request.files:
                    image = request.files['image']
                    temp_file_path, err = self._save_uploaded_file(
                        file_obj=image,
                        prefix='vlm_kline_',
                        default_suffix='.png',
                        allowed_suffixes=ALLOWED_IMAGE_EXTENSIONS,
                    )
                    if err:
                        return jsonify({'success': False, 'error': err}), 400
                    image_file_path = temp_file_path
                else:
                    data = request.json or {}
                    image_file_path = data.get('image_path', '')

                result, err = self.ai_bridge.vlm_analyze_kline(image_file_path)
                if err:
                    return jsonify({'success': False, 'error': err}), 400
                return jsonify({'success': True, 'result': result})
            finally:
                if temp_file_path and Path(temp_file_path).exists():
                    try:
                        os.remove(temp_file_path)
                    except OSError:
                        pass

        @self.app.route('/api/ai/vlm/market', methods=['POST'])
        def ai_vlm_market():
            """VLM 市场文本分析。"""
            payload = request.json or {}

            if not payload:
                payload = self._build_market_payload()

            result, err = self.ai_bridge.vlm_analyze_market(payload)
            if err:
                return jsonify({'success': False, 'error': err}), 400
            return jsonify({'success': True, 'result': result, 'input': payload})

        @self.app.route('/api/ai/image/brief', methods=['POST'])
        def ai_market_brief_image():
            """图像生成：生成行情快报图（新闻+价格）。"""
            data = request.json or {}
            payload = data.get('market_data') or self._build_market_payload()
            news_lines = data.get('news_lines') or self._build_market_news(payload)
            title = data.get('title') or '积存金行情快报'

            try:
                output_name, warn = self.ai_bridge.generate_market_brief_image(
                    market_data=payload,
                    news_lines=news_lines,
                    title=title,
                )
            except Exception as e:
                return jsonify({'success': False, 'error': f'图像生成失败: {e}'}), 500

            return jsonify({
                'success': True,
                'image_file': output_name,
                'image_url': f'/api/ai/artifacts/{output_name}',
                'news_lines': news_lines,
                'warning': warn,
            })

        @self.app.route('/api/ai/chat', methods=['POST'])
        def ai_chat():
            """语音/文本交互统一入口，支持可选图片理解。"""
            message = ''
            temp_file_path = None
            image_file_path = None
            image_result = None

            try:
                if request.content_type and 'multipart/form-data' in request.content_type:
                    message = request.form.get('message', '').strip()
                    if 'image' in request.files:
                        image = request.files['image']
                        temp_file_path, err = self._save_uploaded_file(
                            file_obj=image,
                            prefix='ai_chat_',
                            default_suffix='.png',
                            allowed_suffixes=ALLOWED_IMAGE_EXTENSIONS,
                        )
                        if err:
                            return jsonify({'success': False, 'error': err}), 400
                        image_file_path = temp_file_path
                else:
                    data = request.json or {}
                    message = (data.get('message') or '').strip()
                    image_file_path = data.get('image_path', '')

                if image_file_path:
                    image_result, err = self.ai_bridge.vlm_analyze_image(image_file_path)
                    if err:
                        return jsonify({'success': False, 'error': err}), 400

                payload = self._build_market_payload()
                openclaw_flow = self._build_openclaw_flow()
                analysis_payload = {
                    'user_message': message,
                    'market_payload': payload,
                    'openclaw_flow': openclaw_flow,
                }
                market_result, err = self.ai_bridge.vlm_analyze_market(analysis_payload)
                if err:
                    # VLM 不可用时回退到简要文本
                    openclaw_brief = self._build_openclaw_brief(openclaw_flow)
                    market_result = (
                        f"当前浙商价格 {payload['zheshang'].get('price')} 元/克，"
                        f"民生价格 {payload['minsheng'].get('price')} 元/克。\n{openclaw_brief}"
                    )

                reply_parts = []
                if message:
                    reply_parts.append(f'你的问题: {message}')
                reply_parts.append('OpenClaw 信息流:')
                reply_parts.append(self._build_openclaw_brief(openclaw_flow))
                reply_parts.append('行情分析:')
                reply_parts.append(market_result)

                if image_result:
                    reply_parts.append('图片理解:')
                    reply_parts.append(image_result)

                reply_text = '\n'.join(reply_parts)

                image_url = None
                keywords = ['快报', '海报', '图片', '图像生成', '行情图']
                if any(k in message for k in keywords):
                    news_lines = self._build_market_news(payload)
                    output_name, _ = self.ai_bridge.generate_market_brief_image(
                        market_data=payload,
                        news_lines=news_lines,
                        title='积存金行情快报',
                    )
                    image_url = f'/api/ai/artifacts/{output_name}'
                    reply_text += f"\n\n已为你生成行情快报图: {image_url}"

                return jsonify({
                    'success': True,
                    'reply': reply_text,
                    'market_input': payload,
                    'openclaw_flow': openclaw_flow,
                    'image_analysis': image_result,
                    'image_url': image_url,
                })
            finally:
                if temp_file_path and Path(temp_file_path).exists():
                    try:
                        os.remove(temp_file_path)
                    except OSError:
                        pass

        @self.app.route('/api/ai/artifacts/<filename>')
        def ai_artifact(filename):
            """下载/播放 AI 生成产物（例如 TTS 音频）。"""
            safe_path = self._resolve_artifact_path(filename)
            if safe_path is None:
                return jsonify({'success': False, 'error': '非法文件名或不支持的文件类型'}), 400

            if not safe_path.exists() or not safe_path.is_file():
                return jsonify({'success': False, 'error': '文件不存在'}), 404
            return send_file(str(safe_path), as_attachment=False)
    
    def run(self, host: str = "0.0.0.0", port: int = 8080):
        """运行服务器"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(name)s - %(message)s'
        )
        logger.info('============================================================')
        logger.info('积存金交易 API 服务器启动')
        logger.info('监听地址: http://%s:%s', host, port)
        logger.info('关键端点: /api/health, /api/dashboard, /api/ai/capabilities')
        logger.info('============================================================')
        
        self.app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='积存金交易 API 服务器')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=8080, help='监听端口')
    
    args = parser.parse_args()
    
    server = APIServer()
    server.run(host=args.host, port=args.port)
