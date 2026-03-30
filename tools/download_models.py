#!/usr/bin/env python3
"""
下载 OpenVINO 模型
从 ModelScope 下载 Qwen3 系列模型
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"

# 确保 models 目录存在
MODELS_DIR.mkdir(exist_ok=True)

MODELS = {
    "Qwen3-ASR-0.6B-fp16-ov": "snake7gun/Qwen3-ASR-0.6B-fp16-ov",
    "Qwen3-TTS-CustomVoice-0.6B-fp16-ov": "snake7gun/Qwen3-TTS-CustomVoice-0.6B-fp16-ov",
    "Qwen3-VL-4B-Instruct-int4-ov": "snake7gun/Qwen3-VL-4B-Instruct-int4-ov",
    "Z-Image-Turbo-int4-ov": "snake7gun/Z-Image-Turbo-int4-ov",
}


def download_model(model_name: str, model_id: str):
    """下载单个模型到 models 目录"""
    model_dir = MODELS_DIR / model_name
    
    if model_dir.exists():
        print(f"✓ {model_name} 已存在，跳过下载")
        return
    
    print(f"\n📥 下载 {model_name}...")
    print(f"   来源: {model_id}")
    
    try:
        from modelscope import snapshot_download
        
        snapshot_download(model_id, local_dir=str(model_dir))
        print(f"✓ {model_name} 下载完成")
    except Exception as e:
        print(f"✗ 下载失败: {e}")
        print("  请确保已安装: pip install modelscope")


def download_all_models():
    """下载所有模型"""
    print("=" * 60)
    print("下载 OpenVINO 模型")
    print("=" * 60)
    
    for model_name, model_id in MODELS.items():
        download_model(model_name, model_id)
    
    print("\n" + "=" * 60)
    print("✓ 模型下载完成")
    print("=" * 60)


def check_models():
    """检查模型状态"""
    print("\n模型状态检查:")
    print(f"模型目录: {MODELS_DIR}")
    print("-" * 60)
    
    for model_name in MODELS.keys():
        model_dir = MODELS_DIR / model_name
        status = "✓ 已下载" if model_dir.exists() else "✗ 未下载"
        size = ""
        if model_dir.exists():
            # 计算目录大小
            total_size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
            size = f"({total_size / 1024 / 1024:.1f} MB)"
        print(f"  {model_name:<35} {status} {size}")
    
    print("-" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='下载 OpenVINO 模型')
    parser.add_argument('--check', action='store_true', help='检查模型状态')
    args = parser.parse_args()
    
    if args.check:
        check_models()
    else:
        download_all_models()
        check_models()
