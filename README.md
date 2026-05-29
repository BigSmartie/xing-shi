# 候选人智能筛选工作台

本项目是一个面向招聘筛选场景的全栈考核项目。系统支持上传 PDF 简历，自动解析候选人基础信息、教育背景、项目经历与技能关键词，并结合岗位需求生成匹配评分和筛选结论。

线上形态采用“静态前端 + 云端 API”的分离架构：前端部署到 GitHub Pages，后端部署到阿里云函数计算 FC 3.0。

## 功能概览

- PDF 简历上传与文本提取，支持常规文本型 PDF。
- 扫描版或图片型 PDF 可通过 OCR 进行兜底识别。
- 候选人信息结构化提取：姓名、邮箱、电话、地址、GitHub、博客、教育背景、项目经历、技能等。
- 接入 DeepSeek，对简历进行语义解析与岗位匹配分析。
- 规则引擎兜底：未配置 AI Key 时仍可完成基础解析和评分。
- 技能原文证据过滤，避免把简历中未出现的 Java、React 等技能误展示为候选人技能。
- 岗位需求关键词提取、命中分析、缺口提示、维度评分与推荐结论。
- JSON 缓存机制，按简历内容和岗位需求复用解析结果，减少重复计算。
- Vue 静态前端，可直接部署到 GitHub Pages。

## 项目架构

```text
浏览器 / GitHub Pages
        |
        | HTTPS
        v
阿里云函数计算 FC 3.0 HTTP 触发器
        |
        v
FastAPI 后端服务
        |
        +-- PDF 文本提取：pypdf
        +-- OCR 兜底：PyMuPDF + RapidOCR
        +-- AI 解析：DeepSeek OpenAI-compatible API
        +-- 规则解析：正则、关键词、项目块识别
        +-- 匹配评分：技能、经验、学历、关键词覆盖
        +-- 缓存：JSON 文件缓存，本地为 .cache，云端为 /tmp/resume-cache
```

后端接口负责所有解析、AI 调用、评分和缓存逻辑。前端只负责上传文件、填写岗位需求、调用 API 并渲染结果。

## 技术选型

### 前端

- Vue 3：通过 CDN 使用，保持静态页面部署简单。
- HTML / CSS / JavaScript：不依赖 Node 构建流程，便于 GitHub Pages 直接发布。
- GitHub Pages：承载 `frontend/` 目录下的静态页面。

### 后端

- Python 3.11：主要后端开发语言。
- FastAPI：提供 RESTful API 和自动 Swagger 文档。
- Pydantic / pydantic-settings：定义响应模型和环境变量配置。
- pypdf：优先提取 PDF 内置文本。
- PyMuPDF + rapidocr-onnxruntime：用于扫描版 PDF 的 OCR 兜底识别。
- httpx：调用 DeepSeek 兼容 OpenAI 的 Chat Completions 接口。
- JSON 文件缓存：适合本地和 Serverless `/tmp` 临时目录，后续可替换为 Redis。

### AI 与匹配

- 默认 AI Provider：DeepSeek。
- 默认模型：`deepseek-chat`。
- AI 输出用于增强结构化解析与匹配分析。
- 规则引擎作为兜底，并对最终技能做原文证据过滤，降低模型幻觉风险。

## 目录结构

```text
.
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 路由
│   │   ├── core/         # 配置项
│   │   ├── models/       # Pydantic 数据模型
│   │   └── services/     # PDF、OCR、AI、解析、匹配、缓存服务
│   ├── Dockerfile        # 后端容器镜像
│   └── requirements.txt  # 后端依赖
├── frontend/
│   ├── index.html        # 前端入口
│   ├── app.js            # Vue 页面逻辑
│   └── styles.css        # 页面样式
├── docs/
│   ├── API.md
│   └── aliyun-fc.md
├── tests/                # 后端测试
├── .github/workflows/
│   └── page.yaml         # GitHub Pages 自动部署
├── s.yaml                # Serverless Devs 示例配置
└── README.md
```

## 本地运行

1. 激活 Conda 环境：

```powershell
conda activate 星使智算科技
```

2. 安装后端依赖：

```powershell
pip install -r backend/requirements.txt
```

3. 启动 FastAPI：

```powershell
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

4. 打开前端页面：

```text
frontend/index.html
```

本地开发时，前端 API 地址可填写：

```text
http://127.0.0.1:8000
```

后端健康检查：

```text
http://127.0.0.1:8000/api/v1/health
```

Swagger 文档：

```text
http://127.0.0.1:8000/docs
```

## 环境变量

本地可在项目根目录创建 `.env`：

```env
APP_NAME=AI Resume Analyzer
ENVIRONMENT=local
MAX_UPLOAD_MB=8
CACHE_DIR=.cache
CORS_ORIGINS=["*"]

ENABLE_OCR=true
OCR_PROVIDER=rapidocr
OCR_RENDER_DPI=260
OCR_MAX_PAGES=5

AI_PROVIDER=deepseek
AI_API_BASE=https://api.deepseek.com
AI_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

如果不配置 `DEEPSEEK_API_KEY`，系统会使用规则引擎兜底，但 AI 解析和语义匹配能力会下降。

## API 说明

接口统一前缀为：

```text
/api/v1
```

主要接口：

- `GET /api/v1/health`：健康检查，返回服务状态、AI Provider、模型与 AI 是否启用。
- `POST /api/v1/resumes/analyze`：上传并解析简历。
- `POST /api/v1/resumes/{resume_id}/match`：对已解析简历进行岗位匹配。
- `POST /api/v1/resumes/analyze-and-match`：上传简历并直接生成匹配报告。

更详细的请求示例见 [docs/API.md](./docs/API.md)。

## 部署方式

### 前端部署：GitHub Pages

前端是静态页面，部署目录为：

```text
frontend/
```

当前仓库通过 GitHub Actions 自动部署，配置文件为：

```text
.github/workflows/page.yaml
```

关键配置：

```yaml
- name: Upload artifact
  uses: actions/upload-pages-artifact@v3
  with:
    path: "./frontend"
```

部署完成后，GitHub Pages 地址示例：

```text
https://blog.bigsmartie.cn/xing-shi/
```

如果前端页面左下角显示旧的本地地址，可将后端服务地址改为云端 API 地址：

```text
https://ai-resuanalyzer-kpcqylmskg.cn-hangzhou.fcapp.run
```

不要填写 `/api/v1/health`，前端会自动拼接具体接口路径。

### 后端部署：阿里云函数计算 FC 3.0

后端使用自定义容器镜像部署到阿里云函数计算，HTTP 触发器对外提供 API。

容器启动端口：

```text
9000
```

Dockerfile 默认启动命令：

```dockerfile
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "9000"]
```

在 FC 控制台使用自定义容器时，建议启动命令选择“默认模式”，不要再手动重复填写 `python -m uvicorn ...`，否则可能导致参数被拼接重复。

推荐函数配置：

```text
函数类型：Web 函数
运行环境：自定义镜像 / 使用 ACR 中的镜像
监听端口：9000
内存：1 GB 或以上，OCR 场景建议 2 GB 或以上
超时时间：120 秒
认证方式：匿名访问
请求方法：GET、POST、OPTIONS
```

云端环境变量示例：

```text
PYTHONPATH=/code
CACHE_DIR=/tmp/resume-cache
ENVIRONMENT=production
AI_PROVIDER=deepseek
AI_API_BASE=https://api.deepseek.com
AI_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_deepseek_api_key_here
ENABLE_OCR=true
OCR_PROVIDER=rapidocr
OCR_RENDER_DPI=260
OCR_MAX_PAGES=5
```

构建并推送镜像时，建议固定 Linux AMD64 平台，并关闭 provenance，避免 FC 识别镜像平台为 `unknown/unknown`：

```powershell
docker buildx build `
  --platform linux/amd64 `
  --provenance=false `
  --sbom=false `
  -f backend/Dockerfile `
  -t crpi-7pa44g6k8cgh8jwe.cn-hangzhou.personal.cr.aliyuncs.com/resume-demo/ai-resume-analyzer:fc-amd64-v1 `
  --push .
```

部署成功后，可访问：

```text
https://ai-resuanalyzer-kpcqylmskg.cn-hangzhou.fcapp.run/api/v1/health
```

返回 `200 OK` 且包含 `status: ok` 即表示后端服务正常。

## 使用说明

1. 打开前端页面。
2. 确认左下角后端服务地址为本地或云端 FastAPI 地址。
3. 点击“选择文件”，上传 PDF 简历。
4. 在“岗位需求”中输入招聘要求，例如技能、经验年限、学历要求。
5. 点击“生成筛选报告”。
6. 查看候选人概览、联系方式、技能命中、项目经历、匹配维度、关键词覆盖与 JSON 结果。

如果只想验证解析能力，也可以点击“仅解析”，不填写岗位需求。

## 测试

```powershell
conda activate 星使智算科技
python -m pytest
```

## 常见问题

### 访问根路径返回 404

正常。后端没有定义 `/` 首页，应该访问：

```text
/api/v1/health
```

### GitHub Pages 页面仍然请求 127.0.0.1

浏览器可能保存了旧的 `localStorage`。在页面左下角把 API 地址改为云端地址，或清理该站点的浏览器本地存储。

### DeepSeek 显示未配置

检查后端运行环境是否配置了 `DEEPSEEK_API_KEY`，并重启本地服务或重新部署云端函数。

### 简历解析速度较慢

AI 调用、OCR 和云函数冷启动都会增加耗时。演示时可保持最小实例数为 1，或关闭 OCR 只处理文本型 PDF。
