import requests
import hashlib
import time
import os
from datetime import datetime
from googletrans import Translator
import schedule
import threading

# 配置参数
WEBSITE_URL = "https://d2emu.com/tz-china"
WEBHOOK_URL = os.environ.get('WECHAT_WEBHOOK')  # 从环境变量获取
CHECK_INTERVAL = 3600  # 检查间隔(秒)，默认1小时
CACHE_FILE = "content_cache.txt"

# 初始化翻译器
translator = Translator()

def get_website_content(url):
    """获取网站内容"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"获取网站内容失败: {str(e)}")
        return None

def translate_to_chinese(text):
    """将英文翻译为中文"""
    try:
        if not text:
            return ""
        # 限制翻译文本长度，避免API限制
        if len(text) > 5000:
            text = text[:5000] + "..."
        
        translation = translator.translate(text, dest='zh-cn')
        return translation.text
    except Exception as e:
        print(f"翻译失败: {str(e)}")
        return text  # 翻译失败时返回原文

def get_content_hash(content):
    """计算内容的哈希值用于比较"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def load_last_hash():
    """加载上一次的内容哈希"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return None
    except Exception as e:
        print(f"加载缓存失败: {str(e)}")
        return None

def save_current_hash(hash_value):
    """保存当前内容的哈希"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            f.write(hash_value)
    except Exception as e:
        print(f"保存缓存失败: {str(e)}")

def send_to_wechat(content):
    """发送消息到企业微信"""
    if not WEBHOOK_URL:
        print("未配置企业微信Webhook，无法发送消息")
        return False
    
    try:
        # 格式化消息，限制长度
        if len(content) > 2000:
            content = content[:2000] + "\n\n内容过长，已截断"
        
        data = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("errcode") == 0:
            print("消息发送成功")
            return True
        else:
            print(f"消息发送失败: {result.get('errmsg')}")
            return False
    except Exception as e:
        print(f"发送消息时出错: {str(e)}")
        return False

def check_website_update():
    """检查网站是否更新"""
    print(f"开始检查网站更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取当前网站内容
    current_content = get_website_content(WEBSITE_URL)
    if not current_content:
        return
    
    # 计算当前内容哈希
    current_hash = get_content_hash(current_content)
    
    # 获取上一次的哈希
    last_hash = load_last_hash()
    
    # 首次运行，保存哈希并返回
    if not last_hash:
        save_current_hash(current_hash)
        print("首次运行，已保存初始内容哈希")
        return
    
    # 比较哈希值，判断是否更新
    if current_hash != last_hash:
        print("网站内容已更新！")
        
        # 提取部分内容用于推送（这里取前1000字符作为示例）
        preview_text = current_content[:1000].replace('\n', ' ').replace('\r', '')
        
        # 翻译为中文
        translated_text = translate_to_chinese(preview_text)
        
        # 构建推送消息
        update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = f"网站内容已更新\n时间: {update_time}\n网址: {WEBSITE_URL}\n\n更新内容预览:\n{translated_text}"
        
        # 发送到企业微信
        if send_to_wechat(message):
            # 发送成功后更新缓存
            save_current_hash(current_hash)
    else:
        print("网站内容未更新")

def run_scheduler():
    """运行定时任务"""
    # 立即执行一次
    check_website_update()
    
    # 设置定时任务
    schedule.every(CHECK_INTERVAL).seconds.do(check_website_update)
    
    # 循环执行定时任务
    while True:
        schedule.run_pending()
        time.sleep(1)

# 用于Render的Web服务，防止应用被关闭
from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    return "网站更新监控服务运行中"

if __name__ == "__main__":
    # 启动定时任务线程
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # 启动Flask服务
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
