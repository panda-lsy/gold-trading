#!/usr/bin/env python3
"""
语音合成 (TTS) - 基于 Qwen3-TTS + OpenVINO
使用 baseline 的 OVQwen3TTSModel helper
"""
import os
import re
from pathlib import Path
import numpy as np


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
            raise FileNotFoundError(
                f"TTS 模型不存在: {self.model_dir}。"
                "请从 ModelScope 下载 snake7gun/Qwen3-TTS-CustomVoice-0.6B-fp16-ov"
            )
        
        try:
            from .qwen_3_tts_helper import OVQwen3TTSModel
            
            print(f"加载 TTS 模型 (OpenVINO): {self.model_dir}")
            self.model = OVQwen3TTSModel.from_pretrained(
                model_dir=self.model_dir,
                device=self.device,
            )
            print("✓ TTS 模型加载成功 (OpenVINO 加速)")
        except ImportError as e:
            raise ImportError(f"导入 helper 失败: {e}。请安装依赖: pip install qwen-tts") from e
        except Exception as e:
            raise RuntimeError(f"TTS 加载失败: {e}") from e

    def _normalize_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        cleaned = cleaned.replace("\n", "，")
        return cleaned

    def _split_text(self, text: str, max_chars: int = 80):
        if not text:
            return []
        pieces = []
        for seg in re.split(r"(?<=[。！？!?；;])", text):
            seg = seg.strip(" ，。；;!?！？")
            if not seg:
                continue
            while len(seg) > max_chars:
                pieces.append(seg[:max_chars])
                seg = seg[max_chars:]
            if seg:
                pieces.append(seg)
        return pieces or [text[:max_chars]]

    def _to_int16_waveform(self, wavs):
        waveform = wavs
        if isinstance(waveform, (list, tuple)):
            if len(waveform) == 0:
                raise ValueError("empty waveform")
            waveform = waveform[0]

        waveform = np.asarray(waveform)
        if waveform.ndim > 1:
            waveform = np.squeeze(waveform)
        if waveform.ndim != 1:
            raise ValueError(f"unexpected waveform shape: {waveform.shape}")
        if waveform.size == 0:
            raise ValueError("empty waveform")

        if np.issubdtype(waveform.dtype, np.floating):
            waveform = np.nan_to_num(waveform, nan=0.0, posinf=0.0, neginf=0.0)
            waveform = np.clip(waveform, -1.0, 1.0)
            waveform = (waveform * 32767.0).astype(np.int16)
        elif waveform.dtype != np.int16:
            waveform = waveform.astype(np.int16)
        return waveform
    
    def synthesize(self, text: str, output_file: str = None, speaker: str = "vivian",
                   language: str = "Chinese", instruct: str = "", fast_mode: bool = False,
                   should_cancel=None) -> str:
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

        normalized_text = self._normalize_text(text)
        if fast_mode and len(normalized_text) > 220:
            normalized_text = normalized_text[:220] + '。'
        if not normalized_text:
            print("输入文本为空")
            return None
        
        try:
            chunk_limit = 56 if fast_mode else 90
            chunks = self._split_text(normalized_text, max_chars=chunk_limit)
            if not chunks:
                raise ValueError("empty text chunks")

            pcm_chunks = []
            sr = 24000
            for chunk in chunks:
                if callable(should_cancel) and should_cancel():
                    print("TTS 合成已取消")
                    return None

                token_budget = max(64, min(220 if fast_mode else 900, len(chunk) * (3 if fast_mode else 9)))
                wavs, sr = self.model.generate_custom_voice(
                    text=chunk,
                    speaker=speaker,
                    language=language,
                    instruct=instruct,
                    non_streaming_mode=True,
                    max_new_tokens=token_budget,
                )
                pcm = self._to_int16_waveform(wavs)
                pcm_chunks.append(pcm)

            if callable(should_cancel) and should_cancel():
                print("TTS 合成已取消")
                return None

            # 每段之间插入短静音，降低段落衔接断裂感。
            silence = np.zeros(int(sr * 0.04), dtype=np.int16)
            merged = []
            for i, pcm in enumerate(pcm_chunks):
                merged.append(pcm)
                if i != len(pcm_chunks) - 1:
                    merged.append(silence)
            waveform = np.concatenate(merged).astype(np.int16)
            
            # 保存音频
            import scipy.io.wavfile as wav
            wav.write(output_file, int(sr), waveform)
            
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
