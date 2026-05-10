# 项目:学科知识整合智能体(AI 全栈极速黑客松)

## 比赛信息
- 比赛时长:5 小时(2026-05-10)
- 提交物:GitHub 仓库 + 公网部署链接(必交);P2 技术报告(选交,赛后 24h 内补)

## 核心任务
为 7 本医学教材构建知识图谱,跨教材去重整合(压缩比 ≤30%),提供 RAG 精准问答 + 多轮对话修正决策。

## 技术栈(已锁定,不要随意改)
- **后端**:FastAPI(Python 3.11),uvicorn 起服务
- **前端**:Vite + Vue 3 + TypeScript + Pinia + ECharts;构建产物挂在 FastAPI StaticFiles
- **LLM**:DeepSeek-V4 Pro(`https://api.deepseek.com/v1`),JSON 模式;失败回退到 `deepseek-chat`
- **Embedding**:BGE-small-zh-v1.5(sentence-transformers,本地 CPU)
- **向量库**:ChromaDB(persistent,`data/chroma/`)
- **PDF 解析**:PyMuPDF(逐页流式,**禁止一次性 load 整本**)
- **图谱可视化**:ECharts(graph + tree + sankey 三视图)
- **部署**:魔搭创空间(免费)

## 关键约束
1. **教材 PDF 不进 git**(单文件最大 437MB,GitHub 限制 100MB)
2. **整合后字数 ≤ 原始 30%**(B 维度硬指标,超出按 confidence 升序删冗余)
3. **大文件流式解析**:组胚学 437MB,必须逐页 yield
4. **RAG 强约束**:回答必须含引用,无答案时回复"当前知识库中未找到相关信息"
5. **API key 在 .env**(`DEEPSEEK_API_KEY`),严禁提交到 git

## 目录约定
```
docs/{需求分析,系统设计,Agent架构说明,接口文档}.md
report/整合报告.md
src/backend/{main,config}.py + {api,core,models,storage}/
src/frontend/  Vite 项目,构建到 dist/
data/{textbooks,parsed,graphs,integrated,chroma,sessions}/  全部 gitignored
```

## 评分速记(满分 100 + P1 含 +25 + 创新 10)
- A 文档 15 / B 功能 25 / C 可视化 13 / **D Agent 架构 20**(重头戏)/ E 代码 17 / F 创新 10
- Agent 架构文档评分看论证深度,**单 Agent 论证充分胜过硬拆**

## 开发流程
1. 任务追踪用 TaskList,每完成一项立刻 mark completed
2. 每个阶段(A/B/C/D/E/F/G/H)结束跑一次烟囱测试
3. 部署窗口铁律:**4:10 前必须开始部署**,不可拖到最后

## 数据流图(简化)
```
上传 → Parser → parsed/{id}.json
            ↓
       KG Extractor(LLM, 逐章) → graphs/{id}.json
            ↓
       Integrator(双重对齐) → integrated/master_graph.json + decisions.json
            ↓
       ECharts 前端可视化

并行: parsed/* → Chunker → BGE Embedder → ChromaDB
              ↓
         /api/rag/query → top-5 → LLM(强约束)→ {answer, citations}

反馈: Chat → 解析意图 → 改 decisions.json → 重出 master → 前端刷新
```

## 写代码的偏好
- 中文注释 OK,关键函数加 docstring
- 类型注解必加(Pydantic + 标准 typing)
- 不写多余的空 try/except 兜底,出错就让它崩
- 不要为了"以后扩展"提前抽象,3 行重复优于早期抽象
- 函数 ≤50 行,文件 ≤300 行;超了拆模块
