---
name: gold-trading-production-ops
description: 用于在 Windows 或 Linux/macOS 本地运行积存金生产应用并执行 AI 巡检。当用户需要：启动服务、动态端口分配、导入 OpenClaw 定时任务、默认启用 cpolar 或 NATAPP 公网地址、检查 API/AI 能力、定位常见启动故障时使用。
---

# Gold Trading Production Ops Skill

## Scope

This skill is for production-style local operation on Windows and Linux/macOS.
It focuses on service startup, dynamic port fallback, OpenClaw scheduled-task import, default tunnel setup (cpolar/NATAPP), API health checks, AI capability checks, and production template usage.

## Repository

- GitHub: `https://github.com/panda-lsy/gold-trading`
- Branch: `main`

For skill deployment, use this repository URL as the source when importing into Copaw/Space.

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

## Core Commands (Linux/macOS)

1. Start all services:
   - `./scripts/start_all.sh`
2. Check service status:
   - `./scripts/status.sh`
3. Stop all services:
   - `./scripts/stop_all.sh`
4. Start static portal only:
   - `./scripts/start_web.sh`

## Dynamic Port Behavior

1. All start scripts now prefer default ports and auto-fallback to free ports when occupied.
2. Windows writes runtime ports to:
   - `.service_ports.json`
3. Linux/macOS writes runtime ports to:
   - `.service_ports.env`
4. Status scripts always show current effective endpoints.

Windows quick check:

`powershell -Command "Get-Content .service_ports.json"`

Linux/macOS quick check:

`cat .service_ports.env`

Optional preferred ports before startup:

- `WS_PORT`
- `DASHBOARD_PORT`
- `API_PORT`
- `PORTAL_PORT`

## API Validation Checklist

1. Read actual API port from runtime metadata.
2. API health:
   - `curl http://127.0.0.1:${API_PORT}/api/health`
3. Dashboard aggregate data:
   - `curl http://127.0.0.1:${API_PORT}/api/dashboard`
4. AI capability status:
   - `curl http://127.0.0.1:${API_PORT}/api/ai/capabilities`
5. Open AI Playground:
   - `http://127.0.0.1:${PORTAL_PORT}/ai_playground.html`

If you need shell variables on Linux/macOS:

`source .service_ports.env`

If you need shell variables on Windows PowerShell:

`$p = Get-Content .service_ports.json | ConvertFrom-Json`

## OpenClaw Production Template

Apply production cron template:

`python ops/setup_openclaw.py --mode production --apply`

Expected template file:

`config/openclaw_cron.production.json`

## Import Scheduled Tasks (Required)

Use this section when user asks to import or initialize cron/scheduled tasks.

1. Import production schedule template:
   - `python ops/setup_openclaw.py --mode production --apply`
2. Verify active schedule file exists:
   - `openclaw_cron.json`
3. Verify production template source file exists:
   - `config/openclaw_cron.production.json`
4. Optional quick inspect:
   - `python -m json.tool openclaw_cron.json`

If import fails:

- Re-run command from repository root.
- Ensure file write permission for project root.
- Check JSON validity in `config/openclaw_cron.production.json`.

## Public Access via cpolar

Use this when Copaw workspace cannot directly expose localhost services.

1. Create public tunnels for local API and Dashboard ports.
2. Default cpolar mode: export public base URLs before startup:
   - `PUBLIC_API_BASE`
   - `PUBLIC_DASHBOARD_BASE`
3. Start services with standard scripts.
4. Verify generated runtime config:
   - `web/runtime-config.js`
5. Open portal and verify requests target public bases.

Example (PowerShell):

`$env:PUBLIC_API_BASE="https://xxx.cpolar.top"`

`$env:PUBLIC_DASHBOARD_BASE="https://yyy.cpolar.top"`

`powershell -ExecutionPolicy Bypass -File .\scripts\Start-All.ps1`

Example (Linux/macOS):

`export PUBLIC_API_BASE="https://xxx.cpolar.top"`

`export PUBLIC_DASHBOARD_BASE="https://yyy.cpolar.top"`

`./scripts/start_all.sh`

Recommended default behavior for this skill:

1. Assume cpolar mode is enabled by default.
2. If user has not provided domains, ask them to provide two cpolar URLs (API and Dashboard).
3. Always write `PUBLIC_API_BASE` and `PUBLIC_DASHBOARD_BASE` before startup commands.
4. Validate that `web/runtime-config.js` contains cpolar URLs after startup.

## Public Access via NATAPP

Use this when users prefer NATAPP channels for API and Dashboard.

1. Ensure NATAPP provides two public URLs:
   - API URL -> local API port
   - Dashboard URL -> local Dashboard port
2. Export NATAPP variables before startup:
   - `NATAPP_API_BASE`
   - `NATAPP_DASHBOARD_BASE`
3. Start services with standard scripts.
4. Verify `web/runtime-config.js` contains NATAPP URLs.

Example (PowerShell):

`$env:NATAPP_API_BASE="https://api-xxxxx.natappfree.cc"`

`$env:NATAPP_DASHBOARD_BASE="https://dash-xxxxx.natappfree.cc"`

`powershell -ExecutionPolicy Bypass -File .\scripts\Start-All.ps1`

Example (Linux/macOS):

`export NATAPP_API_BASE="https://api-xxxxx.natappfree.cc"`

`export NATAPP_DASHBOARD_BASE="https://dash-xxxxx.natappfree.cc"`

`./scripts/start_all.sh`

## Quick Troubleshooting

1. Port conflict:
   - Scripts now auto-fallback to free ports. Confirm final ports in `.service_ports.json` or `.service_ports.env`.
2. Python not found:
   - Install Python 3 and ensure executable is on PATH (`py/python` on Windows, `python3/python` on Linux/macOS).
3. AI model dependency missing:
   - Check `optimum-intel`, `transformers`, and model directories.
   - Capability endpoint will show component readiness.
4. Linux script execution denied:
   - Run `chmod +x ./scripts/*.sh` and retry.
5. cpolar domain reachable but API fails:
   - Verify `PUBLIC_API_BASE` and `PUBLIC_DASHBOARD_BASE` values before startup.
   - Re-run start script to regenerate `web/runtime-config.js`.

## Copaw Space Demonstration Notes

For scoring evidence in article:

1. Screenshot of skill import in Copaw space.
2. Screenshot of prompt using this skill to start/check services.
3. Screenshot of returned status including `/api/ai/capabilities` result.
4. Optional short video showing start -> health check -> AI playground.
