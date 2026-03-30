#!/usr/bin/env python3
"""
发送微信通知 - 积存金检查摘要
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
from jijin_trader import JijinTrader, find_working_proxy


def generate_weixin_message() -> str:
    """生成微信消息文本"""
    proxy = find_working_proxy()
    now = datetime.now()
    
    lines = [
        f"📊 积存金检查摘要 ({now.strftime('%m-%d %H:%M')})",
        "",
    ]
    
    for bank in ['zheshang', 'minsheng']:
        trader = JijinTrader(bank=bank, proxy=proxy)
        quote = trader.get_quote()
        summary = trader.get_summary()
        
        if not quote:
            continue
        
        name = '浙商' if bank == 'zheshang' else '民生'
        
        lines.append(f"【{name}】{quote['price']:.0f}元 ({quote['change_rate']})")
        
        if summary['position'] > 0:
            gross = (quote['price'] - summary['avg_price']) / summary['avg_price'] * 100
            net = gross - 0.4
            lines.append(f"  持仓{summary['position']:.0f}克 盈亏{summary['unrealized_pnl']:+.0f}元")
            
            if net > 0.5:
                lines.append(f"  🔴 建议: SELL")
            elif net < -1:
                lines.append(f"  🟡 建议: 止损")
            else:
                lines.append(f"  🟢 建议: HOLD")
        else:
            lines.append(f"  空仓观望")
        
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    msg = generate_weixin_message()
    print(msg)
    
    # 保存到文件供 OpenClaw 读取
    output_path = os.path.join(tempfile.gettempdir(), 'weixin_notify.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(msg)
    
    print(f"\n消息已保存到: {output_path}")
