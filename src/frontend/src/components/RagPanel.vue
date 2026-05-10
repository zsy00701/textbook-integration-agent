<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { api } from '../api/client'
import { useAppStore } from '../stores'
import type { QAResponse } from '../types'

const store = useAppStore()
const question = ref('')
const answer = ref<QAResponse | null>(null)
const expanded = ref<number | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)

const DEMO_QUESTIONS = [
  '动作电位的产生机制是什么?',
  '急性炎症与慢性炎症的区别',
  '细菌内毒素和外毒素如何区分?',
  '心力衰竭的代偿机制有哪些?',
  '什么是细胞凋亡?它与坏死有何不同?',
]

async function buildIndex() {
  store.busy = true
  store.statusText = '建立向量索引…'
  try {
    await api.post('/rag/index')
    await store.loadRagStatus()
  } finally {
    store.busy = false
    store.statusText = ''
  }
}

async function ask(q?: string) {
  const text = (q ?? question.value).trim()
  if (!text) return
  question.value = text
  store.busy = true
  store.statusText = '检索 + 生成…'
  answer.value = null
  expanded.value = null
  try {
    const { data } = await api.post<QAResponse>('/rag/query', { question: text })
    answer.value = data
    await store.loadStats()
  } finally {
    store.busy = false
    store.statusText = ''
  }
}

function setQuestion(q: string) {
  question.value = q
  nextTick(() => textareaEl.value?.focus())
}

// 来自图谱节点 → "用 RAG 深入了解"
watch(
  () => store.pendingRagQuestion,
  (q) => {
    if (q) {
      question.value = q
      store.pendingRagQuestion = ''
      ask(q)
    }
  }
)
</script>

<template>
  <div class="rp fade-in">
    <div class="head">
      <h3>RAG 精准问答</h3>
      <button class="secondary mini" @click="buildIndex" :disabled="store.busy">建立索引</button>
    </div>

    <div class="chips-label">常见问题</div>
    <div class="chips">
      <button
        v-for="q in DEMO_QUESTIONS"
        :key="q"
        class="chip"
        :title="q"
        @click="setQuestion(q)"
      >
        <span>{{ q }}</span>
        <span class="chip-arrow" aria-hidden="true">↗</span>
      </button>
    </div>

    <div class="result-scroll">
      <!-- 加载骨架屏:RAG 提问中,显示 3 行问题-回答-引用占位 -->
      <div v-if="store.busy && !answer && question" class="skeleton fade-in">
        <div class="user-q">
          <div class="user-q-label">你的提问</div>
          <div class="user-q-text">{{ question }}</div>
        </div>
        <div class="sk-answer">
          <div class="sk-answer-head">
            <span class="sk-label">AI 回答</span>
            <span class="sk-status">检索 + 生成中…</span>
          </div>
          <div class="skeleton-line" style="width: 95%"></div>
          <div class="skeleton-line" style="width: 88%; margin-top: 8px"></div>
          <div class="skeleton-line" style="width: 76%; margin-top: 8px"></div>
        </div>
        <div class="sk-cites">
          <div class="skeleton-line" style="width: 60%; height: 10px"></div>
          <div class="skeleton-line" style="width: 100%; height: 28px; margin-top: 6px"></div>
          <div class="skeleton-line" style="width: 100%; height: 28px; margin-top: 6px"></div>
        </div>
      </div>

      <div v-else-if="answer" class="result fade-in">
        <!-- 用户问题(浅灰卡片) -->
        <div class="user-q">
          <div class="user-q-label">你的提问</div>
          <div class="user-q-text">{{ question }}</div>
        </div>

        <!-- 答案元信息行:AI 用了 X 条引用 · 耗时 Xs -->
        <div class="meta-line" v-if="answer.latency_ms">
          <span class="meta-item">
            <span class="meta-num">{{ answer.citations.length }}</span>
            <span class="meta-unit">条引用</span>
          </span>
          <span class="meta-sep">·</span>
          <span class="meta-item">
            <span class="meta-unit">耗时</span>
            <span class="meta-num">{{ (answer.latency_ms.total / 1000).toFixed(1) }}</span>
            <span class="meta-unit">s</span>
          </span>
          <span class="meta-sep">·</span>
          <span class="meta-item dim">
            检索 {{ (answer.latency_ms.retrieval / 1000).toFixed(2) }}s
            / 生成 {{ (answer.latency_ms.generation / 1000).toFixed(2) }}s
          </span>
        </div>

        <!-- AI 回答:墨绿实底 + 白字(视觉锚点) -->
        <div class="answer">
          <div class="answer-head">
            <span class="answer-label">AI 回答</span>
          </div>
          <div class="answer-text">{{ answer.answer }}</div>
        </div>

        <div class="cites" v-if="answer.citations.length">
          <div class="cites-label">
            <span>引用来源</span>
            <span class="cites-count">{{ answer.citations.length }}</span>
          </div>
          <div
            v-for="(c, i) in answer.citations"
            :key="i"
            class="cite"
            :class="{ active: expanded === i }"
            @click="expanded = expanded === i ? null : i"
          >
            <div class="cite-head">
              <span class="cite-meta">
                <span class="cite-book">《{{ c.textbook }}》</span>
                <span class="cite-sep">·</span>
                <span class="cite-chap">{{ c.chapter }}</span>
                <span class="cite-sep">·</span>
                <span class="cite-page">第 {{ c.page }} 页</span>
              </span>
              <span class="score">{{ Math.min(100, c.relevance_score * 100).toFixed(0) }}<span class="score-pct">%</span></span>
            </div>
            <div v-if="expanded === i && answer.source_chunks[i]" class="chunk">
              {{ answer.source_chunks[i] }}
            </div>
          </div>
        </div>
      </div>

      <!-- 空态:墨绿描边图标 + 友好引导 -->
      <div v-else class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor"
            stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
          </svg>
        </div>
        <div class="empty-title">提问后将获得带引用的回答</div>
        <div class="empty-sub">点击上方常见问题快速开始,或自由提问</div>
      </div>
    </div>

    <!-- 输入区(底部固定) -->
    <div class="input-area">
      <textarea
        ref="textareaEl"
        v-model="question"
        rows="3"
        placeholder="输入问题,Ctrl / ⌘ + Enter 发送"
        @keydown.ctrl.enter="ask()"
        @keydown.meta.enter="ask()"
      ></textarea>
      <button class="ask-btn" @click="ask()" :disabled="store.busy || !question.trim()">提问</button>
    </div>
  </div>
</template>

<style scoped>
.rp {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  height: 100%;
  overflow: hidden;
}

.head { display: flex; justify-content: space-between; align-items: center; }
h3 { font-size: var(--fs-md); font-weight: 600; color: var(--text); letter-spacing: -0.01em; }
.mini { font-size: var(--fs-xs); padding: 4px 10px; }

/* —— Demo chips:浅灰底+灰字+1px 边,hover 变深绿;尾随 ↗ 图标暗示 click to fill —— */
.chips-label {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--panel);
  color: var(--text-dim);
  font-size: var(--fs-xs);
  padding: 5px 10px;
  border-radius: var(--r-chip);
  border: 1px solid var(--border);
  max-width: 220px;
  font-weight: 400;
  transition:
    color var(--t-fast) var(--ease-out),
    border-color var(--t-fast) var(--ease-out),
    background-color var(--t-fast) var(--ease-out);
}
.chip > span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.chip-arrow {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
  opacity: 0.6;
  transition:
    transform var(--t-fast) var(--ease-out),
    opacity var(--t-fast) var(--ease-out),
    color var(--t-fast) var(--ease-out);
}
.chip:hover {
  background: var(--panel);
  color: var(--accent);
  border-color: var(--accent);
}
.chip:hover .chip-arrow {
  color: var(--accent);
  opacity: 1;
  transform: translate(1px, -1px);
}

/* —— 滚动结果区 —— */
.result-scroll {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  margin: 0 calc(-1 * var(--space-1));
  padding: 0 var(--space-1);
}
.result { display: flex; flex-direction: column; gap: var(--space-3); }

/* 用户问题:浅灰卡片 */
.user-q {
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: var(--space-3);
}
.user-q-label {
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 6px;
}
.user-q-text {
  color: var(--text);
  font-size: var(--fs-base);
  line-height: 1.6;
  white-space: pre-wrap;
}

/* —— 元信息行:答案上方,引用数 + 耗时 —— */
.meta-line {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 5px;
  padding: 0 var(--space-1);
  font-size: var(--fs-xs);
  color: var(--text-dim);
  margin-top: -4px;
}
.meta-item {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  font-variant-numeric: tabular-nums;
}
.meta-item.dim { color: var(--text-muted); }
.meta-num {
  color: var(--accent);
  font-weight: 600;
  font-size: var(--fs-sm);
}
.meta-unit {
  color: var(--text-muted);
  font-size: 10px;
}
.meta-sep {
  color: var(--text-muted);
  opacity: 0.5;
}

/* AI 回答:墨绿实底 + 白字(视觉锚点) */
.answer {
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--r-md);
  padding: var(--space-4);
  box-shadow: 0 4px 14px rgba(31, 78, 61, 0.12);
}
.answer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}
.answer-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(255, 255, 255, 0.85);
}
.answer-text {
  white-space: pre-wrap;
  line-height: 1.75;
  font-size: var(--fs-base);
  color: var(--text-inverse);
  letter-spacing: 0.005em;
}

/* —— 骨架屏 —— */
.skeleton { display: flex; flex-direction: column; gap: var(--space-3); }
.sk-answer {
  background: var(--accent);
  border-radius: var(--r-md);
  padding: var(--space-4);
}
.sk-answer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}
.sk-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(255, 255, 255, 0.85);
}
.sk-status {
  font-size: var(--fs-xs);
  color: rgba(255, 255, 255, 0.7);
}
.sk-answer .skeleton-line {
  background: linear-gradient(90deg,
    rgba(255,255,255,0.10) 0%,
    rgba(255,255,255,0.20) 50%,
    rgba(255,255,255,0.10) 100%);
  background-size: 200% 100%;
}
.sk-cites { display: flex; flex-direction: column; gap: 6px; padding: var(--space-1); }

/* —— 引用列表 —— */
.cites { display: flex; flex-direction: column; gap: 6px; }
.cites-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-top: var(--space-1);
}
.cites-count {
  color: var(--accent);
  background: var(--accent-soft);
  padding: 1px 6px;
  border-radius: var(--r-pill);
  font-variant-numeric: tabular-nums;
  font-size: 10px;
  letter-spacing: 0;
}

/* 引用卡片:hover 微浮 */
.cite {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: var(--space-2) var(--space-3);
  font-size: var(--fs-sm);
  cursor: pointer;
  transition:
    border-color var(--t-fast) var(--ease-out),
    background-color var(--t-fast) var(--ease-out),
    box-shadow var(--t-fast) var(--ease-out),
    transform var(--t-fast) var(--ease-out);
  position: relative;
}
.cite:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
  box-shadow: var(--shadow-hover);
}
.cite.active {
  border-color: var(--accent);
  background: var(--panel);
  box-shadow: var(--shadow-1);
}
.cite.active::before {
  content: '';
  position: absolute;
  left: -1px; top: 8px; bottom: 8px;
  width: 3px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}

.cite-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}
.cite-meta {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  color: var(--text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-xs);
  flex: 1;
  min-width: 0;
}
.cite-book { color: var(--text); font-weight: 500; }
.cite-sep { color: var(--text-muted); opacity: 0.6; }
.cite-page { font-variant-numeric: tabular-nums; }
.score {
  color: var(--accent);
  font-size: var(--fs-xs);
  font-weight: 600;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  background: var(--accent-soft);
  padding: 1px 8px;
  border-radius: var(--r-pill);
  letter-spacing: -0.01em;
}
.score-pct {
  font-size: 9px;
  margin-left: 1px;
  opacity: 0.75;
}

/* chunk:展开后,使用 mono 字体 + 11.5px 阅读舒适 */
.chunk {
  margin-top: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-soft);
  border-radius: var(--r-sm);
  color: var(--text);
  white-space: pre-wrap;
  font-size: 11.5px;
  line-height: 1.7;
  border: 1px solid var(--border-subtle);
  font-family: -apple-system, "PingFang SC", ui-monospace, "JetBrains Mono", Menlo, Consolas, monospace;
  letter-spacing: 0.01em;
}

/* —— 空态:墨绿描边图标 + 友好引导 —— */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: var(--space-6) var(--space-4);
  color: var(--text-muted);
}
.empty-icon {
  width: 56px; height: 56px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  margin-bottom: var(--space-2);
  border: 1px solid transparent;
}
.empty-title {
  font-size: var(--fs-md);
  color: var(--text);
  font-weight: 600;
  letter-spacing: -0.01em;
}
.empty-sub {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  line-height: 1.6;
}

/* —— 输入区(底部固定) —— */
.input-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
textarea {
  resize: none;
  font-family: inherit;
  line-height: 1.55;
}
textarea:focus {
  border-color: var(--accent);
  box-shadow:
    0 0 0 3px rgba(31, 78, 61, 0.10),
    inset 0 1px 0 rgba(0, 0, 0, 0.01);
}
.ask-btn { align-self: flex-end; min-width: 88px; padding: 7px 18px; }
</style>
