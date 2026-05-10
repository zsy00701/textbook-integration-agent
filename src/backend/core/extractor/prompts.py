"""LLM Prompt 模板。

设计原则:
- 严格 JSON schema 描述 + few-shot 示例
- 一次只处理一个章节,避免上下文过长
- 节点 ≤ 25 个/章,优先核心概念,避免噪声
- 关系类型固定 4 种,枚举值约束
"""

KG_SYSTEM = """你是医学/科学教材的知识图谱抽取专家。\
对给定章节,抽取核心知识点(概念/定理/方法/现象)和它们之间的关系。\
严格按 JSON schema 输出,不要写任何说明文字。\
"""

KG_EXTRACT_PROMPT = """请从下方章节文本中抽取知识图谱,输出 JSON。

【输出 JSON schema】
{{
  "nodes": [
    {{
      "id": "n01",                    // 章内唯一短 id
      "name": "知识点名称",            // 简洁名词,5-15 字
      "definition": "定义/简介(60-150 字)",
      "category": "核心概念" | "定理" | "方法" | "现象" | "结构" | "过程",
      "page": 35                      // 该知识点在章中首次出现的近似页码
    }}
  ],
  "edges": [
    {{
      "source": "n01",
      "target": "n02",
      "relation_type": "prerequisite" | "parallel" | "contains" | "applies_to",
      "description": "一句话说明"
    }}
  ]
}}

【关系类型说明】
- prerequisite:学习目标节点前必须先掌握源节点(学习依赖)
- parallel:同一上位概念下的并列概念
- contains:源节点是上位概念,目标节点是下位概念
- applies_to:源节点是被应用的概念,目标节点是应用场景

【硬性约束】
1. 只抽取本章实际出现的核心知识点(15-25 个为佳,避免堆砌)
2. id 用 "n01"~"n99" 短编号,不要用中文/长串
3. relation_type 必须是上述四个枚举之一
4. 不要抽取章节标题、图表编号、参考文献等非知识点
5. 输出必须是合法 JSON,不带 markdown 围栏

【few-shot 示例(简化)】
输入章节标题"细胞的基本功能",文本片段:"动作电位是细胞受刺激后...静息电位是细胞静息状态下..."
正确输出:
{{
  "nodes": [
    {{"id":"n01","name":"静息电位","definition":"细胞处于静息状态时,膜两侧的电位差,内负外正","category":"核心概念","page":30}},
    {{"id":"n02","name":"动作电位","definition":"细胞受刺激后,膜电位发生的一次快速可逆的倒转","category":"核心概念","page":35}}
  ],
  "edges": [
    {{"source":"n02","target":"n01","relation_type":"prerequisite","description":"动作电位的理解依赖静息电位概念"}}
  ]
}}

【现在请处理】
教材:《{book_title}》
章节:{chapter_title}(第 {page_start}-{page_end} 页)

章节正文(节选,如过长已截断):
\"\"\"
{chapter_content}
\"\"\"

直接输出 JSON,不要解释。"""


# ============ 跨教材整合(LLM 二次裁决) ============
ALIGN_VERIFY_SYSTEM = """你判断两个知识点是否描述同一个概念。只回答严格 JSON。"""

ALIGN_VERIFY_PROMPT = """判断以下两个知识点是否是同一个概念(可能用词不同但本质相同):

A. 名称:{name_a}
   定义:{def_a}
   来源:{book_a}

B. 名称:{name_b}
   定义:{def_b}
   来源:{book_b}

输出 JSON:
{{
  "same": true | false,
  "confidence": 0.0~1.0,
  "reason": "一句话说明"
}}"""


# ============ 整合决策(对一组重复节点决定保留哪个) ============
DECISION_SYSTEM = """你是教材整合决策助手。给定一组判定为重复的知识点,决定保留/合并/删除策略,并给出理由。"""

DECISION_PROMPT = """以下是被判定为同一概念的知识点(来自不同教材):

{cluster_repr}

请决定整合策略,输出 JSON:
{{
  "action": "merge" | "keep" | "remove",
  "reason": "为什么这样做(20-60 字),引用具体教材",
  "result_definition": "整合后保留的定义(若 merge,则取最完整的版本;若 keep,则保留指定版本的定义)",
  "result_name": "整合后的标准名称",
  "kept_node_id": "保留的节点 id(从输入候选中选)",
  "confidence": 0.0~1.0
}}

策略指引:
- 多本教材都讲解同一概念 → merge,保留最系统/最权威的版本
- 只有一本提到 → keep
- 残缺/重复且信息更少 → remove
"""


# ============ RAG 问答 ============
RAG_SYSTEM = """你是基于教材内容的知识助手。严格遵循:
1. 只基于提供的【上下文】回答,不使用自身知识
2. 每个事实都需要引用,引用格式 [教材名,章节,页码]
3. 如果上下文中找不到答案,回复"当前知识库中未找到相关信息",不要编造
4. 回答要精炼、结构化,中文回答"""

RAG_USER_PROMPT = """【上下文】(共 {n} 条片段)
{context}

【用户问题】
{question}

请给出回答。"""


# ============ 多轮对话(整合反馈) ============
CHAT_SYSTEM = """你是教材整合助手,帮助用户理解和修改整合决策。

【你能做的事】
1. 解释为什么某条决策是这样做的(基于 reason 字段)
2. 根据用户反馈修改决策:
   - 用户要求"保留X" → 把对应 remove 决策改为 keep
   - 用户要求"分开X和Y" → 把它们的 merge 决策改为 keep,并删除合并产物
   - 用户要求"合并X和Y" → 新增 merge 决策

【输出格式】
必须输出 JSON:
{{
  "reply": "给用户的自然语言回复",
  "patches": [           // 决策变更列表,可空
    {{
      "decision_id": "merge_001",         // 现有决策 id 或 "new"
      "op": "modify" | "create" | "delete",
      "new_action": "merge" | "keep" | "remove",
      "new_reason": "修改后的理由",
      "affected_nodes": ["..."]            // op=create 时必填
    }}
  ]
}}"""

CHAT_USER_PROMPT = """【当前整合决策摘要】(展示最相关的若干条)
{decisions_summary}

【对话历史】
{history}

【用户最新消息】
{user_message}

按系统提示输出 JSON。"""
