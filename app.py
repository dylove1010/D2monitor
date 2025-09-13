import os
import time
import logging
import requests
from datetime import datetime
from deep_translator import GoogleTranslator
from threading import Thread
from flask import Flask
from bs4 import BeautifulSoup  # 新增：导入解析库  <-- 新增行

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 目标网站URL
TARGET_URL = "https://d2emu.com/tz-china"
# 检查间隔（小时）
CHECK_INTERVAL = 1
# 存储上次的网站内容
last_content = None

# 初始化Flask应用用于端口监听
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Website monitor is running", 200

def run_flask():
    """运行Flask服务器以提供端口监听"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

# 新增：提取网页有效信息的函数  <-- 新增函数
def extract_website_info(html_content):
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, 'lxml')  # 使用lxml解析器
    
    # 根据目标网站结构调整：优先提取主要内容区域（示例规则，需根据实际网页调整）
    # 1. 尝试提取文章内容（假设目标网站用 <article> 标签包裹正文）
    article = soup.find('article')
    if article:
        return article.get_text(strip=True, separator='\n')
    
    # 2. 若没有article标签，尝试提取class为"content"的div
    content_div = soup.find('div', class_='content')
    if content_div:
        return content_div.get_text(strip=True, separator='\n')
    
    # 3. 兜底方案：提取所有段落文本（过滤脚本和样式）
    for script in soup(["script", "style", "nav", "footer"]):
        script.decompose()  # 移除无关标签
    return soup.get_text(strip=True, separator='\n')

# 修改：更新get_website_content函数，添加内容提取逻辑  <-- 修改函数
def get_website_content(url):
    """获取网站内容并提取有效信息"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 调用提取函数，返回有效文本而非原始HTML
        return extract_website_info(response.text)  # 修改此行
    except Exception as e:
        logging.error(f"获取网站内容失败: {str(e)}")
        return None

# 以下函数（translate_to_chinese、send_to_wechat等）保持不变
def translate_to_chinese(text):
    """将英文文本翻译为中文"""
    if not text:
        return "无法获取内容进行翻译"
    
    try:
        max_length = 5000
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        translator = GoogleTranslator(source='en', target='zh-CN')
        chunks = [text[i:i+5000] for i in range(0, len(text), 5000)]
        translated_chunks = [translator.translate(chunk) for chunk in chunks]
        return ''.join(translated_chunks)
    except Exception as e:
        logging.error(f"翻译失败: {str(e)}")
        return f"翻译服务出错: {str(e)}\n原文片段: {text[:200]}..."

# 其余函数（send_to_wechat、check_website_update、monitor_website等）不变
# ...（省略重复代码）
