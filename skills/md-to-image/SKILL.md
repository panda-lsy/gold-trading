# Markdown转图片 Skill

## 描述
将积存金交易报告从Markdown格式渲染成美观的图片，方便微信发送和查看。

## 功能
- 将Markdown文本渲染成图片
- 支持标题、列表、颜色标记
- 适配微信消息尺寸
- 自动生成美观的深色主题图片

## 使用方法

### Python调用
```python
from md_to_image import MarkdownToImage

renderer = MarkdownToImage()

# 渲染Markdown文本
image_path = renderer.render_markdown("# 标题\n- 列表项1\n- 列表项2")

# 渲染积存金报告
image_path = renderer.render_jijin_report(
    zheshang_data,
    minsheng_data,
    output_path="/tmp/report.png"
)
```

### 命令行调用
```bash
python3 md_to_image.py
```

## 依赖
- Python 3.8+
- Pillow (PIL)
- 中文字体 (Noto Sans CJK 或文泉驿)

## 安装依赖
```bash
pip3 install Pillow

# 安装中文字体 (Ubuntu/Debian)
sudo apt-get install fonts-noto-cjk

# 或
sudo apt-get install ttf-wqy-zenhei
```

## 输出示例
- 图片宽度: 800px
- 背景: 深色主题 (#1a1a2e)
- 文字: 白色
- 强调色: 青色 (#00d4ff)
- 成功: 绿色 (#00ff88)
- 警告: 黄色 (#ffc107)
- 危险: 红色 (#ff4444)

## 文件位置
`/home/<user>/.openclaw/workspace/gold-trading/md_to_image.py`

