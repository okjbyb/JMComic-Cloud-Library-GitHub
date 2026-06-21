# JMComic Cloud Library

适用于 Ubuntu 24.04 LTS 的多用户云端漫画下载与 PDF 阅读系统。

## 功能

- 账号注册、登录与密码修改
- 每个用户独立的 PDF 书库
- 搜索、排行榜、单本及批量下载
- 手机友好的 PDF 阅读器
- PDF 自动压缩、线性化和分段加载
- 单本删除与批量书柜管理
- 每用户独立 OPDS 书库
- Docker Compose 一键部署

## 一键部署

```bash
chmod +x deploy.sh
./deploy.sh
```

脚本会安装 Docker、生成管理员强密码、构建镜像并启动服务。默认使用 `80` 端口。

指定其他端口：

```bash
APP_PORT=8080 ./deploy.sh
```

配置保存在 `.env`，用户数据保存在 Docker 卷 `jmcomic_cloud_data`。不要把真实 `.env` 上传到 GitHub。

## 常用命令

```bash
docker compose logs -f
docker compose restart
docker compose up -d --build
```

## 数据安全

仓库只包含 `.env.example`。管理员密码、会话密钥、用户数据库和 PDF 文件均由 `.gitignore` 排除。

## 说明

请遵守所在地法律法规及目标网站服务条款，仅下载和管理你有权访问的内容。
