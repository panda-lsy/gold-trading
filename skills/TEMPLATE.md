---
name: multimodal-understand
description: 构建并运行可在 Windows 本地运行的图像和音频理解工具。当用户需要：搭建多模态推理环境、理解图像/视频内容、识别音频/语音内容、或语音+图像联合理解时使用此技能。基于 Qwen3-VL (视觉语言) 和 Qwen3-ASR (语音识别) 的 OpenVINO 本地推理。
allowed-tools: Bash(python *), Bash(pip *), Bash(cd *), Bash(call *), Read, Glob, Write
---

# 多模态图像与音频理解工具 (Windows 本地)

基于 [modelscope-workshop](https://github.com/openvino-dev-samples/modelscope-workshop) 项目，使用 OpenVINO 在 Windows 本地运行 Qwen3-VL（图像/视频理解）和 Qwen3-ASR（语音识别）。

## 工作目录结构

```
D:\modelscope-workshop\
├── requirements.txt
├── setup_lab.bat
├── run_lab.bat
├── lab1-multimodal-vlm\
│   ├── gradio_helper.py          # Gradio UI 帮助模块
│   ├── Qwen3-VL-4B-Instruct-int4-ov\   # VLM 模型 (预转换 OV 格式)
│   └── lab1-qwen3-vl.ipynb
├── lab2-speech-recognition\
│   ├── gradio_helper.py          # Gradio UI 帮助模块
│   ├── qwen_3_asr_helper.py      # ASR 推理核心
│   ├── Qwen3-ASR-0.6B-fp16-ov\  # ASR 模型 (预转换 OV 格式)
│   └── lab2-qwen3-asr.ipynb
└── utils\
    └── notebook_utils.py
```

---

## 第一步：环境搭建

### 方式 A：使用官方安装脚本（推荐）

```bat
cd D:\modelscope-workshop
call setup_lab.bat
```

脚本会自动创建 `ov_workshop` 虚拟环境并安装所有依赖。

### 方式 B：手动安装

```bat
cd D:\modelscope-workshop
python -m venv ov_workshop
call ov_workshop\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 核心依赖说明

```
openvino>=2025.4          # OpenVINO 推理引擎
optimum-intel             # HuggingFace + OpenVINO 集成 (OVModelForVisualCausalLM)
torch==2.8 (CPU)          # PyTorch CPU 版
qwen-vl-utils             # Qwen-VL 图像/视频预处理
qwen-asr                  # Qwen-ASR 音频处理
gradio==6.9.0             # Web UI
transformers              # 模型加载
```

---

## 第二步：语音识别 (ASR)

使用 `qwen_3_asr_helper.py` 中的 `OVQwen3ASRModel`，无需 optimum-intel 依赖，纯 OpenVINO 推理。

### 程序调用

```python
import sys
sys.path.insert(0, r"D:\modelscope-workshop\lab2-speech-recognition")
from qwen_3_asr_helper import OVQwen3ASRModel

# 加载模型（首次加载约 1-2 分钟，后续秒级）
asr_model = OVQwen3ASRModel.from_pretrained(
    model_dir=r"D:\modelscope-workshop\lab2-speech-recognition\Qwen3-ASR-0.6B-fp16-ov",
    device="CPU",
    max_new_tokens=256,
)

# 转写音频（支持 wav/mp3/flac，最长 20 分钟，超长自动分段）
results = asr_model.transcribe(audio=r"D:\audio\sample.wav", language=None)
# language=None 自动检测；也可指定: "Chinese", "English", "Japanese" 等 52 种语言

for seg in results:
    print(f"语言: {seg.language}")
    print(f"文本: {seg.text}")
    if hasattr(seg, 'words'):
        for word in seg.words:
            print(f"  [{word.start:.2f}s - {word.end:.2f}s] {word.word}")
```

### 启动 Gradio UI

```python
import sys
sys.path.insert(0, r"D:\modelscope-workshop\lab2-speech-recognition")
from qwen_3_asr_helper import OVQwen3ASRModel
from gradio_helper import make_demo

asr_model = OVQwen3ASRModel.from_pretrained(
    model_dir=r"D:\modelscope-workshop\lab2-speech-recognition\Qwen3-ASR-0.6B-fp16-ov",
    device="CPU",
    max_new_tokens=256,
)

demo = make_demo(asr_model)
demo.launch(share=False)   # 浏览器打开 http://127.0.0.1:7860
```

---

## 第三步：图像/视频理解 (VLM)

使用 `OVModelForVisualCausalLM`（来自 optimum-intel），支持图像描述、视觉问答、OCR、视频理解。

### 程序调用

```python
from optimum.intel.openvino import OVModelForVisualCausalLM
from transformers import AutoProcessor
from qwen_vl_utils import process_vision_info

model_dir = r"D:\modelscope-workshop\lab1-multimodal-vlm\Qwen3-VL-4B-Instruct-int4-ov"

# 加载模型（首次约 2-3 分钟，占用约 2-3 GB 内存）
vlm_model = OVModelForVisualCausalLM.from_pretrained(model_dir, device="AUTO")
processor = AutoProcessor.from_pretrained(
    model_dir,
    min_pixels=256 * 28 * 28,
    max_pixels=1280 * 28 * 28
)

def ask_about_image(image_path: str, question: str) -> str:
    """对图像提问，返回模型回答。"""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": f"file://{image_path}"},
                {"type": "text", "text": question},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text], images=image_inputs, videos=video_inputs,
        padding=True, return_tensors="pt"
    )
    generated_ids = vlm_model.generate(**inputs, max_new_tokens=512)
    output_ids = generated_ids[:, inputs["input_ids"].shape[1]:]
    return processor.tokenizer.decode(output_ids[0], skip_special_tokens=True)

def ask_about_video(video_path: str, question: str) -> str:
    """对视频提问，返回模型回答。"""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video", "video": f"file://{video_path}"},
                {"type": "text", "text": question},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text], images=image_inputs, videos=video_inputs,
        padding=True, return_tensors="pt"
    )
    generated_ids = vlm_model.generate(**inputs, max_new_tokens=512)
    output_ids = generated_ids[:, inputs["input_ids"].shape[1]:]
    return processor.tokenizer.decode(output_ids[0], skip_special_tokens=True)

# 示例
print(ask_about_image(r"D:\images\photo.jpg", "这张图片里有什么？"))
print(ask_about_video(r"D:\videos\clip.mp4", "描述这段视频的内容"))
```

### 启动 Gradio UI

```python
import sys
sys.path.insert(0, r"D:\modelscope-workshop\lab1-multimodal-vlm")
from optimum.intel.openvino import OVModelForVisualCausalLM
from transformers import AutoProcessor
from gradio_helper import make_demo   # lab1 的 gradio_helper

model_dir = r"D:\modelscope-workshop\lab1-multimodal-vlm\Qwen3-VL-4B-Instruct-int4-ov"
vlm_model = OVModelForVisualCausalLM.from_pretrained(model_dir, device="AUTO")
processor = AutoProcessor.from_pretrained(model_dir, min_pixels=256*28*28, max_pixels=1280*28*28)

demo = make_demo(vlm_model, processor)
demo.launch(share=False)   # 浏览器打开 http://127.0.0.1:7860
```

---

## 第四步：语音 + 图像联合理解

将 ASR 转写结果作为问题，传给 VLM 回答图像内容——用自然语言语音提问图像。

```python
import sys
sys.path.insert(0, r"D:\modelscope-workshop\lab2-speech-recognition")
from qwen_3_asr_helper import OVQwen3ASRModel
from optimum.intel.openvino import OVModelForVisualCausalLM
from transformers import AutoProcessor
from qwen_vl_utils import process_vision_info

# 加载两个模型
asr_model = OVQwen3ASRModel.from_pretrained(
    model_dir=r"D:\modelscope-workshop\lab2-speech-recognition\Qwen3-ASR-0.6B-fp16-ov",
    device="CPU", max_new_tokens=256,
)
vlm_model = OVModelForVisualCausalLM.from_pretrained(
    r"D:\modelscope-workshop\lab1-multimodal-vlm\Qwen3-VL-4B-Instruct-int4-ov",
    device="AUTO"
)
processor = AutoProcessor.from_pretrained(
    r"D:\modelscope-workshop\lab1-multimodal-vlm\Qwen3-VL-4B-Instruct-int4-ov",
    min_pixels=256*28*28, max_pixels=1280*28*28
)

def voice_ask_image(audio_path: str, image_path: str) -> dict:
    """用语音提问，对图像作答。"""
    # Step 1: 语音 → 文字
    results = asr_model.transcribe(audio=audio_path, language=None)
    question = results[0].text
    print(f"识别问题: {question}")

    # Step 2: 文字 + 图像 → 回答
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": f"file://{image_path}"},
                {"type": "text", "text": question},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                       padding=True, return_tensors="pt")
    generated_ids = vlm_model.generate(**inputs, max_new_tokens=512)
    output_ids = generated_ids[:, inputs["input_ids"].shape[1]:]
    answer = processor.tokenizer.decode(output_ids[0], skip_special_tokens=True)

    return {"question": question, "answer": answer}

result = voice_ask_image(
    audio_path=r"D:\audio\question.wav",
    image_path=r"D:\images\photo.jpg"
)
print(f"问: {result['question']}")
print(f"答: {result['answer']}")
```

---

## 快速检查清单

在运行前确认以下几点：

1. **虚拟环境已激活**：`call D:\modelscope-workshop\ov_workshop\Scripts\activate.bat`
2. **模型目录存在**：
   - `D:\modelscope-workshop\lab1-multimodal-vlm\Qwen3-VL-4B-Instruct-int4-ov\`
   - `D:\modelscope-workshop\lab2-speech-recognition\Qwen3-ASR-0.6B-fp16-ov\`
3. **OpenVINO 版本**：`python -c "import openvino; print(openvino.__version__)"` 应 >= 2025.4
4. **可用设备**：`python -c "import openvino as ov; print(ov.Core().available_devices)"`

---

## 性能参考 (Windows 11, CPU 推理)

| 模型 | 大小 | 内存占用 | 首次加载 | 推理速度 |
|------|------|----------|----------|----------|
| Qwen3-ASR-0.6B (fp16) | ~1.2 GB | ~1.5 GB | ~60s | ~实时 1x |
| Qwen3-VL-4B (int4) | ~2.5 GB | ~3 GB | ~120s | 约 5-15 tok/s |

- 若安装了 Intel Arc GPU 或 Core Ultra NPU，将 `device="CPU"` 改为 `device="AUTO"` 可自动选择最优设备
- `device="GPU"` 显式使用 Intel Arc 独显（需安装 GPU 驱动）

---

## 常见错误排查

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `ModuleNotFoundError: qwen_vl_utils` | 缺少依赖 | `pip install qwen-vl-utils` |
| `ModuleNotFoundError: optimum` | optimum-intel 未安装 | 运行 `setup_lab.bat` 或按 requirements.txt 安装 |
| `FileNotFoundError: model_dir` | 模型未下载 | 确认模型目录路径正确，或重新运行 notebook 下载模型 |
| `OV model not found` | OV 格式模型缺失 | 运行对应 `.ipynb` notebook 的模型转换 cell |
| Gradio 端口占用 | 7860 端口被占用 | `demo.launch(server_port=7861)` |
