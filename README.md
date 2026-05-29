# AI 赋能的智能简历分析系统

这是一个面向招聘筛选场景的全栈考核项目：后端解析 PDF 简历、提取结构化信息、根据岗位描述计算匹配度；前端提供上传、解析、评分和结果查看页面。

## 功能

- 单个 PDF 简历上传，兼容多页文本型 PDF。
- 图片/扫描版 PDF 自动 OCR 兜底识别。
- 简历文本清洗、分段和结构化预览。
- 关键信息提取：姓名、电话、邮箱、地址、求职意向、期望薪资、工作年限、学历、项目经历、技能。
- 岗位需求关键词提取与匹配评分。
- JSON 文件缓存，按简历哈希和岗位描述哈希避免重复计算。
- 可选 AI 模型调用：默认使用 DeepSeek 的 OpenAI-compatible 接口；未配置密钥时自动使用规则提取与评分。
- Vue 3 静态前端页面，可部署到 GitHub Pages。

## 技术栈

- 后端：Python、FastAPI、Pydantic、pypdf、PyMuPDF、RapidOCR、httpx
- 前端：Vue 3、HTML、CSS
- 缓存：本地 JSON 文件缓存，可替换为 Redis
- 部署：本地 Uvicorn、Docker、阿里云函数计算自定义容器/自定义运行时

## 项目结构

```text
.
├── backend/
│   ├── app/
│   │   ├── api/              # RESTful 路由
│   │   ├── core/             # 配置
│   │   ├── models/           # 响应模型
│   │   └── services/         # PDF 解析、AI 提取、匹配评分、缓存
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # GitHub Pages 可直接部署的静态页面
├── docs/                     # API 与部署说明
├── tests/                    # 轻量单元测试
├── .env.example
└── s.yaml                    # 阿里云函数计算 Serverless Devs 示例
```

## 本地运行

使用你已创建的 Conda 环境：

```powershell
conda activate 星使智算科技
pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

打开前端：

```text
frontend/index.html
```

页面中的后端服务地址默认是 `http://127.0.0.1:8000`。它的含义是：前端页面和后端 API 是分离部署的，前端需要知道请求发到哪里。本地开发时使用 `127.0.0.1`，部署到 GitHub Pages 后改成阿里云函数计算或其他云服务的公开 API 地址。

## AI 模型配置

复制 `.env.example` 为 `.env`，按需配置：

默认使用 DeepSeek：

```env
AI_PROVIDER=deepseek
AI_API_BASE=https://api.deepseek.com
AI_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

也可以使用通用变量名：

```env
AI_API_KEY=your_deepseek_api_key_here
```

如果不配置 `DEEPSEEK_API_KEY` 或 `AI_API_KEY`，系统仍会使用规则引擎完成解析与评分，便于本地演示。为避免模型或规则扩写技能，后端会对最终技能做原文证据过滤：简历原文没有出现的技能不会展示。

## OCR 配置

扫描版或图片版 PDF 没有可复制文本，系统会自动使用 OCR 兜底：

```env
ENABLE_OCR=true
OCR_PROVIDER=rapidocr
OCR_RENDER_DPI=180
OCR_MAX_PAGES=5
```

OCR 会增加冷启动时间和内存占用。部署到阿里云函数计算时，建议内存设置为 1024MB 起，超时时间设置为 60 秒以上。

## API

- `GET /api/v1/health`
- `POST /api/v1/resumes/analyze`
- `POST /api/v1/resumes/{resume_id}/match`
- `POST /api/v1/resumes/analyze-and-match`

启动后可访问 Swagger 文档：

```text
http://127.0.0.1:8000/docs
```

更详细的请求示例见 [docs/API.md](./docs/API.md)。

## 前端部署

`frontend/` 是纯静态目录，可直接部署到 GitHub Pages：

1. 将仓库推送到 GitHub。
2. 在仓库 Settings -> Pages 中选择部署 `frontend/` 所在分支目录。
3. 将页面中的 API 地址改为云端后端地址。

## 后端部署

可选路径：

- Docker：使用 [backend/Dockerfile](./backend/Dockerfile) 构建镜像。
- 阿里云函数计算：参考 [docs/aliyun-fc.md](./docs/aliyun-fc.md) 和 [s.yaml](./s.yaml)。

## 测试

```powershell
conda activate 星使智算科技
python -m pytest
```

## 设计说明

评分由四个维度组成：技能匹配、经验相关性、学历匹配、关键词覆盖。系统优先使用确定性规则保证可演示性；配置 AI 模型后，会对结构化提取和最终评分进行增强，并保留规则结果作为兜底。
