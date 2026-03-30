# 贾维斯 (JARVIS) - 积存金智能模拟交易助手

[![OpenVINO](https://img.shields.io/badge/OpenVINO-2026-blue)](https://docs.openvino.ai/)
[![ModelScope](https://img.shields.io/badge/ModelScope-魔搭社区-blue)](https://www.modelscope.cn/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> 🏆 ModelScope x OpenVINO AI 应用实战参赛作品

## 📋 项目简介

基于 **OpenVINO** 加速的积存金（黄金定投）智能模拟交易系统，集成实时行情、策略分析、可视化 Dashboard、OpenClaw 调度，以及语音识别、语音合成、多模态理解等 AI 能力，为用户提供智能化的黄金投资服务。

### ✨ 核心功能

| 功能                   | 描述                          | 技术                 |
| ---------------------- | ----------------------------- | -------------------- |
| 🎙️**语音交互** | 语音命令查询价格、持仓、交易  | Qwen3-ASR + OpenVINO |
| 📊**智能分析**   | AI 分析市场走势，给出买卖建议 | Qwen3-VL + OpenVINO  |
| 🔊**语音播报**   | 价格提醒、交易确认语音播报    | Qwen3-TTS + OpenVINO |
| 📈**可视化**     | 专业 K 线图和实时交易面板     | ECharts + WebSocket  |
| 🤖**自动化**     | 定时任务和自动交易策略        | OpenClaw + Python    |

## 1. 当前项目结构

```text
gold-trading/
├── app/                      # 应用层（Web/API 服务）
│   ├── api_server.py         # 主 API 服务（含 AI 端点）
│   ├── dashboard_v3.py       # Dashboard 服务
│   └── openclaw_integration.py
├── ops/                      # 运维层（任务、监控、模板切换）
│   ├── jijin_service.py
│   ├── smart_monitor.py
│   ├── setup_openclaw.py
│   └── notify_weixin.py
├── tools/                    # 工具层
│   ├── download_models.py
│   ├── md_to_image.py
│   └── strategy_analysis.py
├── src/                      # 交易核心模块
├── ai_interface/             # AI 接口实现（ASR/TTS/VLM）
├── config/                   # OpenClaw 模板配置
├── web/                      # 静态页面（运维门户 + AI Playground）
├── scripts/                  # Windows PowerShell 脚本入口
│   ├── Start-All.ps1
│   ├── Stop-All.ps1
│   └── Status.ps1
└── skills/                   # OpenClaw Skill 封装
```

## 2. 快速开始

### 环境要求

- **操作系统**: Linux / Windows / macOS
- **Python**: 3.10+
- **内存**: 8GB+ (推荐 16GB)
- **存储**: 10GB+ (用于模型文件)

### 2.1 安装依赖

```bash
pip install -r requirements.txt
```

### 2.2 下载模型（首次）

```bash
python tools/download_models.py
```

### 2.3 启动服务

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-All.ps1
```

访问地址：

- Dashboard: http://127.0.0.1:5000
- API: http://127.0.0.1:8080
- WebSocket: ws://127.0.0.1:8765

### 2.4 状态与停止

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Status.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\Stop-All.ps1
```

## 3. Web 接入 AI 多场景（ai_interface）

基于 OpenVINO Workshop Baseline 的二次开发能力：

- 视觉理解（VLM）：对上传图片与 K 线图进行理解分析
- 语音识别（ASR）：Web 语音聊天输入（浏览器麦克风）
- 语音合成（TTS）：语音播报开关，支持行情与分析结果朗读
- 图像生成：生成包含行情与热点摘要的“行情快报图”

### 3.1 页面入口

启动静态页：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-Web.ps1
```

访问：

- 运维入口: http://127.0.0.1:8090
- AI Playground: http://127.0.0.1:8090/ai_playground.html

### 3.2 已接入能力

- Web 语音聊天（支持麦克风输入 + 图片提问）
- TTS 文本转语音
- ASR 音频识别（支持上传文件）
- VLM 图像分析（支持图片理解与 K 线专项分析）
- VLM 市场分析（自动抓取当前行情）
- 图像生成（行情快报图：新闻要点 + 当前价格）

### 3.3 AI API 列表

- GET /api/ai/capabilities
- POST /api/ai/chat
- POST /api/ai/tts
- POST /api/ai/asr
- POST /api/ai/vlm/image
- POST /api/ai/vlm/kline
- POST /api/ai/vlm/market
- POST /api/ai/image/brief
- GET /api/ai/artifacts/`<filename>`

## 4. OpenClaw 生产模板

- 生产版模板: config/openclaw_cron.production.json
- 当前生效配置: openclaw_cron.json

应用生产模板：

```bash
python ops/setup_openclaw.py --mode production --apply
```

## 5. 生产部署建议

详见：DEPLOY_PRODUCTION.md

最小闭环：

1. 安装依赖 + 下载模型
2. 启动 scripts/Start-All.ps1
3. 校验 /api/health 与 Dashboard
4. 视需求启动 scripts/Start-Web.ps1 提供运维门户

## 6. 比赛提交

最终核对清单：FINAL_SUBMISSION_CHECKLIST.md

建议流程：

1. 跑通核心服务
2. 跑通 AI Playground（截图取证）
3. 发布灵感流代码
4. 发布征文（含环境、场景、运行展示、总结）

## 7. 说明

- 历史脚本和旧文档已归档至 archieve/。
- 运行时生成文件（日志、PID、AI 音频产物）已加入 .gitignore。

## 8. OpenClaw Skill 与 Copaw

- Skill 模板示例：skills/TEMPLATE.md
- 本项目封装 Skill：skills/gold-trading-production-ops/SKILL.md
- Copaw 跑通指南：docs/COPAW_SKILL_RUNBOOK.md
- 二合一工作台：web/dashboard_ai_unified.html
- 灵感流 Notebook：inspiration_flow_dashboard_ai.ipynb

## 🎯 创新点

1. **多模态交互**: 首创语音交互的黄金交易系统
2. **AI 驱动**: 基于大模型的智能市场分析
3. **实时性**: WebSocket 实时推送 + OpenVINO 加速
4. **自动化**: 完整的定时任务和预警系统
5. **易用性**: 零代码部署，开箱即用

## 📝 技术栈

- **推理框架**: OpenVINO 2025.0
- **模型**: Qwen3-ASR/TTS/VL (INT4量化)
- **后端**: Python + Flask
- **前端**: HTML5 + ECharts
- **实时通信**: WebSocket
- **任务调度**: OpenClaw

## 🙏 致谢

- [OpenVINO](https://github.com/openvinotoolkit/openvino)
- [ModelScope](https://www.modelscope.cn/)
- [Qwen3](https://github.com/QwenLM/Qwen3)
