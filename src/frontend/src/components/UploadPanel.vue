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
    <div class="section-head">
      <h3>教材管理</h3>
      <span class="count" v-if="store.textbooks.length">{{ store.textbooks.length }}</span>
    </div>

    <div
      class="drop"
      :class="{ over: dragOver }"
      @click="onPick"
      @dragover.prevent="dragOver = true"
      @dragleave="dragOver = false"
      @drop="onDrop"
    >
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
        stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      <div class="drop-title">拖拽文件到此处</div>
      <div class="sub">支持 PDF / Markdown / TXT / DOCX</div>
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
      <button @click="store.loadGraph('master')"
        :class="{ pulse: store.selectedBookId !== 'master' && store.sysStats?.totals.master_nodes }"
        :disabled="!store.textbooks.length">
        整合图谱
      </button>
    </div>

    <div class="list-head">教材列表</div>
    <div class="list">
      <div v-if="!store.textbooks.length" class="empty">暂无教材</div>
      <div
        v-for="b in store.textbooks"
        :key="b.textbook_id"
        class="item"
        :class="{ active: store.selectedBookId === b.textbook_id }"
        @click="selectBook(b.textbook_id)"
      >
        <div class="row1">
          <span class="title" :title="b.filename">{{ b.title || b.filename }}</span>
          <span class="tag" :class="statusTag(b.status)">{{ statusLabel(b.status) }}</span>
        </div>
        <div class="meta">
          {{ b.total_pages }} 页 · {{ b.chapter_count }} 章 ·
          {{ (b.total_chars / 1000).toFixed(1) }}k 字
        </div>
        <div class="row-btns" v-if="b.status === 'parsed'" @click.stop>
          <button
            class="mini secondary"
            @click="buildGraph(b.textbook_id)"
            :disabled="b.status !== 'parsed'"
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
.upload { display: flex; flex-direction: column; gap: var(--space-3); }

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-1);
}
h3 {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.count {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  background: var(--panel);
  border: 1px solid var(--border);
  padding: 1px 8px;
  border-radius: var(--r-pill);
  font-variant-numeric: tabular-nums;
}

/* —— 上传拖拽区:浅色虚线框 —— */
.drop {
  padding: var(--space-4) var(--space-3);
  border: 1px dashed var(--border-strong);
  border-radius: var(--r-md);
  background: var(--panel);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease,
    color 0.15s ease;
  color: var(--text-dim);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.drop svg { color: var(--text-muted); transition: color 0.15s ease; }
.drop:hover, .drop.over {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
}
.drop:hover svg, .drop.over svg { color: var(--accent); }
.drop-title { font-size: var(--fs-sm); font-weight: 500; }
.sub { font-size: var(--fs-xs); color: var(--text-muted); }

/* —— 操作区 —— */
.actions { display: flex; gap: var(--space-2); }
.actions button { flex: 1; padding: 7px 12px; font-size: var(--fs-sm); }

/* 待整合时的脉动:换成墨绿色低强度光晕 */
.actions .pulse {
  animation: pulse 2.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(31, 78, 61, 0.35); }
  50%      { box-shadow: 0 0 0 6px rgba(31, 78, 61, 0); }
}

/* —— 列表 —— */
.list-head {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-top: var(--space-2);
  padding: 0 var(--space-1);
}
.list { display: flex; flex-direction: column; gap: 4px; }
.empty {
  color: var(--text-muted);
  font-size: var(--fs-sm);
  padding: var(--space-4);
  text-align: center;
  background: var(--panel);
  border: 1px dashed var(--border);
  border-radius: var(--r-md);
}

/* 教材卡片:Notion 风,极简边框 + hover 微变化 */
.item {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: var(--space-2) var(--space-3);
  font-size: var(--fs-sm);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
  position: relative;
}
.item:hover { border-color: var(--border-strong); background: var(--panel); }
.item.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.item.active::before {
  content: '';
  position: absolute;
  left: -1px; top: 8px; bottom: 8px;
  width: 3px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}

.row1 { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
.title {
  font-weight: 500;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
  font-size: var(--fs-sm);
}
.meta {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  margin-top: 3px;
  font-variant-numeric: tabular-nums;
}
.row-btns { display: flex; gap: 4px; margin-top: 6px; }
.mini { font-size: var(--fs-xs); padding: 4px 10px; }
.err-msg {
  color: var(--err);
  font-size: var(--fs-xs);
  margin-top: 4px;
  background: var(--err-soft);
  padding: 4px 8px;
  border-radius: 4px;
}
</style>
