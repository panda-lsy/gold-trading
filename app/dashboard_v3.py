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
        :root {
            --ai-sidebar-top: 100px;
            --ai-sidebar-right: 14px;
            --ai-sidebar-width: 390px;
            --ai-sidebar-bottom-gap: 12px;
        }
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
        .page-controls { display: flex; justify-content: flex-end; margin: -4px 0 14px; }
        .pnl-toggle-btn {
            border: 1px solid #3d5f98;
            border-radius: 999px;
            background: rgba(16, 31, 58, 0.92);
            color: #d5e7ff;
            cursor: pointer;
            padding: 7px 14px;
            font-size: 12px;
            transition: all 0.2s;
        }
        .pnl-toggle-btn:hover { border-color: #78a6ff; transform: translateY(-1px); }
        .pnl-toggle-btn.active { background: rgba(54, 112, 204, 0.88); border-color: #8db8ff; color: #eff6ff; }
        .trade-ops { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
        .trade-op-btn { border: 1px solid #30363d; border-radius: 10px; cursor: pointer; padding: 10px 12px; font-size: 0.92em; transition: all 0.2s; }
        .trade-op-buy { background: rgba(35, 197, 94, 0.15); color: #7ef0aa; }
        .trade-op-sell { background: rgba(239, 68, 68, 0.14); color: #ffb3b3; }
        .trade-op-topup { background: rgba(76, 145, 255, 0.14); color: #b9d7ff; }
        .trade-op-btn:hover { transform: translateY(-1px); border-color: #5d7ec7; }
        .trade-op-tip { margin-top: 8px; color: #8b949e; font-size: 12px; }
        .trade-modal-mask {
            position: fixed;
            inset: 0;
            background: rgba(2, 6, 18, 0.78);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 999;
            padding: 14px;
        }
        .trade-modal {
            width: min(460px, 100%);
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 14px;
            box-shadow: 0 18px 42px rgba(0,0,0,0.45);
            overflow: hidden;
        }
        .trade-modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 16px;
            border-bottom: 1px solid #30363d;
        }
        .trade-modal-title { font-size: 1.02em; color: #e6edf3; }
        .trade-modal-close { background: transparent; border: none; color: #8b949e; font-size: 18px; cursor: pointer; }
        .trade-modal-body { padding: 16px; }
        .trade-quote { background: rgba(255,255,255,0.03); border: 1px solid #30363d; border-radius: 10px; padding: 12px; margin-bottom: 12px; }
        .trade-quote-main { font-size: 1.3em; color: #ffd97a; margin-bottom: 4px; }
        .trade-quote-sub { font-size: 0.88em; color: #8b949e; }
        .trade-modal-field label { display: block; color: #8b949e; font-size: 12px; margin-bottom: 6px; }
        .trade-modal-field input { width: 100%; }
        .trade-modal-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
        .trade-modal-msg { margin-top: 10px; min-height: 46px; color: #d9e6ff; white-space: pre-wrap; line-height: 1.5; font-size: 13px; }
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
        .chat-header-row { display: flex; align-items: center; justify-content: space-between; }
        .chat-header-actions { display: flex; align-items: center; gap: 8px; }
        .chat-window { flex: 1; min-height: 180px; max-height: 265px; overflow: auto; border: 1px solid #36507a; border-radius: 10px; padding: 12px 12px 4px; background: #0f1830; margin-bottom: 10px; }
        .chat-window::-webkit-scrollbar { width: 10px; }
        .chat-window::-webkit-scrollbar-track { background: #0a1224; border-radius: 10px; }
        .chat-window::-webkit-scrollbar-thumb { background: linear-gradient(180deg, #2e73d8, #6ca7ff); border-radius: 10px; border: 2px solid #0a1224; }
        .chat-window { scrollbar-width: thin; scrollbar-color: #4d8cf1 #0a1224; }
        .chat-item { margin-bottom: 10px; display: flex; flex-direction: column; gap: 4px; }
        .role { font-size: 12px; color: #8b949e; margin-bottom: 0; }
        .bubble { max-width: 92%; background: rgba(255,255,255,0.06); border: 1px solid #36507a; border-radius: 12px; padding: 9px 10px; white-space: pre-wrap; line-height: 1.5; }
        .chat-item.user .role { text-align: right; color: #9dc3ff; }
        .chat-item.user .bubble {
            align-self: flex-end;
            background: linear-gradient(135deg, rgba(58, 129, 231, 0.92), rgba(40, 102, 188, 0.92));
            border-color: rgba(121, 178, 255, 0.65);
            color: #edf5ff;
        }
        .chat-item.ai .bubble { align-self: flex-start; }
        .chat-item.system .role { color: #c8a969; }
        .chat-item.system .bubble {
            align-self: stretch;
            max-width: 100%;
            background: rgba(255, 217, 122, 0.08);
            border: 1px dashed rgba(255, 217, 122, 0.4);
            color: #ffe8bf;
        }
        .loading-inline { display: inline-flex; align-items: center; gap: 8px; color: #cfe2ff; }
        .spinner { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.2); border-top-color: #7ab3ff; border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .ctrl-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .chat-composer {
            display: grid;
            grid-template-columns: 40px 1fr 40px;
            gap: 8px;
            align-items: center;
            margin-top: 4px;
        }
        .composer-input-wrap {
            border: 1px solid #36507a;
            border-radius: 999px;
            background: rgba(7, 16, 35, 0.9);
            padding: 0 10px;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        .composer-input-wrap:focus-within { border-color: #7eaefc; box-shadow: 0 0 0 2px rgba(126, 174, 252, 0.2); }
        .composer-input-wrap .input {
            border: none;
            background: transparent;
            padding: 10px 0;
            min-width: 0;
        }
        .composer-input-wrap .input:focus { outline: none; }
        .composer-icon-btn {
            width: 40px;
            height: 40px;
            border-radius: 999px;
            border: 1px solid #4d6aa6;
            background: rgba(19, 35, 65, 0.9);
            color: #d8e8ff;
            cursor: pointer;
            font-size: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }
        .btn-icon-wrap { width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; }
        .btn-icon-svg {
            width: 18px;
            height: 18px;
            stroke: currentColor;
            stroke-width: 2;
            fill: none;
            stroke-linecap: round;
            stroke-linejoin: round;
            display: block;
        }
        .btn-label { font-size: 13px; letter-spacing: 0.2px; }
        .composer-icon-btn:hover { border-color: #78a6ff; background: rgba(31, 55, 97, 0.95); }
        .composer-icon-btn.recording {
            background: rgba(176, 53, 53, 0.95);
            border-color: #ef7777;
            box-shadow: 0 0 0 2px rgba(239, 119, 119, 0.2);
        }
        .composer-icon-btn.send {
            background: linear-gradient(135deg, rgba(53,120,216,0.95), rgba(81,150,247,0.95));
            border-color: #7ab3ff;
            font-size: 14px;
            font-weight: 700;
            width: auto;
            min-width: 64px;
            padding: 0 12px;
        }
        .composer-icon-btn.muted { opacity: 0.55; cursor: not-allowed; }
        .chat-upload-preview {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            border: 1px solid rgba(122, 166, 255, 0.35);
            border-radius: 8px;
            background: rgba(12, 24, 51, 0.9);
            color: #dbe7ff;
            padding: 6px 10px;
            margin-bottom: 8px;
        }
        .chat-upload-main { display: flex; align-items: center; gap: 8px; min-width: 0; }
        .chat-upload-thumb {
            width: 44px;
            height: 44px;
            border-radius: 8px;
            object-fit: cover;
            border: 1px solid rgba(122, 166, 255, 0.45);
            background: rgba(5, 11, 24, 0.85);
            flex: 0 0 auto;
        }
        #chatUploadName {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 210px;
            font-size: 12px;
        }
        .chat-upload-remove {
            border: 1px solid #45639e;
            border-radius: 999px;
            padding: 2px 8px;
            background: rgba(17, 34, 65, 0.95);
            color: #d3e4ff;
            cursor: pointer;
        }
        .chat-bubble-image {
            width: 132px;
            max-width: 100%;
            border-radius: 10px;
            object-fit: cover;
            border: 1px solid rgba(193, 220, 255, 0.5);
            display: block;
            margin-bottom: 6px;
            background: rgba(9, 19, 36, 0.8);
        }
        .chat-bubble-text { line-height: 1.45; }
        .chat-composer.dragover {
            border: 1px dashed #84b2ff;
            border-radius: 12px;
            padding: 6px;
            background: rgba(52, 97, 171, 0.18);
        }
        .voice-toggle-btn {
            width: 38px;
            height: 38px;
            border-radius: 999px;
            border: 1px solid #4d6aa6;
            background: rgba(19, 35, 65, 0.9);
            color: #d8e8ff;
            cursor: pointer;
            font-size: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            position: relative;
        }
        .voice-toggle-btn:hover { border-color: #78a6ff; background: rgba(31, 55, 97, 0.95); }
        .voice-toggle-btn.active { box-shadow: 0 0 0 2px rgba(76, 140, 255, 0.22); }
        .voice-toggle-btn.muted { opacity: 0.62; }
        .voice-toggle-btn.busy { color: transparent; pointer-events: none; }
        .voice-toggle-btn .btn-icon-wrap { width: 18px; height: 18px; }
        .voice-toggle-btn .btn-icon-svg { width: 18px; height: 18px; }
        .voice-toggle-btn.busy::after {
            content: '';
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.22);
            border-top-color: #d9ebff;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            position: absolute;
            inset: 0;
            margin: auto;
        }
        .stop-stream-btn {
            border-color: #c06a6a;
            background: rgba(122, 38, 38, 0.95);
            color: #ffe5e5;
        }
        .stop-stream-btn:hover { border-color: #ef9292; background: rgba(150, 44, 44, 0.95); }
        .chat-image-preview-mask {
            position: fixed;
            inset: 0;
            background: rgba(3, 8, 18, 0.82);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1200;
            padding: 20px;
        }
        .chat-image-preview-large {
            max-width: min(780px, 92vw);
            max-height: 82vh;
            border-radius: 12px;
            border: 1px solid rgba(157, 195, 255, 0.65);
            box-shadow: 0 22px 60px rgba(0, 0, 0, 0.45);
            object-fit: contain;
            background: rgba(7, 15, 32, 0.95);
        }
        .mic-btn {
            border: 1px solid #4a7cc7;
            border-radius: 999px;
            background: linear-gradient(135deg, rgba(32,70,136,0.95), rgba(66,111,193,0.95));
            color: #e8f1ff;
            font-weight: 600;
            padding: 8px 14px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .mic-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(55, 103, 187, 0.35); }
        .mic-btn.listening {
            background: linear-gradient(135deg, rgba(173,55,55,0.95), rgba(224,92,92,0.95));
            border-color: #ef7777;
            box-shadow: 0 0 0 2px rgba(239, 119, 119, 0.2);
        }
        .mic-btn.muted { opacity: 0.55; cursor: not-allowed; }
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
            right: var(--ai-sidebar-right);
            top: var(--ai-sidebar-top);
            width: var(--ai-sidebar-width);
            height: calc(100vh - var(--ai-sidebar-top) - var(--ai-sidebar-bottom-gap));
            overflow: hidden;
            padding-right: 0;
            z-index: 90;
            transition: transform 0.25s ease, opacity 0.25s ease;
        }
        .ai-sidebar-toggle {
            position: fixed;
            right: calc(var(--ai-sidebar-right) + var(--ai-sidebar-width) + 8px);
            top: calc(var(--ai-sidebar-top) + 24px);
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
            transform: translateX(calc(var(--ai-sidebar-width) + 22px));
            opacity: 0;
            pointer-events: none;
        }
        body.ai-collapsed .ai-sidebar-toggle {
            right: var(--ai-sidebar-right);
        }
        body.no-ai-sidebar #tab-ai.ai-embedded,
        body.no-ai-sidebar .ai-sidebar-toggle {
            display: none !important;
        }
        body.no-ai-sidebar .container {
            padding-right: 20px !important;
        }
        @media (max-width: 1280px) {
            .container { padding-right: calc(var(--ai-sidebar-width) + 20px); }
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
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .header-content { flex-direction: column; gap: 15px; }
            .chat-composer { grid-template-columns: 36px 1fr 54px; }
            .composer-icon-btn { width: 36px; height: 36px; font-size: 16px; }
            .composer-icon-btn.send { min-width: 54px; padding: 0 10px; font-size: 13px; }
            .chat-window { max-height: 235px; }
        }
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
            <div class="page-controls">
                <button id="pnlFeeToggleBtn" class="pnl-toggle-btn" type="button" onclick="togglePnLFeeMode()">浮动盈亏：不计入预估卖出手续费</button>
            </div>
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
                    <div class="tiny" id="aiContextHint" style="margin-top: 6px;">对话优先走 VL 模型分析，模型状态灯会自动刷新。</div>
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
                <button class="ai-window-btn" id="btn-ai-vision" onclick="switchAIWindow('vision', this)">视觉分析</button>
                <button class="ai-window-btn" id="btn-ai-image" onclick="switchAIWindow('image', this)">快报生成</button>
            </div>

            <div class="ai-window active" id="ai-window-chat">
                <div class="card ai-chat-card" style="margin-bottom: 10px;">
                    <div class="card-header chat-header-row">
                        <div class="card-title">语音聊天（可选上传图片）</div>
                        <div class="chat-header-actions">
                            <button class="voice-toggle-btn active" id="ttsToggleBtn" title="回复语音播报开关" onclick="toggleTTS()"></button>
                            <button class="voice-toggle-btn stop-stream-btn" id="streamStopBtn" title="停止当前生成" onclick="stopChatStream()" style="display:none;"></button>
                        </div>
                    </div>
                    <div id="chatWindow" class="chat-window"></div>
                    <div id="chatUploadPreview" class="chat-upload-preview" style="display:none;">
                        <div class="chat-upload-main">
                            <img id="chatUploadThumb" class="chat-upload-thumb" alt="图片预览" />
                            <span id="chatUploadName">已选择图片</span>
                        </div>
                        <button class="chat-upload-remove" type="button" onclick="clearChatImageSelection()">移除</button>
                    </div>
                    <div class="chat-composer">
                        <button class="composer-icon-btn" id="micBtn" title="开始语音输入" onclick="toggleMic()"></button>
                        <div class="composer-input-wrap"><input id="chatInput" class="input" type="text" placeholder="输入问题，回车发送；Ctrl+V 可粘贴图片" /></div>
                        <button class="composer-icon-btn" id="chatActionBtn" title="添加图片" onclick="handleChatAction()"></button>
                        <input id="chatImage" type="file" accept="image/*" style="display:none;" />
                    </div>
                    <div class="tiny" id="micStatus" style="margin-top: 8px;">麦克风状态：未启动</div>
                </div>
            </div>

            <div class="ai-window" id="ai-window-vision">
                <div class="ai-window-grid">
                    <div class="card">
                        <div class="card-header chat-header-row">
                            <div class="card-title">K线专项分析（自动截取）</div>
                            <button class="voice-toggle-btn active" id="visionTtsToggleBtn" title="视觉分析语音播报开关" onclick="toggleVisionTTS()"></button>
                        </div>
                        <div class="tiny" style="margin-bottom: 10px;">无需上传文件，系统将自动从 K 线数据生成图像快照并分析。</div>
                        <div class="ctrl-row">
                            <button class="tab" style="padding: 8px 14px;" onclick="runVLMKlineAuto('zheshang')">分析浙商K线</button>
                            <button class="tab" style="padding: 8px 14px;" onclick="runVLMKlineAuto('minsheng')">分析民生K线</button>
                        </div>
                        <div id="vlmImageOut" class="out">等待执行...</div>
                    </div>
                </div>
            </div>

            <div class="ai-window" id="ai-window-image">
                <div class="card">
                    <div class="card-header"><div class="card-title">图像生成：行情快报</div></div>
                    <input id="briefTitle" class="input" type="text" value="积存金行情快报" />
                    <div class="ctrl-row">
                        <button class="tab" style="padding: 8px 14px;" onclick="generateBriefImage()">生成快报图</button>
                        <button class="tab" style="padding: 8px 14px;" onclick="generateBriefImageAndDownload()">生成并下载</button>
                        <button class="tab" style="padding: 8px 14px;" onclick="previewBriefNews()">预览新闻源</button>
                        <a id="briefDownload" href="#" target="_blank" rel="noopener" class="tiny">打开最新图片</a>
                    </div>
                    <div class="tiny" style="margin-top: 8px;">
                        <label><input id="briefUseExternalNews" type="checkbox" checked /> 启用联网快讯（含金十分类 + 联网搜索）</label>
                    </div>
                    <div id="briefOut" class="out">等待执行...</div>
                    <img id="briefImage" class="img-preview" style="display:none;" />
                </div>
            </div>
        </div>
    </div>

    <div id="tradeModalMask" class="trade-modal-mask" onclick="closeTradeModal()">
        <div class="trade-modal" onclick="event.stopPropagation()">
            <div class="trade-modal-header">
                <div class="trade-modal-title" id="tradeModalTitle">手动模拟交易</div>
                <button class="trade-modal-close" type="button" onclick="closeTradeModal()">×</button>
            </div>
            <div class="trade-modal-body">
                <div class="trade-quote">
                    <div class="trade-quote-main" id="tradeModalPrice">-- 元/克</div>
                    <div class="trade-quote-sub" id="tradeModalQuoteMeta">最新行情: --</div>
                </div>
                <div class="trade-modal-field">
                    <label for="tradeModalGrams">输入交易克数</label>
                    <input id="tradeModalGrams" class="input" type="number" min="0.01" step="0.01" value="1" />
                </div>
                <div class="trade-modal-actions">
                    <button class="trade-op-btn" type="button" onclick="closeTradeModal()">取消</button>
                    <button class="trade-op-btn" id="tradeModalConfirm" type="button" onclick="confirmTradeFromModal()">确认</button>
                </div>
                <div class="trade-modal-msg" id="tradeModalMsg"></div>
            </div>
        </div>
    </div>

    <div id="rechargeModalMask" class="trade-modal-mask" onclick="closeRechargeModal()">
        <div class="trade-modal" onclick="event.stopPropagation()">
            <div class="trade-modal-header">
                <div class="trade-modal-title" id="rechargeModalTitle">增加余额</div>
                <button class="trade-modal-close" type="button" onclick="closeRechargeModal()">×</button>
            </div>
            <div class="trade-modal-body">
                <div class="trade-quote">
                    <div class="trade-quote-main" id="rechargeBalanceNow">-- 元</div>
                    <div class="trade-quote-sub" id="rechargeBalanceMeta">当前账户余额</div>
                </div>
                <div class="trade-modal-field">
                    <label for="rechargeAmount">输入充值金额（元）</label>
                    <input id="rechargeAmount" class="input" type="number" min="0.01" step="0.01" value="1000" />
                </div>
                <div class="trade-modal-actions">
                    <button class="trade-op-btn" type="button" onclick="closeRechargeModal()">取消</button>
                    <button class="trade-op-btn trade-op-topup" type="button" onclick="confirmRecharge()">确认增加</button>
                </div>
                <div class="trade-modal-msg" id="rechargeModalMsg"></div>
            </div>
        </div>
    </div>

    <div id="chatImagePreviewMask" class="chat-image-preview-mask" onclick="closeChatImagePreview()">
        <img id="chatImagePreviewLarge" class="chat-image-preview-large" alt="图片预览" onclick="event.stopPropagation()" />
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
        const DASHBOARD_PORTS = DASHBOARD_PORTS_JSON;
        const DASHBOARD_API_PORT = Number(DASHBOARD_PORTS.api || 8080);
        const DASHBOARD_WS_PORT = Number(DASHBOARD_PORTS.websocket || 8765);

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
        const API_DIRECT = (REMOTE_PAGE || isLikelyGatewayPort)
            ? CURRENT_ORIGIN
            : `${PROTOCOL}//${HOST}:${DASHBOARD_API_PORT}`;
        const API = QUERY_API_BASE || (!SHOULD_IGNORE_CONFIG_API && CONFIG_API_BASE) || API_DIRECT;

        const CONFIG_WS_BASE = (window.__WS_BASE__ || '').trim();
        const WS_BASE = QUERY_WS_BASE || CONFIG_WS_BASE;
        const DISABLE_AI_SIDEBAR = URL_PARAMS.get('embed') === '1' || URL_PARAMS.get('hide_ai') === '1';
        let recognition = null;
        let listening = false;
        let micAbortRequested = false;
        let micFinalTranscript = '';
        let aiInitialized = false;
        let aiCollapsed = false;
        let activeTradeContext = null;
        let activeRechargeBank = null;
        let includeFeeInUnrealized = false;
        let ttsEnabled = true;
        let ttsBusy = false;
        let ttsQueue = Promise.resolve();
        let ttsAbortController = null;
        let ttsActiveRequestId = '';
        let ttsAudioPlayer = null;
        let visionTtsEnabled = true;
        let visionTtsBusy = false;
        let visionTtsAbortController = null;
        let visionTtsActiveRequestId = '';
        let visionTtsAudioPlayer = null;
        let chatComposerBound = false;
        let chatSelectedImageFile = null;
        let chatUploadPreviewUrl = null;
        let chatStreamAbortController = null;
        let chatStreaming = false;
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

        function updateAISidebarMetrics() {
            if (DISABLE_AI_SIDEBAR) return;
            const header = document.querySelector('.header');
            const root = document.documentElement;
            if (!header || !root) return;

            const headerHeight = Math.ceil(header.getBoundingClientRect().height || 0);
            const top = Math.max(92, headerHeight + 10);
            root.style.setProperty('--ai-sidebar-top', `${top}px`);
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
            const loading = !ok && (msg.includes('loading') || msg.includes('加载中') || msg.includes('初始化中') || msg.includes('initializing'));
            const notLoaded = !ok && (msg.includes('not loaded') || msg.includes('未加载') || msg.includes('未初始化'));
            const notDeployed = !ok && (
                msg.includes('模型不存在') ||
                msg.includes('请从 modelscope 下载') ||
                msg.includes('未部署') ||
                msg.includes('检查模型目录')
            );
            const statusText = ok
                ? '就绪'
                : (loading ? '加载中' : (notLoaded ? '未加载' : (notDeployed ? '未部署' : '异常')));
            const stateClass = ok
                ? 'tag-ready'
                : ((loading || notLoaded || notDeployed) ? 'tag-loading' : 'tag-down');
            tag.className = 'model-tag ' + stateClass;
            tag.textContent = `${labels[key] || key.toUpperCase()}: ${statusText}`;
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

        function loadingMarkup(text) {
            return `<span class="loading-inline"><span class="spinner"></span>${String(text || '处理中...')}</span>`;
        }

        function escapeHtml(text) {
            return String(text || '').replace(/[&<>"']/g, (ch) => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            }[ch]));
        }

        function setOutLoading(outEl, text) {
            if (!outEl) return;
            outEl.innerHTML = loadingMarkup(text || '处理中...');
        }

        function renderButtonIcon(kind) {
            const icons = {
                speakerOn: `<svg class="btn-icon-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4z"></path><path d="M15 9a5 5 0 0 1 0 6"></path><path d="M18 7a8 8 0 0 1 0 10"></path></svg>`,
                speakerOff: `<svg class="btn-icon-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4z"></path><path d="M22 2 2 22"></path></svg>`,
                mic: `<svg class="btn-icon-svg" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="12" rx="3"></rect><path d="M5 11a7 7 0 0 0 14 0"></path><path d="M12 18v3"></path><path d="M8 21h8"></path></svg>`,
                stop: `<svg class="btn-icon-svg" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><rect x="9" y="9" width="6" height="6" rx="1"></rect></svg>`,
                plus: `<svg class="btn-icon-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14"></path><path d="M5 12h14"></path></svg>`
            };
            return `<span class="btn-icon-wrap">${icons[kind] || ''}</span>`;
        }

        function setButtonIcon(btn, kind) {
            if (!btn) return;
            btn.innerHTML = renderButtonIcon(kind);
        }

        function setButtonLabel(btn, labelText) {
            if (!btn) return;
            btn.innerHTML = `<span class="btn-label">${labelText}</span>`;
        }

        function cancelActiveTTS() {
            const rid = ttsActiveRequestId;
            ttsActiveRequestId = '';

            if (ttsAbortController) {
                try { ttsAbortController.abort(); } catch (_) {}
                ttsAbortController = null;
            }
            if (rid) {
                fetch(`${API}/api/ai/tts/cancel`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ request_id: rid })
                }).catch(() => {});
            }
            if (ttsAudioPlayer) {
                try {
                    ttsAudioPlayer.pause();
                    ttsAudioPlayer.currentTime = 0;
                } catch (_) {}
            }
            ttsBusy = false;
            updateTTSButton();
        }

        function updateTTSButton() {
            const btn = document.getElementById('ttsToggleBtn');
            if (!btn) return;

            btn.className = 'voice-toggle-btn';
            if (ttsEnabled) btn.classList.add('active');
            else btn.classList.add('muted');
            if (ttsBusy) btn.classList.add('busy');

            setButtonIcon(btn, ttsEnabled ? 'speakerOn' : 'speakerOff');
            btn.title = ttsEnabled ? '点击关闭回复语音播报' : '点击开启回复语音播报';
        }

        function updateVisionTTSButton() {
            const btn = document.getElementById('visionTtsToggleBtn');
            if (!btn) return;

            btn.className = 'voice-toggle-btn';
            if (visionTtsEnabled) btn.classList.add('active');
            else btn.classList.add('muted');
            if (visionTtsBusy) btn.classList.add('busy');

            setButtonIcon(btn, visionTtsEnabled ? 'speakerOn' : 'speakerOff');
            btn.title = visionTtsEnabled ? '点击关闭视觉分析语音播报' : '点击开启视觉分析语音播报';
        }

        function cancelVisionTTS() {
            const rid = visionTtsActiveRequestId;
            visionTtsActiveRequestId = '';

            if (visionTtsAbortController) {
                try { visionTtsAbortController.abort(); } catch (_) {}
                visionTtsAbortController = null;
            }
            if (rid) {
                fetch(`${API}/api/ai/tts/cancel`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ request_id: rid })
                }).catch(() => {});
            }
            if (visionTtsAudioPlayer) {
                try {
                    visionTtsAudioPlayer.pause();
                    visionTtsAudioPlayer.currentTime = 0;
                } catch (_) {}
            }
            visionTtsBusy = false;
            updateVisionTTSButton();
        }

        function toggleVisionTTS() {
            visionTtsEnabled = !visionTtsEnabled;
            if (!visionTtsEnabled) {
                cancelVisionTTS();
            }
            updateVisionTTSButton();
        }

        async function playVisionTTS(rawText) {
            if (!visionTtsEnabled) return;
            const text = toSpeechText(rawText);
            if (!text) return;

            visionTtsBusy = true;
            updateVisionTTSButton();

            const controller = new AbortController();
            visionTtsAbortController = controller;
            const requestId = `vision_${Date.now()}_${Math.random().toString(16).slice(2, 10)}`;
            visionTtsActiveRequestId = requestId;

            try {
                const r = await fetch(`${API}/api/ai/tts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, fast: true, request_id: requestId }),
                    signal: controller.signal,
                });
                const d = await r.json();
                if (!d.success || !d.audio_url) return;

                if (!visionTtsEnabled || visionTtsActiveRequestId !== requestId) return;
                if (!visionTtsAudioPlayer) visionTtsAudioPlayer = new Audio();
                visionTtsAudioPlayer.pause();
                visionTtsAudioPlayer.src = `${API}${d.audio_url}`;

                await new Promise((resolve, reject) => {
                    visionTtsAudioPlayer.onended = () => resolve();
                    visionTtsAudioPlayer.onerror = () => reject(new Error('audio playback error'));
                    const p = visionTtsAudioPlayer.play();
                    if (p && typeof p.then === 'function') p.catch(reject);
                });
            } catch (_) {
            } finally {
                if (visionTtsAbortController === controller) visionTtsAbortController = null;
                if (visionTtsActiveRequestId === requestId) visionTtsActiveRequestId = '';
                visionTtsBusy = false;
                updateVisionTTSButton();
            }
        }

        async function speakVisionText(text) {
            if (!visionTtsEnabled) return;
            cancelVisionTTS();
            return playVisionTTS(text).catch(() => {});
        }

        function toggleTTS() {
            ttsEnabled = !ttsEnabled;
            if (!ttsEnabled) {
                cancelActiveTTS();
                ttsQueue = Promise.resolve();
            }
            updateTTSButton();
        }

        function toSpeechText(text) {
            const src = String(text || '').trim();
            if (!src) return '';
            let cleaned = src
                .replace(/你的问题\s*[:：].*/g, '')
                .replace(/图片理解\s*[:：]/g, '图片分析：')
                .replace(/\\n+/g, '，')
                .replace(/\s+/g, ' ')
                .trim();
            if (cleaned.length > 96) cleaned = cleaned.slice(0, 96) + '。';
            return cleaned;
        }

        async function playTTSOnce(rawText) {
            if (!ttsEnabled) return;
            const text = toSpeechText(rawText);
            if (!text) return;

            ttsBusy = true;
            updateTTSButton();
            const controller = new AbortController();
            ttsAbortController = controller;
            const requestId = `${Date.now()}_${Math.random().toString(16).slice(2, 10)}`;
            ttsActiveRequestId = requestId;

            try {
                const r = await fetch(`${API}/api/ai/tts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, fast: true, request_id: requestId }),
                    signal: controller.signal,
                });
                const d = await r.json();
                if (!d.success || !d.audio_url) return;

                if (!ttsEnabled || ttsActiveRequestId !== requestId) return;
                if (!ttsAudioPlayer) ttsAudioPlayer = new Audio();
                ttsAudioPlayer.pause();
                ttsAudioPlayer.src = `${API}${d.audio_url}`;

                await new Promise((resolve, reject) => {
                    ttsAudioPlayer.onended = () => resolve();
                    ttsAudioPlayer.onerror = () => reject(new Error('audio playback error'));
                    const p = ttsAudioPlayer.play();
                    if (p && typeof p.then === 'function') p.catch(reject);
                });
            } catch (_) {
            } finally {
                if (ttsAbortController === controller) ttsAbortController = null;
                if (ttsActiveRequestId === requestId) ttsActiveRequestId = '';
                ttsBusy = false;
                updateTTSButton();
            }
        }

        function updateMicButtonUI() {
            const btn = document.getElementById('micBtn');
            if (!btn) return;
            btn.className = 'composer-icon-btn' + (listening ? ' recording' : '');
            setButtonIcon(btn, listening ? 'stop' : 'mic');
            btn.title = listening ? '点击停止录音' : '开始语音输入';
        }

        function hasChatImageSelected() {
            return !!chatSelectedImageFile;
        }

        function updateChatUploadPreview() {
            const imageInput = document.getElementById('chatImage');
            const preview = document.getElementById('chatUploadPreview');
            const nameEl = document.getElementById('chatUploadName');
            const thumbEl = document.getElementById('chatUploadThumb');
            if (!imageInput || !preview || !nameEl || !thumbEl) return;

            const file = chatSelectedImageFile || (imageInput.files && imageInput.files[0]);
            if (file) {
                chatSelectedImageFile = file;
                if (chatUploadPreviewUrl) {
                    try { URL.revokeObjectURL(chatUploadPreviewUrl); } catch (_) {}
                    chatUploadPreviewUrl = null;
                }
                chatUploadPreviewUrl = URL.createObjectURL(file);
                thumbEl.src = chatUploadPreviewUrl;
                nameEl.textContent = file.name || 'clipboard-image.png';
                preview.style.display = 'flex';
            } else {
                if (chatUploadPreviewUrl) {
                    try { URL.revokeObjectURL(chatUploadPreviewUrl); } catch (_) {}
                    chatUploadPreviewUrl = null;
                }
                thumbEl.removeAttribute('src');
                preview.style.display = 'none';
            }
        }

        function openChatImagePreview() {
            const mask = document.getElementById('chatImagePreviewMask');
            const large = document.getElementById('chatImagePreviewLarge');
            if (!mask || !large || !chatUploadPreviewUrl) return;
            large.src = chatUploadPreviewUrl;
            mask.style.display = 'flex';
        }

        function closeChatImagePreview() {
            const mask = document.getElementById('chatImagePreviewMask');
            const large = document.getElementById('chatImagePreviewLarge');
            if (mask) mask.style.display = 'none';
            if (large) large.removeAttribute('src');
        }

        function updateChatStreamingState(active) {
            chatStreaming = !!active;
            const stopBtn = document.getElementById('streamStopBtn');
            const actionBtn = document.getElementById('chatActionBtn');
            const input = document.getElementById('chatInput');
            if (stopBtn) {
                stopBtn.style.display = chatStreaming ? 'inline-flex' : 'none';
                setButtonIcon(stopBtn, 'stop');
            }
            if (actionBtn) {
                actionBtn.disabled = chatStreaming;
                actionBtn.classList.toggle('muted', chatStreaming);
            }
            if (input) input.disabled = chatStreaming;
        }

        function stopChatStream() {
            if (chatStreamAbortController) {
                try { chatStreamAbortController.abort(); } catch (_) {}
            }
            cancelActiveTTS();
        }

        function updateChatActionButton() {
            const btn = document.getElementById('chatActionBtn');
            const input = document.getElementById('chatInput');
            if (!btn || !input) return;

            const hasText = (input.value || '').trim().length > 0;
            const hasImage = hasChatImageSelected();
            if (hasText || hasImage) {
                btn.className = 'composer-icon-btn send';
                setButtonLabel(btn, '发送');
                btn.title = '发送消息';
            } else {
                btn.className = 'composer-icon-btn';
                setButtonIcon(btn, 'plus');
                btn.title = '添加图片';
            }
        }

        function clearChatImageSelection() {
            const imageInput = document.getElementById('chatImage');
            chatSelectedImageFile = null;
            if (imageInput) imageInput.value = '';
            if (chatUploadPreviewUrl) {
                try { URL.revokeObjectURL(chatUploadPreviewUrl); } catch (_) {}
                chatUploadPreviewUrl = null;
            }
            updateChatUploadPreview();
            updateChatActionButton();
        }

        function setChatImageFile(file) {
            const imageInput = document.getElementById('chatImage');
            if (!imageInput || !file) return;
            chatSelectedImageFile = file;
            try {
                const dt = new DataTransfer();
                dt.items.add(file);
                imageInput.files = dt.files;
            } catch (_) {
            }
            updateChatUploadPreview();
            updateChatActionButton();
        }

        function handleChatAction() {
            const input = document.getElementById('chatInput');
            const imageInput = document.getElementById('chatImage');
            if (!input || !imageInput) return;

            const hasText = (input.value || '').trim().length > 0;
            const hasImage = hasChatImageSelected();
            if (hasText || hasImage) {
                sendChat();
                return;
            }
            imageInput.click();
        }

        function bindChatComposerEvents() {
            if (chatComposerBound) return;
            const input = document.getElementById('chatInput');
            const imageInput = document.getElementById('chatImage');
            const composer = document.querySelector('.chat-composer');
            const thumbEl = document.getElementById('chatUploadThumb');
            if (!input || !imageInput || !composer) return;

            chatComposerBound = true;
            input.addEventListener('input', () => updateChatActionButton());
            input.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    const hasText = (input.value || '').trim().length > 0;
                    if (hasText || hasChatImageSelected()) {
                        handleChatAction();
                    }
                }
            });
            input.addEventListener('paste', (event) => {
                const items = event.clipboardData && event.clipboardData.items;
                if (!items) return;
                for (let i = 0; i < items.length; i += 1) {
                    const item = items[i];
                    if (item.type && item.type.startsWith('image/')) {
                        const blob = item.getAsFile();
                        if (!blob) return;
                        const file = new File([blob], `paste_${Date.now()}.png`, { type: blob.type || 'image/png' });
                        setChatImageFile(file);
                        event.preventDefault();
                        return;
                    }
                }
            });
            imageInput.addEventListener('change', () => {
                chatSelectedImageFile = (imageInput.files && imageInput.files[0]) || null;
                updateChatUploadPreview();
                updateChatActionButton();
            });
            if (thumbEl) {
                thumbEl.addEventListener('click', openChatImagePreview);
            }

            composer.addEventListener('dragover', (event) => {
                event.preventDefault();
                composer.classList.add('dragover');
            });
            composer.addEventListener('dragleave', () => {
                composer.classList.remove('dragover');
            });
            composer.addEventListener('drop', (event) => {
                event.preventDefault();
                composer.classList.remove('dragover');
                const files = event.dataTransfer && event.dataTransfer.files;
                if (!files || !files.length) return;
                const firstImage = Array.from(files).find((f) => String(f.type || '').startsWith('image/'));
                if (!firstImage) return;
                setChatImageFile(firstImage);
            });
        }

        function addChat(role, content, html = false) {
            const box = document.getElementById('chatWindow');
            if (!box) return null;
            const item = document.createElement('div');
            const roleText = String(role || '');
            const roleClass = roleText === '你' ? 'user' : (roleText === 'AI' ? 'ai' : 'system');
            item.className = `chat-item ${roleClass}`;
            const roleNode = document.createElement('div');
            roleNode.className = 'role';
            roleNode.textContent = roleText;

            const bubbleNode = document.createElement('div');
            bubbleNode.className = 'bubble';
            if (html) bubbleNode.innerHTML = String(content || '');
            else bubbleNode.textContent = String(content || '');

            item.appendChild(roleNode);
            item.appendChild(bubbleNode);
            box.appendChild(item);
            box.scrollTop = box.scrollHeight;
            return { item, bubble: bubbleNode };
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
                const r = await fetch(`${API}/api/ai/capabilities?fast=false`);
                const d = await r.json();
                if (!d.success) throw new Error(d.error || 'unknown error');
                renderCaps(d.capabilities || {});
                const hint = document.getElementById('aiContextHint');
                if (hint) hint.textContent = '对话优先走 VL 模型分析，模型状态灯会自动刷新。';
            } catch (e) {
                ['asr', 'tts', 'vlm', 'image_generation'].forEach((key) => setModelTagState(key, false, e.message));
                const hint = document.getElementById('aiContextHint');
                if (hint) hint.textContent = `模型状态检查失败: ${e.message}`;
            }
        }

        async function fetchCanonicalDashboardData() {
            const candidates = [
                `${API}/api/dashboard`,
                '/api/data'
            ];

            let lastError = null;
            for (const url of candidates) {
                try {
                    const r = await fetch(url);
                    if (!r.ok) throw new Error(`HTTP ${r.status}`);
                    const data = await r.json();
                    if (!data || !data.prices || !data.positions) {
                        throw new Error('invalid dashboard payload');
                    }
                    return data;
                } catch (e) {
                    lastError = e;
                }
            }

            throw (lastError || new Error('dashboard data unavailable'));
        }

        async function refreshDashboardData(snapshot = null) {
            const data = snapshot || await fetchCanonicalDashboardData();
            currentData = data;
            updatePnLToggleButton();
            renderStats();
            renderPrices();
            renderTrades();
            updateRealtimeCharts();
            document.getElementById('updateTime').textContent = '更新于: ' + formatDateTime(data.timestamp);
            return data;
        }

        function getBankLabel(bank) {
            return bank === 'zheshang' ? '浙商积存金' : '民生积存金';
        }

        function getActionLabel(action) {
            return action === 'BUY' ? '买入' : '卖出';
        }

        function updatePnLToggleButton() {
            const btn = document.getElementById('pnlFeeToggleBtn');
            if (!btn) return;
            btn.classList.toggle('active', includeFeeInUnrealized);
            btn.textContent = includeFeeInUnrealized ? '浮动盈亏：计入预估卖出手续费(0.4%)' : '浮动盈亏：不计入预估卖出手续费';
        }

        function togglePnLFeeMode(forceValue = null) {
            if (typeof forceValue === 'boolean') includeFeeInUnrealized = forceValue;
            else includeFeeInUnrealized = !includeFeeInUnrealized;

            try {
                localStorage.setItem('dashboard.pnlIncludeFee', includeFeeInUnrealized ? '1' : '0');
            } catch (_) {
            }

            updatePnLToggleButton();
            renderPrices();
        }

        function openRechargeModal(bank) {
            activeRechargeBank = bank;
            const maskEl = document.getElementById('rechargeModalMask');
            const titleEl = document.getElementById('rechargeModalTitle');
            const nowEl = document.getElementById('rechargeBalanceNow');
            const metaEl = document.getElementById('rechargeBalanceMeta');
            const amountEl = document.getElementById('rechargeAmount');
            const msgEl = document.getElementById('rechargeModalMsg');
            if (!maskEl || !titleEl || !nowEl || !metaEl || !amountEl || !msgEl) return;

            const pos = currentData.positions?.[bank] || {};
            const currentBalance = Number(pos.balance || 0);
            titleEl.textContent = `${getBankLabel(bank)} · 增加余额`;
            nowEl.textContent = `${currentBalance.toFixed(2)} 元`;
            metaEl.textContent = '当前账户余额';
            msgEl.textContent = '';
            amountEl.value = '1000';
            maskEl.style.display = 'flex';
            amountEl.focus();
            amountEl.select();
        }

        function closeRechargeModal() {
            const maskEl = document.getElementById('rechargeModalMask');
            if (maskEl) maskEl.style.display = 'none';
            activeRechargeBank = null;
        }

        async function confirmRecharge() {
            if (!activeRechargeBank) return;
            const amountEl = document.getElementById('rechargeAmount');
            const msgEl = document.getElementById('rechargeModalMsg');
            if (!amountEl || !msgEl) return;

            const amount = Number.parseFloat(amountEl.value || '0');
            if (!Number.isFinite(amount) || amount <= 0) {
                msgEl.textContent = '请输入大于 0 的充值金额。';
                return;
            }

            msgEl.textContent = '充值处理中...';
            try {
                const r = await fetch(`${API}/api/account/recharge`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bank: activeRechargeBank, amount })
                });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || '充值失败');
                await refreshDashboardData(d.snapshot || null);
                msgEl.textContent = d.message || '余额增加成功';
            } catch (e) {
                msgEl.textContent = `失败: ${e.message}`;
            }
        }

        function updateTradeModalQuote() {
            const priceEl = document.getElementById('tradeModalPrice');
            const metaEl = document.getElementById('tradeModalQuoteMeta');
            if (!priceEl || !metaEl || !activeTradeContext) return;

            const priceInfo = (currentData.prices || {})[activeTradeContext.bank] || {};
            const price = Number(priceInfo.price || 0);
            const changeRate = priceInfo.change_rate || '--';
            const changeAmt = priceInfo.change_amt || '--';
            const ts = priceInfo.datetime || currentData.timestamp || '--';
            priceEl.textContent = `${price > 0 ? price.toFixed(2) : '--'} 元/克`;
            metaEl.textContent = `最新行情: ${changeAmt} (${changeRate}) · 更新时间 ${formatDateTime(ts)}`;
        }

        function openTradeModal(bank, action) {
            activeTradeContext = {
                bank,
                action: String(action || 'BUY').toUpperCase()
            };

            const titleEl = document.getElementById('tradeModalTitle');
            const confirmEl = document.getElementById('tradeModalConfirm');
            const gramsEl = document.getElementById('tradeModalGrams');
            const msgEl = document.getElementById('tradeModalMsg');
            const maskEl = document.getElementById('tradeModalMask');
            if (!titleEl || !confirmEl || !gramsEl || !msgEl || !maskEl) return;

            const actionLabel = getActionLabel(activeTradeContext.action);
            titleEl.textContent = `${getBankLabel(bank)} · ${actionLabel}`;
            confirmEl.textContent = `确认${actionLabel}`;
            confirmEl.className = 'trade-op-btn ' + (activeTradeContext.action === 'BUY' ? 'trade-op-buy' : 'trade-op-sell');
            msgEl.textContent = '';
            gramsEl.value = '1';
            updateTradeModalQuote();
            maskEl.style.display = 'flex';
            gramsEl.focus();
            gramsEl.select();
        }

        function closeTradeModal() {
            const maskEl = document.getElementById('tradeModalMask');
            if (maskEl) maskEl.style.display = 'none';
            activeTradeContext = null;
        }

        async function submitManualTrade(bank, action, grams) {
            const r = await fetch(`${API}/api/trade/manual`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bank, action, grams })
            });
            const d = await r.json();
            if (!d.success) throw new Error(d.error || '模拟交易失败');
            await refreshDashboardData(d.snapshot || null);
            return d;
        }

        async function confirmTradeFromModal() {
            if (!activeTradeContext) return;

            const gramsEl = document.getElementById('tradeModalGrams');
            const msgEl = document.getElementById('tradeModalMsg');
            if (!gramsEl || !msgEl) return;

            const grams = Number.parseFloat(gramsEl.value || '0');
            if (!Number.isFinite(grams) || grams <= 0) {
                msgEl.textContent = '请输入大于 0 的克数。';
                return;
            }

            const bank = activeTradeContext.bank;
            const action = activeTradeContext.action;
            const actionLabel = getActionLabel(action);
            msgEl.textContent = `${actionLabel}执行中...`;

            try {
                const d = await submitManualTrade(bank, action, grams);
                const trade = d.trade || {};
                msgEl.textContent = [
                    d.message || '操作成功',
                    `${getBankLabel(bank)} ${actionLabel} ${Number(trade.grams || grams).toFixed(2)} 克 @ ${Number(trade.price || 0).toFixed(2)} 元/克`,
                    trade.fee ? `手续费: ${Number(trade.fee).toFixed(2)} 元` : '',
                    trade.profit !== undefined ? `盈亏: ${(Number(trade.profit || 0) >= 0 ? '+' : '')}${Number(trade.profit || 0).toFixed(2)} 元` : ''
                ].filter(Boolean).join('\\n');
                updateTradeModalQuote();
            } catch (e) {
                msgEl.textContent = `失败: ${e.message}`;
            }
        }

        async function speakText(text) {
            if (!ttsEnabled) return;
            cancelActiveTTS();
            ttsQueue = playTTSOnce(text).catch(() => {});
            return ttsQueue;
        }

        function appendChatDelta(pending, text) {
            if (!pending || !pending.bubble) return;
            const next = String(text || '');
            if (!next) return;
            pending.bubble.textContent = (pending.bubble.textContent || '') + next;
            const box = document.getElementById('chatWindow');
            if (box) box.scrollTop = box.scrollHeight;
        }

        async function requestChatOnce(message, selectedImage) {
            let r;
            if (selectedImage) {
                const fd = new FormData();
                fd.append('message', message);
                fd.append('image', selectedImage, selectedImage.name || 'chat-image.png');
                r = await fetch(`${API}/api/ai/chat`, { method: 'POST', body: fd });
            } else {
                r = await fetch(`${API}/api/ai/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message })
                });
            }
            const d = await r.json();
            if (!d.success) throw new Error(d.error || d.message || `HTTP ${r.status}`);
            return d;
        }

        async function requestChatStream(message, selectedImage, pending, options = {}) {
            const signal = options && options.signal;
            let r;
            if (selectedImage) {
                const fd = new FormData();
                fd.append('message', message);
                fd.append('image', selectedImage, selectedImage.name || 'chat-image.png');
                r = await fetch(`${API}/api/ai/chat/stream`, { method: 'POST', body: fd, signal });
            } else {
                r = await fetch(`${API}/api/ai/chat/stream`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message }),
                    signal
                });
            }

            if (!r.ok) {
                let errMsg = `HTTP ${r.status}`;
                try {
                    const d = await r.json();
                    errMsg = d.error || d.message || errMsg;
                } catch (_) {
                }
                throw new Error(errMsg);
            }

            const ctype = (r.headers.get('content-type') || '').toLowerCase();
            if (!ctype.includes('text/event-stream')) {
                throw new Error('服务端未返回流式响应');
            }
            if (!r.body || !r.body.getReader) {
                throw new Error('当前环境不支持流式读取');
            }

            const reader = r.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';
            let finalReply = '';
            let imageUrl = null;
            let done = false;
            let pendingDelta = '';
            let rafId = 0;

            const abortError = () => {
                const e = new Error('用户已停止生成');
                e.name = 'AbortError';
                return e;
            };

            const flushDelta = () => {
                if (!pendingDelta) return;
                const chunk = pendingDelta;
                pendingDelta = '';
                appendChatDelta(pending, chunk);
            };

            const scheduleFlush = () => {
                if (rafId) return;
                rafId = window.requestAnimationFrame(() => {
                    rafId = 0;
                    flushDelta();
                });
            };

            const handleAbort = () => {
                try { reader.cancel(); } catch (_) {}
            };

            if (signal) {
                if (signal.aborted) throw abortError();
                signal.addEventListener('abort', handleAbort, { once: true });
            }

            const handleSSE = (block) => {
                const lines = block.split('\\n');
                let eventName = 'message';
                const dataLines = [];
                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        eventName = line.slice(6).trim();
                    } else if (line.startsWith('data:')) {
                        dataLines.push(line.slice(5).trimStart());
                    }
                }
                if (!dataLines.length) return;

                let payload = {};
                try {
                    payload = JSON.parse(dataLines.join('\\n'));
                } catch (_) {
                    return;
                }

                if (eventName === 'delta') {
                    const chunk = String(payload.text || '');
                    if (chunk) {
                        finalReply += chunk;
                        pendingDelta += chunk;
                        if (pendingDelta.length >= 48) flushDelta();
                        else scheduleFlush();
                    }
                    return;
                }
                if (eventName === 'done') {
                    imageUrl = payload.image_url || null;
                    if (!finalReply && payload.reply) {
                        finalReply = String(payload.reply);
                        pending.bubble.textContent = finalReply;
                    }
                    done = true;
                    return;
                }
                if (eventName === 'error') {
                    throw new Error(payload.error || '流式接口返回错误');
                }
            };

            try {
                while (true) {
                    const { value, done: streamDone } = await reader.read();
                    if (streamDone) break;
                    buffer += decoder.decode(value, { stream: true });
                    buffer = buffer.replace(/\\r\\n/g, '\\n');

                    let idx = buffer.indexOf('\\n\\n');
                    while (idx !== -1) {
                        const block = buffer.slice(0, idx).trim();
                        buffer = buffer.slice(idx + 2);
                        if (block) handleSSE(block);
                        idx = buffer.indexOf('\\n\\n');
                    }
                }

                if (!done && buffer.trim()) {
                    handleSSE(buffer.trim());
                }

                if (signal && signal.aborted) {
                    throw abortError();
                }

                if (rafId) {
                    window.cancelAnimationFrame(rafId);
                    rafId = 0;
                }
                flushDelta();

                if (!finalReply) {
                    throw new Error('流式返回为空');
                }
                return { reply: finalReply, image_url: imageUrl };
            } finally {
                if (signal) {
                    signal.removeEventListener('abort', handleAbort);
                }
            }
        }

        async function sendChat() {
            const input = document.getElementById('chatInput');
            const imageInput = document.getElementById('chatImage');
            if (!input || !imageInput) return;
            const message = (input.value || '').trim();
            const selectedImage = chatSelectedImageFile || (imageInput.files && imageInput.files[0]);

            if (!message && !selectedImage) {
                addChat('系统', '请输入消息或上传图片。');
                return;
            }

            if (selectedImage) {
                const imageUrl = URL.createObjectURL(selectedImage);
                const textHtml = message ? `<div class="chat-bubble-text">${escapeHtml(message)}</div>` : '';
                addChat('你', `<img class="chat-bubble-image" src="${imageUrl}" alt="已发送图片" />${textHtml}`, true);
                setTimeout(() => {
                    try { URL.revokeObjectURL(imageUrl); } catch (_) {}
                }, 60_000);
            } else {
                addChat('你', message);
            }
            input.value = '';
            if (selectedImage) {
                clearChatImageSelection();
            } else {
                updateChatActionButton();
            }
            const pending = addChat('AI', '', false);
            const abortController = new AbortController();
            chatStreamAbortController = abortController;
            updateChatStreamingState(true);

            try {
                const d = await requestChatStream(message, selectedImage, pending, { signal: abortController.signal });
                if (d.image_url) addChat('AI', `快报图链接: ${API}${d.image_url}`);
                speakText(d.reply || '').catch(() => {});
            } catch (streamErr) {
                if (streamErr && streamErr.name === 'AbortError') {
                    if (pending && pending.bubble && !pending.bubble.textContent) {
                        pending.bubble.textContent = '(已停止)';
                    }
                    addChat('系统', '已停止当前生成。');
                    return;
                }
                if (pending && pending.item) pending.item.remove();
                addChat('系统', `失败: ${streamErr.message || '模型回复失败'}`);
                updateChatActionButton();
            } finally {
                if (chatStreamAbortController === abortController) {
                    chatStreamAbortController = null;
                }
                updateChatStreamingState(false);
                clearChatImageSelection();
            }
        }

        function initSpeechRecognition() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                const statusEl = document.getElementById('micStatus');
                const btnEl = document.getElementById('micBtn');
                if (statusEl) statusEl.textContent = '麦克风状态：浏览器不支持语音识别';
                if (btnEl) {
                    btnEl.disabled = true;
                    btnEl.classList.add('muted');
                }
                return;
            }

            recognition = new SpeechRecognition();
            recognition.lang = 'zh-CN';
            recognition.interimResults = true;
            recognition.continuous = true;

            recognition.onstart = () => {
                micAbortRequested = false;
                const input = document.getElementById('chatInput');
                const existing = (input && input.value ? String(input.value) : '').trim();
                micFinalTranscript = existing ? `${existing} ` : '';
                listening = true;
                updateMicButtonUI();
                document.getElementById('micStatus').textContent = '麦克风状态：听写中...（再次点击可停止）';
            };

            recognition.onend = () => {
                listening = false;
                updateMicButtonUI();
                document.getElementById('micStatus').textContent = micAbortRequested ? '麦克风状态：已停止' : '麦克风状态：未启动';
                micAbortRequested = false;
            };

            recognition.onerror = (event) => {
                document.getElementById('micStatus').textContent = `麦克风错误: ${event.error}`;
            };

            recognition.onresult = (event) => {
                if (micAbortRequested) return;
                let interim = '';
                for (let i = event.resultIndex; i < event.results.length; i += 1) {
                    const piece = String(event.results[i][0].transcript || '');
                    if (!piece) continue;
                    if (event.results[i].isFinal) micFinalTranscript += piece;
                    else interim += piece;
                }
                const input = document.getElementById('chatInput');
                if (!input) return;
                input.value = `${micFinalTranscript}${interim}`.trim();
                updateChatActionButton();
            };
        }

        function toggleMic() {
            if (!recognition) return;
            if (listening) {
                micAbortRequested = true;
                try { recognition.abort(); } catch (_) { recognition.stop(); }
                listening = false;
                updateMicButtonUI();
                document.getElementById('micStatus').textContent = '麦克风状态：正在停止...';
                return;
            }
            try {
                recognition.start();
            } catch (e) {
                document.getElementById('micStatus').textContent = `麦克风启动失败: ${e.message || e}`;
            }
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

        async function fetchVisionKlineData(bank) {
            const safeBank = bank === 'minsheng' ? 'minsheng' : 'zheshang';
            const candidates = [
                `${API}/api/kline/${safeBank}?period=1m&limit=120`,
                `/api/kline/${safeBank}?period=1m&limit=120`,
            ];

            let lastError = null;
            for (const url of candidates) {
                try {
                    const r = await fetch(url);
                    if (!r.ok) {
                        throw new Error(`HTTP ${r.status}`);
                    }
                    const d = await r.json();
                    const hasDataArray = d && Array.isArray(d.data);
                    const successFlag = d && d.success;
                    if (!(successFlag === true || hasDataArray)) {
                        throw new Error((d && d.error) || 'K线数据读取失败');
                    }
                    return hasDataArray ? d.data : [];
                } catch (e) {
                    lastError = e;
                }
            }

            throw new Error(`K线数据读取失败: ${lastError ? lastError.message : 'unknown error'}`);
        }

        function buildVisionKlineOption(bank, data) {
            const label = bank === 'minsheng' ? '民生积存金' : '浙商积存金';
            const xAxis = data.map(k => String(k.datetime || '').substring(5, 16));
            const candleData = data.map(k => [k.open, k.close, k.low, k.high]);
            return {
                backgroundColor: '#0f1526',
                animation: false,
                title: {
                    text: `${label} K线快照`,
                    left: 12,
                    top: 8,
                    textStyle: { color: '#dbe7ff', fontSize: 15, fontWeight: 500 }
                },
                grid: [{ left: 56, right: 18, top: 42, bottom: 34, containLabel: true }],
                xAxis: [{
                    type: 'category',
                    data: xAxis,
                    scale: true,
                    boundaryGap: false,
                    axisLine: { lineStyle: { color: '#334766' } },
                    axisLabel: { color: '#8aa5cf', fontSize: 10 },
                    splitLine: { show: false }
                }],
                yAxis: [{
                    scale: true,
                    axisLine: { lineStyle: { color: '#334766' } },
                    axisLabel: { color: '#8aa5cf', margin: 10, formatter: (v) => Number(v).toFixed(2) },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }
                }],
                series: [{
                    name: 'K线',
                    type: 'candlestick',
                    data: candleData,
                    itemStyle: {
                        color: '#23c55e',
                        color0: '#ef4444',
                        borderColor: '#23c55e',
                        borderColor0: '#ef4444'
                    }
                }]
            };
        }

        async function buildVisionKlineSnapshotFile(bank, data) {
            const container = document.createElement('div');
            container.style.cssText = 'position: fixed; left: -10000px; top: -10000px; width: 980px; height: 560px; pointer-events: none;';
            document.body.appendChild(container);

            let chart = null;
            try {
                chart = echarts.init(container, 'dark');
                chart.setOption(buildVisionKlineOption(bank, data), true);
                await new Promise((resolve) => setTimeout(resolve, 100));
                chart.resize({ width: 980, height: 560 });
                await new Promise((resolve) => setTimeout(resolve, 80));

                const dataUrl = chart.getDataURL({
                    type: 'png',
                    pixelRatio: 2,
                    backgroundColor: '#0f1526'
                });

                const blob = await (await fetch(dataUrl)).blob();
                return new File([blob], `kline_auto_${bank}_${Date.now()}.png`, { type: 'image/png' });
            } finally {
                if (chart) {
                    try { chart.dispose(); } catch (_) {}
                }
                container.remove();
            }
        }

        async function runVLMKlineAuto(bank = 'zheshang') {
            const out = document.getElementById('vlmImageOut');
            setOutLoading(out, '正在从K线图自动截取并进行VL分析...');
            try {
                const data = await fetchVisionKlineData(bank);
                const count = data.length;
                if (count < 8) {
                    throw new Error(`K线数据过少（当前 ${count} 根），请稍后再试`);
                }

                const warning = count < 20 ? `提醒：当前仅 ${count} 根K线，样本偏少，结论仅供参考。\n\n` : '';
                const imageFile = await buildVisionKlineSnapshotFile(bank, data);

                const formData = new FormData();
                formData.append('image', imageFile, imageFile.name || 'kline_auto.png');
                const r = await fetch(`${API}/api/ai/vlm/kline`, { method: 'POST', body: formData });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || 'K线分析失败');

                out.textContent = warning + (d.result || '(空结果)');
                speakVisionText(d.result || '').catch(() => {});
            } catch (e) {
                out.textContent = `失败: ${e.message}`;
            }
        }

        async function runVLMMarket() {
            const out = document.getElementById('vlmMarketOut');
            setOutLoading(out, 'VL 模型正在生成市场分析...');
            try {
                const r = await fetch(`${API}/api/ai/vlm/market`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || 'VLM市场分析失败');
                out.textContent = d.result || '(空结果)';
                speakVisionText(d.result || '').catch(() => {});
            } catch (e) {
                out.textContent = `失败: ${e.message}`;
            }
        }

        async function generateBriefImage(options = {}) {
            const out = document.getElementById('briefOut');
            const img = document.getElementById('briefImage');
            const link = document.getElementById('briefDownload');
            const extNewsToggle = document.getElementById('briefUseExternalNews');
            setOutLoading(out, 'AI 模型正在生成快报图...');
            img.style.display = 'none';
            try {
                const title = document.getElementById('briefTitle').value || '积存金行情快报';
                const includeExternalNews = !extNewsToggle || extNewsToggle.checked;
                const r = await fetch(`${API}/api/ai/image/brief`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title,
                        include_external_news: includeExternalNews
                    })
                });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || '快报图生成失败');
                const url = `${API}${d.image_url}`;
                const allLines = Array.isArray(d.news_lines) ? d.news_lines : [];
                const jinLines = allLines.filter((x) => String(x || '').startsWith('金十贵金属:'));
                const localLines = allLines.filter((x) => !String(x || '').startsWith('金十贵金属:'));
                const previewParts = [];
                if (jinLines.length) previewParts.push(`金十贵金属:\\n- ${jinLines.slice(0, 2).join('\\n- ')}`);
                if (localLines.length) previewParts.push(`本地行情:\\n- ${localLines.slice(0, 2).join('\\n- ')}`);
                const newsPreview = previewParts.length ? `\\n新闻摘要:\\n${previewParts.join('\\n')}` : '';
                out.textContent = `生成成功: ${d.image_file}` + (d.warning ? `\\n提示: ${d.warning}` : '') + newsPreview;
                img.src = url;
                img.style.display = 'block';
                link.href = url;
                link.textContent = '打开最新图片';
                if (options.autoDownload) {
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = d.image_file || 'market_brief.png';
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                }
                return d;
            } catch (e) {
                out.textContent = `失败: ${e.message}`;
                throw e;
            }
        }

        async function previewBriefNews() {
            const out = document.getElementById('briefOut');
            const extNewsToggle = document.getElementById('briefUseExternalNews');
            const includeExternalNews = !extNewsToggle || extNewsToggle.checked;
            setOutLoading(out, '正在抓取快报新闻源...');
            try {
                const r = await fetch(`${API}/api/ai/news/brief`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ include_external_news: includeExternalNews })
                });
                const d = await r.json();
                if (!d.success) throw new Error(d.error || '新闻预览失败');
                const lines = Array.isArray(d.news_lines) ? d.news_lines : [];
                if (!lines.length) {
                    out.textContent = '暂无可用新闻。';
                    return;
                }
                const jinLines = lines.filter((x) => String(x || '').startsWith('金十贵金属:'));
                const localLines = lines.filter((x) => !String(x || '').startsWith('金十贵金属:'));
                const blocks = [];
                if (jinLines.length) blocks.push(`【金十贵金属分类】\\n- ${jinLines.slice(0, 8).join('\\n- ')}`);
                if (localLines.length) blocks.push(`【本地行情补充】\\n- ${localLines.slice(0, 6).join('\\n- ')}`);
                out.textContent = `新闻预览（共 ${lines.length} 条）:\\n${blocks.join('\\n')}`;
            } catch (e) {
                out.textContent = `失败: ${e.message}`;
            }
        }

        async function generateBriefImageAndDownload() {
            try {
                await generateBriefImage({ autoDownload: true });
            } catch (_) {
            }
        }

        function initAITab() {
            if (DISABLE_AI_SIDEBAR) {
                applyAISidebarState();
                return;
            }
            if (aiInitialized) return;
            aiInitialized = true;
            updateAISidebarMetrics();
            addChat('系统', '欢迎使用 AI 多场景助手。你可以语音提问，或上传新闻截图/K线图。');
            initSpeechRecognition();
            bindChatComposerEvents();
            updateTTSButton();
            updateVisionTTSButton();
            updateMicButtonUI();
            updateChatUploadPreview();
            updateChatActionButton();
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
                const baseUnrealized = Number(pos.unrealized_pnl || 0);
                const estimatedExitFee = Number(pos.position_value || 0) * 0.004;
                const feeAdjust = includeFeeInUnrealized ? estimatedExitFee : 0;
                const unrealizedDisplay = baseUnrealized - feeAdjust;
                const pnlClass = unrealizedDisplay >= 0 ? 'profit-positive' : 'profit-negative';
                
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
                            <div class="info-item"><div class="info-label">浮动盈亏${includeFeeInUnrealized ? '(含预估卖出手续费)' : ''}</div><div class="info-value ${pnlClass}">${unrealizedDisplay >= 0 ? '+' : ''}${unrealizedDisplay.toFixed(2)} 元</div></div>
                            <div class="info-item"><div class="info-label">已实现盈亏</div><div class="info-value">${(pos.realized_pnl || 0) >= 0 ? '+' : ''}${(pos.realized_pnl || 0).toFixed(2)} 元</div></div>
                            <div class="info-item"><div class="info-label">累计手续费</div><div class="info-value">${(pos.total_fees || 0).toFixed(2)} 元</div></div>
                            <div class="info-item"><div class="info-label">预估卖出手续费(0.4%)</div><div class="info-value">${estimatedExitFee.toFixed(2)} 元</div></div>
                            <div class="info-item"><div class="info-label">总资产</div><div class="info-value" style="color: #FFD700; font-size: 1.2em;">${(pos.total_value || 0).toFixed(2)} 元</div></div>
                        </div>
                        <div class="trading-hours">
                            <div class="trading-hours-title">交易时间</div>
                            <div class="trading-hours-content">${bank === 'zheshang' ? '周一 9:00 - 周六 2:00' : '周一-周六 9:10-02:30'}</div>
                        </div>
                        <div class="trade-ops">
                            <button class="trade-op-btn trade-op-buy" type="button" onclick="openTradeModal('${bank}', 'BUY')">买入（按实时价）</button>
                            <button class="trade-op-btn trade-op-sell" type="button" onclick="openTradeModal('${bank}', 'SELL')">卖出（按实时价）</button>
                            <button class="trade-op-btn trade-op-topup" type="button" onclick="openRechargeModal('${bank}')">增加余额</button>
                        </div>
                        <div class="trade-op-tip">点击后弹窗输入克数，并显示当前买卖参考价格。</div>
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
        
        function updateStatus(connected, fallbackMode = false) {
            const statusDiv = document.getElementById('wsStatus');
            if (connected) {
                statusDiv.className = 'ws-status ws-connected';
                statusDiv.innerHTML = '<span>●</span> 实时推送中';
                return;
            }

            if (fallbackMode) {
                statusDiv.className = 'ws-status ws-connected';
                statusDiv.innerHTML = '<span>●</span> 轮询刷新中';
                return;
            }

            statusDiv.className = 'ws-status ws-disconnected';
            statusDiv.innerHTML = '<span>●</span> 未连接';
        }
        
        function buildWebSocketUrls() {
            const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const urls = [];

            if (WS_BASE) {
                if (WS_BASE.startsWith('ws://') || WS_BASE.startsWith('wss://')) {
                    urls.push(WS_BASE);
                } else if (WS_BASE.startsWith('/')) {
                    urls.push(`${wsProto}//${window.location.host}${WS_BASE}`);
                }
            }

            if (REMOTE_PAGE) {
                urls.push(`${wsProto}//${window.location.host}/ws`);
            }
            if (isLikelyGatewayPort) {
                urls.push(`${wsProto}//${window.location.host}/ws`);
            }

            urls.push(`${wsProto}//${window.location.hostname}:${DASHBOARD_WS_PORT}`);
            return Array.from(new Set(urls.filter(Boolean)));
        }

        function connectWebSocket() {
            const wsUrls = buildWebSocketUrls();
            let attemptIndex = 0;

            const connectWithIndex = (index) => {
                const wsUrl = wsUrls[Math.min(index, wsUrls.length - 1)];
                let opened = false;

                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    opened = true;
                    updateStatus(true);
                };

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
                        updateTradeModalQuote();
                        document.getElementById('updateTime').textContent = '更新于: ' + formatDateTime(data.timestamp);
                    }
                };

                ws.onclose = () => {
                    if (!opened && attemptIndex < wsUrls.length - 1) {
                        attemptIndex += 1;
                        setTimeout(() => connectWithIndex(attemptIndex), 200);
                        return;
                    }
                    updateStatus(false, true);
                    setTimeout(connectWebSocket, 3000);
                };

                ws.onerror = () => {
                    if (!opened) {
                        try { ws.close(); } catch (_) {}
                    }
                };
            };

            connectWithIndex(attemptIndex);
        }
        
        try {
            includeFeeInUnrealized = localStorage.getItem('dashboard.pnlIncludeFee') === '1';
        } catch (_) {
            includeFeeInUnrealized = false;
        }
        updatePnLToggleButton();

        renderStats();
        renderPrices();
        renderTrades();
        updateRealtimeCharts();
        updateAISidebarMetrics();
        window.addEventListener('resize', updateAISidebarMetrics);
        connectWebSocket();
        initAITab();
        refreshDashboardData().then(() => updateTradeModalQuote()).catch(() => {});
        
        setInterval(() => {
            refreshDashboardData()
                .then(() => updateTradeModalQuote())
                .catch(e => console.error('刷新失败:', e));
        }, 2000);
    </script>
</body>
</html>'''


class DashboardV3Server:
    """Dashboard v3 服务器"""
    
    def __init__(self):
        self.proxy = find_working_proxy()
        self.service_ports = self._load_service_ports()
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

    def _load_service_ports(self):
        defaults = {
            'websocket': 8765,
            'dashboard': 5000,
            'api': 8080,
            'portal': 8090,
        }

        ports_file = PROJECT_ROOT / '.service_ports.json'
        if not ports_file.exists():
            return defaults

        try:
            raw = json.loads(ports_file.read_text(encoding='utf-8'))
        except Exception:
            return defaults

        for key in defaults.keys():
            value = raw.get(key)
            if isinstance(value, int) and value > 0:
                defaults[key] = value
        return defaults
    
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
            html = html.replace('DASHBOARD_PORTS_JSON', json.dumps(self.service_ports))
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
