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
  <div class="rp">
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
        {{ q }}
      </button>
    </div>

    <div class="result-scroll">
      <div v-if="answer" class="result">
        <!-- 用户问题(浅灰卡片) -->
        <div class="user-q">
          <div class="user-q-label">你的提问</div>
          <div class="user-q-text">{{ question }}</div>
        </div>

        <!-- AI 回答:墨绿实底 + 白字(视觉锚点) -->
        <div class="answer">
          <div class="answer-head">
            <span class="answer-label">AI 回答</span>
            <span class="latency" v-if="answer.latency_ms">
              {{ (answer.latency_ms.total / 1000).toFixed(1) }}s
              · 检索 {{ (answer.latency_ms.retrieval / 1000).toFixed(2) }}s
              · 生成 {{ (answer.latency_ms.generation / 1000).toFixed(2) }}s
            </span>
          </div>
          <div class="answer-text">{{ answer.answer }}</div>
        </div>

        <div class="cites" v-if="answer.citations.length">
          <div class="cites-label">引用来源 · {{ answer.citations.length }} 条</div>
          <div
            v-for="(c, i) in answer.citations"
            :key="i"
            class="cite"
            :class="{ active: expanded === i }"
            @click="expanded = expanded === i ? null : i"
          >
            <div class="cite-head">
              <span class="cite-meta">《{{ c.textbook }}》· {{ c.chapter }} · 第 {{ c.page }} 页</span>
              <span class="score">{{ Math.min(100, c.relevance_score * 100).toFixed(0) }}%</span>
            </div>
            <div v-if="expanded === i && answer.source_chunks[i]" class="chunk">
              {{ answer.source_chunks[i] }}
            </div>
          </div>
        </div>
      </div>

      <!-- 空态 -->
      <div v-else class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
            stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
          </svg>
        </div>
        <div class="empty-title">提问后将获得带引用的回答</div>
        <div class="empty-sub">点击上方常见问题快速开始</div>
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
h3 { font-size: var(--fs-md); font-weight: 600; color: var(--text); }
.mini { font-size: var(--fs-xs); padding: 4px 10px; }

/* —— Demo chips:浅灰底+灰字+1px 边,hover 变深绿描边 —— */
.chips-label {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  background: var(--panel);
  color: var(--text-dim);
  font-size: var(--fs-xs);
  padding: 5px 10px;
  border-radius: var(--r-chip);
  border: 1px solid var(--border);
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
  max-width: 200px;
  font-weight: 400;
}
.chip:hover {
  background: var(--panel);
  color: var(--accent);
  border-color: var(--accent);
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
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}
.user-q-text {
  color: var(--text);
  font-size: var(--fs-base);
  line-height: 1.6;
  white-space: pre-wrap;
}

/* AI 回答:墨绿实底 + 白字(视觉锚点) */
.answer {
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--r-md);
  padding: var(--space-4);
  box-shadow: var(--shadow-1);
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
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.85);
}
.latency {
  font-size: var(--fs-xs);
  color: rgba(255, 255, 255, 0.7);
  font-variant-numeric: tabular-nums;
}
.answer-text {
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: var(--fs-base);
  color: var(--text-inverse);
}

/* —— 引用列表 —— */
.cites { display: flex; flex-direction: column; gap: 6px; }
.cites-label {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-top: var(--space-1);
}

/* 引用卡片:未展开白底浅灰边;展开时左边 3px 深绿条 */
.cite {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: var(--space-2) var(--space-3);
  font-size: var(--fs-sm);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease,
    box-shadow 0.15s ease;
  position: relative;
}
.cite:hover { border-color: var(--border-strong); }
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
  color: var(--text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-xs);
  flex: 1;
  min-width: 0;
}
.score {
  color: var(--accent);
  font-size: var(--fs-xs);
  font-weight: 600;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  background: var(--accent-soft);
  padding: 1px 8px;
  border-radius: var(--r-pill);
}
.chunk {
  margin-top: var(--space-2);
  padding: var(--space-2);
  background: var(--bg-soft);
  border-radius: var(--r-sm);
  color: var(--text);
  white-space: pre-wrap;
  font-size: var(--fs-xs);
  line-height: 1.65;
  border: 1px solid var(--border-subtle);
}

/* —— 空态 —— */
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
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--bg-soft);
  color: var(--text-muted);
  margin-bottom: var(--space-2);
}
.empty-title { font-size: var(--fs-base); color: var(--text-dim); font-weight: 500; }
.empty-sub { font-size: var(--fs-xs); color: var(--text-muted); }

/* —— 输入区(底部固定) —— */
.input-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
textarea { resize: none; font-family: inherit; line-height: 1.55; }
.ask-btn { align-self: flex-end; min-width: 88px; padding: 7px 18px; }
</style>
