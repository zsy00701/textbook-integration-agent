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
      <div class="hint-title">可以这样反馈,点击填入</div>
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
        placeholder="输入反馈,Enter 发送 / Shift+Enter 换行"
        @keydown.enter.exact.prevent="send"
        @keydown.shift.enter.exact="message += '\n'"
      ></textarea>
      <button @click="send" :disabled="store.busy || !message.trim()">发送</button>
    </div>
  </div>
</template>

<style scoped>
.cp {
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

/* —— 提示区(空对话时) —— */
.hint {
  color: var(--text-dim);
  font-size: var(--fs-sm);
  padding: var(--space-3);
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  line-height: 1.6;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hint-title {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 2px;
}
.ex-chip {
  display: block;
  width: 100%;
  text-align: left;
  background: var(--bg-soft);
  color: var(--text-dim);
  border: 1px solid var(--border);
  font-size: var(--fs-sm);
  padding: 7px 10px;
  border-radius: var(--r-sm);
  white-space: normal;
  font-weight: 400;
  line-height: 1.5;
  transition: all 0.15s ease;
}
.ex-chip:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

/* —— 消息列表 —— */
.msgs {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: 0 var(--space-1);
}
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }

.bubble {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--r-md);
  max-width: 86%;
  font-size: var(--fs-sm);
  white-space: pre-wrap;
  line-height: 1.65;
}
/* 用户气泡:浅灰 */
.msg.user .bubble {
  background: var(--bg-soft);
  color: var(--text);
  border: 1px solid var(--border);
  border-bottom-right-radius: 4px;
}
/* AI 气泡:墨绿底白字,与 RAG 一致 */
.msg.assistant .bubble {
  background: var(--accent);
  color: var(--text-inverse);
  border-bottom-left-radius: 4px;
}

/* —— 输入区 —— */
.input-area {
  display: flex;
  gap: var(--space-2);
  align-items: flex-end;
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}
textarea { flex: 1; resize: none; font-family: inherit; line-height: 1.55; }
.input-area button { padding: 7px 16px; min-width: 72px; }
</style>
