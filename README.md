# 邮件转发微信机器人

一个自动将Gmail和QQ邮箱的新邮件转发到企业微信群的服务。部署在Vercel上，无需自己的服务器。

## 功能特点

- 支持Gmail和QQ邮箱的IMAP监控
- 实时转发新邮件到企业微信群机器人
- 显示北京时间的邮件接收时间
- 自动@所有人提醒
- 部署在Vercel上，免费且无需维护
- 使用cron-job.org进行定时触发

## 配置步骤

### 1. 邮箱配置

#### Gmail配置
1. 登录Gmail账号
2. 开启两步验证：访问 [Google账号安全设置](https://myaccount.google.com/security)
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

### 2. 企业微信配置

1. 在企业微信群中添加机器人
2. 复制机器人的Webhook地址

### 3. 环境变量配置

建 `.env` 文件，填入以下信息：
```
# Gmail配置
GMAIL_EMAIL=你的Gmail地址
GMAIL_PASSWORD=Gmail应用专用密码

# QQ邮箱配置
QQ_EMAIL=你的QQ邮箱地址
QQ_PASSWORD=QQ邮箱授权码

# 微信机器人配置
WEIXIN_WEBHOOK=企业微信机器人的Webhook地址

# 安全配置
API_KEY=自定义的API密钥（用于手动触发检查）
```

### 4. Vercel部署

1. 安装Vercel CLI：
```bash
npm i -g vercel
```

2. 登录Vercel：
```bash
vercel login
```

3. 部署项目：
```bash
vercel
```

### 5. 定时任务配置

使用 [cron-job.org](https://cron-job.org) 设置定时触发：

1. 注册并登录cron-job.org
2. 创建新的定时任务：
   - URL：`https://你的vercel域名/wake`
   - 执行频率：建议每5分钟一次
   - 超时时间：默认值即可
   - 失败重试：建议开启，最多重试2次

> 关于检查频率的说明：
> - 建议设置为5分钟，这样每月约8,640次请求
> - Vercel免费版每月限制100,000次请求
> - 设置过短的间隔（如1分钟）会快速消耗免费额度
> - 过于频繁的请求可能触发邮箱服务器的限制

### 6. Vercel免费额度说明

Vercel的免费计划（Hobby Plan）包含：
- 每月100,000次函数调用
- 每个函数最长执行时间10秒
- 每月100GB带宽

以5分钟检查一次计算：
- 每小时12次请求
- 每天288次请求
- 每月约8,640次请求
- 占用免费额度约8.6%

如果您需要更频繁的检查，建议：
1. 升级到Vercel的Pro计划
2. 使用自己的服务器部署
3. 考虑使用邮箱的推送服务

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

## 注意事项

1. Gmail注意事项：
   - 需要开启两步验证
   - 使用应用专用密码而不是账号密码
   - 需要允许不够安全的应用访问

2. QQ邮箱注意事项：
   - 必须开启IMAP服务
   - 使用授权码而不是QQ密码
   - 确保邮箱已绑定手机号

3. 企业微信机器人：
   - Webhook地址要保密
   - 消息会自动@所有人
   - 邮件内容限制在500字以内

4. 定时任务：
   - 使用cron-job.org确保服务持续运行
   - 每分钟触发一次/wake接口
   - 重复的检查会自动跳过

## 故障排查

1. 邮件没有转发：
   - 检查邮箱配置是否正确
   - 访问 `/status` 查看服务状态
   - 手动触发 `/check` 测试

2. 服务不稳定：
   - 确认cron-job.org定时任务正常运行
   - 检查Vercel部署日志
   - 查看 `/status` 接口的错误统计

## 开发说明

- 使用Python FastAPI框架
- 支持异步处理和后台任务
- 所有时间均已转换为北京时间
- 包含完整的错误处理和日志记录

## 许可证

MIT License