#!/usr/bin/env python3
"""
图像生成模块
- 优先尝试使用 OpenVINO 加速的文生图模型（若存在）
- 回退到标准 Diffusers 管线
- 最终回退到 Pillow 海报渲染，确保生产环境可用
"""
from __future__ import annotations

import importlib
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class MarketImageGenerator:
    """市场快报图生成器 - 支持 OpenVINO 加速。"""

    def __init__(self, model_dir: str = None, output_dir: Optional[str] = None, device: str = "AUTO"):
        self.project_root = Path(__file__).resolve().parents[1]
        if model_dir is None:
            # 默认使用 models 目录
            self.model_dir = self.project_root / "models" / "Z-Image-Turbo-int4-ov"
        else:
            self.model_dir = self.project_root / model_dir
        self.output_dir = Path(output_dir) if output_dir else self.project_root / "data" / "ai_outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.device = device

        self.pipeline = None
        self.pipeline_error = None
        self._use_openvino = False
        self._infer_lock = threading.Lock()
        self._try_load_pipeline()

    def _configure_scheduler(self):
        """对齐 workshop 的调度器参数（若后端支持）。"""
        if self.pipeline is None:
            return
        try:
            diffusers_mod = importlib.import_module('diffusers')
            scheduler_cls = getattr(diffusers_mod, 'FlowMatchEulerDiscreteScheduler', None)
            if scheduler_cls is None:
                return
            self.pipeline.scheduler = scheduler_cls(num_train_timesteps=1000, shift=3.0)
        except Exception:
            # 调度器不可用时保持默认，不影响主流程。
            return

    def _has_diffusers_weights(self) -> bool:
        """检查是否存在标准 Diffusers 所需的关键权重文件。"""
        transformer_dir = self.model_dir / "transformer"
        if not transformer_dir.exists():
            return False

        required = [
            "diffusion_pytorch_model.bin",
            "diffusion_pytorch_model.safetensors",
            "pytorch_model.bin",
            "model.safetensors",
        ]
        return any((transformer_dir / name).exists() for name in required)

    def _try_load_pipeline(self):
        """尝试加载文生图管线，优先 OpenVINO，不成功则回退到模板渲染。"""
        if not self.model_dir.exists():
            self.pipeline_error = f"文生图模型目录不存在: {self.model_dir}"
            return

        # 首先尝试使用 OpenVINO 加载
        openvino_reason = None
        try:
            optimum_intel = importlib.import_module('optimum.intel')
            OVZImagePipeline = getattr(optimum_intel, 'OVZImagePipeline', None)
            if OVZImagePipeline is None:
                openvino_reason = "当前 optimum.intel 版本不包含 OVZImagePipeline"
                raise RuntimeError(openvino_reason)

            print(f"加载文生图模型 (OpenVINO): {self.model_dir}")
            self.pipeline = OVZImagePipeline.from_pretrained(
                str(self.model_dir),
                device=self.device
            )
            self._use_openvino = True
            self._configure_scheduler()
            self.pipeline_error = None
            print("✓ 文生图模型加载成功 (OpenVINO 加速)")
            return
        except Exception as e:
            openvino_reason = openvino_reason or str(e)
            print(f"OpenVINO 加载失败: {openvino_reason}")

        if not self._has_diffusers_weights():
            self.pipeline = None
            self.pipeline_error = f"文生图模型缺少 Diffusers 权重，已启用模板渲染（OpenVINO 原因: {openvino_reason}）"
            return

        print("尝试标准 Diffusers 加载...")

        # 回退到标准 Diffusers
        try:
            diffusers_mod = importlib.import_module('diffusers')
            auto_pipeline_cls = getattr(diffusers_mod, 'AutoPipelineForText2Image')

            self.pipeline = auto_pipeline_cls.from_pretrained(str(self.model_dir))
            self._use_openvino = False
            self.pipeline_error = None
            print("✓ 文生图模型加载成功 (标准 Diffusers)")
        except Exception as e:
            self.pipeline = None
            self.pipeline_error = f"文生图模型加载失败，已回退模板渲染: {e}（OpenVINO 原因: {openvino_reason}）"

    def _compose_prompt(self, market_data: Dict, news_lines: List[str]) -> str:
        zs = market_data.get('zheshang', {})
        ms = market_data.get('minsheng', {})
        z_price = zs.get('price', 'N/A')
        z_rate = zs.get('change_rate', 'N/A')
        m_price = ms.get('price', 'N/A')
        m_rate = ms.get('change_rate', 'N/A')
        headline = (news_lines[0] if news_lines else '关注短线波动与仓位管理').replace('\n', ' ').strip()

        # 参考 workshop 的中文提示词风格，约束版式和可读性，减少错字与乱码。
        return (
            "金融科技信息图海报，深蓝黑背景，金色数字高亮，高对比，清晰中文排版。"
            "布局要求：上方主标题，中间两栏数据卡片，底部风险提示。"
            "只生成一张海报，不要人物，不要卡通，不要多余装饰文字。"
            f"主标题：积存金行情快报。"
            f"卡片1：浙商积存金 当前 {z_price} 元/克，涨跌 {z_rate}。"
            f"卡片2：民生积存金 当前 {m_price} 元/克，涨跌 {m_rate}。"
            f"快报要点：{headline}。"
            "字体要求：中文可读，数字大号，避免错别字、重影、乱码。"
        )

    def _get_font(self, size: int):
        imagefont_mod = importlib.import_module('PIL.ImageFont')
        ImageFont = getattr(imagefont_mod, 'ImageFont', None)
        load_default = getattr(imagefont_mod, 'load_default')
        truetype = getattr(imagefont_mod, 'truetype')

        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for font_path in candidates:
            if Path(font_path).exists():
                try:
                    return truetype(font_path, size)
                except OSError:
                    continue
        return load_default()

    def _render_template_image(
        self,
        output_path: Path,
        title: str,
        market_data: Dict,
        news_lines: List[str],
    ):
        """使用 Pillow 渲染稳定可用的行情快报图。"""
        image_mod = importlib.import_module('PIL.Image')
        draw_mod = importlib.import_module('PIL.ImageDraw')
        Image = getattr(image_mod, 'Image')
        ImageDraw = getattr(draw_mod, 'ImageDraw')
        new_image = getattr(image_mod, 'new')
        draw_factory = getattr(draw_mod, 'Draw')

        width, height = 1200, 675
        image = new_image("RGB", (width, height), "#0b1020")
        draw = draw_factory(image)

        # 简单分层背景
        draw.rectangle((0, 0, width, 110), fill="#111a2d")
        draw.rectangle((0, 112, width, height), fill="#0f1526")

        title_font = self._get_font(42)
        section_font = self._get_font(30)
        text_font = self._get_font(24)
        small_font = self._get_font(20)

        draw.text((40, 30), title, fill="#ffd166", font=title_font)
        draw.text((880, 38), datetime.now().strftime("%Y-%m-%d %H:%M"), fill="#8ba0c8", font=small_font)

        zs = market_data.get('zheshang', {})
        ms = market_data.get('minsheng', {})

        draw.text((40, 140), "行情概览", fill="#8cc2ff", font=section_font)
        draw.text((60, 190), f"浙商积存金: {zs.get('price', 'N/A')} 元/克  ({zs.get('change_rate', 'N/A')})", fill="#e9effb", font=text_font)
        draw.text((60, 230), f"民生积存金: {ms.get('price', 'N/A')} 元/克  ({ms.get('change_rate', 'N/A')})", fill="#e9effb", font=text_font)

        draw.text((40, 300), "发生了什么", fill="#8cc2ff", font=section_font)
        y = 350
        for idx, line in enumerate(news_lines[:5], start=1):
            draw.text((60, y), f"{idx}. {line}", fill="#dbe7ff", font=text_font)
            y += 46

        draw.text((40, height - 40), "Generated by JARVIS AI Interface", fill="#6f88b7", font=small_font)

        image.save(str(output_path))

    def generate_market_brief(
        self,
        market_data: Dict,
        news_lines: Optional[List[str]] = None,
        title: str = "积存金行情快报",
    ) -> Tuple[str, Optional[str]]:
        """
        生成行情快报图。

        Returns:
            (文件名, 错误信息)
        """
        if news_lines is None or len(news_lines) == 0:
            news_lines = [
                "国际贵金属波动加剧，短线情绪偏谨慎",
                "端侧监控显示价格出现分钟级波动",
                "建议关注晚间宏观数据与美元指数变化",
            ]

        output_name = f"market_brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        output_path = self.output_dir / output_name

        if self.pipeline is not None:
            try:
                prompt = self._compose_prompt(market_data, news_lines)

                # OpenVINO 管线在并发时可能报 "Infer Request is busy"，这里串行化推理并做一次重试。
                image = None
                for attempt in range(2):
                    try:
                        with self._infer_lock:
                            if self._use_openvino:
                                import torch
                                ov_kwargs = {
                                    'prompt': prompt,
                                    'height': 512,
                                    'width': 512,
                                    'num_inference_steps': 9,
                                    'guidance_scale': 0.0,
                                    'negative_prompt': "乱码文字, 错字, 重影, 模糊文字, 低清晰度, watermark",
                                    'generator': torch.Generator("cpu").manual_seed(42),
                                }
                                try:
                                    image = self.pipeline(**ov_kwargs).images[0]
                                except TypeError:
                                    ov_kwargs.pop('negative_prompt', None)
                                    image = self.pipeline(**ov_kwargs).images[0]
                            else:
                                image = self.pipeline(prompt=prompt, num_inference_steps=20).images[0]
                        break
                    except Exception as e:
                        if 'busy' in str(e).lower() and attempt == 0:
                            time.sleep(0.25)
                            continue
                        raise
                
                image.save(str(output_path))
                mode = "OpenVINO" if self._use_openvino else "Diffusers"
                print(f"✓ 图像生成成功 ({mode}): {output_name}")
                return output_name, None
            except Exception as e:
                self.pipeline_error = f"文生图推理失败，已回退模板渲染: {e}"

        self._render_template_image(output_path, title=title, market_data=market_data, news_lines=news_lines)
        return output_name, self.pipeline_error
