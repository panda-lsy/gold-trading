#!/usr/bin/env python3
"""
语音合成 (TTS) - 基于 Qwen3-TTS + OpenVINO
使用 baseline 的 OVQwen3TTSModel helper
"""
import os
from pathlib import Path


class Qwen3TTS:
    """Qwen3-TTS 语音合成器 - OpenVINO 加速版"""
    
    def __init__(self, model_dir: str = None, device: str = "AUTO"):
        if model_dir is None:
            # 默认使用 models 目录
            model_dir = Path(__file__).resolve().parents[1] / "models" / "Qwen3-TTS-CustomVoice-0.6B-fp16-ov"
        
        self.model_dir = Path(model_dir)
        self.device = device
        self.model = None
        
        self._load_model()
    
    def _load_model(self):
        """加载 OpenVINO 模型"""
        if not self.model_dir.exists():
            print(f"模型不存在: {self.model_dir}")
            print("请从 ModelScope 下载:")
            print("  modelscope download snake7gun/Qwen3-TTS-CustomVoice-0.6B-fp16-ov")
            return
        
        try:
            from .qwen_3_tts_helper import OVQwen3TTSModel
            
            print(f"加载 TTS 模型 (OpenVINO): {self.model_dir}")
            self.model = OVQwen3TTSModel.from_pretrained(
                model_dir=self.model_dir,
                device=self.device,
            )
            print("✓ TTS 模型加载成功 (OpenVINO 加速)")
        except ImportError as e:
            print(f"导入 helper 失败: {e}")
            print("请安装依赖: pip install qwen-tts")
        except Exception as e:
            print(f"加载失败: {e}")
    
    def synthesize(self, text: str, output_file: str = None, speaker: str = "vivian", 
                   language: str = "Chinese", instruct: str = "") -> str:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            output_file: 输出音频文件路径
            speaker: 说话人名称
            language: 语言
            instruct: 风格指令
        
        Returns:
            输出文件路径
        """
        if self.model is None:
            print("模型未加载")
            return None
        
        if output_file is None:
            output_file = "/tmp/tts_output.wav"
        
        try:
            # 使用 OVQwen3TTSModel 的 generate_custom_voice API
            wavs, sr = self.model.generate_custom_voice(
                text=text,
                speaker=speaker,
                language=language,
                instruct=instruct,
                non_streaming_mode=True,
                max_new_tokens=2048,
            )
            
            # 保存音频
            import scipy.io.wavfile as wav
            wav.write(output_file, sr, wavs)
            
            print(f"✓ 语音已保存 (OpenVINO): {output_file}")
            return output_file
        except Exception as e:
            print(f"合成失败: {e}")
            return None
    
    def speak(self, text: str):
        """
        合成并播放语音
        
        Args:
            text: 要播放的文本
        """
        output_file = self.synthesize(text)
        if output_file:
            self._play_audio(output_file)
    
    def _play_audio(self, audio_file: str):
        """播放音频文件"""
        try:
            import sounddevice as sd
            import scipy.io.wavfile as wav
            
            # 加载音频
            samplerate, data = wav.read(audio_file)
            
            # 播放
            sd.play(data, samplerate)
            sd.wait()
        except Exception as e:
            print(f"播放失败: {e}")


if __name__ == "__main__":
    # 测试
    tts = Qwen3TTS()
    
    # 测试合成
    test_text = "当前金价1001元，建议持有"
    tts.speak(test_text)
