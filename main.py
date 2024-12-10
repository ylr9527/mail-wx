import os
import imaplib
import email
import requests
from fastapi import FastAPI
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class EmailMonitor:
    def __init__(self, email_addr, password, imap_server):
        self.email_addr = email_addr
        self.password = password
        self.imap_server = imap_server
        self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')

    def connect(self):
        try:
            self.imap = imaplib.IMAP4_SSL(self.imap_server)
            self.imap.login(self.email_addr, self.password)
            return True
        except Exception as e:
            logger.error(f"连接邮箱失败: {str(e)}")
            return False

    def send_to_weixin(self, subject, sender, content):
        try:
            message = f"新邮件通知\n发件人: {sender}\n主题: {subject}\n内容: {content}"
            response = requests.post(
                self.weixin_webhook,
                json={"msgtype": "text", "text": {"content": message}}
            )
            if response.status_code == 200:
                logger.info("成功发送到微信")
            else:
                logger.error(f"发送到微信失败: {response.text}")
        except Exception as e:
            logger.error(f"发送到微信时出错: {str(e)}")

    def check_emails(self):
        if not self.connect():
            return

        try:
            self.imap.select('INBOX')
            _, messages = self.imap.search(None, 'UNSEEN')
            
            for num in messages[0].split():
                _, msg = self.imap.fetch(num, '(RFC822)')
                email_body = msg[0][1]
                email_message = email.message_from_bytes(email_body)
                
                subject = email_message['subject']
                sender = email_message['from']
                content = ""

                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            content = part.get_payload(decode=True).decode()
                            break
                else:
                    content = email_message.get_payload(decode=True).decode()

                self.send_to_weixin(subject, sender, content[:500])  # 限制内容长度
                
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
    gmail_monitor.check_emails()
    qq_monitor.check_emails()

@app.on_event("startup")
async def startup_event():
    # 创建一个线程池来处理邮件检查
    executor = ThreadPoolExecutor(max_workers=2)
    
    async def periodic_check():
        while True:
            await asyncio.get_event_loop().run_in_executor(executor, check_all_emails)
            await asyncio.sleep(60)  # 每60秒检查一次
    
    asyncio.create_task(periodic_check())

@app.get("/")
async def root():
    return {"status": "running", "message": "邮件监控服务正在运行"} 