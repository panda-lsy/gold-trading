#!/usr/bin/env python3
"""
价格预警服务
支持价格阈值预警、涨跌幅预警、技术指标预警
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, asdict
from sqlite_store import SQLiteStore


@dataclass
class AlertRule:
    """预警规则"""
    id: str
    name: str
    bank: str  # zheshang / minsheng
    alert_type: str  # price_above, price_below, change_above, change_below, ma_cross
    threshold: float
    enabled: bool = True
    created_at: str = None
    triggered_at: str = None
    triggered_count: int = 0
    cooldown_minutes: int = 60  # 冷却时间（分钟）
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class AlertService:
    """价格预警服务"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.sqlite_store = SQLiteStore(data_dir=data_dir)
        
        self.rules: List[AlertRule] = []
        self.history: List[Dict] = []
        self.callbacks: List[Callable] = []
        self.running = False
        
        self._load_rules()
        self._load_history()
    
    def _load_rules(self):
        """加载预警规则"""
        try:
            data = self.sqlite_store.load_alert_rules()
            self.rules = [AlertRule(**r) for r in data if isinstance(r, dict)]
        except Exception as e:
            print(f"加载预警规则失败: {e}")
            self.rules = []
    
    def _save_rules(self):
        """保存预警规则"""
        self.sqlite_store.save_alert_rules([asdict(r) for r in self.rules])
    
    def _load_history(self):
        """加载预警历史"""
        try:
            self.history = self.sqlite_store.load_alert_history(limit=5000)
        except Exception:
            self.history = []
    
    def _save_history(self):
        """保存预警历史"""
        self.sqlite_store.save_alert_history(self.history)
    
    def add_rule(
        self,
        name: str,
        bank: str,
        alert_type: str,
        threshold: float,
        cooldown_minutes: int = 60
    ) -> AlertRule:
        """添加预警规则"""
        import uuid
        
        rule = AlertRule(
            id=str(uuid.uuid4())[:8],
            name=name,
            bank=bank,
            alert_type=alert_type,
            threshold=threshold,
            cooldown_minutes=cooldown_minutes
        )
        
        self.rules.append(rule)
        self._save_rules()
        
        return rule
    
    def remove_rule(self, rule_id: str) -> bool:
        """删除预警规则"""
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                self.rules.pop(i)
                self._save_rules()
                return True
        return False
    
    def enable_rule(self, rule_id: str, enabled: bool = True) -> bool:
        """启用/禁用预警规则"""
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = enabled
                self._save_rules()
                return True
        return False
    
    def get_rules(self, bank: str = None, enabled_only: bool = False) -> List[AlertRule]:
        """获取预警规则"""
        rules = self.rules
        
        if bank:
            rules = [r for r in rules if r.bank == bank]
        
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        
        return rules
    
    def check_price_alert(self, price_data: Dict) -> List[Dict]:
        """
        检查价格预警
        
        Args:
            price_data: {
                'bank': 'zheshang',
                'price': 1000.0,
                'change_rate': 0.5,
                'ma5': 995.0,
                'ma10': 990.0
            }
        
        Returns:
            触发的预警列表
        """
        triggered = []
        bank = price_data.get('bank')
        price = price_data.get('price', 0)
        change_rate = price_data.get('change_rate', 0)
        
        now = datetime.now()
        history_entries = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            if rule.bank != bank:
                continue
            
            # 检查冷却时间
            if rule.triggered_at:
                last_triggered = datetime.fromisoformat(rule.triggered_at)
                cooldown = timedelta(minutes=rule.cooldown_minutes)
                if now - last_triggered < cooldown:
                    continue
            
            triggered_alert = None
            
            if rule.alert_type == 'price_above' and price > rule.threshold:
                triggered_alert = {
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'alert_type': 'price_above',
                    'message': f'{rule.name}: 价格 {price:.2f} 超过阈值 {rule.threshold:.2f}',
                    'current_value': price,
                    'threshold': rule.threshold
                }
            
            elif rule.alert_type == 'price_below' and price < rule.threshold:
                triggered_alert = {
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'alert_type': 'price_below',
                    'message': f'{rule.name}: 价格 {price:.2f} 低于阈值 {rule.threshold:.2f}',
                    'current_value': price,
                    'threshold': rule.threshold
                }
            
            elif rule.alert_type == 'change_above' and change_rate > rule.threshold:
                triggered_alert = {
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'alert_type': 'change_above',
                    'message': f'{rule.name}: 涨幅 {change_rate:.2f}% 超过阈值 {rule.threshold:.2f}%',
                    'current_value': change_rate,
                    'threshold': rule.threshold
                }
            
            elif rule.alert_type == 'change_below' and change_rate < rule.threshold:
                triggered_alert = {
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'alert_type': 'change_below',
                    'message': f'{rule.name}: 跌幅 {change_rate:.2f}% 低于阈值 {rule.threshold:.2f}%',
                    'current_value': change_rate,
                    'threshold': rule.threshold
                }
            
            elif rule.alert_type == 'ma_cross':
                ma5 = price_data.get('ma5', 0)
                ma10 = price_data.get('ma10', 0)
                if ma5 > ma10 and price > ma5:
                    triggered_alert = {
                        'rule_id': rule.id,
                        'rule_name': rule.name,
                        'alert_type': 'ma_cross',
                        'message': f'{rule.name}: 价格突破均线，MA5={ma5:.2f}, MA10={ma10:.2f}',
                        'current_value': price,
                        'threshold': rule.threshold
                    }
            
            if triggered_alert:
                # 更新规则状态
                rule.triggered_at = now.isoformat()
                rule.triggered_count += 1
                
                # 添加到历史
                history_entry = {
                    'timestamp': now.isoformat(),
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'bank': bank,
                    'alert_type': rule.alert_type,
                    'message': triggered_alert['message'],
                    'current_value': triggered_alert['current_value'],
                    'threshold': triggered_alert['threshold']
                }
                self.history.append(history_entry)
                history_entries.append(history_entry)
                
                triggered.append(triggered_alert)
        
        if triggered:
            self._save_rules()
            self.sqlite_store.append_alert_history(history_entries)
        
        return triggered
    
    def get_history(self, bank: str = None, limit: int = 50) -> List[Dict]:
        """获取预警历史"""
        return self.sqlite_store.load_alert_history(bank=bank, limit=limit)
    
    def clear_history(self):
        """清空预警历史"""
        self.history = []
        self.sqlite_store.clear_alert_history()
    
    def register_callback(self, callback: Callable):
        """注册预警回调函数"""
        self.callbacks.append(callback)
    
    def notify(self, alerts: List[Dict]):
        """通知所有回调"""
        for callback in self.callbacks:
            try:
                callback(alerts)
            except Exception as e:
                print(f"回调执行失败: {e}")


class AlertNotifier:
    """预警通知器"""
    
    @staticmethod
    def console_notify(alerts: List[Dict]):
        """控制台通知"""
        print("\n" + "=" * 60)
        print("⚠️ 价格预警触发!")
        print("=" * 60)
        for alert in alerts:
            print(f"[{alert['rule_name']}] {alert['message']}")
        print("=" * 60 + "\n")
    
    @staticmethod
    def file_notify(alerts: List[Dict], filename: str = 'alerts.log'):
        """文件通知"""
        with open(filename, 'a') as f:
            for alert in alerts:
                f.write(f"{datetime.now().isoformat()} - {alert['message']}\n")


if __name__ == "__main__":
    service = AlertService()
    
    print("价格预警服务")
    print("=" * 60)
    
    # 添加示例规则
    print("\n添加预警规则...")
    
    rule1 = service.add_rule(
        name="浙商高价预警",
        bank="zheshang",
        alert_type="price_above",
        threshold=1010.0
    )
    print(f"✓ 添加规则: {rule1.name} (ID: {rule1.id})")
    
    rule2 = service.add_rule(
        name="浙商大跌预警",
        bank="zheshang",
        alert_type="change_below",
        threshold=-1.0
    )
    print(f"✓ 添加规则: {rule2.name} (ID: {rule2.id})")
    
    # 测试检查
    print("\n\n测试价格检查:")
    print("-" * 60)
    
    test_data = {
        'bank': 'zheshang',
        'price': 1015.0,
        'change_rate': 1.5,
        'ma5': 1005.0,
        'ma10': 1000.0
    }
    
    alerts = service.check_price_alert(test_data)
    if alerts:
        AlertNotifier.console_notify(alerts)
    else:
        print("未触发预警")
    
    # 显示规则
    print("\n\n当前预警规则:")
    print("-" * 60)
    for rule in service.get_rules():
        status = "✓ 启用" if rule.enabled else "✗ 禁用"
        print(f"[{rule.id}] {rule.name} - {status}")
        print(f"    类型: {rule.alert_type}, 阈值: {rule.threshold}")
        if rule.triggered_at:
            print(f"    上次触发: {rule.triggered_at}")
