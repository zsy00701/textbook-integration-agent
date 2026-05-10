<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api/client'
import { useAppStore } from '../stores'
import type { QAResponse } from '../types'

const store = useAppStore()
const question = ref('')
const answer = ref<QAResponse | null>(null)
const expanded = ref<number | null>(null)

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

async function ask() {
  if (!question.value.trim()) return
  store.busy = true
  store.statusText = '检索 + 生成…'
  answer.value = null
  expanded.value = null
  try {
    const { data } = await api.post<QAResponse>('/rag/query', { question: question.value })
    answer.value = data
  } finally {
    store.busy = false
    store.statusText = ''
  }
}
</script>

<template>
  <div class="rp">
    <div class="head">
      <h3>RAG 精准问答</h3>
      <button class="secondary" @click="buildIndex" :disabled="store.busy">建立索引</button>
    </div>

    <div class="input-area">
      <textarea
        v-model="question"
        rows="3"
        placeholder="提问,例如:动作电位的产生机制是什么?"
        @keydown.ctrl.enter="ask"
        @keydown.meta.enter="ask"
      ></textarea>
      <button @click="ask" :disabled="store.busy || !question.trim()">提问 (Ctrl+Enter)</button>
    </div>

    <div v-if="answer" class="result">
      <div class="answer card">
        <div class="label">回答</div>
        <div class="text">{{ answer.answer }}</div>
      </div>

      <div class="cites" v-if="answer.citations.length">
        <div class="label">引用来源 ({{ answer.citations.length }})</div>
        <div
          v-for="(c, i) in answer.citations"
          :key="i"
          class="cite card"
          :class="{ active: expanded === i }"
          @click="expanded = expanded === i ? null : i"
        >
          <div class="cite-head">
            <span>《{{ c.textbook }}》· {{ c.chapter }} · 第 {{ c.page }} 页</span>
            <span class="score">{{ (c.relevance_score * 100).toFixed(0) }}%</span>
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
.input-area { display: flex; flex-direction: column; gap: 6px; }
textarea { resize: none; font-family: inherit; }
.result { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.label { color: var(--text-dim); font-size: 11px; margin-bottom: 4px; }
.answer .text { white-space: pre-wrap; line-height: 1.65; }
.cites { display: flex; flex-direction: column; gap: 4px; }
.cite { padding: 6px 10px; font-size: 12px; cursor: pointer; transition: border-color 0.15s; }
.cite:hover, .cite.active { border-color: var(--accent); }
.cite-head { display: flex; justify-content: space-between; align-items: center; }
.score { color: var(--accent); font-size: 11px; }
.chunk { margin-top: 6px; padding: 6px; background: var(--panel-2); border-radius: 3px; color: var(--text-dim); white-space: pre-wrap; font-size: 11px; }
</style>
