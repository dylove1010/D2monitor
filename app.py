import os
import time
import logging
import requests
from datetime import datetime
from deep_translator import GoogleTranslator
from threading import Thread
from flask import Flask
from bs4 import BeautifulSoup  # 新增HTML解析库

# 配置日志（增强版，包含文件输出）
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
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
    port = int(os.environ.get('PORT', 10000))  # 使用Render提供的端口或默认10000
    app.run(host='0.0.0.0', port=port, debug=False)

def extract_clean_text(html_content):
    """从HTML中提取纯文本内容（过滤标签和无关元素）"""
    if not html_content:
        return ""
    
    # 解析HTML
    soup = BeautifulSoup(html_content, 'lxml')
    
    # 移除无关标签（可根据目标网站结构调整）
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()  # 删除这些标签及其内容
    
    # 提取主要内容（优先找常见正文标签）
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    if main_content:
        text = main_content.get_text(separator='\n', strip=True)
    else:
        # 兜底：提取整个页面的文本
        text = soup.get_text(separator='\n', strip=True)
    
    # 过滤空行和多余空格
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)

def get_website_content(url):
    """获取网站内容并提取纯文本"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 抛出HTTP错误
        
        # 调用提取函数，返回纯文本（替换原始HTML）
        return extract_clean_text(response.text)
    except Exception as e:
        logging.error(f"获取网站内容失败: {str(e)}")
        return None

def translate_to_chinese(text):
    """将文本翻译为中文"""
    if not text:
        return "无法获取内容进行翻译"
    
    try:
        # 限制文本长度以避免翻译API错误
        max_length = 5000
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        translator = GoogleTranslator(source='auto', target='zh-CN')  # 自动检测源语言
        # 处理长文本，分块翻译
        chunks = [text[i:i+5000] for i in range(0, len(text), 5000)]
        translated_chunks = [translator.translate(chunk) for chunk in chunks]
        return ''.join(translated_chunks)
    except Exception as e:
        logging.error(f"翻译失败: {str(e)}")
        return f"翻译服务出错: {str(e)}\n原文片段: {text[:200]}..."

def send_to_wechat(content, is_update=True):
    """发送消息到企业微信"""
    webhook_url = os.environ.get('WECHAT_WEBHOOK')
    if not webhook_url:
        logging.error("未配置企业微信Webhook，请检查环境变量")
        return False
    
    try:
        # 准备消息内容
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = "网站更新通知" if is_update else "网站当前内容"
        
        message = {
            "msgtype": "text",
            "text": {
                "content": f"{title}\n时间: {timestamp}\n网站: {TARGET_URL}\n\n{content[:2000]}  # 内容可能已截断"
            }
        }
        
        response = requests.post(webhook_url, json=message, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('errcode') == 0:
            logging.info("消息成功推送到企业微信")
            return True
        else:
            logging.error(f"企业微信推送失败: {result.get('errmsg')}")
            return False
    except Exception as e:
        logging.error(f"发送消息失败: {str(e)}")
        return False

def check_website_update():
    """检查网站更新并处理"""
    global last_content
    
    current_content = get_website_content(TARGET_URL)
    if not current_content:
        return False
    
    # 首次运行，记录内容并推送当前状态
    if last_content is None:
        last_content = current_content
        logging.info("已记录初始网站内容")
        
        # 翻译内容
        translated = translate_to_chinese(current_content)
        
        # 立即推送一次当前内容
        send_to_wechat(translated, is_update=False)
        return True
    
    # 检查内容是否有变化
    if current_content != last_content:
        logging.info("检测到网站内容更新")
        
        # 翻译新内容
        translated = translate_to_chinese(current_content)
        
        # 推送更新
        send_to_wechat(translated, is_update=True)
        
        # 更新记录的内容
        last_content = current_content
        return True
    else:
        logging.info("网站内容未发生变化")
        return False

def monitor_website():
    """监控网站的主循环"""
    logging.info("网站更新监控程序启动")
    logging.info(f"目标监控网站: {TARGET_URL}")
    logging.info(f"检查间隔: {CHECK_INTERVAL}小时")
    
    # 立即检查一次
    check_website_update()
    
    # 定时检查
    while True:
        logging.debug(f"等待{CHECK_INTERVAL}小时后再次检查...")
        time.sleep(CHECK_INTERVAL * 3600)  # 转换为秒
        check_website_update()

if __name__ == "__main__":
    logging.info("程序开始启动...")
    # 启动Flask线程用于端口监听
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logging.info("Flask线程已启动")
    
    # 启动监控程序
    monitor_website()
