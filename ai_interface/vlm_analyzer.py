#!/usr/bin/env python3
"""
视觉语言分析 (VLM) - 基于 Qwen3-VL + OpenVINO
用于分析K线图并生成交易建议
"""
import os
from pathlib import Path
from typing import Optional
from threading import Thread


class Qwen3VLAnalyzer:
    """Qwen3-VL 视觉语言分析器"""
    
    def __init__(self, model_dir: str = None, device: str = "AUTO"):
        if model_dir is None:
            # 默认使用 models 目录
            model_dir = Path(__file__).resolve().parents[1] / "models" / "Qwen3-VL-4B-Instruct-int4-ov"
        
        self.model_dir = Path(model_dir)
        self.device = device
        self.model = None
        self.processor = None
        self.tokenizer = None
        self.backend = "none"
        self.fallback_reason = None
        self.last_response_mode = "unknown"
        
        self._load_model()
    
    def _load_model(self):
        """加载 OpenVINO 模型"""
        if not self.model_dir.exists():
            print(f"模型不存在: {self.model_dir}")
            print("请从 ModelScope 下载:")
            print("  modelscope download snake7gun/Qwen3-VL-4B-Instruct-int4-ov")
            return
        
        try:
            from optimum.intel.openvino import modeling_visual_language as ov_vlm
            from optimum.intel import OVModelForVisualCausalLM
            try:
                from transformers import AutoProcessor  # type: ignore
            except Exception:
                from transformers.models.auto.processing_auto import AutoProcessor  # type: ignore

            try:
                from transformers import AutoTokenizer  # type: ignore
            except Exception:
                from transformers.models.auto.tokenization_auto import AutoTokenizer  # type: ignore

            # 当前 optimum 版本未声明 qwen3_vl，映射到 qwen2_5_vl 兼容类可正常加载 IR。
            if "qwen3_vl" not in ov_vlm.MODEL_TYPE_TO_CLS_MAPPING and "qwen2_5_vl" in ov_vlm.MODEL_TYPE_TO_CLS_MAPPING:
                ov_vlm.MODEL_TYPE_TO_CLS_MAPPING["qwen3_vl"] = ov_vlm.MODEL_TYPE_TO_CLS_MAPPING["qwen2_5_vl"]
            
            print(f"加载 VLM 模型: {self.model_dir}")
            self.model = OVModelForVisualCausalLM.from_pretrained(
                str(self.model_dir),
                device=self.device,
                trust_remote_code=True,
            )
            self.tokenizer = AutoTokenizer.from_pretrained(
                str(self.model_dir),
                trust_remote_code=True,
            )

            try:
                self.processor = AutoProcessor.from_pretrained(
                    str(self.model_dir),
                    trust_remote_code=True,
                )
            except Exception as proc_err:
                self.processor = None
                print(f"VLM Processor 加载失败，降级文本模式: {proc_err}")

            self.backend = "openvino" if self.processor is not None else "openvino-text"
            print("✓ VLM 模型加载成功")
        except Exception as e:
            self.model = object()
            self.processor = None
            self.tokenizer = None
            self.backend = "fallback"
            self.fallback_reason = str(e)
            print(f"VLM OpenVINO 加载失败，已启用规则分析回退: {e}")

    def _extract_market_context(self, payload: dict):
        """兼容 chat 场景的嵌套结构，抽取市场数据与用户问题。"""
        if not isinstance(payload, dict):
            payload = {}

        market = payload.get('market_payload') if isinstance(payload.get('market_payload'), dict) else payload
        if not isinstance(market, dict):
            market = {}

        user_message = str(payload.get('user_message') or '').strip()
        return market, user_message

    def _stream_generate(self, inputs: dict, tokenizer, max_new_tokens: int = 256):
        """基于 TextIteratorStreamer 进行模型级 token 流输出。"""
        try:
            from transformers import TextIteratorStreamer  # type: ignore
        except Exception:
            from transformers.generation.streamers import TextIteratorStreamer  # type: ignore

        streamer = TextIteratorStreamer(
            tokenizer,
            timeout=600.0,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        gen_kwargs = {
            **inputs,
            'max_new_tokens': max_new_tokens,
            'do_sample': False,
            'streamer': streamer,
        }

        error_holder = {}

        def _target():
            try:
                self.model.generate(**gen_kwargs)
            except Exception as exc:
                error_holder['error'] = exc

        worker = Thread(target=_target, daemon=True)
        worker.start()

        for token in streamer:
            if token:
                yield token

        worker.join(timeout=1.0)
        err = error_holder.get('error')
        if err is not None:
            raise err

    def _build_market_prompt(self, market_data: dict, user_message: str) -> str:
        return (
            "你是积存金助手，请基于行情给出交易建议。\n"
            f"用户问题: {user_message or '给出中性建议'}\n"
            f"浙商: {market_data.get('zheshang', {}).get('price', 'N/A')} 元/克, 涨跌 {market_data.get('zheshang', {}).get('change_rate', 'N/A')}, 持仓 {market_data.get('zheshang', {}).get('position', 'N/A')} 克。\n"
            f"民生: {market_data.get('minsheng', {}).get('price', 'N/A')} 元/克, 涨跌 {market_data.get('minsheng', {}).get('change_rate', 'N/A')}, 持仓 {market_data.get('minsheng', {}).get('position', 'N/A')} 克。\n"
            "回答要求：\n"
            "- 先直接回答用户问题\n"
            "- 若涉及交易动作，再补充操作建议和风险提示（各1句）\n"
            "- 禁止固定编号模板，禁止默认输出重复句\n"
            "- 结论必须是完整句，不能只输出“可/谨慎/不建议”单字\n"
        )

    def analyze_kline_stream(self, kline_image: str):
        """流式分析图片，逐段输出模型 token。"""
        if self.model is None:
            yield "模型未加载"
            return

        if self.backend in {"fallback", "openvino-text"}:
            yield (
                "当前处于文本分析模式（视觉分支暂不可用）。\n"
                "建议: 观察价格重心、长下影线与成交量同步放大情况；"
                "若放量突破前高可小仓试多，若跌破前低需止损控制。"
            )
            return

        if not os.path.exists(kline_image):
            yield f"图片不存在: {kline_image}"
            return

        if self.processor is None:
            yield "图片分析暂不可用：VLM 处理器未加载成功，请检查视觉依赖。"
            return

        from qwen_vl_utils import process_vision_info

        prompt = (
            "请分析这张积存金相关图片，给出：\n"
            "1) 关键信号判断\n"
            "2) 对应交易建议\n"
            "3) 风险提示\n"
            "要求中文、简洁、可执行。"
        )

        image_uri = f"file://{Path(kline_image).resolve().as_posix()}"
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image_uri},
                {"type": "text", "text": prompt},
            ],
        }]

        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )

        for token in self._stream_generate(inputs=inputs, tokenizer=self.processor.tokenizer, max_new_tokens=256):
            yield token

    def analyze_market_stream(self, price_data: dict):
        """流式分析市场文本，逐段输出模型 token。"""
        market_data, user_message = self._extract_market_context(price_data)
        self.last_response_mode = "unknown"

        if self.model is None:
            self.last_response_mode = "unavailable"
            yield "模型未加载"
            return

        if self.backend == "fallback":
            self.last_response_mode = "rule"
            yield self._rule_based_market_analysis(market_data, user_message=user_message)
            return

        tokenizer = self.tokenizer
        if tokenizer is None and self.processor is not None:
            tokenizer = getattr(self.processor, 'tokenizer', None)
        if tokenizer is None:
            self.last_response_mode = "error"
            yield "分析失败: tokenizer/processor 均不可用"
            return

        prompt = self._build_market_prompt(market_data, user_message)
        chat_text = prompt
        if hasattr(tokenizer, 'apply_chat_template'):
            chat_text = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = tokenizer(chat_text, return_tensors='pt')
        self.last_response_mode = "model"
        # 提高回复上限，避免句尾在流式场景中被硬截断。
        for token in self._stream_generate(inputs=inputs, tokenizer=tokenizer, max_new_tokens=128):
            yield token

    def _rule_based_market_analysis(self, market_data: dict, user_message: str = '') -> str:
        zh = market_data.get('zheshang', {})
        ms = market_data.get('minsheng', {})

        def _to_rate(value):
            try:
                return float(str(value).replace('%', '').strip())
            except Exception:
                return 0.0

        zh_rate = _to_rate(zh.get('change_rate', 0))
        ms_rate = _to_rate(ms.get('change_rate', 0))
        avg_rate = (zh_rate + ms_rate) / 2

        if avg_rate >= 0.3:
            trend = "短线偏强"
            advice = "回踩分批买入，避免追高"
        elif avg_rate <= -0.3:
            trend = "短线偏弱"
            advice = "控制仓位，等待企稳信号"
        else:
            trend = "震荡整理"
            advice = "高抛低吸，小仓位试探"

        msg = user_message.lower()
        if any(k in msg for k in ['还能买吗', '能买', '买入', '补仓', '加仓']):
            qa = "针对你的问题: 若分时回踩不破支撑，可小仓分批；若已快速拉升，优先等回落确认。"
        elif any(k in msg for k in ['卖出', '减仓', '止盈', '离场']):
            qa = "针对你的问题: 可采用分批止盈，避免一次性全出；若跌破关键位要执行止损。"
        elif any(k in msg for k in ['拜拜', '再见']):
            qa = "收到，若你稍后继续看盘，建议重点关注波动放大时段。"
        else:
            qa = "策略提示: 先看趋势，再定仓位，严格执行风控。"

        return (
            f"当前两家报价偏{trend}：浙商 {zh.get('price', 'N/A')} 元/克（{zh.get('change_rate', 'N/A')}），"
            f"民生 {ms.get('price', 'N/A')} 元/克（{ms.get('change_rate', 'N/A')}）。\n"
            f"{advice}。{qa}\n"
            "风险提示：关注美元指数与美债收益率波动，避免满仓追涨杀跌。"
        )
    
    def analyze_kline(self, kline_image: str) -> str:
        """
        分析K线图
        
        Args:
            kline_image: K线图图片路径
        
        Returns:
            分析结果文本
        """
        try:
            result = ''.join(self.analyze_kline_stream(kline_image)).strip()
            return result or "模型未返回有效内容"
        except Exception as e:
            return f"分析失败: {e}"
    
    def analyze_market(self, price_data: dict) -> str:
        """
        分析市场数据（文本模式）
        
        Args:
            price_data: 价格数据字典
        
        Returns:
            分析结果
        """
        try:
            result = ''.join(self.analyze_market_stream(price_data)).strip()
            return result or "模型未返回有效内容"
        except Exception as e:
            return f"分析失败: {e}"


if __name__ == "__main__":
    # 测试
    analyzer = Qwen3VLAnalyzer()
    
    # 测试文本分析
    test_data = {
        'zheshang': {'price': 1001, 'change_rate': '-0.45%', 'position': 10},
        'minsheng': {'price': 1001, 'change_rate': '+0.02%', 'position': 0}
    }
    
    result = analyzer.analyze_market(test_data)
    print(f"分析结果:\n{result}")
