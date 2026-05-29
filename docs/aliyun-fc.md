# 阿里云函数计算部署参考

本项目建议用函数计算 FC 的自定义容器或自定义运行时部署 FastAPI 服务。

## 方式一：自定义容器

构建镜像：

```bash
docker build -f backend/Dockerfile -t ai-resume-analyzer:latest .
```

推送至阿里云容器镜像服务后，在函数计算中创建 HTTP 函数：

- 运行端口：`9000`
- 启动命令：镜像内已配置
- 内存：文本型 PDF 建议 512MB 起；启用 OCR 后建议 1024MB 起
- 超时：建议 60 秒起
- 环境变量：按需配置 `DEEPSEEK_API_KEY`、`AI_API_BASE`、`AI_MODEL`、`ENABLE_OCR`

## 方式二：Serverless Devs

根目录提供了 `s.yaml` 示例。安装 Serverless Devs 并配置阿里云密钥后：

```bash
s deploy
```

部署成功后，将前端页面中的 API 地址改为函数计算 HTTP 触发器地址。

## 生产注意事项

- 如果 PDF 大量上传，建议将原始文件放到 OSS，仅在函数中处理临时文件。
- 函数实例本地磁盘缓存不保证长期存在，生产环境可把 `JsonFileCache` 替换为 Redis。
- 扫描版 PDF 已内置 RapidOCR 兜底；如果生产环境并发较高，可替换为阿里云 OCR 或独立 OCR 服务。
- 前端域名需要加入 CORS 白名单；本项目默认允许所有来源，生产环境应收紧。
