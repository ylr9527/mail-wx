import os
import imaplib
import email
import requests
from fastapi import FastAPI, HTTPException, Security, Depends, BackgroundTasks
from fastapi.security.api_key import APIKeyHeader, APIKey
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from email.header import decode_header
import time
from datetime import datetime, timedelta
import pytz
from exchangelib import Credentials, Account, DELEGATE, Configuration
from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter
import urllib3

# 禁用SSL警告
urllib3.disable_warnings()
BaseProtocol.HTTP_ADAPTER_CLS = NoVerifyHTTPAdapter

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 设置北京时区
beijing_tz = pytz.timezone('Asia/Shanghai')

# 配置检查间隔（秒）
CHECK_INTERVAL = 300  # 5分钟检查一次

# 服务状态
service_status = {
    "last_check_time": None,
    "last_check_status": "未开始",
    "error_count": 0,
    "consecutive_errors": 0,
    "is_checking": False
}

# 邮箱配置
def get_email_configs():
    configs = {
        'gmail': [],
        'qq': [],
        'outlook': []
    }
    
    # Gmail配置
    gmail_emails = os.getenv('GMAIL_EMAILS', '').split(',')
    gmail_passwords = os.getenv('GMAIL_PASSWORDS', '').split(',')
    for email, password in zip(gmail_emails, gmail_passwords):
        if email and password:
            configs['gmail'].append({
                'email': email.strip(),
                'password': password.strip()
            })
    
    # QQ邮箱配置
    qq_emails = os.getenv('QQ_EMAILS', '').split(',')
    qq_passwords = os.getenv('QQ_PASSWORDS', '').split(',')
    for email, password in zip(qq_emails, qq_passwords):
        if email and password:
            configs['qq'].append({
                'email': email.strip(),
                'password': password.strip()
            })
    
    # Outlook配置
    outlook_emails = os.getenv('OUTLOOK_EMAILS', '').split(',')
    outlook_passwords = os.getenv('OUTLOOK_PASSWORDS', '').split(',')
    for email, password in zip(outlook_emails, outlook_passwords):
        if email and password:
            configs['outlook'].append({
                'email': email.strip(),
                'password': password.strip()
            })
    
    return configs

app = FastAPI()

# API密钥验证
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == os.getenv("API_KEY"):
        return api_key_header
    raise HTTPException(
        status_code=403,
        detail="无效的API密钥"
    )

def update_service_status(success: bool, error_message: str = None):
    """更新服务状态"""
    service_status["last_check_time"] = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    if success:
        service_status["last_check_status"] = "成功"
        service_status["consecutive_errors"] = 0
    else:
        service_status["last_check_status"] = f"失败: {error_message}"
        service_status["error_count"] += 1
        service_status["consecutive_errors"] += 1

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
    def __init__(self, email_addr, password, imap_server, email_type):
        self.email_addr = email_addr
        self.password = password
        self.imap_server = imap_server
        self.email_type = email_type  # 'Gmail' 或 'QQ'
        self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')
        self.last_check_time = datetime.now(beijing_tz)

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
            # 转换为北京时间
            if received_time.tzinfo is None:
                received_time = pytz.utc.localize(received_time)
            beijing_time = received_time.astimezone(beijing_tz)
            
            # 格式化北京时间
            time_str = beijing_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 根据邮箱类型设置不同的图标
            icon = "📧 Gmail" if self.email_type == "Gmail" else "📨 QQ邮箱"
            
            message = {
                "msgtype": "text",
                "text": {
                    "content": f"{icon}邮件通知\n\n📬 收件邮箱: {self.email_addr}\n⏰ 接收时间: {time_str} (北京时间)\n👤 发件人: {sender}\n📑 主题: {subject}\n\n📝 内容预览:\n{content}",
                    "mentioned_list": ["@all"]
                }
            }
            response = requests.post(
                self.weixin_webhook,
                json=message
            )
            if response.status_code == 200:
                logger.info(f"{self.email_type}邮件发送到微信成功")
            else:
                logger.error(f"{self.email_type}邮件发送到微信失败: {response.text}")
        except Exception as e:
            logger.error(f"{self.email_type}发送到微信时出错: {str(e)}")

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
        logger.info(f"开始检查{self.email_type}邮箱: {self.email_addr}")
        
        if not self.connect():
            return

        try:
            self.imap.select('INBOX')
            
            # QQ邮箱和Gmail使用不同的搜索条件
            if self.email_type == 'QQ':
                # QQ邮箱搜索最近天的未读邮件
                date = (datetime.now(beijing_tz) - timedelta(days=1)).strftime("%d-%b-%Y")
                _, messages = self.imap.search(None, f'(UNSEEN SINCE "{date}")')
            else:
                # Gmail使用时间过滤，使用北京时间
                date = (datetime.now(beijing_tz) - timedelta(minutes=30)).strftime("%d-%b-%Y")
                _, messages = self.imap.search(None, f'(UNSEEN SINCE "{date}")')
            
            message_count = len(messages[0].split())
            logger.info(f"发现 {message_count} 封新{self.email_type}邮件")
            
            for num in messages[0].split():
                try:
                    _, msg = self.imap.fetch(num, '(RFC822)')
                    email_body = msg[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # 获取邮件接收时间
                    date_str = email_message['date']
                    if date_str:
                        try:
                            # 解析邮件时间并转换为UTC时间
                            received_time = datetime.fromtimestamp(
                                email.utils.mktime_tz(
                                    email.utils.parsedate_tz(date_str)
                                ),
                                pytz.utc
                            )
                        except:
                            received_time = datetime.now(pytz.utc)
                    else:
                        received_time = datetime.now(pytz.utc)
                    
                    # 转换为北京时间进行比较
                    beijing_received_time = received_time.astimezone(beijing_tz)
                    time_diff = datetime.now(beijing_tz) - beijing_received_time
                    
                    # QQ邮箱处理最近24小时的邮件，Gmail处理最近30分钟的邮件
                    if (self.email_type == 'QQ' and time_diff > timedelta(days=1)) or \
                       (self.email_type == 'Gmail' and time_diff > timedelta(minutes=30)):
                        # 将超时的邮件标记为已读
                        self.imap.store(num, '+FLAGS', '\\Seen')
                        continue

                    subject = self.decode_subject(email_message['subject'])
                    sender = email_message['from']
                    content = self.get_email_content(email_message)

                    logger.info(f"发送{self.email_type}邮件到微信: {subject}")
                    self.send_to_weixin(subject, sender, content, received_time)
                    
                    # 发送成功后将邮件标记为已读
                    self.imap.store(num, '+FLAGS', '\\Seen')
                    
                except Exception as e:
                    logger.error(f"处理{self.email_type}邮件时出错: {str(e)}")
                    continue
                
        except Exception as e:
            logger.error(f"检查{self.email_type}邮件时出错: {str(e)}")
        finally:
            try:
                self.imap.close()
                self.imap.logout()
            except:
                pass

class OutlookMonitor:
    def __init__(self, email_addr, password):
        self.email_addr = email_addr
        self.password = password
        self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')
        self.last_check_time = datetime.now(beijing_tz)

    def connect(self):
        try:
            credentials = Credentials(self.email_addr, self.password)
            config = Configuration(credentials=credentials, server='outlook.office365.com')
            self.account = Account(
                primary_smtp_address=self.email_addr,
                config=config,
                access_type=DELEGATE
            )
            return True
        except Exception as e:
            logger.error(f"连接Outlook邮箱失败: {str(e)}")
            return False

    def send_to_weixin(self, subject, sender, content, received_time):
        try:
            # 转换为北京时间
            if received_time.tzinfo is None:
                received_time = pytz.utc.localize(received_time)
            beijing_time = received_time.astimezone(beijing_tz)
            
            # 格式化北京时间
            time_str = beijing_time.strftime("%Y-%m-%d %H:%M:%S")
            
            message = {
                "msgtype": "text",
                "text": {
                    "content": f"📨 Outlook邮件通知\n\n📬 收件邮箱: {self.email_addr}\n⏰ 接收时间: {time_str} (北京时间)\n👤 发件人: {sender}\n📑 主题: {subject}\n\n📝 内容预览:\n{content}",
                    "mentioned_list": ["@all"]
                }
            }
            response = requests.post(
                self.weixin_webhook,
                json=message
            )
            if response.status_code == 200:
                logger.info("Outlook邮件发送到微信成功")
            else:
                logger.error(f"Outlook邮件发送到微信失败: {response.text}")
        except Exception as e:
            logger.error(f"发送到微信时出错: {str(e)}")

    def check_emails(self):
        logger.info(f"开始检查Outlook邮箱: {self.email_addr}")
        
        if not self.connect():
            return

        try:
            # 获取最近30分钟的未读邮件
            filter_date = datetime.now(beijing_tz) - timedelta(minutes=30)
            unread_messages = self.account.inbox.filter(
                is_read=False,
                datetime_received__gt=filter_date
            )

            for message in unread_messages:
                try:
                    content = message.body[:500]  # 限制内容长度
                    self.send_to_weixin(
                        message.subject,
                        str(message.sender),
                        content,
                        message.datetime_received
                    )
                    message.is_read = True
                    message.save()
                except Exception as e:
                    logger.error(f"处理Outlook邮件时出错: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"检查Outlook邮件时出错: {str(e)}")

async def check_all_emails(background_tasks: BackgroundTasks):
    """检查所有配置的邮箱"""
    if service_status["is_checking"]:
        return {"message": "邮件检查正在进行中"}
    
    service_status["is_checking"] = True
    configs = get_email_configs()
    
    try:
        # 检查Gmail邮箱
        for gmail_config in configs['gmail']:
            monitor = EmailMonitor(
                gmail_config['email'],
                gmail_config['password'],
                'imap.gmail.com',
                'Gmail'
            )
            monitor.check_emails()
        
        # 检查QQ邮箱
        for qq_config in configs['qq']:
            monitor = EmailMonitor(
                qq_config['email'],
                qq_config['password'],
                'imap.qq.com',
                'QQ'
            )
            monitor.check_emails()
        
        # 检查Outlook邮箱
        for outlook_config in configs['outlook']:
            monitor = OutlookMonitor(
                outlook_config['email'],
                outlook_config['password']
            )
            monitor.check_emails()
        
        update_service_status(True)
    except Exception as e:
        error_message = f"检查邮件时出错: {str(e)}"
        logger.error(error_message)
        update_service_status(False, error_message)
    finally:
        service_status["is_checking"] = False

@app.get("/wake")
async def wake_service(background_tasks: BackgroundTasks):
    """唤醒服务并检查邮件"""
    background_tasks.add_task(check_all_emails, background_tasks)
    return {"message": "开始检查邮件"}

@app.get("/check", dependencies=[Depends(get_api_key)])
async def check_emails_endpoint(background_tasks: BackgroundTasks):
    """手动触发邮件检查"""
    return await check_all_emails(background_tasks)

@app.get("/status")
async def get_status():
    """获取服务状态"""
    return service_status

@app.get("/test")
async def test_webhook():
    """测试微信机器人"""
    return send_test_message()

@app.on_event("startup")
async def startup_event():
    async def keep_alive():
        while True:
            try:
                # 只保持服务活跃，不执行检查
                if os.getenv('VERCEL_URL'):
                    requests.get(f"https://{os.getenv('VERCEL_URL')}")
            except Exception as e:
                logger.error(f"keep-alive请求失败: {str(e)}")
            
            await asyncio.sleep(60)  # 每分钟ping一次
    
    # 创建keep-alive任务
    asyncio.create_task(keep_alive()) 