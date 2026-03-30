#!/usr/bin/env python3
"""
视觉语言分析 (VLM) - 基于 Qwen3-VL + OpenVINO
用于分析K线图并生成交易建议
"""
import os
from pathlib import Path
from typing import Optional


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
        self.backend = "none"
        self.fallback_reason = None
        
        self._load_model()
    
    def _load_model(self):
        """加载 OpenVINO 模型"""
        if not self.model_dir.exists():
            print(f"模型不存在: {self.model_dir}")
            print("请从 ModelScope 下载:")
            print("  modelscope download snake7gun/Qwen3-VL-4B-Instruct-int4-ov")
            return
        
        try:
            from optimum.intel import OVModelForVisualCausalLM
            from transformers import AutoProcessor
            
            print(f"加载 VLM 模型: {self.model_dir}")
            self.model = OVModelForVisualCausalLM.from_pretrained(
                str(self.model_dir),
                device=self.device,
                trust_remote_code=True,
            )
            self.processor = AutoProcessor.from_pretrained(
                str(self.model_dir),
                trust_remote_code=True,
            )
            self.backend = "openvino"
            print("✓ VLM 模型加载成功")
        except Exception as e:
            self.model = object()
            self.processor = None
            self.backend = "fallback"
            self.fallback_reason = str(e)
            print(f"VLM OpenVINO 加载失败，已启用规则分析回退: {e}")

    def _rule_based_market_analysis(self, price_data: dict) -> str:
        zh = price_data.get('zheshang', {})
        ms = price_data.get('minsheng', {})

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

        return (
            f"市场趋势: {trend}\n"
            f"浙商: {zh.get('price', 'N/A')} 元/克 ({zh.get('change_rate', 'N/A')})\n"
            f"民生: {ms.get('price', 'N/A')} 元/克 ({ms.get('change_rate', 'N/A')})\n"
            f"建议: {advice}\n"
            f"风险提示: 关注美元指数与美债收益率波动。"
        )
    
    def analyze_kline(self, kline_image: str) -> str:
        """
        分析K线图
        
        Args:
            kline_image: K线图图片路径
        
        Returns:
            分析结果文本
        """
        if self.model is None:
            return "模型未加载"

        if self.backend == "fallback":
            return (
                "当前处于规则分析回退模式（VLM 原生模型暂不可用）。\n"
                "建议: 观察价格重心、长下影线与成交量同步放大情况；"
                "若放量突破前高可小仓试多，若跌破前低需止损控制。"
            )
        
        if not os.path.exists(kline_image):
            return f"图片不存在: {kline_image}"
        
        try:
            from PIL import Image
            
            # 加载图片
            image = Image.open(kline_image)
            
            # 构建提示词
            prompt = """分析这张积存金K线图，请提供：
1. 当前趋势判断（上涨/下跌/震荡）
2. 技术指标分析（MA均线、成交量等）
3. 买卖建议（买入/卖出/持有）
4. 风险提示

请用简短的中文回答。"""
            
            # 处理输入
            inputs = self.processor(
                images=image,
                text=prompt,
                return_tensors="pt"
            )
            
            # 推理
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False
            )
            
            # 解码
            result = self.processor.batch_decode(outputs)[0]
            
            return result
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
        if self.model is None:
            return "模型未加载"

        if self.backend == "fallback":
            return self._rule_based_market_analysis(price_data)
        
        # 构建提示词
        prompt = f"""分析以下积存金市场数据：

浙商积存金:
- 当前价格: {price_data.get('zheshang', {}).get('price', 'N/A')}元/克
- 涨跌幅: {price_data.get('zheshang', {}).get('change_rate', 'N/A')}
- 持仓: {price_data.get('zheshang', {}).get('position', 'N/A')}克

民生积存金:
- 当前价格: {price_data.get('minsheng', {}).get('price', 'N/A')}元/克
- 涨跌幅: {price_data.get('minsheng', {}).get('change_rate', 'N/A')}
- 持仓: {price_data.get('minsheng', {}).get('position', 'N/A')}克

请提供：
1. 市场趋势判断
2. 持仓建议
3. 风险提示

用简短中文回答。"""
        
        try:
            inputs = self.processor(text=prompt, return_tensors="pt")
            outputs = self.model.generate(**inputs, max_new_tokens=256)
            result = self.processor.batch_decode(outputs)[0]
            return result
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
