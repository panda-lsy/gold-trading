---
name: gold-trading-production-ops
description: 用于在 Windows 本地运行积存金生产应用并执行 AI 巡检。当用户需要：启动服务、检查 API/AI 能力、应用 OpenClaw 生产模板、生成行情快报图、定位常见启动故障时使用。
---

# Gold Trading Production Ops Skill

## Scope

This skill is for production-style local operation on Windows.
It focuses on service startup, API health checks, AI capability checks, and OpenClaw production template usage.

## Prerequisites

1. Python 3.10+ installed and available in PATH.
2. Dependencies installed:
   - `pip install -r requirements.txt`
3. Optional model download:
   - `python tools/download_models.py`

## Core Commands (Windows)

1. Start all services:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\Start-All.ps1`
2. Check service status:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\Status.ps1`
3. Stop all services:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\Stop-All.ps1`
4. Start static portal only:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\Start-Web.ps1`

## API Validation Checklist

1. API health:
   - `curl http://127.0.0.1:8080/api/health`
2. Dashboard aggregate data:
   - `curl http://127.0.0.1:8080/api/dashboard`
3. AI capability status:
   - `curl http://127.0.0.1:8080/api/ai/capabilities`
4. Open AI Playground:
   - `http://127.0.0.1:8090/ai_playground.html`

## OpenClaw Production Template

Apply production cron template:

`python ops/setup_openclaw.py --mode production --apply`

Expected template file:

`config/openclaw_cron.production.json`

## Quick Troubleshooting

1. Port conflict:
   - Stop all and restart with scripts above.
2. Python not found:
   - Install Python 3 and ensure `py` or `python` is on PATH.
3. AI model dependency missing:
   - Check `optimum-intel`, `transformers`, and model directories.
   - Capability endpoint will show component readiness.

## Copaw Space Demonstration Notes

For scoring evidence in article:

1. Screenshot of skill import in Copaw space.
2. Screenshot of prompt using this skill to start/check services.
3. Screenshot of returned status including `/api/ai/capabilities` result.
4. Optional short video showing start -> health check -> AI playground.
