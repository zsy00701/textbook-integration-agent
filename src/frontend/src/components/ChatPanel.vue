<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { api } from '../api/client'
import { useAppStore } from '../stores'

const store = useAppStore()
const message = ref('')
const scrollEl = ref<HTMLDivElement | null>(null)

const EXAMPLES = [
  '为什么把"炎症"几个版本合并了?详细解释',
  '请保留所有关于"免疫应答"的节点',
  '把"抗原"和"免疫原"分开,它们不是同一个概念',
  '炎症反应在《病理学》和《传染病学》里有什么差异?',
]

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
      <div class="hint-title">💡 可以这样反馈(点击直接填入):</div>
      <button
        v-for="ex in EXAMPLES"
        :key="ex"
        class="ex-chip"
        @click="message = ex"
      >{{ ex }}</button>
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
.hint-title { margin-bottom: 6px; }
.ex-chip {
  display: block; width: 100%; text-align: left;
  background: var(--panel-2); color: var(--text-dim);
  border: 1px solid var(--border);
  font-size: 12px; padding: 5px 9px; margin-bottom: 4px;
  border-radius: 4px;
  white-space: normal;
}
.ex-chip:hover { border-color: var(--accent); color: var(--text); }
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
