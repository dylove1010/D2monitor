import os
import time
import logging
import requests
from datetime import datetime
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup
import hashlib
import schedule

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
WECHAT_WEBHOOK = os.getenv("WECHAT_WEBHOOK")
CHECK_INTERVAL = 3600  # 检查间隔，单位：秒（1小时）
PREVIOUS_CONTENT_HASH = None

def get_website_content(url):
    """获取网站内容"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # 提取文本内容并清理
        text = soup.get_text(separator=' ', strip=True)
        # 取前2000字符作为监控对象（避免内容过长）
        return text[:2000]
    except Exception as e:
        logging.error(f"获取网站内容失败: {str(e)}")
        return None

def translate_to_chinese(text):
    """将英文翻译为中文"""
    try:
        if not text:
            return "无内容可翻译"
            
        translator = GoogleTranslator(source='en', target='zh-CN')
        # 翻译可能有长度限制，分段翻译
        chunks = [text[i:i+5000] for i in range(0, len(text), 5000)]
        translated_chunks = [translator.translate(chunk) for chunk in chunks]
        return ''.join(translated_chunks)
    except Exception as e:
        logging.error(f"翻译失败: {str(e)}")
        # 翻译失败时返回原始文本
        return f"翻译失败，原始内容：{text[:500]}..."

def send_to_wechat(content, is_update=True):
    """发送消息到企业微信"""
    if not WECHAT_WEBHOOK:
        logging.error("未配置企业微信Webhook")
        return False
        
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = "网站更新通知" if is_update else "网站当前内容"
        
        message = {
            "msgtype": "text",
            "text": {
                "content": f"{title}\n时间: {current_time}\n网站: {WEBSITE_URL}\n内容: {content[:1000]}..."  # 限制长度
            }
        }
        
        response = requests.post(WECHAT_WEBHOOK, json=message, timeout=10)
        response.raise_for_status()
        logging.info("消息已成功发送到企业微信")
        return True
    except Exception as e:
        logging.error(f"发送消息到企业微信失败: {str(e)}")
        return False

def check_website_update():
    """检查网站更新"""
    global PREVIOUS_CONTENT_HASH
    
    current_content = get_website_content(WEBSITE_URL)
    if not current_content:
        return
        
    # 计算内容哈希值
    current_hash = hashlib.md5(current_content.encode()).hexdigest()
    
    # 首次运行或内容有变化
    if PREVIOUS_CONTENT_HASH is None:
        logging.info("首次运行，记录初始内容")
        PREVIOUS_CONTENT_HASH = current_hash
        # 首次运行时立即推送一次当前内容
        translated_content = translate_to_chinese(current_content)
        send_to_wechat(translated_content, is_update=False)
    elif current_hash != PREVIOUS_CONTENT_HASH:
        logging.info("检测到网站内容更新")
        PREVIOUS_CONTENT_HASH = current_hash
        translated_content = translate_to_chinese(current_content)
        send_to_wechat(translated_content, is_update=True)
    else:
        logging.info("网站内容未发生变化")

def main():
    logging.info("网站监控程序启动")
    
    # 立即执行一次检查（会触发首次推送）
    check_website_update()
    
    # 设置定时任务
    schedule.every(CHECK_INTERVAL).seconds.do(check_website_update)
    
    # 保持程序运行
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次是否有定时任务需要执行
    except KeyboardInterrupt:
        logging.info("程序被用户终止")
    except Exception as e:
        logging.error(f"程序运行出错: {str(e)}")

if __name__ == "__main__":
    main()
    
