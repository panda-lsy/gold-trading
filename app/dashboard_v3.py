#!/usr/bin/env python3
"""积存金 Dashboard v3.0 - 专业K线图版"""
import json
import sys
import threading
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
from jijin_trader import JijinTrader, find_working_proxy
from trade_manager import TradeManager
from kline_service import KlineService

# HTML 模板 - 使用 ECharts 专业图表
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>贾维斯 - 积存金交易系统</title>
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ccircle cx='50' cy='50' r='45' fill='%23FFD700' stroke='%23FFA500' stroke-width='3'/%3E%3Ctext x='50' y='68' font-size='42' text-anchor='middle' fill='%238B6914' font-weight='bold'%3EAu%3C/text%3E%3C/svg%3E">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; min-height: 100vh; }
        .header { background: #161b22; padding: 20px; border-bottom: 1px solid #30363d; position: sticky; top: 0; z-index: 100; }
        .header-content { max-width: 1400px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
        .logo { display: flex; align-items: center; gap: 15px; }
        .logo-icon { width: 50px; height: 50px; background: linear-gradient(135deg, #FFD700, #FFA500); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #8B6914; font-size: 22px; box-shadow: 0 0 20px rgba(255, 215, 0, 0.3); }
        .logo-text h1 { font-size: 1.8em; font-weight: 300; color: #FFD700; }
        .logo-text p { color: #8b949e; font-size: 0.85em; }
        .status-bar { display: flex; gap: 20px; align-items: center; }
        .ws-status { padding: 8px 16px; border-radius: 20px; font-size: 0.85em; }
        .ws-connected { background: rgba(35, 197, 94, 0.15); color: #23c55e; border: 1px solid rgba(35, 197, 94, 0.3); }
        .ws-disconnected { background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
        .tab { padding: 12px 24px; border-radius: 8px; cursor: pointer; transition: all 0.3s; color: #8b949e; background: transparent; border: none; font-size: 1em; }
        .tab:hover { background: rgba(255,255,255,0.05); color: #fff; }
        .tab.active { background: rgba(255, 215, 0, 0.15); color: #FFD700; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: #161b22; border-radius: 12px; padding: 24px; border: 1px solid #30363d; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #30363d; }
        .card-title { font-size: 1.2em; font-weight: 500; color: #e6edf3; }
        .status-badge { padding: 6px 12px; border-radius: 20px; font-size: 0.75em; font-weight: 600; }
        .status-open { background: rgba(35, 197, 94, 0.15); color: #23c55e; }
        .status-closed { background: rgba(110, 118, 129, 0.15); color: #6e7681; }
        .price-display { text-align: center; padding: 20px 0; }
        .price-main { font-size: 3em; font-weight: 300; color: #FFD700; text-shadow: 0 0 30px rgba(255, 215, 0, 0.4); }
        .price-unit { font-size: 0.4em; color: #8b949e; margin-left: 5px; }
        .price-change { display: flex; justify-content: center; gap: 20px; margin-top: 10px; font-size: 1.1em; }
        .change-positive { color: #23c55e; }
        .change-negative { color: #ef4444; }
        .info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 15px; }
        .info-item { background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px; }
        .info-label { color: #8b949e; font-size: 0.8em; margin-bottom: 4px; }
        .info-value { font-size: 1.1em; font-weight: 500; color: #e6edf3; }
        .profit-positive { color: #23c55e; }
        .profit-negative { color: #ef4444; }
        .trading-hours { background: rgba(0, 212, 255, 0.1); border-radius: 8px; padding: 12px; margin-top: 15px; border-left: 3px solid #00d4ff; }
        .trading-hours-title { font-size: 0.8em; color: #00d4ff; margin-bottom: 4px; }
        .trading-hours-content { font-size: 0.9em; color: #ccc; }
        .table-container { overflow-x: auto; margin-top: 15px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }
        th { color: #8b949e; font-weight: 500; font-size: 0.85em; text-transform: uppercase; background: rgba(255,255,255,0.02); }
        tr:hover { background: rgba(255,255,255,0.03); }
        .badge { padding: 4px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 500; }
        .badge-buy { background: rgba(35, 197, 94, 0.15); color: #23c55e; }
        .badge-sell { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
        .chart-container { position: relative; height: 400px; margin-top: 15px; background: #0d1117; border-radius: 8px; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: #161b22; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #30363d; }
        .stat-value { font-size: 2em; font-weight: 300; color: #FFD700; margin-bottom: 5px; }
        .stat-label { color: #8b949e; font-size: 0.85em; }
        .ai-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px; }
        #tab-ai .card { background: linear-gradient(180deg, rgba(32,47,78,0.45), rgba(22,29,43,0.95)); border-color: #36507a; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25); }
        #tab-ai .card-header { border-bottom-color: rgba(140, 178, 235, 0.25); }
        .ai-toolbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 10px; }
        .model-status-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
        .model-tag { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border: 1px solid #5d5f68; border-radius: 999px; font-size: 12px; color: #d7dce8; background: rgba(45, 48, 56, 0.45); }
        .model-tag::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: #f1c40f; box-shadow: 0 0 8px rgba(241, 196, 15, 0.6); }
        .model-tag.tag-ready { border-color: rgba(35, 197, 94, 0.45); color: #b7f5cf; }
        .model-tag.tag-ready::before { background: #23c55e; box-shadow: 0 0 10px rgba(35, 197, 94, 0.7); }
        .model-tag.tag-down { border-color: rgba(239, 68, 68, 0.45); color: #ffcbcb; }
        .model-tag.tag-down::before { background: #ef4444; box-shadow: 0 0 10px rgba(239, 68, 68, 0.7); }
        .model-tag.tag-loading { border-color: rgba(241, 196, 15, 0.45); color: #ffe6a6; }
        .model-tag.tag-loading::before { background: #f1c40f; box-shadow: 0 0 10px rgba(241, 196, 15, 0.7); }
        .ai-window-nav { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
        .ai-window-btn { padding: 8px 14px; border-radius: 10px; border: 1px solid #36507a; background: rgba(17, 30, 55, 0.9); color: #c9d1d9; cursor: pointer; }
        .ai-window-btn.active { background: rgba(73, 137, 255, 0.25); color: #cfe2ff; border-color: #5a8de0; }
        .ai-window { display: none; flex: 1; min-height: 0; }
        .ai-window.active { display: flex; flex-direction: column; min-height: 0; overflow-y: auto; padding-right: 4px; }
        .ai-window-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }
        .ai-chat-card { display: flex; flex-direction: column; min-height: 0; }
        .chat-window { flex: 1; min-height: 180px; max-height: 265px; overflow: auto; border: 1px solid #36507a; border-radius: 10px; padding: 10px; background: #0f1830; margin-bottom: 10px; }
        .chat-window::-webkit-scrollbar { width: 10px; }
        .chat-window::-webkit-scrollbar-track { background: #0a1224; border-radius: 10px; }
        .chat-window::-webkit-scrollbar-thumb { background: linear-gradient(180deg, #2e73d8, #6ca7ff); border-radius: 10px; border: 2px solid #0a1224; }
        .chat-window { scrollbar-width: thin; scrollbar-color: #4d8cf1 #0a1224; }
        .chat-item { margin-bottom: 10px; }
        .role { font-size: 12px; color: #8b949e; margin-bottom: 4px; }
        .bubble { background: rgba(255,255,255,0.06); border: 1px solid #36507a; border-radius: 8px; padding: 8px; white-space: pre-wrap; line-height: 1.5; }
        .ctrl-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .input, .file, .textarea { width: 100%; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; color: #e6edf3; padding: 10px; }
        .textarea { min-height: 90px; resize: vertical; }
        .out { margin-top: 8px; border: 1px dashed #4f73af; border-radius: 8px; padding: 10px; white-space: pre-wrap; min-height: 72px; color: #d9e6ff; background: rgba(8, 16, 34, 0.7); font-size: 13px; line-height: 1.5; }
        .img-preview { width: 100%; border-radius: 8px; border: 1px solid #30363d; margin-top: 10px; }
        .tiny { font-size: 12px; color: #8b949e; }
        .kline-empty { height: 100%; display: flex; align-items: center; justify-content: center; color: #8b949e; font-size: 13px; border: 1px dashed rgba(139, 148, 158, 0.35); border-radius: 8px; background: rgba(13, 17, 23, 0.5); }
        #tab-ai.ai-embedded {
            display: flex;
            flex-direction: column;
            position: fixed;
            right: 14px;
            top: 86px;
            width: 390px;
            height: calc(100vh - 100px);
            overflow: hidden;
            padding-right: 0;
            z-index: 90;
            transition: transform 0.25s ease, opacity 0.25s ease;
        }
        .ai-sidebar-toggle {
            position: fixed;
            right: 412px;
            top: 110px;
            z-index: 95;
            border: 1px solid #36507a;
            border-radius: 10px;
            background: rgba(17, 30, 55, 0.95);
            color: #dbe9ff;
            padding: 8px 10px;
            cursor: pointer;
            font-size: 12px;
            line-height: 1;
            transition: right 0.25s ease;
        }
        body.ai-collapsed #tab-ai.ai-embedded {
            transform: translateX(412px);
            opacity: 0;
            pointer-events: none;
        }
        body.ai-collapsed .ai-sidebar-toggle {
            right: 14px;
        }
        body.no-ai-sidebar #tab-ai.ai-embedded,
        body.no-ai-sidebar .ai-sidebar-toggle {
            display: none !important;
        }
        body.no-ai-sidebar .container {
            padding-right: 20px !important;
        }
        @media (max-width: 1280px) {
            .container { padding-right: 410px; }
            body.ai-collapsed .container { padding-right: 20px; }
        }
        @media (max-width: 980px) {
            #tab-ai.ai-embedded {
                position: static;
                width: auto;
                height: auto;
                padding-right: 0;
                margin-top: 12px;
            }
            .ai-sidebar-toggle { position: static; margin: 10px 0; }
            body.ai-collapsed #tab-ai.ai-embedded {
                transform: none;
                opacity: 1;
                pointer-events: auto;
                display: none;
            }
            .container { padding-right: 20px; }
        }
        @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } .stats-grid { grid-template-columns: repeat(2, 1fr); } .header-content { flex-direction: column; gap: 15px; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo">
                <div class="logo-icon">Au</div>
                <div class="logo-text">
                    <h1>JARVIS</h1>
                    <p>积存金智能交易系统 v3.0</p>
                </div>
            </div>
            <div class="status-bar">
                <div class="ws-status ws-disconnected" id="wsStatus"><span>●</span> 未连接</div>
                <div style="color: #6e7681; font-size: 0.85em;" id="updateTime">更新于: --</div>
            </div>
        </div>
    </div>
    
    <div class="container">
        <button id="aiSidebarToggle" class="ai-sidebar-toggle" onclick="toggleAISidebar()">收起 AI</button>
        <div class="stats-grid" id="statsGrid"></div>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('prices', this)">📊 实时行情</button>
            <button class="tab" onclick="switchTab('trades', this)">📋 交易记录</button>
            <button class="tab" onclick="switchTab('charts', this)">📈 K线图表</button>
        </div>
        
        <div id="tab-prices" class="tab-content active">
            <div class="grid" id="pricesGrid"></div>
        </div>
        
        <div id="tab-trades" class="tab-content">
            <div class="card">
                <div class="card-header"><div class="card-title">📋 最近交易记录</div></div>
                <div class="table-container">
                    <table>
                        <thead><tr><th>时间</th><th>银行</th><th>动作</th><th>价格</th><th>数量</th><th>金额</th><th>手续费</th><th>盈亏</th></tr></thead>
                        <tbody id="tradesBody"></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div id="tab-charts" class="tab-content">
            <div class="grid">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">📈 浙商积存金 - 专业K线</div>
                        <div id="zheshangKlineMeta" style="color: #8b949e; font-size: 0.9em;">默认 1 分钟级 K 线，实时记录驱动</div>
                    </div>
                    <div class="chart-container" id="zheshangChart" style="height:350px;"></div>
                    <div class="card-title" style="margin-top:20px; font-size:1em; color:#e6edf3;">⏱ 实时秒级价格走势</div>
                    <div class="chart-container" id="zheshangRt" style="height:150px; margin-top:5px; background: transparent; border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;"></div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">📈 民生积存金 - 专业K线</div>
                        <div id="minshengKlineMeta" style="color: #8b949e; font-size: 0.9em;">默认 1 分钟级 K 线，实时记录驱动</div>
                    </div>
                    <div class="chart-container" id="minshengChart" style="height:350px;"></div>
                    <div class="card-title" style="margin-top:20px; font-size:1em; color:#e6edf3;">⏱ 实时秒级价格走势</div>
                    <div class="chart-container" id="minshengRt" style="height:150px; margin-top:5px; background: transparent; border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;"></div>
                </div>
            </div>
        </div>

        <div id="tab-ai" class="tab-content ai-embedded">
            <div class="card ai-toolbar">
                <div>
                    <div class="card-title">🤖 AI 常驻助手</div>
                    <div class="tiny" id="aiContextHint" style="margin-top: 6px;">OpenClaw 信息流已接入，模型状态灯会自动刷新。</div>
                    <div class="model-status-row" id="modelStatusRow">
                        <span class="model-tag tag-loading" id="tag-asr">ASR: 加载中</span>
                        <span class="model-tag tag-loading" id="tag-tts">TTS: 加载中</span>
                        <span class="model-tag tag-loading" id="tag-vlm">VLM: 加载中</span>
                        <span class="model-tag tag-loading" id="tag-image_generation">IMG: 加载中</span>
                    </div>
                </div>
                <button class="tab" style="padding: 8px 14px;" onclick="loadCapabilities()">刷新模型状态</button>
            </div>

            <div class="ai-window-nav">
                <button class="ai-window-btn active" id="btn-ai-chat" onclick="switchAIWindow('chat', this)">对话窗口</button>
                <button class="ai-window-btn" id="btn-ai-speech" onclick="switchAIWindow('speech', this)">语音工具</button>
                <button class="ai-window-btn" id="btn-ai-vision" onclick="switchAIWindow('vision', this)">视觉分析</button>
                <button class="ai-window-btn" id="btn-ai-image" onclick="switchAIWindow('image', this)">快报生成</button>
            </div>

            <div class="ai-window active" id="ai-window-chat">
                <div class="card ai-chat-card" style="margin-bottom: 10px;">
                    <div class="card-header"><div class="card-title">语音聊天（可选上传图片）</div></div>
                    <div id="chatWindow" class="chat-window"></div>
                    <div class="ctrl-row" style="margin-bottom: 8px;"><input id="chatInput" class="input" type="text" placeholder="输入问题，例如：当前适合买入吗？" /></div>
                    <div class="ctrl-row">
                        <input id="chatImage" class="file" style="max-width: 260px;" type="file" accept="image/*" />
                        <button class="tab" style="padding: 8px 14px;" onclick="sendChat()">发送</button>
                        <button class="tab" style="padding: 8px 14px;" id="micBtn" onclick="toggleMic()">开始语音输入</button>
                        <label class="tiny"><input type="checkbox" id="ttsToggle" checked /> 回复语音播报</label>
                    </div>
                    <div class="tiny" id="micStatus" style="margin-top: 8px;">麦克风状态：未启动</div>
                </div>
            </div>

            <div class="ai-window" id="ai-window-speech">
                <div class="ai-window-grid">
                    <div class="card">
                        <div class="card-header"><div class="card-title">TTS 文本转语音</div></div>
                        <textarea id="ttsText" class="textarea">你好，这是积存金 AI 助手的语音演示。</textarea>
                        <button class="tab" style="padding: 8px 14px;" onclick="runTTS()">生成语音</button>
                        <div id="ttsOut" class="out">等待执行...</div>
                        <audio id="ttsAudio" controls style="width: 100%; margin-top: 10px;"></audio>
                    </div>

                    <div class="card">
                        <div class="card-header"><div class="card-title">ASR 语音识别</div></div>
                        <input id="asrFile" class="file" type="file" accept="audio/*" />
                        <button class="tab" style="padding: 8px 14px;" onclick="runASR()">执行识别</button>
                        <div id="asrOut" class="out">等待执行...</div>
                    </div>
                </div>
            </div>

            <div class="ai-window" id="ai-window-vision">
                <div class="ai-window-grid">
                    <div class="card">
                        <div class="card-header"><div class="card-title">VLM 图像理解 / K线分析</div></div>
                        <input id="vlmFile" class="file" type="file" accept="image/*" />
                        <div class="ctrl-row">
                            <button class="tab" style="padding: 8px 14px;" onclick="runVLMImage()">图像理解</button>
                            <button class="tab" style="padding: 8px 14px;" onclick="runVLMKline()">K线专项分析</button>
                        </div>
                        <div id="vlmImageOut" class="out">等待执行...</div>
                    </div>

                    <div class="card">
                        <div class="card-header"><div class="card-title">VLM 市场分析</div></div>
                        <button class="tab" style="padding: 8px 14px;" onclick="runVLMMarket()">生成市场分析</button>
                        <div id="vlmMarketOut" class="out">等待执行...</div>
                    </div>
                </div>
            </div>

            <div class="ai-window" id="ai-window-image">
                <div class="card">
                    <div class="card-header"><div class="card-title">图像生成：行情快报</div></div>
                    <input id="briefTitle" class="input" type="text" value="积存金行情快报" />
                    <div class="ctrl-row">
                        <button class="tab" style="padding: 8px 14px;" onclick="generateBriefImage()">生成快报图</button>
                        <a id="briefDownload" href="#" target="_blank" rel="noopener" class="tiny">打开最新图片</a>
                    </div>
                    <div id="briefOut" class="out">等待执行...</div>
                    <img id="briefImage" class="img-preview" style="display:none;" />
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let currentData = INITIAL_DATA;
        let ws = null;
        let charts = {};
        const HOST = window.location.hostname || '127.0.0.1';
        const PROTOCOL = window.location.protocol || 'http:';
        const PORT = window.location.port || (PROTOCOL === 'https:' ? '443' : '80');
        const CURRENT_ORIGIN = `${PROTOCOL}//${HOST}${window.location.port ? ':' + window.location.port : ''}`;
        const isLikelyGatewayPort = !/^5[0-9]{3}$/.test(PORT);
        const URL_PARAMS = new URLSearchParams(window.location.search);
        const QUERY_API_BASE = (URL_PARAMS.get('api_base') || '').trim();
        const QUERY_WS_BASE = (URL_PARAMS.get('ws_base') || '').trim();

        function isLoopbackUrl(raw) {
            if (!raw) return false;
            try {
                const u = new URL(raw, CURRENT_ORIGIN);
                return u.hostname === '127.0.0.1' || u.hostname === 'localhost';
            } catch (_) {
                return false;
            }
        }

        const CONFIG_API_BASE = (window.__API_BASE__ || '').trim();
        const REMOTE_PAGE = !(HOST === '127.0.0.1' || HOST === 'localhost');
        const SHOULD_IGNORE_CONFIG_API = REMOTE_PAGE && isLoopbackUrl(CONFIG_API_BASE);
        const API = QUERY_API_BASE || (!SHOULD_IGNORE_CONFIG_API && CONFIG_API_BASE) || (isLikelyGatewayPort ? CURRENT_ORIGIN : `${PROTOCOL}//${HOST}:8080`);

        const CONFIG_WS_BASE = (window.__WS_BASE__ || '').trim();
        const WS_BASE = QUERY_WS_BASE || CONFIG_WS_BASE;
        const DISABLE_AI_SIDEBAR = URL_PARAMS.get('embed') === '1' || URL_PARAMS.get('hide_ai') === '1';
        let recognition = null;
        let listening = false;
        let aiInitialized = false;
        let aiCollapsed = false;
// Realtime Charts Variables
        let rtCharts = {};
        const maxPoints = 60;
        let priceHistory = {
            zheshang: Array(maxPoints).fill(null),
            minsheng: Array(maxPoints).fill(null)
        };

        function updateRealtimeCharts() {
            const isChartsActive = document.getElementById('tab-charts').classList.contains('active');

            for(const bank of ['zheshang', 'minsheng']) {
                if (currentData.prices && currentData.prices[bank] && currentData.prices[bank].price) {
                    priceHistory[bank].push(currentData.prices[bank].price);
                    if (priceHistory[bank].length > maxPoints) {
                        priceHistory[bank].shift();
                    }
                }

                if (!isChartsActive) {
                    continue;
                }

                if(!rtCharts[bank]) {
                    const dom = document.getElementById(bank + 'Rt');
                    if(dom) {
                        rtCharts[bank] = echarts.init(dom, 'dark');
                        rtCharts[bank].setOption({
                            backgroundColor: 'transparent',
                            animation: false,
                            grid: { left: 78, right: 15, top: 10, bottom: 20, containLabel: true },
                            xAxis: { type: 'category', data: Array(maxPoints).fill(''), axisLabel: {show: false}, splitLine: {show: false} },
                            yAxis: { type: 'value', scale: true, axisLabel: { color: '#8b949e', margin: 10, formatter: (v) => Number(v).toFixed(2) }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                            series: [{ type: 'line', data: [], smooth: true, showSymbol: false, lineStyle: { color: '#FFD700', width: 2 }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: 'rgba(255, 215, 0, 0.3)'}, {offset: 1, color: 'rgba(255, 215, 0, 0.0)'}]) } }]
                        });
                        window.addEventListener('resize', () => rtCharts[bank] && rtCharts[bank].resize());
                    }
                }

                if(rtCharts[bank]) {
                    rtCharts[bank].setOption({
                        series: [{ data: priceHistory[bank] }]
                    });
                }
            }
        }
        
        function switchTab(tabName, tabElement) {
            document.querySelectorAll('.tabs > .tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            if (tabElement) {
                tabElement.classList.add('active');
            }
            document.getElementById('tab-' + tabName).classList.add('active');
            const aiPanel = document.getElementById('tab-ai');
            if (!DISABLE_AI_SIDEBAR && aiPanel) aiPanel.classList.add('ai-embedded');
            if (tabName === 'charts') {
                setTimeout(() => {
                    initKlineCharts();
                    updateRealtimeCharts();
                    if (charts.zheshang) charts.zheshang.resize();
                    if (charts.minsheng) charts.minsheng.resize();
                    if (rtCharts.zheshang) rtCharts.zheshang.resize();
                    if (rtCharts.minsheng) rtCharts.minsheng.resize();
                }, 120);
            }
        }

        function applyAISidebarState() {
            const body = document.body;
            if (DISABLE_AI_SIDEBAR) {
                body.classList.add('no-ai-sidebar');
                body.classList.remove('ai-collapsed');
                return;
            }
            const toggleBtn = document.getElementById('aiSidebarToggle');
            if (!toggleBtn) return;

            if (aiCollapsed) {
                body.classList.add('ai-collapsed');
                toggleBtn.textContent = '展开 AI';
            } else {
                body.classList.remove('ai-collapsed');
                toggleBtn.textContent = '收起 AI';
            }
        }

        function toggleAISidebar() {
            if (DISABLE_AI_SIDEBAR) return;
            aiCollapsed = !aiCollapsed;
            try { localStorage.setItem('dashboard.aiCollapsed', aiCollapsed ? '1' : '0'); } catch (_) {}
            applyAISidebarState();
        }

        function setModelTagState(key, ready, message) {
            const tag = document.getElementById('tag-' + key);
            if (!tag) return;
            const labels = { asr: 'ASR', tts: 'TTS', vlm: 'VLM', image_generation: 'IMG' };
            const ok = ready === true;
            const msg = String(message || '').toLowerCase();
            const loading = !ok && (msg.includes('not loaded') || msg.includes('加载中') || msg.includes('loading'));
            tag.className = 'model-tag ' + (ok ? 'tag-ready' : (loading ? 'tag-loading' : 'tag-down'));
            tag.textContent = `${labels[key] || key.toUpperCase()}: ${ok ? '就绪' : (loading ? '加载中' : '异常')}`;
            if (message) tag.title = String(message);
            else tag.removeAttribute('title');
        }

        function setAllModelTagsLoading() {
            ['asr', 'tts', 'vlm', 'image_generation'].forEach((key) => {
                const tag = document.getElementById('tag-' + key);
                if (!tag) return;
                const label = key === 'image_generation' ? 'IMG' : key.toUpperCase();
                tag.className = 'model-tag tag-loading';
                tag.textContent = `${label}: 加载中`;
                tag.removeAttribute('title');
            });
        }

        function switchAIWindow(name, btn) {
            document.querySelectorAll('.ai-window-btn').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.ai-window').forEach(el => el.classList.remove('active'));
            if (btn) btn.classList.add('active');
            const target = document.getElementById('ai-window-' + name);
            if (target) target.classList.add('active');
        }

        function addChat(role, content) {
            const box = document.getElementById('chatWindow');
            if (!box) return;
            const item = document.createElement('div');
            item.className = 'chat-item';
            const roleNode = document.createElement('div');
            roleNode.className = 'role';
            roleNode.textContent = String(role || '');

            const bubbleNode = document.createElement('div');
            bubbleNode.className = 'bubble';
            bubbleNode.textContent = String(content || '');

            item.appendChild(roleNode);
            item.appendChild(bubbleNode);
            box.appendChild(item);
            box.scrollTop = box.scrollHeight;
        }

        function renderCaps(caps) {
            ['asr', 'tts', 'vlm', 'image_generation'].forEach((key) => {
                const item = caps[key] || {};
                setModelTagState(key, item.ready === true, item.message || '');
            });
        }

        async function loadCapabilities() {
            setAllModelTagsLoading();
            try {
                const r = await fetch(`${API}/api/ai/capabilities?fast=1`);
                const d = await r.json();
                if (!d.success) throw new Error(d.error || 'unknown error');
                renderCaps(d.capabilities || {});
                const hint = document.getElementById('aiContextHint');
                if (hint) hint.textContent = 'OpenClaw 信息流已接入，模型状态灯会自动刷新。';
            } catch (e) {
                ['asr', 'tts', 'vlm', 'image_generation'].forEach((key) => setModelTagState(key, false, e.message));
                const hint = document.getElementById('aiContextHint');
                if (hint) hint.textContent = `模型状态检查失败: ${e.message}`;
            }
        }

        async function speakText(text) {
            const toggle = document.getElementById('ttsToggle');
            if (!toggle || !toggle.checked || !text) return;
            try {
                const r = await fetch(`${API}/api/ai/tts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                });
                const d = await r.json();
                if (!d.success) return;
                const audio = new Audio(`${API}${d.audio_url}`);
                audio.play().catch(() => {});
            } catch (_) {}
        }

        async function sendChat() {
            const input = document.getElementById('chatInput');
            const imageInput = document.getElementById('chatImage');
            if (!input || !imageInput) return;
            const message = (input.value || '').trim();

            if (!message && (!imageInput.files || imageInput.files.length === 0)) {
                addChat('系统', '请输入消息或上传图片。');
                return;
            }

            addChat('你', message || '[图片提问]');
            input.value = '';

            try {
                let r;
                if (imageInput.files && imageInput.files.length > 0) {
                    const fd = new FormData();
                    fd.append('message', message);
                    fd.append('image', imageInput.files[0]);
                    r = await fetch(`${API}/api/ai/chat`, { method: 'POST', body: fd });
                    imageInput.value = '';
                } else {
                    r = await fetch(`${API}/api/ai/chat`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message })
                    });
                }
                const d = await r.json();
                if (!d.success) throw new Error(d.error || 'chat failed');
                addChat('AI', d.reply || '(空回复)');
                if (d.image_url) addChat('AI', `快报图链接: ${API}${d.image_url}`);
                await speakText(d.reply || '');
            } catch (e) {
                addChat('系统', `失败: ${e.message}`);
            }
        }

        function initSpeechRecognition() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                const statusEl = document.getElementById('micStatus');
                const btnEl = document.getElementById('micBtn');
                if (statusEl) statusEl.textContent = '麦克风状态：浏览器不支持语音识别';
                if (btnEl) btnEl.disabled = true;
                return;
            }

            recognition = new SpeechRecognition();
            recognition.lang = 'zh-CN';
            recognition.interimResults = false;
            recognition.continuous = false;

            recognition.onstart = () => {
                listening = true;
                document.getElementById('micBtn').textContent = '停止语音输入';
                document.getElementById('micStatus').textContent = '麦克风状态：识别中...';
            };

            recognition.onend = () => {
                listening = false;
                document.getElementById('micBtn').textContent = '开始语音输入';
                document.getElementById('micStatus').textContent = '麦克风状态：未启动';
            };

            recognition.onerror = (event) => {
                document.getElementById('micStatus').textContent = `麦克风错误: ${event.error}`;
            };

            recognition.onresult = (event) => {
                const text = event.results[0][0].transcript;
                document.getElementById('chatInput').value = text;
                sendChat();
            };
        }

        function toggleMic() {
            if (!recognition) return;
            if (listening) recognition.stop();
            else recognition.start();
        }

        async function runTTS() {
            const out = document.getElementById('ttsOut');
            const audio = document.getElementById('ttsAudio');
            out.textContent = '执行中...';
            audio.src = '';
            try {
                const text = document.getElementById('ttsText').value || '';
                const r = await fetch(`${API}/api/ai/tts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || 'TTS失败');
                out.textContent = `生成成功: ${d.audio_file}`;
                audio.src = `${API}${d.audio_url}`;
            } catch (e) {
                out.textContent = `失败: ${e.message}`;
            }
        }

        async function runASR() {
            const out = document.getElementById('asrOut');
            const fileInput = document.getElementById('asrFile');
            out.textContent = '执行中...';
            try {
                if (!fileInput.files || fileInput.files.length === 0) throw new Error('请先选择音频文件');
                const formData = new FormData();
                formData.append('audio', fileInput.files[0]);
                const r = await fetch(`${API}/api/ai/asr`, { method: 'POST', body: formData });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || 'ASR失败');
                out.textContent = d.text || '(空结果)';
            } catch (e) {
                out.textContent = `失败: ${e.message}`;
            }
        }

        async function runVLMImage() { await runVLMByEndpoint('/api/ai/vlm/image', 'vlmImageOut'); }
        async function runVLMKline() { await runVLMByEndpoint('/api/ai/vlm/kline', 'vlmImageOut'); }

        async function runVLMByEndpoint(endpoint, outputId) {
            const out = document.getElementById(outputId);
            const fileInput = document.getElementById('vlmFile');
            out.textContent = '执行中...';
            try {
                if (!fileInput.files || fileInput.files.length === 0) throw new Error('请先选择图像文件');
                const formData = new FormData();
                formData.append('image', fileInput.files[0]);
                const r = await fetch(`${API}${endpoint}`, { method: 'POST', body: formData });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || 'VLM分析失败');
                out.textContent = d.result || '(空结果)';
                await speakText(d.result || '');
            } catch (e) {
                out.textContent = `失败: ${e.message}`;
            }
        }

        async function runVLMMarket() {
            const out = document.getElementById('vlmMarketOut');
            out.textContent = '执行中...';
            try {
                const r = await fetch(`${API}/api/ai/vlm/market`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || 'VLM市场分析失败');
                out.textContent = d.result || '(空结果)';
                await speakText(d.result || '');
            } catch (e) {
                out.textContent = `失败: ${e.message}`;
            }
        }

        async function generateBriefImage() {
            const out = document.getElementById('briefOut');
            const img = document.getElementById('briefImage');
            const link = document.getElementById('briefDownload');
            out.textContent = '执行中...';
            img.style.display = 'none';
            try {
                const title = document.getElementById('briefTitle').value || '积存金行情快报';
                const r = await fetch(`${API}/api/ai/image/brief`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title })
                });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || '快报图生成失败');
                const url = `${API}${d.image_url}`;
                out.textContent = `生成成功: ${d.image_file}`;
                img.src = url;
                img.style.display = 'block';
                link.href = url;
                link.textContent = '打开最新图片';
            } catch (e) {
                out.textContent = `失败: ${e.message}`;
            }
        }

        function initAITab() {
            if (DISABLE_AI_SIDEBAR) {
                applyAISidebarState();
                return;
            }
            if (aiInitialized) return;
            aiInitialized = true;
            addChat('系统', '欢迎使用 AI 多场景助手。你可以语音提问，或上传新闻截图/K线图。');
            initSpeechRecognition();
            loadCapabilities();
            const defaultBtn = document.getElementById('btn-ai-chat');
            switchAIWindow('chat', defaultBtn);
            try { aiCollapsed = localStorage.getItem('dashboard.aiCollapsed') === '1'; } catch (_) { aiCollapsed = false; }
            applyAISidebarState();
        }
        
        function formatTime(isoString) {
            if (!isoString) return '--';
            return new Date(isoString).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        }
        
        function formatDateTime(isoString) {
            return isoString ? new Date(isoString).toLocaleString('zh-CN') : '--';
        }
        
        function renderStats() {
            const stats = currentData.stats || {};
            document.getElementById('statsGrid').innerHTML = `
                <div class="stat-card"><div class="stat-value">${stats.total_trades || 0}</div><div class="stat-label">总交易次数</div></div>
                <div class="stat-card"><div class="stat-value">${(stats.total_profit || 0).toFixed(2)}</div><div class="stat-label">总盈亏 (元)</div></div>
                <div class="stat-card"><div class="stat-value">${(stats.total_fees || 0).toFixed(2)}</div><div class="stat-label">总手续费 (元)</div></div>
                <div class="stat-card"><div class="stat-value">${stats.win_rate || 0}%</div><div class="stat-label">胜率</div></div>
            `;
        }
        
        function renderPrices() {
            const grid = document.getElementById('pricesGrid');
            let html = '';
            for (const [bank, data] of Object.entries(currentData.prices || {})) {
                const isTrading = data.is_trading;
                const statusClass = isTrading ? 'status-open' : 'status-closed';
                const statusText = isTrading ? '交易中' : '休市';
                const changeClass = (data.change_rate || '').includes('+') ? 'change-positive' : 'change-negative';
                const pos = currentData.positions?.[bank] || {};
                const pnlClass = (pos.unrealized_pnl || 0) >= 0 ? 'profit-positive' : 'profit-negative';
                
                html += `
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">🏦 ${data.name}</div>
                            <span class="status-badge ${statusClass}">${statusText}</span>
                        </div>
                        <div class="price-display">
                            <div class="price-main">${data.price?.toFixed(2) || '--'}<span class="price-unit">元/克</span></div>
                            <div class="price-change">
                                <span class="${changeClass}">${data.change_amt || '--'}</span>
                                <span class="${changeClass}">${data.change_rate || '--'}</span>
                            </div>
                        </div>
                        <div class="info-grid">
                            <div class="info-item"><div class="info-label">账户余额</div><div class="info-value">${(pos.balance || 0).toFixed(2)} 元</div></div>
                            <div class="info-item"><div class="info-label">持仓数量</div><div class="info-value">${(pos.position || 0).toFixed(2)} 克</div></div>
                            <div class="info-item"><div class="info-label">持仓均价</div><div class="info-value">${(pos.avg_price || 0).toFixed(2)} 元/克</div></div>
                            <div class="info-item"><div class="info-label">持仓市值</div><div class="info-value">${(pos.position_value || 0).toFixed(2)} 元</div></div>
                            <div class="info-item"><div class="info-label">浮动盈亏</div><div class="info-value ${pnlClass}">${(pos.unrealized_pnl || 0) >= 0 ? '+' : ''}${(pos.unrealized_pnl || 0).toFixed(2)} 元</div></div>
                            <div class="info-item"><div class="info-label">已实现盈亏</div><div class="info-value">${(pos.realized_pnl || 0) >= 0 ? '+' : ''}${(pos.realized_pnl || 0).toFixed(2)} 元</div></div>
                            <div class="info-item"><div class="info-label">累计手续费</div><div class="info-value">${(pos.total_fees || 0).toFixed(2)} 元</div></div>
                            <div class="info-item"><div class="info-label">总资产</div><div class="info-value" style="color: #FFD700; font-size: 1.2em;">${(pos.total_value || 0).toFixed(2)} 元</div></div>
                        </div>
                        <div class="trading-hours">
                            <div class="trading-hours-title">交易时间</div>
                            <div class="trading-hours-content">${bank === 'zheshang' ? '周一 9:00 - 周六 2:00' : '周一-周六 9:10-02:30'}</div>
                        </div>
                    </div>
                `;
            }
            grid.innerHTML = html;
        }
        
        function renderTrades() {
            const tbody = document.getElementById('tradesBody');
            const trades = currentData.trades || [];
            if (trades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #6e7681; padding: 40px;">暂无交易记录</td></tr>';
                return;
            }
            tbody.innerHTML = trades.map(t => `
                <tr>
                    <td>${formatDateTime(t.time)}</td>
                    <td>${t.bank === 'zheshang' ? '浙商' : '民生'}</td>
                    <td><span class="badge badge-${t.action.toLowerCase()}">${t.action === 'BUY' ? '买入' : '卖出'}</span></td>
                    <td>${t.price.toFixed(2)}</td>
                    <td>${t.grams.toFixed(2)} 克</td>
                    <td>${t.cost.toFixed(2)} 元</td>
                    <td>${(t.fee || 0).toFixed(2)} 元</td>
                    <td style="color: ${(t.profit || 0) >= 0 ? '#23c55e' : '#ef4444'}">${t.profit ? (t.profit >= 0 ? '+' : '') + t.profit.toFixed(2) : '--'} 元</td>
                </tr>
            `).join('');
        }
        
        function updateKlineMeta(bank, text) {
            const meta = document.getElementById(bank + 'KlineMeta');
            if (meta) meta.textContent = text;
        }

        function showKlineEmpty(bank, text) {
            const chartDom = document.getElementById(bank + 'Chart');
            if (!chartDom) return;
            chartDom.innerHTML = `<div class="kline-empty">${text}</div>`;
        }

        async function initKlineCharts() {
            for (const bank of ['zheshang', 'minsheng']) {
                if (charts[bank]) continue;

                const chartDom = document.getElementById(bank + 'Chart');
                if (!chartDom) continue;
                
                try {
                    const response = await fetch('/api/kline/' + bank + '?period=1m&limit=120');
                    const result = await response.json();
                    const data = result.data || [];

                    if (data.length === 0) {
                        updateKlineMeta(bank, '暂无可用 K 线，正在运行时记录价格...');
                        showKlineEmpty(bank, '暂无 K 线数据，正在记录 1 分钟级实时价格');
                        continue;
                    }

                    chartDom.innerHTML = '';
                    const myChart = echarts.init(chartDom, 'dark');

                    const periodLabel = (result.period || '1m').toUpperCase();
                    const fallbackTip = result.fallback ? '（数据不足，自动回退 1m）' : '';
                    const sampleTip = data.length < 20 ? '，样本不足 20 根，均线仅供参考' : '';
                    updateKlineMeta(bank, `${periodLabel} K 线 ${fallbackTip}${sampleTip}`.trim());
                    
                    // 准备K线数据 [open, close, low, high]
                    const candleData = data.map(k => [k.open, k.close, k.low, k.high]);
                    const volumes = data.map((k, i) => [i, k.volume, k.close > k.open ? 1 : -1]);
                    
                    const option = {
                        backgroundColor: 'transparent',
                        animation: false,
                        legend: { data: ['K线', 'MA5', 'MA10', 'MA20'], textStyle: { color: '#8b949e' }, top: 10 },
                        tooltip: {
                            trigger: 'axis',
                            axisPointer: { type: 'cross' },
                            backgroundColor: 'rgba(13, 17, 23, 0.95)',
                            borderColor: '#30363d',
                            textStyle: { color: '#c9d1d9' }
                        },
                        grid: [{ left: 78, right: 20, top: 42, height: '50%', containLabel: true }, { left: 78, right: 20, top: '68%', height: '16%', containLabel: true }],
                        xAxis: [
                            { type: 'category', data: data.map(k => k.datetime.substring(5, 16)), scale: true, boundaryGap: false, axisLine: { lineStyle: { color: '#30363d' } }, axisLabel: { color: '#8b949e' }, splitLine: { show: false } },
                            { type: 'category', gridIndex: 1, data: data.map(k => k.datetime.substring(5, 16)), axisLabel: { show: false } }
                        ],
                        yAxis: [
                            { scale: true, axisLine: { lineStyle: { color: '#30363d' } }, axisLabel: { color: '#8b949e', margin: 10, formatter: (v) => Number(v).toFixed(2) }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                            { scale: true, gridIndex: 1, axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } }
                        ],
                        dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 }],
                        series: [
                            { name: 'K线', type: 'candlestick', data: candleData, itemStyle: { color: '#23c55e', color0: '#ef4444', borderColor: '#23c55e', borderColor0: '#ef4444' } },
                            { name: 'MA5', type: 'line', data: calculateMA(5, candleData), smooth: true, lineStyle: { opacity: 0.8, width: 1 } },
                            { name: 'MA10', type: 'line', data: calculateMA(10, candleData), smooth: true, lineStyle: { opacity: 0.8, width: 1 } },
                            { name: 'MA20', type: 'line', data: calculateMA(20, candleData), smooth: true, lineStyle: { opacity: 0.8, width: 1 } },
                            { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes.map(v => [v[0], v[1]]), itemStyle: { color: (params) => volumes[params.dataIndex][2] > 0 ? '#23c55e' : '#ef4444' } }
                        ]
                    };
                    
                    myChart.setOption(option);
                    charts[bank] = myChart;
                    
                    window.addEventListener('resize', () => myChart.resize());
                } catch (e) {
                    console.error('加载K线数据失败:', e);
                }
            }
        }
        
        function calculateMA(dayCount, data) {
            const result = [];
            for (let i = 0; i < data.length; i++) {
                if (i < dayCount - 1) {
                    result.push('-');
                    continue;
                }
                let sum = 0;
                for (let j = 0; j < dayCount; j++) {
                    sum += data[i - j][1];
                }
                result.push((sum / dayCount).toFixed(2));
            }
            return result;
        }
        
        function updateStatus(connected) {
            const statusDiv = document.getElementById('wsStatus');
            statusDiv.className = 'ws-status ' + (connected ? 'ws-connected' : 'ws-disconnected');
            statusDiv.innerHTML = '<span>●</span> ' + (connected ? '实时推送中' : '未连接');
        }
        
        function buildWebSocketUrl() {
            if (WS_BASE) {
                if (WS_BASE.startsWith('ws://') || WS_BASE.startsWith('wss://')) {
                    return WS_BASE;
                }
                if (WS_BASE.startsWith('/')) {
                    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    return `${wsProto}//${window.location.host}${WS_BASE}`;
                }
            }
            const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            if (REMOTE_PAGE) {
                return `${wsProto}//${window.location.host}/ws`;
            }
            if (isLikelyGatewayPort) {
                return `${wsProto}//${window.location.host}/ws`;
            }
            return 'ws://' + window.location.hostname + ':8765';
        }

        function connectWebSocket() {
            const wsUrl = buildWebSocketUrl();
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => { updateStatus(true); };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'price_update' && data.prices) {
                    for (const [bank, priceData] of Object.entries(data.prices)) {
                        if (currentData.prices[bank]) {
                            currentData.prices[bank].price = priceData.price;
                            currentData.prices[bank].change_amt = priceData.change_amt;
                            currentData.prices[bank].change_rate = priceData.change_rate;
                        }
                    }
                    currentData.timestamp = data.timestamp;
                    renderPrices();
                    updateRealtimeCharts();
                    document.getElementById('updateTime').textContent = '更新于: ' + formatDateTime(data.timestamp);
                }
            };
            
            ws.onclose = () => { updateStatus(false); setTimeout(connectWebSocket, 3000); };
            ws.onerror = () => { updateStatus(false); };
        }
        
        renderStats();
        renderPrices();
        renderTrades();
        updateRealtimeCharts();
        connectWebSocket();
        initAITab();
        
        setInterval(() => {
            fetch('/api/data').then(r => r.json()).then(data => {
                currentData = data;
                renderStats();
                renderPrices();
                renderTrades();
                updateRealtimeCharts();
                document.getElementById('updateTime').textContent = '更新于: ' + formatDateTime(data.timestamp);
            }).catch(e => console.error('刷新失败:', e));
        }, 2000);
    </script>
</body>
</html>'''


class DashboardV3Server:
    """Dashboard v3 服务器"""
    
    def __init__(self):
        self.proxy = find_working_proxy()
        self.traders = {
            'zheshang': JijinTrader(bank='zheshang', proxy=self.proxy),
            'minsheng': JijinTrader(bank='minsheng', proxy=self.proxy)
        }
        self.trade_manager = TradeManager()
        self.kline_service = KlineService(proxy=self.proxy)
        self._kline_recorder_started = False
        self._start_kline_recorder()

    def _kline_recorder_loop(self):
        """后台定时记录金价，保证 K 线在运行时持续更新。"""
        while True:
            for bank in ['zheshang', 'minsheng']:
                try:
                    self.kline_service.record_price(bank)
                except Exception as e:
                    print(f"K线记录失败({bank}): {e}")
            time.sleep(30)

    def _start_kline_recorder(self):
        if self._kline_recorder_started:
            return
        t = threading.Thread(target=self._kline_recorder_loop, daemon=True)
        t.start()
        self._kline_recorder_started = True
    
    def get_data(self):
        """获取数据"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'prices': {},
            'positions': {},
            'trades': [],
            'stats': self.trade_manager.get_trade_stats()
        }
        
        for bank, trader in self.traders.items():
            self.kline_service.record_price(bank)
            quote = trader.get_quote()
            if quote:
                data['prices'][bank] = {
                    'bank': bank,
                    'name': quote['name'],
                    'price': quote['price'],
                    'yesterday_price': quote['yesterday_price'],
                    'change_amt': quote['change_amt'],
                    'change_rate': quote['change_rate'],
                    'datetime': quote['datetime'],
                    'is_trading': trader.is_trading_time()
                }
            data['positions'][bank] = trader.get_summary()
        
        trades = self.trade_manager.get_all_trades()
        trades.reverse()
        for t in trades[:20]:
            data['trades'].append({
                'time': t.time,
                'action': t.action,
                'bank': t.bank,
                'price': t.price,
                'grams': t.grams,
                'cost': t.cost,
                'fee': t.fee,
                'profit': t.profit
            })
        
        return data
    
    def run(self, host='0.0.0.0', port=5000):
        """运行服务器"""
        app = Flask(__name__)
        CORS(app)
        
        @app.route('/')
        def index():
            data = self.get_data()
            html = HTML_TEMPLATE.replace('INITIAL_DATA', json.dumps(data))
            return html
        
        @app.route('/api/data')
        def api_data():
            return jsonify(self.get_data())
        
        @app.route('/api/kline/<bank>')
        def api_kline(bank):
            """获取K线数据"""
            if bank not in ['zheshang', 'minsheng']:
                return jsonify({'error': 'Invalid bank'}), 400

            period = request.args.get('period', '1m')
            limit = request.args.get('limit', 120, type=int)
            limit = max(20, min(limit, 500))

            self.kline_service.record_price(bank)
            chart_data = self.kline_service.get_kline_data(bank, period=period, limit=limit)
            fallback = False

            if period != '1m' and len(chart_data) < 20:
                minute_data = self.kline_service.get_kline_data(bank, period='1m', limit=limit)
                if len(minute_data) > len(chart_data):
                    chart_data = minute_data
                    period = '1m'
                    fallback = True

            if len(chart_data) < 2:
                chart_data = []

            for item in chart_data:
                if isinstance(item.get('datetime'), str):
                    item['datetime'] = item['datetime'].replace('T', ' ')
            return jsonify({
                'bank': bank,
                'period': period,
                'fallback': fallback,
                'count': len(chart_data),
                'data': chart_data
            })
        
        @app.route('/api/health')
        def health():
            return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

        print('=' * 60)
        print('🚀 积存金 Dashboard v3.0 启动')
        print('=' * 60)
        print(f'地址: http://{host}:{port}')
        print()
        
        app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    
    server = DashboardV3Server()
    server.run(host=args.host, port=args.port)
