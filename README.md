# 贾维斯 (JARVIS) - 积存金智能模拟交易助手

[![OpenVINO](https://img.shields.io/badge/OpenVINO-2026-blue)](https://docs.openvino.ai/)
[![ModelScope](https://img.shields.io/badge/ModelScope-魔搭社区-blue)](https://www.modelscope.cn/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> ModelScope x OpenVINO AI 应用实战参赛作品

## 项目简介

本项目是一个基于 OpenVINO 加速的积存金智能模拟交易系统，提供行情采集、策略分析、可视化大盘、OpenClaw 调度与多模态 AI 能力（ASR/TTS/VLM/图像生成）。

## 核心能力

| 能力       | 描述                           | 技术                 |
| ---------- | ------------------------------ | -------------------- |
| 语音交互   | 语音输入问价、问仓位、问策略   | Qwen3-ASR + OpenVINO |
| 智能分析   | 图文与行情联合分析             | Qwen3-VL + OpenVINO  |
| 语音播报   | AI 回复语音合成播报            | Qwen3-TTS + OpenVINO |
| 可视化     | Dashboard + WebSocket 实时推送 | Flask + ECharts      |
| 自动化运维 | 模板化定时任务和巡检           | OpenClaw + Python    |

## 目录结构

```text
gold-trading/
├── app/                      # Web/API 服务
├── ai_interface/             # ASR/TTS/VLM/图像生成接口
├── src/                      # 交易核心模块
├── ops/                      # 监控、通知、OpenClaw 模板管理
├── scripts/                  # Windows + Linux/macOS 运维脚本
├── web/                      # 统一工作台静态入口
├── config/                   # 配置与模板
└── skills/                   # Skill 文档
```

## 快速开始

### 环境要求

- 操作系统: Windows / Linux / macOS
- Python: 3.10+
- 内存: 8GB+（建议 16GB）
- 存储: 10GB+（模型文件）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 首次下载模型（可选）

```bash
python tools/download_models.py
```

### 启动全部服务

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-All.ps1
```

Linux/macOS:

```bash
./scripts/start_all.sh
```

### 查看状态与停止

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Status.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\Stop-All.ps1
```

Linux/macOS:

```bash
./scripts/status.sh
./scripts/stop_all.sh
```

## 端口说明（已支持动态分配）

脚本会优先使用默认端口，如果端口被占用会自动寻找可用端口。

- 默认端口:
  - Dashboard: 5000
  - API: 8080
  - WebSocket: 8765
  - Portal: 8090
- 运行时端口记录:
  - Windows: .service_ports.json
  - Linux/macOS: .service_ports.env

可选端口环境变量（启动前设置）:

- WS_PORT
- DASHBOARD_PORT
- API_PORT
- PORTAL_PORT

## 统一工作台与 AI 页面

静态门户启动：

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-Web.ps1
```

Linux/macOS:

```bash
./scripts/start_web.sh
```

访问地址使用状态脚本输出的 Portal 实际端口，例如：

- 统一工作台: http://127.0.0.1:PORTAL/
- AI Playground: http://127.0.0.1:PORTAL/ai_playground.html

## 主要 AI API

- GET /api/ai/capabilities
- POST /api/ai/chat
- POST /api/ai/tts
- POST /api/ai/asr
- POST /api/ai/vlm/image
- POST /api/ai/vlm/kline
- POST /api/ai/vlm/market
- POST /api/ai/image/brief
- GET /api/ai/artifacts/`<filename>`

## 公网访问（cpolar 等）

当运行在 Copaw/受限环境，无法直接暴露 localhost 时，可使用隧道工具。

启动前配置：

- PUBLIC_API_BASE
- PUBLIC_DASHBOARD_BASE

Windows 示例：

```powershell
$env:PUBLIC_API_BASE="https://xxx.cpolar.top"
$env:PUBLIC_DASHBOARD_BASE="https://yyy.cpolar.top"
powershell -ExecutionPolicy Bypass -File .\scripts\Start-All.ps1
```

Linux/macOS 示例：

```bash
export PUBLIC_API_BASE="https://xxx.cpolar.top"
export PUBLIC_DASHBOARD_BASE="https://yyy.cpolar.top"
./scripts/start_all.sh
```

脚本会自动生成 web/runtime-config.js，将统一工作台指向公网地址。

## OpenClaw 生产模板

```bash
python ops/setup_openclaw.py --mode production --apply
```

模板文件：

- config/openclaw_cron.production.json

## 补充文档

- 脚本说明: scripts/README.md
- 生产运维 Skill: skills/gold-trading-production-ops/SKILL.md

## 常见问题

1. 端口占用导致启动失败
   - 先运行停止脚本，再重新启动；当前脚本已支持自动换端口。
2. Linux/macOS 执行脚本被拒绝
   - 运行 chmod +x ./scripts/*.sh。
3. Python 不在 PATH
   - Windows 确认 py/python，Linux/macOS 确认 python3/python。
4. cpolar 域名可打开但 API 调用失败
   - 重新检查 PUBLIC_API_BASE 和 PUBLIC_DASHBOARD_BASE，并重启服务。

## 致谢

- [OpenVINO](https://github.com/openvinotoolkit/openvino)
- [ModelScope](https://www.modelscope.cn/)
- [Qwen3](https://github.com/QwenLM/Qwen3)
