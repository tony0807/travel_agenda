# 设计与架构说明书 (Design & Architecture Specification)

## 📌 项目概述 (Project Overview)

**项目名称**：智能旅程规划专家 (Travel Agenda)
**定位**：一款面向中国用户的智能、沉浸式端到端旅行行程单生成与可视化网页应用。
**核心功能**：通过自然语言输入（如“我想去日本京都玩3天，喜欢古建筑和美食”），智能整合全网最新攻略，调用大模型生成含有结构化数据的详细旅行日程。随后在前端动态渲染出包含地点坐标地图、每日时间轴、精美插图以及路线概览的沉浸式网页，并支持一键导出或打印为 PDF 格式。

---

## 🏗 技术栈选型 (Technology Stack)

### **后端与驱动层 (Backend & Core Logic)**

- **Web 框架**: `Streamlit` - 用于快速搭建 Python 互动式应用面板，并在云端容器内快速部署。
- **大语言模型 (LLM)**: `DeepSeek V3.2` (阿里云百炼 DashScope) - 承载所有文本理解、旅游常识问答和严格标准的 JSON 数据树结构化输出。
- **原生爬虫 (Crawler)**: `urllib.request` + `re` (正则表达式)
  - **架构亮点**：完全摒弃了可能在 Streamlit Cloud 轻量级容器中引发编译错误的第三方库（例如 `ddgs`），依靠纯内置模块动态拦截 DuckDuckGo 流量并爬取诸如“马蜂窝”、“穷游”、“小红书”、“Tripadvisor” 的有机搜索列表前六位的实时攻略，注入至 Prompt 中以确保 LLM 生成的时效性。
- **图片 API**: `Wikipedia Action API` (核心) / `Bing Thumbnail API` (兜底)
  - **架构亮点**：为避免 Unsplash 的图片重复或相关性差的问题。首先尝试通过提取关键词调用维基百科的 Thumbnail 提供高清景点或城市首图。如果在维基百科获取不到图片，则自动降级到自带长缓冲池缩略图特性的 Bing 搜索层，确保每一张行程节点上的照片都能绝无遗漏地展示出来。

### **前端与可视化渲染 (Frontend & Rendering)**

由于 Streamlit 本身的组件限制严重，无法完成“全屏、交互式沉浸的文旅卡片页面”，该项目采取了 **"HTML 倒模大屏注入技术"**。后端在拿到 LLM 的 JSON 数据结构后，运用 Python 内置字符串插值与模板生成纯粹的 HTML/DOM 块，通过 `streamlit.components.v1.html` 将整个自研的网页硬嵌入。

- **视觉呈现 (CSS/Design)**:
  - **主色调**: 焦糖暖咖色 (`#f0ebe3`, `#b8860b`)，突出轻奢高雅的沉浸式旅游杂志感。
  - **响应式**: 完全适配 Web 端宽屏及 Mobile 端竖屏（通过 Media Query 进行 Title 字号与图片布局缩放）。
  - **排版细节**: 设置了悬浮（Sticky）横向滚动导航条（`scroll-snap-type: x mandatory`）直达每天行程；每日行程采用交替照片与地图的精致时间轴排版。
- **交互地图**: 引入了极其轻量且开源的 `Leaflet.js`，基于真实的 Lat/Lng 节点进行初始化。
  - **地图资源配置**:
    - **中国境内范围** (智能正则或边界圈定过滤)：默认加载高德地图 (`amapLayer`) HTTPS 瓦片切片源。
    - **海外旅行范围**：默认加载无偏的 Google Map (`googleLayer`)。
  - **交互**: 鼠标滚轮缩放关闭（防止网页滑动打架）；自带缩放按钮和全屏 (Fullscreen) 控制，完美兼容移动与 PC 的拖拽手势。

---

## 🎨 关键架构设计与解耦 (Key Architectural Designs)

### 1. 业务串行流程 (Control Flow)

1. **用户输入与 UI 重置**：拦截用户的 Prompt 后，隐藏掉初始页面的全屏背景与引导横幅。
2. **多模态异步加载**：
   - 触发多线程 `threading.Thread` 的 `call_api()` 方法避免主线程（UI UI刷新）阻塞。
   - 同时主线程挂起循环展示诸如 `🧳 🏃‍♂️ 💨` 行李箱旅人的 CSS 过渡动画与循环旅行小知识 (Travel Tips) 及诗意加载短句，大幅提高用户的加载期望爽感。
3. **Prompt 与爬虫合并**：
   `Final_User_Prompt = User_input + Scraped_Newest_Tips(马蜂窝/小红书...)` -> 提交至 `deepseek-v3.2` 模型。
4. **HTML 模板倒模与呈现**：
   模型吐出 JSON -> `generate_html_template()` 进行拼装 -> 调用大尺寸 `iframe` 显示 -> 自动注入“隐身 CSS” 将外层 Streamlit 自带输入框和所有边框强行干掉（呈现出独占首屏的干净页面）。

### 2. Streamlit 屏蔽层对抗 (Streamlit Obstruction Evasion)

为了追求极致精美、原生的 Web App 效果，项目针对 Streamlit 原生自带的、不可控的冗杂 UI 进行了一系列安全但极端的覆写与销毁。

- **CSS 属性毁灭**: 利用 `[data-testid=...]` 以及绝对定位探测 `div[style*="position: fixed"][style*="bottom"]` 并赋以 `display: none !important`。
- **跨域跨沙盒移除 (JavaScript 级)**: 由于 Streamlit Cloud 将用户程序框在独立 `iframe`，其强制追加在最外层（parent.document）的广告浮层和 GitHub Deploy 图标无法被常规 CSS 清除。项目创新性地利用 `components.html()` 创建了一个静默 `script` 脚本。脚本尝试探测外部宿主 (`window.parent.document`) 并在每秒持续动态向系统顶层注入样式黑名单节点，实现即便元素试图重新生成，也能将其“防爆破式”拔除。

---

## 📂 项目结构描述 (File Structure)

仅需一个非常轻量的大一统执行文件及云端依赖：

- **`app.py`**
  包含了 Streamlit UI 逻辑、网络原生爬虫抓取器、大模型请求逻辑（带重试处理）、多线程渲染、以及生成沉浸式 HTML 与交互地图的巨型代码串模板引擎。是最根本且唯一的文件。
- **`requirements.txt`**
  极其克制的依赖项描述，仅含有 `streamlit` 和 `openai` (用于连接相兼容的通义千问 LLM endpoint)。不带有任何低级包负担。
- **`.streamlit/config.toml`** (系统配置文件)
  配置云端默认屏蔽官方工具栏项 `[client] toolbarMode = "minimal"` 以辅助清理右上角的多余内容。

## 💡 未来扩展方向 (Future Roadmap)

- 本地化保存功能：支持在生成的静态 HTML 中点击导出 `*.ics` 日程文件导入至苹果或谷歌日历。
- 进一步集成高德/Google Direction API 实现两点之间物理路线距离、交通工具预测用时的自动回显。
