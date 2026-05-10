# 学科知识整合智能体

> AI 全栈极速黑客松 · 2026-05-10

为多本教材构建知识图谱并跨教材去重整合(压缩比 ≤30%),提供 RAG 精准问答 + 多轮对话修正决策。

**部署链接**:见提交表单
**演示视频**:`docs/demo.mp4`(若有)

---

## ✨ 主要特性

- **多格式解析**:PDF / Markdown / TXT / DOCX(含 100MB+ 大文件流式处理)
- **章节级 KG 抽取**:DeepSeek JSON 模式输出节点 + 4 类关系(prerequisite / parallel / contains / applies_to)
- **跨教材双重对齐**:BGE 嵌入 + LLM 边界裁决,LLM 调用 ≤80 次完成 1500+ 节点对齐
- **30% 压缩约束**:语义合并 + 按 confidence 升序删冗余,merge 决策永不被反向打回
- **混合 RAG 检索**:向量 + BM25 → RRF 融合,每个回答必带 `[教材, 章节, 页码]` 引用
- **对话即决策**:教师用自然语言反馈即可热更新整合方案,图谱秒级刷新
- **图谱 3 视图**:力导向 / 树状 / 桑基,一键切换

---

## 🛠 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + uvicorn(Python 3.12) |
| 前端 | Vite + Vue 3 + TypeScript + Pinia + ECharts |
| LLM | DeepSeek-V4 Pro(JSON 模式) |
| Embedding | BGE-small-zh-v1.5(本地 CPU) |
| 向量库 | ChromaDB(persistent) |
| PDF 解析 | PyMuPDF |

---

## 📦 安装与运行

### 环境要求
- Python 3.12+(3.11 也可)
- Node.js 20+
- ~5GB 磁盘(向量索引 + 模型缓存)

### 1. 克隆与配置
```bash
git clone <repo-url>
cd ai-textbook-integration
cp .env.example .env
# 编辑 .env,填入 DEEPSEEK_API_KEY
```

### 2. 后端依赖
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 前端构建
```bash
cd src/frontend
npm install
npm run build   # 输出到 src/frontend/dist
cd ../..
```

### 4. 启动服务
```bash
uvicorn src.backend.main:app --host 0.0.0.0 --port 8000
```
访问 `http://localhost:8000` 即看到完整界面;`/docs` 是 Swagger API 文档。

---

## 🚀 一键 Docker 部署

```bash
docker-compose up --build
```
默认在 `http://localhost:8000` 提供完整服务。教材数据通过 web 界面上传,不打包进镜像。

---

## 📚 使用流程

1. **上传教材**(左侧拖拽,或点击"刷新"扫描已有的 `data/textbooks/`)
2. **抽取知识点**:每本"已解析"的教材点"抽取知识点",或调 `POST /api/graph/extract_all`
3. **跨教材整合**:右侧"整合"标签页 → "▶ 一键整合"
4. **建立 RAG 索引**:右侧"RAG 问答" → "建立索引"
5. **提问**:在 RAG 面板输入问题,获得带引用的答案
6. **对话修正**:在"对话修正"标签页用自然语言反馈,图谱实时更新

---

## 🗂 仓库结构

```
.
├── docs/
│   ├── 需求分析.md
│   ├── 系统设计.md
│   ├── Agent架构说明.md   ★ Agent 架构 20 分核心
│   └── 接口文档.md
├── report/
│   └── 整合报告.md          以 7 本教材为例的实测数据
├── src/
│   ├── backend/             FastAPI + 业务逻辑
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/             6 个路由模块
│   │   ├── core/            parser / extractor / integrator / rag / chat / agent
│   │   ├── models/schemas.py
│   │   └── storage/data_store.py
│   └── frontend/            Vite + Vue 3
│       ├── package.json
│       ├── vite.config.ts
│       └── src/
├── data/                   gitignored 教材原文 + 持久化数据
│   ├── textbooks/
│   ├── parsed/
│   ├── graphs/
│   ├── integrated/
│   ├── chroma/
│   └── sessions/
├── requirements.txt
├── package.json
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── CLAUDE.md               开发者笔记/约定
```

---

## 🔑 配置说明(.env)

```
DEEPSEEK_API_KEY=sk-xxxxx              # 必填
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat            # 或 deepseek-v4-pro

EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5  # 首次启动会自动从 HuggingFace 下载
CHROMA_PERSIST_DIR=data/chroma

ALIGN_THRESHOLD=0.85                    # 跨教材对齐阈值(更低=更激进合并)
COMPRESSION_RATIO_LIMIT=0.30            # 压缩比硬上限

HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

---

## 🧪 引用的开源项目

- [FastAPI](https://github.com/tiangolo/fastapi)
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF)
- [Vue 3](https://vuejs.org)
- [ECharts](https://echarts.apache.org)
- [ChromaDB](https://github.com/chroma-core/chroma)
- [BGE-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- [sentence-transformers](https://github.com/UKPLab/sentence-transformers)
- [rank_bm25](https://github.com/dorianbrown/rank_bm25)
- [openai-python SDK](https://github.com/openai/openai-python)(用于调用 DeepSeek 兼容接口)

核心逻辑(对齐算法、决策器、压缩控制、RAG pipeline、对话 patch 应用)均为自主实现。

---

## 📝 评分对照表

| 维度 | 实现位置 | 状态 |
|---|---|---|
| A 文档完整性(15) | `docs/`、`README.md`、`report/` | ✅ |
| B 功能完整性(25) | 见各模块 | ✅ |
| C 可视化创新(13) | `GraphView.vue`(3 视图切换) | ✅ |
| D Agent 架构(20) | `docs/Agent架构说明.md` | ✅ |
| E 代码质量(17) | `src/`(模块化,类型注解,docstring) | ✅ |
| F 创新自由发挥(10) | 见 Agent 架构说明 §e | ✅ |

