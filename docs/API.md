# API 文档

默认服务地址：`http://127.0.0.1:8000`

## 健康检查

```http
GET /api/v1/health
```

响应：

```json
{
  "status": "ok",
  "service": "AI Resume Analyzer"
}
```

## 上传并解析简历

```http
POST /api/v1/resumes/analyze
Content-Type: multipart/form-data
```

表单字段：

- `file`：PDF 文件，必填。
- `force_refresh`：是否跳过缓存，默认 `false`。

响应包含：

- `resume_id`：简历内容哈希，后续匹配接口使用。
- `page_count`：PDF 页数。
- `text_preview`：清洗后的文本预览。
- `sections`：分段结果。
- `profile`：结构化关键信息。
- `from_cache`：是否命中缓存。

## 简历与岗位匹配

```http
POST /api/v1/resumes/{resume_id}/match
Content-Type: application/json
```

请求：

```json
{
  "job_description": "Python 后端工程师，熟悉 FastAPI、Redis、Serverless，有 2 年以上项目经验，本科及以上。"
}
```

响应：

```json
{
  "resume_id": "...",
  "score": 82.5,
  "dimension_scores": {
    "skill_match": 80.0,
    "experience_relevance": 100.0,
    "education_fit": 100.0,
    "keyword_coverage": 63.4
  },
  "matched_keywords": ["Python", "FastAPI", "Redis"],
  "missing_keywords": ["Serverless"],
  "recommendation": "推荐进入下一轮筛选",
  "explanation": "命中：Python、FastAPI、Redis；待补充：Serverless；经验年限较匹配。"
}
```

## 上传、解析并匹配

```http
POST /api/v1/resumes/analyze-and-match
Content-Type: multipart/form-data
```

表单字段：

- `file`：PDF 文件，必填。
- `job_description`：岗位描述，可选。
- `force_refresh`：是否跳过缓存，默认 `false`。

该接口用于前端一次性完成上传、解析和评分。

