# 邮件转发微信机器人

这是一个将Gmail和QQ邮箱收到的邮件自动转发到企业微信机器人的服务。

## 功能特点

- 支持Gmail和QQ邮箱
- 自动检测新邮件
- 实时转发到企业微信机器人
- 部署在Vercel上，无需服务器

## 配置说明

1. 复制`.env.example`文件为`.env`
2. 填写以下配置信息：

### Gmail配置
- `GMAIL_EMAIL`: Gmail邮箱地址
- `GMAIL_PASSWORD`: Gmail应用专用密码（需要在Gmail安全设置中生成）

### QQ邮箱配置
- `QQ_EMAIL`: QQ邮箱地址
- `QQ_PASSWORD`: QQ邮箱授权码（需要在QQ邮箱设置中生成）

### 微信机器人配置
- `WEIXIN_WEBHOOK`: 企业微信机器人的Webhook地址

## 本地开发

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 运行服务：
```bash
uvicorn main:app --reload
```

## Vercel部署

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

## 注意事项

1. Gmail需要开启"不够安全的应用访问权限"
2. QQ邮箱需要开启IMAP服务
3. 建议��用应用专用密码而不是账号主密码
4. 微信机器人的消息长度有限制，邮件内容会被截断 