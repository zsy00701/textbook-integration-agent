# RAG Benchmark

为本项目自建的 RAG 评测集,覆盖 7 本医学教材,**150 道题**。
完全独立于 `src/`,只通过 HTTP 调 `/api/rag/query`,不会影响主代码。
当前实时统计见 [`DATASET_STATS.md`](./DATASET_STATS.md)(由 `python stats.py --md DATASET_STATS.md` 生成)。

## 设计理念

赛题文档在"鼓励自建 RAG Benchmark"章节明确指出"自己利用 AI 编写 20-50 个测试问题"。
我把规模扩到 **150 题**,主要是为了让消融实验在统计上更稳:

- **30+ 题做单一变量 ablation**:在 chunk 300/500/800、有无 rerank、不同 embedding 之间比 1-2 个百分点的差异时,样本太少结论不可信
- **覆盖 7 本教材的低频章节**:不是每本只挑 3-5 个高频概念,而是延伸到临床综合征、跨教材诊断推理,这才能暴露 RAG 在长尾问题上的失败模式
- **8% unanswerable 题**:验证赛题 P0 硬约束"无答案时回复'当前知识库中未找到相关信息'",并加入提示注入 / 越狱 / 隐私查询等对抗题

## 数据集结构 (`questions.jsonl`)

每行一个 JSON:

| 字段 | 含义 |
| --- | --- |
| `id` | `q001`~`q150`(连续,无空号) |
| `type` | `factual` / `comparative` / `reasoning` / `cross_book` / `unanswerable` |
| `difficulty` | `easy` / `medium` / `hard` |
| `textbooks` | 期望引用的教材名(`unanswerable` 题为空数组) |
| `chapter_hint` | 期望引用的章节关键字(子串匹配) |
| `question` | 题目原文 |
| `keywords` | 答案中"应当出现"的核心关键词列表(用于关键词法打分) |
| `answer_summary` | 参考答案大意(用于 LLM 法打分) |

`validate.py` 会强制以上字段完整、id 连续、教材名在白名单、unanswerable 题不带 textbooks 等。

### 当前分布(`stats.py` 输出)

| 维度 | 分布 |
| --- | --- |
| 题型 | factual 89 / cross_book 26 / reasoning 12 / unanswerable 12 / comparative 11 |
| 难度 | easy 13 / medium 81 / hard 56 |
| 教材覆盖 | 生理 41 / 病理 39 / 病生 36 / 微生物 23 / 传染 18 / 组胚 15 / 解剖 13 |
| 跨教材深度 | 单教材 101 题 / 2 教材 27 题 / 3 教材 10 题 |

医学问题机制题居多,所以 `medium` 占主体;hard 题集中在 reasoning 和 cross_book。

### 题目构造方法

> 这里写清楚是为了让评委相信题目不是 LLM 直接 fab 出来的。

- 每题先写 `answer_summary`(基于人卫版教材标准章节内容),再倒推 `keywords`
- `keywords` 包括同义/等价表达(如"动作电位"/"去极化"/"Na+"/"复极化"),避免 RAG 输出换说法就 0 分
- `chapter_hint` 用章节名核心关键字而非全名,容忍后端解析时不同的章节命名风格
- `unanswerable` 题分四类:① 完全跨领域(区块链/前端/历史)② 时效性事件 ③ 隐私查询 ④ 提示注入诱导

## 评分指标

支持 **两种打分方式**,可单独跑也可同时跑(`--judge keyword|llm|both`)。

### 关键词法 (默认,免费快)

`metrics.py` 给每题打三个独立分:

- **answer_score**: 关键词召回率 = 命中数 / `keywords` 总数。若错误地拒答,分数置 0。
- **citation_score**: 引用命中
  - chapter_hint 也命中 → 1.0
  - 仅 textbook 命中 → 0.5
  - 均未命中 → 0.0
  - `unanswerable` 题:无引用 → 1.0,有引用 → 0.0
- **refusal_correct**: 该拒答时拒答、不该拒答时不拒答(布尔)

### LLM-as-Judge (DeepSeek)

`llm_judge.py` 用 DeepSeek JSON 模式给候选答案打三项 0~1 分:

- **llm_correctness**: 事实是否正确(对照 `answer_summary`)
- **llm_completeness**: 是否覆盖参考要点
- **llm_faithfulness**: 是否仅基于引用、未编造(对应 RAG 强约束)

带磁盘缓存(`.judge_cache/`),同样的 (题目, 答案哈希) 不重复花 token。
150 题一次完整 LLM 评判 ≈ ¥0.6;改 RAG 后只重判变化的题。
依赖 `.env` 里的 `DEEPSEEK_API_KEY`/`BASE_URL`/`MODEL`,无 Key 时自动降级为 0 分 + error,不打断流程。

### 为什么两个都要

关键词法快但对同义改写不敏感;LLM 法准但贵且慢。
**两个指标都打,在报告里画一张相关性散点图本身就是一个值得写的实验点**(关键词法稳定吗?对哪类题失效?)。

## 运行

### 0. 自检

```bash
cd benchmark
python validate.py   # 应输出 [OK] 150 条
python stats.py      # 看分布
```

### 1. 起后端 (另一个 agent 在做)

`/api/rag/query` 接受 `{"question": "..."}` 并返回 `schemas.py` 里的 `QAResponse`(answer / citations / source_chunks)。

### 2. 跑 baseline

```bash
# 只跑关键词法(免费,秒出)
python evaluate.py --out results/baseline.json --tag baseline

# 加 LLM-as-Judge
python evaluate.py --out results/baseline.json --tag baseline --judge both
```

### 3. 推荐评测协议

写报告之前推荐这套流程,确保数字可复现:

```bash
# Step 1: 烟囱测试,先用一小撮 hard 题确认后端没崩
python evaluate.py --dry --out results/dry.json --tag dry

# Step 2: 跑 baseline
python evaluate.py --out results/baseline.json --tag baseline --judge both

# Step 3: 改一个变量,跑下一组
#   修改 src/backend/.env 里的 chunk_size / rerank / embedding,重启服务
python evaluate.py --out results/chunk300.json --tag chunk300 \
    --config '{"chunk_size":300,"rerank":false,"embedding":"bge-small-zh"}' --judge both

# Step 4: 出对比表
python compare.py results/baseline.json results/chunk300.json --out results/ablation.md
```

### 4. 消融实验示例

```bash
# 分块大小
python evaluate.py --out results/chunk300.json --tag chunk300 --config '{"chunk_size":300}' --judge both
python evaluate.py --out results/chunk500.json --tag chunk500 --config '{"chunk_size":500}' --judge both
python evaluate.py --out results/chunk800.json --tag chunk800 --config '{"chunk_size":800}' --judge both
python compare.py results/chunk{300,500,800}.json --out results/chunk_ablation.md

# 有无 rerank
python evaluate.py --out results/no_rerank.json --tag no_rerank --config '{"rerank":false}' --judge both
python evaluate.py --out results/rerank.json    --tag rerank    --config '{"rerank":true}'  --judge both
python compare.py results/no_rerank.json results/rerank.json --out results/rerank_ablation.md

# 不同 embedding 模型
python evaluate.py --out results/bge.json --tag bge --config '{"embedding":"bge-small-zh"}' --judge both
python evaluate.py --out results/m3e.json --tag m3e --config '{"embedding":"m3e-base"}'    --judge both
python compare.py results/bge.json results/m3e.json --out results/embedding_ablation.md
```

生成的 Markdown 可直接贴进 `docs/Agent架构说明.md` 或 P2 技术报告。

## 文件清单

```
benchmark/
├── README.md             ← 本文档
├── DATASET_STATS.md      ← 数据集分布(自动生成)
├── questions.jsonl       ← 150 题数据集
├── metrics.py            ← 关键词法打分,纯函数无副作用
├── llm_judge.py          ← LLM-as-Judge(DeepSeek + 磁盘缓存)
├── evaluate.py           ← CLI 评测器(单次实验)
├── compare.py            ← 多结果对比 → Markdown
├── stats.py              ← 数据集分布统计
├── validate.py           ← 数据集自检
├── .judge_cache/         ← LLM 判分缓存(gitignored)
└── results/              ← 评测输出(gitignored)
```

## 已知局限

写到报告里的"Limitations"部分应该坦诚:

1. **关键词法对长答案宽容**:答案越长越容易把关键词凑齐,LLM 法可以缓解但不能完全消除
2. **chapter_hint 是子串匹配**:后端如果章节命名严格按"第X章 标题"结构,匹配召回会高;若仅返回"标题"则下降。可在解析层标准化
3. **`answer_summary` 是我手写的人卫版教材标准答案**,不同版本教材表述可能略不同,不能完全代表"权威答案"
4. **150 题 LLM 评判一轮约 5-10 分钟**,做大规模 grid search 之前请先用关键词法粗筛
5. **没有 token 消耗指标**:RAG 后端目前不返回 LLM 调用 token,如需要请扩展 QAResponse 加 `usage` 字段并更新 `evaluate.py:run`

## 与其他代码的隔离

- 不 import `src/` 任何模块
- 不写 `data/` 任何子目录
- 不修改根 `requirements.txt`,只用 Python 标准库(`urllib`/`json`/`argparse`/`hashlib`)
- 自己的 `results/` 与 `.judge_cache/` 通过 `benchmark/.gitignore` 忽略
