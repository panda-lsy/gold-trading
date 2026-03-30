#!/usr/bin/env python3
"""
语音识别 (ASR) - 基于 Qwen3-ASR + OpenVINO
使用 baseline 的 OVQwen3ASRModel helper
"""
import os
from pathlib import Path


class Qwen3ASR:
    """Qwen3-ASR 语音识别器 - OpenVINO 加速版"""
    
    def __init__(self, model_dir: str = None, device: str = "AUTO"):
        if model_dir is None:
            # 默认使用 models 目录
            model_dir = Path(__file__).resolve().parents[1] / "models" / "Qwen3-ASR-0.6B-fp16-ov"
        
        self.model_dir = Path(model_dir)
        self.device = device
        self.model = None
        
        self._load_model()
    
    def _load_model(self):
        """加载 OpenVINO 模型"""
        if not self.model_dir.exists():
            print(f"模型不存在: {self.model_dir}")
            print("请从 ModelScope 下载:")
            print("  modelscope download snake7gun/Qwen3-ASR-0.6B-fp16-ov")
            return
        
        try:
            from .qwen_3_asr_helper import OVQwen3ASRModel
            
            print(f"加载 ASR 模型 (OpenVINO): {self.model_dir}")
            self.model = OVQwen3ASRModel.from_pretrained(
                model_dir=str(self.model_dir),
                device=self.device,
                max_inference_batch_size=32,
                max_new_tokens=256,
            )
            print("✓ ASR 模型加载成功 (OpenVINO 加速)")
        except ImportError as e:
            print(f"导入 helper 失败: {e}")
            print("请安装依赖: pip install qwen-asr")
        except Exception as e:
            print(f"加载失败: {e}")
    
    def recognize(self, audio_file: str, language: str = None) -> str:
        """
        识别语音文件
        
        Args:
            audio_file: 音频文件路径
            language: 语言代码 (None 表示自动检测)
        
        Returns:
            识别文本
        """
        if self.model is None:
            return "模型未加载"
        
        try:
            # 使用 OVQwen3ASRModel 的 transcribe API
            results = self.model.transcribe(
                audio=audio_file,
                language=language,
            )
            
            # 返回第一个结果的文本
            if results and len(results) > 0:
                return results[0].text
            return "识别结果为空"
        except Exception as e:
            return f"识别失败: {e}"
    
    def recognize_microphone(self, duration: int = 5) -> str:
        """
        从麦克风录音并识别
        
        Args:
            duration: 录音时长（秒）
        
        Returns:
            识别文本
        """
        try:
            import sounddevice as sd
            import numpy as np
            
            print(f"录音 {duration} 秒...")
            
            # 录音
            audio = sd.rec(
                int(duration * 16000),
                samplerate=16000,
                channels=1,
                dtype=np.float32
            )
            sd.wait()
            
            # 保存临时文件
            temp_file = "/tmp/temp_recording.wav"
            import scipy.io.wavfile as wav
            wav.write(temp_file, 16000, audio)
            
            # 识别
            return self.recognize(temp_file)
        except Exception as e:
            return f"录音失败: {e}"


if __name__ == "__main__":
    # 测试
    asr = Qwen3ASR()
    
    # 测试识别
    test_file = "test_audio.wav"
    if os.path.exists(test_file):
        result = asr.recognize(test_file)
        print(f"识别结果: {result}")
    else:
        print(f"测试文件不存在: {test_file}")
        print("请提供音频文件进行测试")
