#!/usr/bin/env python3
"""
Markdown 转图片工具
用于将检查摘要渲染为图片发送到微信
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jijin_trader import JijinTrader, find_working_proxy


def generate_summary() -> str:
    """生成检查摘要 Markdown"""
    proxy = find_working_proxy()
    now = datetime.now()
    
    lines = [
        f"## 积存金检查摘要 ({now.strftime('%Y-%m-%d %H:%M')})",
        "",
        "### 📊 市场概况",
        f"- 时间: {now.strftime('%Y-%m-%d %H:%M')}",
        f"- 状态: {'✅ 交易中' if any(JijinTrader(b, proxy).is_trading_time() for b in ['zheshang', 'minsheng']) else '⏸️ 休市中'}",
        "",
    ]
    
    for bank in ['zheshang', 'minsheng']:
        trader = JijinTrader(bank=bank, proxy=proxy)
        quote = trader.get_quote()
        summary = trader.get_summary()
        
        if not quote:
            continue
        
        name = '浙商积存金' if bank == 'zheshang' else '民生积存金'
        
        lines.extend([
            f"### {name}",
            "",
            "| 项目 | 数值 |",
            "|------|------|",
            f"| 当前价 | {quote['price']:.2f}元/克 ({quote['change_rate']}) |",
        ])
        
        if summary['position'] > 0:
            gross = (quote['price'] - summary['avg_price']) / summary['avg_price'] * 100 if summary['avg_price'] > 0 else 0
            net = gross - 0.4
            
            lines.extend([
                f"| 持仓 | {summary['position']:.2f}克 |",
                f"| 成本均价 | {summary['avg_price']:.2f}元/克 |",
                f"| 市值 | {summary['position_value']:.2f}元 |",
                f"| 浮动盈亏 | {summary['unrealized_pnl']:+.2f}元 ({net:+.2f}%) |",
            ])
            
            if net > 0.5:
                lines.append(f"| 建议 | 🔴 SELL (盈利达标) |")
            elif net < -1:
                lines.append(f"| 建议 | 🟡 止损 (亏损过大) |")
            else:
                lines.append(f"| 建议 | 🟢 HOLD |")
        else:
            lines.append(f"| 持仓 | 空仓 |")
            lines.append(f"| 建议 | ⚪ 观望 |")
        
        lines.append("")
    
    lines.extend([
        "### 📈 分析",
        "- 市场正常运行中",
        "- 系统自动监控中",
        "",
        f"**更新时间**: {now.strftime('%H:%M')}",
    ])
    
    return "\n".join(lines)


def markdown_to_html(md: str) -> str:
    """简单 Markdown 转 HTML"""
    html = md
    
    # 标题
    html = html.replace("## ", "<h2 style='color:#FFD700;margin:10px 0;'>")
    html = html.replace("### ", "<h3 style='color:#00d4ff;margin:8px 0;'>")
    
    # 表格
    lines = html.split('\n')
    in_table = False
    result = []
    
    for line in lines:
        if line.startswith('|'):
            if not in_table:
                result.append("<table style='border-collapse:collapse;width:100%;margin:10px 0;'>")
                in_table = True
            
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if '---' in line:
                continue
            
            row = "<tr>"
            for i, cell in enumerate(cells):
                tag = "th" if i == 0 else "td"
                style = "style='background:#161b22;padding:8px;border:1px solid #30363d;'" if i == 0 else "style='padding:8px;border:1px solid #30363d;'"
                row += f"<{tag} {style}>{cell}</{tag}>"
            row += "</tr>"
            result.append(row)
        else:
            if in_table:
                result.append("</table>")
                in_table = False
            result.append(line)
    
    if in_table:
        result.append("</table>")
    
    html = '\n'.join(result)
    
    # 列表
    html = html.replace("- ", "<li style='margin:5px 0;'>")
    html = html.replace("**", "<b style='color:#FFD700;'>")
    
    # 包装
    html = f"""
    <html>
    <head>
        <style>
            body {{
                background: #0d1117;
                color: #c9d1d9;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                padding: 20px;
                max-width: 600px;
            }}
            h2 {{ color: #FFD700; border-bottom: 2px solid #FFD700; padding-bottom: 5px; }}
            h3 {{ color: #00d4ff; }}
            table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
            th, td {{ padding: 10px; border: 1px solid #30363d; text-align: left; }}
            th {{ background: #161b22; color: #FFD700; }}
            li {{ margin: 5px 0; }}
        </style>
    </head>
    <body>
        {html}
    </body>
    </html>
    """
    
    return html


def save_summary_as_image(output_file: Optional[str] = None) -> str:
    """生成摘要并保存为图片"""
    md = generate_summary()
    html = markdown_to_html(md)

    if not output_file:
        output_file = os.path.join(tempfile.gettempdir(), 'gold_summary.png')
    
    # 保存 HTML
    html_file = os.path.join(tempfile.gettempdir(), 'gold_summary.html')
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    # 使用 wkhtmltoimage 或类似工具转换为图片
    # 如果没有，使用文本方式
    try:
        import subprocess
        result = subprocess.run([
            'wkhtmltoimage', '--width', '600', '--quality', '80',
            html_file, output_file
        ], capture_output=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(output_file):
            return output_file
    except:
        pass
    
    # 备用：返回 HTML 文件路径
    return html_file


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    
    result = save_summary_as_image(args.output)
    print(f"Summary saved to: {result}")
    
    # 也打印 Markdown
    print("\n" + "="*60)
    print(generate_summary())
