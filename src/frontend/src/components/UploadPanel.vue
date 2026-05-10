<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api/client'
import { useAppStore } from '../stores'

const store = useAppStore()
const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)
let pollTimer: number | null = null

async function uploadFiles(files: FileList | File[]) {
  if (!files || files.length === 0) return
  const fd = new FormData()
  for (const f of Array.from(files)) fd.append('files', f)
  store.busy = true
  store.statusText = `上传 ${files.length} 个文件…`
  try {
    await api.post('/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    await store.refreshTextbooks()
    startPolling()
  } finally {
    store.busy = false
    store.statusText = ''
  }
}

function onPick() {
  fileInput.value?.click()
}
function onChange(e: Event) {
  const f = (e.target as HTMLInputElement).files
  if (f) uploadFiles(f)
}
function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  if (e.dataTransfer?.files) uploadFiles(e.dataTransfer.files)
}

function startPolling() {
  if (pollTimer) return
  pollTimer = window.setInterval(async () => {
    await store.refreshTextbooks()
    const stillBusy = store.textbooks.some(
      (b) => b.status === 'parsing' || b.status === 'extracting'
    )
    if (!stillBusy && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }, 2000)
}

async function buildGraph(bookId: string) {
  store.busy = true
  store.statusText = `抽取知识点 (${bookId})…`
  try {
    await api.post(`/graph/${bookId}/extract`)
    await store.refreshTextbooks()
  } finally {
    store.busy = false
    store.statusText = ''
  }
}

async function selectBook(bookId: string) {
  await store.loadGraph(bookId)
}

function statusTag(s: string): string {
  return ({
    parsing: 'run',
    parsed: 'warn',
    extracting: 'run',
    ready: 'ok',
    failed: 'err',
  } as const)[s as 'parsing'] || ''
}

function statusLabel(s: string): string {
  return ({
    parsing: '解析中',
    parsed: '已解析',
    extracting: '抽取中',
    ready: '已就绪',
    failed: '失败',
  } as const)[s as 'parsing'] || s
}
</script>

<template>
  <div class="upload">
    <h3>📁 教材管理</h3>

    <div
      class="drop"
      :class="{ over: dragOver }"
      @click="onPick"
      @dragover.prevent="dragOver = true"
      @dragleave="dragOver = false"
      @drop="onDrop"
    >
      <div>拖拽 PDF / Markdown / TXT / DOCX</div>
      <div class="sub">或点击选择文件</div>
    </div>
    <input
      ref="fileInput"
      type="file"
      multiple
      accept=".pdf,.md,.txt,.docx,.xlsx"
      style="display: none"
      @change="onChange"
    />

    <div class="actions">
      <button class="secondary" @click="store.refreshTextbooks()">刷新</button>
      <button @click="store.loadGraph('master')" :disabled="!store.textbooks.length">
        查看整合图谱
      </button>
    </div>

    <div class="list">
      <div v-if="!store.textbooks.length" class="empty">暂无教材</div>
      <div v-for="b in store.textbooks" :key="b.textbook_id" class="item">
        <div class="row1">
          <span class="title" :title="b.filename">{{ b.title || b.filename }}</span>
          <span class="tag" :class="statusTag(b.status)">{{ statusLabel(b.status) }}</span>
        </div>
        <div class="meta">
          {{ b.total_pages }} 页 · {{ b.chapter_count }} 章 ·
          {{ (b.total_chars / 1000).toFixed(1) }}k 字
        </div>
        <div class="row-btns">
          <button class="mini" @click="selectBook(b.textbook_id)" :disabled="b.status === 'parsing'">
            查看
          </button>
          <button
            class="mini secondary"
            @click="buildGraph(b.textbook_id)"
            :disabled="b.status !== 'parsed'"
            v-if="b.status === 'parsed'"
          >
            抽取知识点
          </button>
        </div>
        <div v-if="b.error" class="err-msg">{{ b.error }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.upload { display: flex; flex-direction: column; gap: 10px; }
h3 { font-size: 13px; color: var(--text-dim); font-weight: 500; }
.drop {
  padding: 20px;
  border: 2px dashed var(--border);
  border-radius: 6px;
  text-align: center;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--text-dim);
}
.drop:hover, .drop.over { border-color: var(--accent); color: var(--text); }
.sub { font-size: 11px; margin-top: 4px; }
.actions { display: flex; gap: 6px; }
.actions button { flex: 1; }
.list { display: flex; flex-direction: column; gap: 6px; }
.empty { color: var(--text-dim); font-size: 12px; padding: 10px; text-align: center; }
.item {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 8px 10px;
  font-size: 12px;
}
.row1 { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
.title { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { color: var(--text-dim); font-size: 11px; margin-top: 3px; }
.row-btns { display: flex; gap: 4px; margin-top: 6px; }
.mini { font-size: 11px; padding: 3px 8px; }
.err-msg { color: var(--err); font-size: 11px; margin-top: 4px; }
</style>
