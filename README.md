# 🧠 AI Vocab Agent | 智能英语学习引擎

![Vue.js](https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![LangChain](https://img.shields.io/badge/LangChain-121212?style=for-the-badge&logo=chainlink&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS-Vector_Search-blue?style=for-the-badge)
![ECharts](https://img.shields.io/badge/ECharts-Graph-E43961?style=for-the-badge)

🚀 **本项目旨在探索大模型技术在教育领域的深度应用。结合 Multi-Agent 架构与 GraphRAG 技术，打造从“无结构数据提取”到“网状知识图谱记忆”，再到“SRS 间隔重复测试”的极速沉浸式学习体验。**

🔗 **[点此在线体验 AI Vocab Agent (Web端)]**([https://daduduvocab-tiy2h3qtey.edgeone.cool?eo_token=e5e60edd83c8485ac062db6598732838&eo_time=1778121154])

*(注：由于腾讯云域名链接仅提供3小时限时预览，如想体验网站联系xbcmsbh2025@163.com)*

---

## ✨ 核心特性 / Features

- 📸 **多模态 OCR 提取 (Vision Agent)**
  - 支持拖拽上传纯图片构成的 `.docx` 文件。利用 Vision 大模型进行图片识别、自动去重聚合，并在后台自动生成支持按单元（Unit）划分的本地 JSON 词库。
- 🌌 **词根知识图谱与 GraphRAG**
  - 不再是死记硬背！引入 ECharts 力导向图（Force-Directed Graph），通过 LLM 深度分析同源词根并生成动态星状图。点击节点可呼出结合外刊真实语料（RAG）的单词释义、记忆法与例句。
- ⚡ **毫秒级语义向量雷达 (Semantic Retrieval)**
  - **创新点**：针对 LLM 生成过慢与 L2 距离的字符偏见问题，采用 **Agentic Query Expansion + FAISS 归一化余弦相似度（Cosine）碰撞** 架构。点击单词瞬间，从全局书架中 O(1) 召回语义高度相似的近义词（如 amend -> revise），彻底打通知识盲区。
- 🎯 **SRS 动态智能记忆流转**
  - 内置基于遗忘曲线的闪卡测试系统。自动提取当前单元词典进行无延迟缓存，记录用户单词停留耗时与熟练度。做错的单词自动进入队列末尾循环，直到完全掌握。
- 🚀 **极速工程架构优化**
  - 采用 Vue3 + FastAPI 前后端分离；自主实现**大模型并发锁**、**内存级数据缓存池**与**后台静默预加载队列（Pre-fetching）**，将长文本推理的等待时间优化至“0 秒无缝切换”。

---

## 📸 项目截图 / Screenshots

![界面展示1 - 词根星状图与语义雷达](https://github.com/user-attachments/assets/6dceae08-18ae-43c3-af70-45bd500b77b2)

![界面展示2 - 词根释义](https://github.com/user-attachments/assets/321c84e9-2eab-44b3-8326-abd032c65034)

![界面展示3 - 测试页面](https://github.com/user-attachments/assets/d7f36c32-b7d9-4112-92b2-36ed1448de9d)

![界面展示4 - SRS沉浸式测试与复盘](https://github.com/user-attachments/assets/90ef2e16-a02a-4276-8353-25a2cc215a20)

---

## 🛠️ 本地运行指南 / Quick Start

### 1. 后端服务 (Backend)
```bash
cd backend
python -m venv venv
# 激活虚拟环境 (Windows: venv\Scripts\activate, Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
```

### 配置环境变量：在 backend 目录下新建 .env 文件：
```bash
ZHIPU_API_KEY="你的智谱/大模型 API KEY"
ZHIPU_API_BASE="https://open.bigmodel.cn/api/paas/v4"
VISION_MODEL_NAME="glm-4v"
```

### 启动后端：
```bash
python main.py
```

### 2. 前端服务 (Frontend)
```bash
cd frontend
npm install
npm run dev
```

# 打开浏览器访问 http://localhost:5173 即可开始使用！
