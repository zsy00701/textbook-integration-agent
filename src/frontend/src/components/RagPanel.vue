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
      <h3>🔍 RAG 精准问答</h3>
      <button class="secondary mini" @click="buildIndex" :disabled="store.busy">建立索引</button>
    </div>

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

    <div class="input-area">
      <textarea
        ref="textareaEl"
        v-model="question"
        rows="3"
        placeholder="提问,例如:动作电位的产生机制是什么?(Ctrl/⌘+Enter 发送)"
        @keydown.ctrl.enter="ask()"
        @keydown.meta.enter="ask()"
      ></textarea>
      <button @click="ask()" :disabled="store.busy || !question.trim()">提问</button>
    </div>

    <div v-if="answer" class="result">
      <div class="answer card">
        <div class="meta-bar">
          <span class="label">回答</span>
          <span class="latency" v-if="answer.latency_ms">
            ⏱ {{ (answer.latency_ms.total / 1000).toFixed(1) }}s
            (检索 {{ (answer.latency_ms.retrieval / 1000).toFixed(2) }}s ·
            生成 {{ (answer.latency_ms.generation / 1000).toFixed(2) }}s)
          </span>
        </div>
        <div class="text">{{ answer.answer }}</div>
      </div>

      <div class="cites" v-if="answer.citations.length">
        <div class="label">📎 引用来源 ({{ answer.citations.length }})·点击展开原文</div>
        <div
          v-for="(c, i) in answer.citations"
          :key="i"
          class="cite card"
          :class="{ active: expanded === i }"
          @click="expanded = expanded === i ? null : i"
        >
          <div class="cite-head">
            <span>《{{ c.textbook }}》· {{ c.chapter }} · 第 {{ c.page }} 页</span>
            <span class="score">{{ Math.min(100, c.relevance_score * 100).toFixed(0) }}%</span>
          </div>
          <div v-if="expanded === i && answer.source_chunks[i]" class="chunk">
            {{ answer.source_chunks[i] }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rp { padding: 12px; display: flex; flex-direction: column; gap: 10px; height: 100%; overflow: hidden; }
.head { display: flex; justify-content: space-between; align-items: center; }
h3 { font-size: 13px; }
.mini { font-size: 11px; padding: 3px 10px; }
.chips { display: flex; flex-wrap: wrap; gap: 4px; }
.chip {
  background: var(--panel-2); color: var(--text-dim);
  font-size: 11px; padding: 4px 9px; border-radius: 12px;
  border: 1px solid var(--border);
  text-overflow: ellipsis; overflow: hidden; white-space: nowrap; max-width: 180px;
}
.chip:hover { background: var(--panel); color: var(--text); border-color: var(--accent); }
.input-area { display: flex; flex-direction: column; gap: 6px; }
textarea { resize: none; font-family: inherit; }
.result { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.label { color: var(--text-dim); font-size: 11px; margin-bottom: 4px; }
.meta-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.latency { color: var(--accent); font-size: 11px; }
.answer .text { white-space: pre-wrap; line-height: 1.65; }
.cites { display: flex; flex-direction: column; gap: 4px; }
.cite { padding: 6px 10px; font-size: 12px; cursor: pointer; transition: border-color 0.15s; }
.cite:hover, .cite.active { border-color: var(--accent); }
.cite-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.cite-head > span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.score { color: var(--accent); font-size: 11px; flex-shrink: 0; }
.chunk { margin-top: 6px; padding: 6px; background: var(--panel-2); border-radius: 3px; color: var(--text-dim); white-space: pre-wrap; font-size: 11px; }
</style>
