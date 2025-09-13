import os
import time
import hashlib
import requests
import logging
from datetime import datetime
import schedule
from deep_translator import GoogleTranslator
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("monitor.log"),
        logging.StreamHandler()
    ]
)

# 配置
WEBSITE_URL = "https://d2emu.com/tz-china"
CHECK_INTERVAL = 3600  # 检查间隔（秒）- 1小时
WEBHOOK_URL = os.getenv('WECHAT_WEBHOOK')

# 存储上次内容的哈希值
last_content_hash = None

def get_website_content(url):
    """获取网站内容"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logging.error(f"获取网站内容失败: {str(e)}")
        return None

def translate_to_chinese(text):
    """将文本翻译成中文"""
    try:
        # 限制文本长度，避免翻译API限制
        if len(text) > 5000:
            text = text[:5000] + "..."
        
        translator = GoogleTranslator(source='auto', target='zh-CN')
        translation = translator.translate(text)
        return translation
    except Exception as e:
        logging.error(f"翻译失败: {str(e)}")
        return f"翻译服务暂时不可用，原文：{text[:200]}..."

def send_to_wechat(content, original_content):
    """发送消息到企业微信"""
    if not WEBHOOK_URL:
        logging.error("未配置企业微信Webhook")
        return False

    try:
        # 翻译内容
        translated = translate_to_chinese(original_content[:1000])  # 只翻译前1000字符
        
        # 构建消息
        message = {
            "msgtype": "text",
            "text": {
                "content": f"{content}\n\n更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n翻译内容:\n{translated}\n\n原文链接: {WEBSITE_URL}"
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=message, timeout=10)
        response.raise_for_status()
        
        if response.json().get('errcode') == 0:
            logging.info("消息成功发送到企业微信")
            return True
        else:
            logging.error(f"发送消息失败: {response.text}")
            return False
    except Exception as e:
        logging.error(f"发送消息时出错: {str(e)}")
        return False

def check_website_update():
    """检查网站是否更新"""
    global last_content_hash
    logging.info("开始检查网站更新...")
    
    content = get_website_content(WEBSITE_URL)
    if not content:
        return
    
    # 计算内容哈希值
    current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
    
    # 首次运行
    if last_content_hash is None:
        last_content_hash = current_hash
        logging.info("已记录初始网站内容")
        return
    
    # 检查是否有更新
    if current_hash != last_content_hash:
        logging.info("检测到网站内容更新!")
        # 发送通知
        send_to_wechat("检测到网站有新的更新内容：", content)
        # 更新哈希值
        last_content_hash = current_hash
    else:
        logging.info("网站内容未发生变化")

def run_scheduler():
    """运行定时任务"""
    # 立即执行一次
    check_website_update()
    
    # 设置定时任务
    schedule.every(CHECK_INTERVAL).seconds.do(check_website_update)
    logging.info(f"定时任务已启动，将每{CHECK_INTERVAL/3600}小时检查一次网站更新")
    
    # 循环执行任务
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次是否有任务需要执行

if __name__ == "__main__":
    logging.info("网站更新监控程序启动")
    # 使用线程运行定时任务，避免阻塞
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # 保持主进程运行
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logging.info("程序已手动终止")
    
