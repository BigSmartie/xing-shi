const { createApp } = Vue;

createApp({
  data() {
    return {
      apiBase: localStorage.getItem("resume-api-base") || "https://ai-resuanalyzer-kpcqylmskg.cn-hangzhou.fcapp.run",
      activePanel: "overview",
      selectedFile: null,
      jobDescription: "",
      resume: null,
      match: null,
      loading: false,
      toast: "",
      isDragging: false,
      healthOk: false,
      healthText: "服务未连接",
      aiEnabled: false,
      aiProvider: "deepseek",
      aiModel: "",
    };
  },
  computed: {
    navItems() {
      return [
        { id: "overview", label: "候选人概览", badge: this.resume ? "OK" : "" },
        { id: "match", label: "匹配分析", badge: this.match ? Math.round(this.match.score) : "" },
        { id: "evidence", label: "原文证据", badge: this.resume?.page_count || "" },
        { id: "json", label: "JSON 结果", badge: this.resume ? "API" : "" },
      ];
    },
    profile() {
      return this.resume?.profile || {};
    },
    basicInfo() {
      return this.profile.basic_info || {};
    },
    jobInfo() {
      return this.profile.job_info || {};
    },
    backgroundInfo() {
      return this.profile.background_info || {};
    },
    candidateName() {
      return this.basicInfo.name || (this.resume ? "候选人" : "等待上传");
    },
    candidateInitial() {
      const name = this.basicInfo.name || "候";
      return name.slice(0, 1).toUpperCase();
    },
    headline() {
      if (this.jobInfo.job_intention) {
        return this.jobInfo.job_intention;
      }
      if (this.backgroundInfo.education) {
        return this.backgroundInfo.education;
      }
      return this.resume ? "已完成简历解析" : "上传简历后生成候选人档案";
    },
    skills() {
      return this.backgroundInfo.skills || [];
    },
    projects() {
      return this.backgroundInfo.project_experiences || [];
    },
    sections() {
      return this.resume?.sections || [];
    },
    scorePercent() {
      return this.match ? Math.max(0, Math.min(100, Number(this.match.score || 0))) : 0;
    },
    resumeSummary() {
      if (!this.resume) {
        return "上传 PDF 简历并填写岗位需求后，系统会生成结构化筛选报告。";
      }
      return this.profile.summary || "简历结构化解析完成。";
    },
    extractionSource() {
      if (!this.resume) {
        return "待解析";
      }
      return this.profile.extraction_source === "ai" ? "DeepSeek AI" : "规则兜底";
    },
    aiStatusLabel() {
      if (!this.healthOk) {
        return "AI 待连接";
      }
      const provider = this.aiProvider === "deepseek" ? "DeepSeek" : this.aiProvider;
      return this.aiEnabled ? `${provider} 已启用` : `${provider} 未配置`;
    },
    contactItems() {
      return [
        { label: "邮箱", value: this.basicInfo.email },
        { label: "电话", value: this.basicInfo.phone },
        { label: "微信", value: this.basicInfo.wechat },
        { label: "GitHub", value: this.basicInfo.github },
        { label: "博客", value: this.basicInfo.blog },
        { label: "地址", value: this.basicInfo.address },
      ].filter((item) => this.hasValue(item.value));
    },
    profileRows() {
      return [
        { label: "姓名", value: this.basicInfo.name },
        { label: "电话", value: this.basicInfo.phone },
        { label: "邮箱", value: this.basicInfo.email },
        { label: "微信", value: this.basicInfo.wechat },
        { label: "GitHub", value: this.basicInfo.github },
        { label: "博客", value: this.basicInfo.blog },
        { label: "地址", value: this.basicInfo.address },
        { label: "求职意向", value: this.jobInfo.job_intention },
        { label: "期望薪资", value: this.jobInfo.expected_salary },
        { label: "工作年限", value: this.formatYears(this.backgroundInfo.years_of_experience) },
        { label: "学历背景", value: this.backgroundInfo.education },
      ].filter((row) => this.hasValue(row.value));
    },
    matchedKeywords() {
      return this.match?.matched_keywords || [];
    },
    missingKeywords() {
      return this.match?.missing_keywords || [];
    },
    keywordCoverage() {
      const total = this.matchedKeywords.length + this.missingKeywords.length;
      if (!total) {
        return "待分析";
      }
      return `${Math.round((this.matchedKeywords.length / total) * 100)}%`;
    },
    stats() {
      return [
        {
          label: "综合评分",
          value: this.match ? Math.round(this.match.score) : "--",
          caption: this.match ? this.match.recommendation : "等待岗位匹配",
        },
        {
          label: "技能命中",
          value: this.match ? `${this.matchedKeywords.length}/${this.jobKeywordCount}` : "--",
          caption: this.match ? "岗位关键词覆盖" : "上传后计算",
        },
        {
          label: "候选技能",
          value: this.skills.length || "--",
          caption: this.skills.length ? this.skills.slice(0, 3).join(" / ") : "待识别",
        },
        {
          label: "解析来源",
          value: this.resume ? this.extractionSource : "--",
          caption: this.resume?.from_cache ? "缓存命中" : "实时分析",
        },
      ];
    },
    jobKeywordCount() {
      return this.match?.job_keywords?.length || this.matchedKeywords.length + this.missingKeywords.length;
    },
    metrics() {
      const scores = this.match?.dimension_scores || {};
      return [
        {
          label: "技能匹配",
          value: Number(scores.skill_match || 0),
          caption: "简历技能与岗位关键词的重合度",
        },
        {
          label: "经验相关",
          value: Number(scores.experience_relevance || 0),
          caption: "工作年限与经历描述的相关性",
        },
        {
          label: "学历匹配",
          value: Number(scores.education_fit || 0),
          caption: "学历背景与岗位要求的匹配度",
        },
        {
          label: "关键词覆盖",
          value: Number(scores.keyword_coverage || 0),
          caption: "岗位描述在简历文本中的覆盖情况",
        },
      ];
    },
    insightItems() {
      if (!this.resume) {
        return [
          { title: "待上传", body: "上传简历后生成候选人摘要。", tone: "neutral" },
          { title: "待匹配", body: "填写岗位需求后生成匹配建议。", tone: "neutral" },
        ];
      }
      const items = [];
      if (this.skills.length) {
        items.push({
          title: "技能画像",
          body: this.skills.slice(0, 6).join("、"),
          tone: "positive",
        });
      }
      if (this.match) {
        items.push({
          title: "岗位匹配",
          body: this.matchedKeywords.length
            ? `命中 ${this.matchedKeywords.slice(0, 5).join("、")}`
            : "暂无明显岗位关键词命中",
          tone: this.matchedKeywords.length ? "positive" : "warning",
        });
        if (this.missingKeywords.length) {
          items.push({
            title: "待确认项",
            body: this.missingKeywords.slice(0, 5).join("、"),
            tone: "warning",
          });
        }
      }
      if (!this.basicInfo.phone || !this.basicInfo.email) {
        items.push({
          title: "信息完整度",
          body: "联系方式字段仍有缺失，建议人工复核。",
          tone: "warning",
        });
      }
      return items.slice(0, 4);
    },
    textLength() {
      const text = this.resume?.full_text || this.resume?.text_preview || "";
      return text ? `${text.length} 字` : "暂无";
    },
    jsonResult() {
      if (!this.resume) {
        return "暂无内容";
      }
      return JSON.stringify({ resume: this.resume, match: this.match }, null, 2);
    },
  },
  mounted() {
    this.checkHealth();
  },
  methods: {
    chooseFile() {
      this.$refs.fileInput.click();
    },
    handleFileChange(event) {
      this.selectedFile = event.target.files[0] || null;
      this.resetAnalysisState();
    },
    handleDrop(event) {
      this.isDragging = false;
      const file = event.dataTransfer.files[0];
      if (!file) {
        return;
      }
      if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
        this.showToast("请选择 PDF 文件。");
        return;
      }
      this.selectedFile = file;
      this.resetAnalysisState();
    },
    saveApiBase() {
      localStorage.setItem("resume-api-base", this.apiBase);
      this.checkHealth();
    },
    async checkHealth() {
      const base = this.normalizedApiBase();
      if (!base) {
        this.healthOk = false;
        this.healthText = "服务未配置";
        return;
      }
      try {
        const response = await fetch(`${base}/api/v1/health`);
        const payload = await response.json().catch(() => ({}));
        this.healthOk = response.ok;
        this.healthText = response.ok ? "服务已连接" : "服务未连接";
        this.aiEnabled = Boolean(payload.ai_enabled);
        this.aiProvider = payload.ai_provider || "deepseek";
        this.aiModel = payload.ai_model || "";
      } catch {
        this.healthOk = false;
        this.healthText = "服务未连接";
        this.aiEnabled = false;
      }
    },
    async submitResume(withMatch) {
      if (!this.selectedFile) {
        this.showToast("请先选择 PDF 简历。");
        return;
      }
      if (withMatch && !this.jobDescription) {
        this.showToast("请填写岗位需求。");
        return;
      }

      const body = new FormData();
      body.append("file", this.selectedFile);
      if (withMatch) {
        body.append("job_description", this.jobDescription);
      }

      this.loading = true;
      this.resetAnalysisState();
      this.match = null;
      try {
        const response = await fetch(`${this.normalizedApiBase()}/api/v1/resumes/analyze-and-match`, {
          method: "POST",
          body,
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || "请求失败");
        }
        this.resume = payload.resume;
        this.match = payload.match;
        this.activePanel = withMatch ? "match" : "overview";
        this.healthOk = true;
        this.healthText = "服务已连接";
      } catch (error) {
        this.showToast(error.message || "服务暂时不可用。");
      } finally {
        this.loading = false;
      }
    },
    normalizedApiBase() {
      const base = this.apiBase.trim().replace(/\/$/, "");
      localStorage.setItem("resume-api-base", base);
      return base;
    },
    formatYears(value) {
      if (value === null || value === undefined || value === "") {
        return "";
      }
      return `${Number(value).toLocaleString("zh-CN")} 年`;
    },
    hasValue(value) {
      return value !== null && value !== undefined && String(value).trim() !== "";
    },
    resetAnalysisState() {
      this.resume = null;
      this.match = null;
      this.activePanel = "overview";
    },
    formatFileSize(size) {
      if (size < 1024 * 1024) {
        return `${(size / 1024).toFixed(1)} KB`;
      }
      return `${(size / 1024 / 1024).toFixed(2)} MB`;
    },
    showToast(message) {
      this.toast = message;
      window.clearTimeout(this.toastTimer);
      this.toastTimer = window.setTimeout(() => {
        this.toast = "";
      }, 3600);
    },
  },
}).mount("#app");
