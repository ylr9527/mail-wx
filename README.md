代码来自 https://github.com/1143520/mail-wx 文档也是修改自原作者的，方便和我有一样需求的小白使用

# 邮件转发

一个自动将Gmail、QQ邮箱和Outlook的新邮件转发到钉钉、飞书、企业微信机器人和PushMe的服务。支持多邮箱配置，部署在自己的服务器上。

## 配置步骤

### 1. 邮箱配置

#### Gmail配置
1. 登录Gmail账号
2. 开启两步验证访问 [Google账号安全设置](https://myaccount.google.com/security)
3. 生成应用专用密码：
   - 访问 [应用专用密码设置](https://myaccount.google.com/apppasswords)
   - 选择"其他"，输入名称（如"Mail-Trans"）
   - 复制生成的16位密码

#### QQ邮箱配置
1. 登录QQ邮箱
2. 开启IMAP服务：
   - 设置 -> 账户 -> POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务
   - 开启"IMAP/SMTP服务"
3. 生成授权码（将作为密码使用）

#### Outlook配置
1. 确保使用Microsoft 365账户
2. 开启IMAP访问：
   - 登录Outlook网页版
   - 设置 -> 查看所有Outlook设置 -> 邮件 -> POP和IMAP
   - 确保IMAP已启用
3. 如果开启了双重认证：
   - 访问 [安全信息](https://account.microsoft.com/security)
   - 生成应用密码并使用它代替普通密码

### 2. Webhook配置

1. 支持钉钉、飞书、企业微信机器人和PushMe
2. 前面几个需要企业认证，推荐使用[PushMe](https://push.i-i.me/)

### 3. 环境变量配置

编辑 `.env` 文件，填入以下信息：
```
# Gmail配置 (多个账号用逗号分隔)
GMAIL_EMAILS=email1@gmail.com,email2@gmail.com
GMAIL_PASSWORDS=password1,password2

# QQ邮箱配置 (多个账号用逗号分隔)
QQ_EMAILS=qq1@qq.com,qq2@qq.com
QQ_PASSWORDS=password1,password2

# Outlook邮箱配置 (多个账号用逗号分隔)
OUTLOOK_EMAILS=user1@outlook.com,user2@outlook.com
OUTLOOK_PASSWORDS=password1,password2

# Webhook配置
WEIXIN_WEBHOOK=Webhook地址

# 安全配置
API_KEY=自定义的API密钥（用于手动触发检查）
```
#### 环境变量说明

1. 邮箱配置格式：
   - 多个邮箱地址用英文逗号分隔
   - 密码顺序要与邮箱地址一一对应
   - 示例：`GMAIL_EMAILS=a@gmail.com,b@gmail.com`

2. 密码说明：
   - Gmail：使用应用专用密码
   - QQ邮箱：使用授权码
   - Outlook：使用应用密码或账户密码

3. 安全建议：
   - 不要将 `.env` 文件提交到代码仓库
   - 定期更换API_KEY
   - 建议对每个邮箱使用单独的应用密码

4. 可选配置：
   ```
   # 检查间隔（分钟，默认5）
   CHECK_INTERVAL=5
   
   # 是否启用特定邮箱服务
   ENABLE_GMAIL=true
   ENABLE_QQ=true
   ENABLE_OUTLOOK=true
   
   # 调试模式
   DEBUG=false
   ```

### 4. 服务器部署

1. 上传 main.py、.env、requirements.txt到服务器，最好新建一个文件夹，比如mail

2. 部署项目：
```bash
cd /root/mail
sudo apt install python3.10-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. 配置systemd ：
创建文件/etc/systemd/system/mail.service
```bash
[Unit]
Description=FastAPI Application
After=network.target

[Service]
User=root
WorkingDirectory=/root/mail
EnvironmentFile=/root/mail/.env
ExecStart=/root/mail/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```
4. 启动项目
```bash
sudo systemctl daemon-reload
sudo systemctl start mail
sudo systemctl enable mail
```
### 5. 定时任务配置

使用 [cron-job.org](https://cron-job.org) 设置定时触发：

1. 注册并登录cron-job.org
2. 创建新的定时任务：
   - URL：`http://你的ip或者域名/wake`
   - 执行频率：建议每5分钟一次
   - 超时时间：默认值即可
   - 失败重试：建议开启，最多重试2次


> 关于检查频率的说明：
> - 建议设置为5分钟
> - 过于频繁的请求可能触发邮箱服务器的限制

不一定要用这个，宝塔、1panel、青龙都可以

## API接口说明

1. `/wake`：触发邮件检查（用于定时任务）
   - 无需认证
   - 立即返回，后台执行检查

2. `/check`：手动触发检查（需要API密钥）
   - 需要在请求头中加入 `X-API-Key`
   ```bash
   curl -H "X-API-Key: 你的API密钥" https://你的域名/check
   ```

3. `/status`：查看服务状态
   - 显示最后检查时间和状态
   - 显示错误统计
   - 显示当前是否正在检查

4. `/test`：测试微信机器人连接
   - 发送测试消息到企业微信群
   - 验证配置是否正确

## 注意事项

1. 多邮箱配置注意事项：
   - 确保邮箱地址和密码的数量匹配
   - 不同邮箱使用不同图标便于区分
   - 每个邮箱独立检查，互不影响

2. Gmail注意事项：
   - 需要开启两步验证
   - 使用应用专用密码而不是账号密码
   - 需要允许不够安全的应用访问

3. QQ邮箱注意事项：
   - 必须开启IMAP服务
   - 使用授权码而不是QQ密码
   - 确保邮箱已绑定手机号

4. Outlook注意事项：
   - 推荐使用Microsoft 365账户
   - 确保IMAP访问已启用
   - 双重认证用户需使用应用密码

5. 企业微信机器人：
   - Webhook地址要保密
   - 消息会自动@所有人
   - 邮件内容限制在500字以内

6. 定时任务：
   - 使用cron-job.org确保服务持续运行
   - 建议每5分钟触发一次
   - 重复的检查会自动跳过

## 故障排查

1. 邮件没有转发：
   - 检查各个邮箱配是否正确
   - 访问 `/status` 查看服务状态
   - 使用 `/test` 测试机器人连接
   - 手动触发 `/check` 测试

2. 服务不稳定：
   - 确认cron-job.org定时任务正常运行
   - 查看 `/status` 接口的错误统计

3. 特定邮箱不工作：
   - 检查该邮箱的IMAP设置
   - 确认密码/授权码是否正确
   - 查看日志中的具体错误信息

## 开发说明

- 使用Python FastAPI框架
- 支持异步处理和后台任务
- 使用exchangelib处理Outlook邮箱
- 使用imapclient处理Gmail和QQ邮箱
- 所有时间均已转换为北京时间
- 包含完整的错误处理和日志记录

## 许可证

MIT License
