import os
import imaplib
import email
import requests
from fastapi import FastAPI
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from email.header import decode_header
import time
from datetime import datetime, timedelta

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

def send_test_message():
    webhook_url = os.getenv('WEIXIN_WEBHOOK')
    try:
        message = {
            "msgtype": "text",
            "text": {
                "content": "这是一条测试消息，来自邮件转发机器人",
                "mentioned_list": ["@all"]
            }
        }
        response = requests.post(webhook_url, json=message)
        if response.status_code == 200:
            return {"status": "success", "message": "测试消息发送成功"}
        else:
            return {"status": "error", "message": f"发送失败: {response.text}"}
    except Exception as e:
        return {"status": "error", "message": f"发送出错: {str(e)}"}

class EmailMonitor:
    def __init__(self, email_addr, password, imap_server):
        self.email_addr = email_addr
        self.password = password
        self.imap_server = imap_server
        self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')
        self.last_check_time = datetime.now()

    def decode_subject(self, subject):
        if subject is None:
            return ""
        decoded_parts = []
        for part, encoding in decode_header(subject):
            if isinstance(part, bytes):
                try:
                    decoded_parts.append(part.decode(encoding or 'utf-8', errors='replace'))
                except:
                    decoded_parts.append(part.decode('utf-8', errors='replace'))
            else:
                decoded_parts.append(str(part))
        return ' '.join(decoded_parts)

    def connect(self):
        try:
            self.imap = imaplib.IMAP4_SSL(self.imap_server)
            self.imap.login(self.email_addr, self.password)
            return True
        except Exception as e:
            logger.error(f"连接邮箱失败: {str(e)}")
            return False

    def send_to_weixin(self, subject, sender, content, received_time):
        try:
            # 格式化接收时间
            time_str = received_time.strftime("%Y-%m-%d %H:%M:%S")
            message = {
                "msgtype": "text",
                "text": {
                    "content": f"📧 新邮件通知\n\n⏰ 接收时间: {time_str}\n👤 发件人: {sender}\n📑 主题: {subject}\n\n📝 内容预览:\n{content}",
                    "mentioned_list": ["@all"]
                }
            }
            response = requests.post(
                self.weixin_webhook,
                json=message
            )
            if response.status_code == 200:
                logger.info("成功发送到微信")
            else:
                logger.error(f"发送到微信失败: {response.text}")
        except Exception as e:
            logger.error(f"发送到微信时出错: {str(e)}")

    def get_email_content(self, email_message):
        content = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        content = part.get_payload(decode=True).decode(errors='replace')
                        break
                    except:
                        continue
        else:
            try:
                content = email_message.get_payload(decode=True).decode(errors='replace')
            except:
                content = "无法解析邮件内容"
        return content[:500]  # 限制内容长度

    def check_emails(self):
        logger.info(f"开始检查邮箱: {self.email_addr}")
        
        if not self.connect():
            return

        try:
            self.imap.select('INBOX')
            # 搜索最近30分钟内的未读邮件
            date = (datetime.now() - timedelta(minutes=30)).strftime("%d-%b-%Y")
            _, messages = self.imap.search(None, f'(UNSEEN SINCE "{date}")')
            
            message_count = len(messages[0].split())
            logger.info(f"发现 {message_count} 封新邮件")
            
            for num in messages[0].split():
                try:
                    _, msg = self.imap.fetch(num, '(RFC822)')
                    email_body = msg[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # 获取邮件接收时间
                    received_time = datetime.fromtimestamp(
                        email.utils.mktime_tz(
                            email.utils.parsedate_tz(email_message['date'])
                        )
                    )
                    
                    # 只处理最近30分钟内的邮件
                    if datetime.now() - received_time > timedelta(minutes=30):
                        continue

                    subject = self.decode_subject(email_message['subject'])
                    sender = email_message['from']
                    content = self.get_email_content(email_message)

                    logger.info(f"发送邮件到微信: {subject}")
                    self.send_to_weixin(subject, sender, content, received_time)
                    
                except Exception as e:
                    logger.error(f"处理邮件时出错: {str(e)}")
                    continue
                
        except Exception as e:
            logger.error(f"检查邮件时出错: {str(e)}")
        finally:
            try:
                self.imap.close()
                self.imap.logout()
            except:
                pass

# 创建邮箱监控实例
gmail_monitor = EmailMonitor(
    os.getenv('GMAIL_EMAIL'),
    os.getenv('GMAIL_PASSWORD'),
    'imap.gmail.com'
)

qq_monitor = EmailMonitor(
    os.getenv('QQ_EMAIL'),
    os.getenv('QQ_PASSWORD'),
    'imap.qq.com'
)

def check_all_emails():
    logger.info("开始检查所有邮箱")
    try:
        gmail_monitor.check_emails()
        qq_monitor.check_emails()
        logger.info("邮箱检查完成")
    except Exception as e:
        logger.error(f"检查邮箱时发生错误: {str(e)}")

@app.get("/check")
async def manual_check():
    """手动触发邮件检查"""
    try:
        check_all_emails()
        return {"status": "success", "message": "邮件检查完成"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
async def root():
    return {"status": "running", "message": "邮件监控服务正在运行"}

# 添加定时任务
@app.on_event("startup")
async def startup_event():
    async def keep_alive():
        while True:
            await asyncio.sleep(60)  # 每分钟ping一次
            requests.get(f"https://{os.getenv('VERCEL_URL', 'your-app-url')}")
    
    async def periodic_check():
        while True:
            await asyncio.sleep(60)  # 每分钟检查一次
            try:
                check_all_emails()
            except Exception as e:
                logger.error(f"定时检查时出错: {str(e)}")
    
    if os.getenv('VERCEL_URL'):  # 只在Vercel环境中运行
        asyncio.create_task(keep_alive())
        asyncio.create_task(periodic_check()) 