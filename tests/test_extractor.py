from backend.app.core.config import Settings
from backend.app.services.extractor import ResumeExtractor, extract_skills


def _settings_without_ai() -> Settings:
    return Settings(_env_file=None, ai_api_key=None, deepseek_api_key=None)


def test_extract_skills_from_resume_text():
    text = "熟悉 Python、FastAPI、Redis、Docker，有 Serverless 项目经验。"
    assert extract_skills(text) == ["Python", "FastAPI", "Redis", "Docker", "Serverless"]


def test_javascript_does_not_imply_java():
    text = "熟悉 JavaScript、TypeScript、Vue 和 Node.js。"
    skills = extract_skills(text)
    assert "JavaScript" in skills
    assert "Java" not in skills


def test_react_agent_does_not_imply_react_framework():
    text = "基于 LangChain ReAct Agent 构建智能体执行链，前端使用 Vue3。"
    skills = extract_skills(text)
    assert "LangChain" in skills
    assert "React" not in skills
    assert "Vue" not in skills


def test_user_resume_skill_snippet_has_no_java_or_react():
    text = """
    前端开发：熟悉 Vue3 及其生态，掌握 HTML/CSS/JavaScript 基础。
    后端开发：具备 Go、Python 语言后端开发能力，熟悉 Gin、GORM 以及 FastAPI。
    基于 LangChain ReAct Agent 构建智能体执行链。
    技术栈：Python、FastAPI、LangChain、Ollama、Qdrant、MCP、Vue3、Vite、Electron
    """
    skills = extract_skills(text)
    assert "JavaScript" in skills
    assert "Java" not in skills
    assert "React" not in skills


def test_heuristic_resume_extraction():
    text = """
    张三
    电话：13800138000
    邮箱：zhangsan@example.com
    地址：上海市浦东新区
    求职意向：Python 后端工程师
    期望薪资：20k-25k
    3年工作经验
    本科 计算机科学与技术
    技能：Python FastAPI Redis Docker
    """
    extractor = ResumeExtractor(_settings_without_ai())
    profile = extractor._heuristic_extract(text)
    assert profile.basic_info.name == "张三"
    assert profile.basic_info.phone == "13800138000"
    assert profile.basic_info.email == "zhangsan@example.com"
    assert profile.job_info.job_intention == "Python 后端工程师"
    assert profile.background_info.years_of_experience == 3
    assert "FastAPI" in profile.background_info.skills


def test_education_extraction_ignores_awards():
    text = """
    教育背景
    某某大学 本科 计算机科学与技术
    获国家励志奖学金、优秀学生干部
    项目经历
    基于 Vue 的简历系统
    """
    extractor = ResumeExtractor(_settings_without_ai())
    profile = extractor._heuristic_extract(text)
    assert profile.background_info.education == "某某大学 本科 计算机科学与技术"
    assert "奖学金" not in profile.background_info.education


def test_ocr_education_line_is_spaced_and_intention_city_is_address():
    text = """
    陈静
    邮箱：dodolalorc@gmail.com
    电话：17543809322
    GitHub:https://github.com/dodolalorc
    博客：https://dodolalorc.cn/
    微信：dodolalorc
    意向职位：前端开发/客户端开发
    意向城市：杭州/上海/深圳/北京
    教育经历
    东北师范大学2022.09-2026.06本科计算机科学与技术
    东北师范大学“创新创业”奖学金
    工作经历
    """
    extractor = ResumeExtractor(_settings_without_ai())
    profile = extractor._heuristic_extract(text)
    assert profile.basic_info.email == "dodolalorc@gmail.com"
    assert profile.basic_info.phone == "17543809322"
    assert profile.basic_info.github == "https://github.com/dodolalorc"
    assert profile.basic_info.blog == "https://dodolalorc.cn/"
    assert profile.basic_info.wechat == "dodolalorc"
    assert profile.basic_info.address == "杭州/上海/深圳/北京"
    assert profile.job_info.job_intention == "前端开发/客户端开发"
    assert profile.background_info.education == "东北师范大学 2022.09-2026.06 本科 计算机科学与技术"


def test_github_url_does_not_swallow_blog_url_on_same_line():
    text = """
    丰浩
    GitHub https://github.com/BigSmartie 博客：https://bigsmartie.cn/
    """
    extractor = ResumeExtractor(_settings_without_ai())
    profile = extractor._heuristic_extract(text)
    assert profile.basic_info.github == "https://github.com/BigSmartie"
    assert profile.basic_info.blog == "https://bigsmartie.cn/"


def test_project_experience_is_grouped_by_project_header():
    text = """
    项目经历
    东北师范大学校园爱心超市 https://mart.bluemsun.com.cn 前端负责人 2026.1 - 至今
    技术栈和框架：Vue3，Vite，TypeScript，Pinia，Vue Router，Element Plus，Axios，Sass
    项目描述：本项目面向校园资助对象和爱心超市管理场景，支持多角色登录、商品浏览、购物车结算。
    主要工作：
    负责学生端核心流程开发，完成页面建设；并基于 Pinia 拆分各类业务状态。
    项目成就：目前已上线并服务于东北师范大学资助对象及相关管理人员。
    个人桌面宠物 https://github.com/Bigsmartie/Desktop-Pet 全栈开发 2026.3 - 至今
    技术栈：Python、FastAPI、LangChain、Ollama、Qdrant、MCP、Vue3、Vite、Electron
    项目描述：独立设计并开发一套本地化个人桌面宠物 Agent 系统。
    主要工作：
    设计 FastAPI 后端接口，完成聊天、用户画像设置、日志等 API 模块。
    奖项
    2026 年中国大学生计算机设计大赛省级二等奖
    """
    extractor = ResumeExtractor(_settings_without_ai())
    profile = extractor._heuristic_extract(text)
    projects = profile.background_info.project_experiences
    assert len(projects) == 2
    assert projects[0].name == "东北师范大学校园爱心超市"
    assert projects[0].role == "前端负责人"
    assert "购物车结算" in projects[0].description
    assert "个人桌面宠物" in projects[1].name
    assert projects[1].role == "全栈开发"
    assert "FastAPI" in projects[1].technologies


def test_project_header_with_link_and_date_next_line_is_grouped():
    text = """
    项目经历
    哈佛教育论坛一一新兴科技与未来人才联合论坛网站前端负责人链接：https://harvardces.eduhk.hk/
    2024.11-2025.05
    技术栈和框架：Nuxt,TypeScript，TailwindCSS，Git
    项目描述：本项目为香港教育大学举办的教育论坛的线上信息平台。
    主要工作：参与项目结构设计、本项目页面的设计和实现。
    东北师范大学第二学士学位报名审核系统前端负责人链接：https://tslxbm.nenu.edu.cn/
    2024.09-2025.05
    技术栈和框架：Vue3，TypeScript,Vite，PiniaTailwindCSS，ElementPlus
    项目描述：管理员端提供批量导入学生账号、审核申请、查询用户信息等功能。
    奖项
    """
    extractor = ResumeExtractor(_settings_without_ai())
    projects = extractor._heuristic_extract(text).background_info.project_experiences
    assert len(projects) == 2
    assert projects[0].name == "哈佛教育论坛一一新兴科技与未来人才联合论坛网站"
    assert projects[0].role == "前端负责人"
    assert "2024.11-2025.05" in projects[0].description
    assert projects[1].name == "东北师范大学第二学士学位报名审核系统"
