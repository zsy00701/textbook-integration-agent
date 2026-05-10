<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { api } from '../api/client'
import { useAppStore } from '../stores'

const store = useAppStore()
const message = ref('')
const scrollEl = ref<HTMLDivElement | null>(null)

async function send() {
  const text = message.value.trim()
  if (!text) return
  message.value = ''
  store.chatHistory.push({ role: 'user', content: text, timestamp: Date.now() / 1000 })
  await scrollDown()
  store.busy = true
  store.statusText = '处理反馈…'
  try {
    const { data } = await api.post('/chat', {
      session_id: store.sessionId || undefined,
      message: text,
    })
    store.sessionId = data.session_id
    store.chatHistory = data.history
    if (data.decisions_changed?.length) {
      // 决策变了 → 重新加载主图谱与决策
      await store.loadDecisions()
      if (store.selectedBookId === 'master' || !store.selectedBookId) {
        await store.loadGraph('master')
      }
    }
    await scrollDown()
  } finally {
    store.busy = false
    store.statusText = ''
  }
}

async function scrollDown() {
  await nextTick()
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}

function clear() {
  store.sessionId = ''
  store.chatHistory = []
}
</script>

<template>
  <div class="cp">
    <div class="head">
      <h3>对话修正整合</h3>
      <button class="mini secondary" @click="clear">新会话</button>
    </div>

    <div class="hint" v-if="!store.chatHistory.length">
      可以这样问:<br />
      · 为什么把《生理学》的"炎症"和《病理学》的"炎症反应"合并了?<br />
      · 我觉得"免疫应答"不应该被删除,请保留<br />
      · 把"抗原"和"免疫原"分开,它们不是同一个概念
    </div>

    <div ref="scrollEl" class="msgs">
      <div v-for="(m, i) in store.chatHistory" :key="i" :class="['msg', m.role]">
        <div class="bubble">{{ m.content }}</div>
      </div>
    </div>

    <div class="input-area">
      <textarea
        v-model="message"
        rows="2"
        placeholder="输入反馈…"
        @keydown.enter.exact.prevent="send"
        @keydown.shift.enter.exact="message += '\n'"
      ></textarea>
      <button @click="send" :disabled="store.busy || !message.trim()">发送</button>
    </div>
  </div>
</template>

<style scoped>
.cp { padding: 12px; display: flex; flex-direction: column; gap: 10px; height: 100%; overflow: hidden; }
.head { display: flex; justify-content: space-between; align-items: center; }
h3 { font-size: 13px; }
.mini { font-size: 11px; padding: 3px 8px; }
.hint { color: var(--text-dim); font-size: 12px; padding: 10px; background: var(--panel); border-radius: 4px; line-height: 1.7; }
.msgs { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; padding: 4px; }
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble { padding: 8px 12px; border-radius: 8px; max-width: 80%; font-size: 13px; white-space: pre-wrap; line-height: 1.55; }
.msg.user .bubble { background: var(--accent); color: white; }
.msg.assistant .bubble { background: var(--panel); border: 1px solid var(--border); }
.input-area { display: flex; gap: 6px; align-items: flex-end; }
textarea { flex: 1; resize: none; font-family: inherit; }
</style>
