<script setup lang="ts">
import { ref, computed } from 'vue'
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

// —— 全局操作 ——

// 待抽取的教材数(状态为 parsed)
const parsedCount = computed(() =>
  store.textbooks.filter((b) => b.status === 'parsed').length
)

async function extractAll() {
  if (!parsedCount.value) return
  store.busy = true
  store.statusText = `批量抽取 ${parsedCount.value} 本…`
  try {
    await api.post('/graph/extract_all')
    await store.refreshTextbooks()
    startPolling()
  } finally {
    store.busy = false
    store.statusText = ''
  }
}

async function runIntegration() {
  store.busy = true
  store.statusText = '跨教材整合中…'
  try {
    await api.post('/integration/run')
    await store.loadDecisions()
    await store.loadGraph('master')
  } finally {
    store.busy = false
    store.statusText = ''
  }
}

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
    <!-- 顶部 标题区,稍大字号、给呼吸空间 -->
    <div class="header-block">
      <div class="title-line">
        <span class="title-main">教材管理</span>
        <span class="count" v-if="store.textbooks.length">{{ store.textbooks.length }}</span>
      </div>
      <div class="title-sub" v-if="store.textbooks.length">
        {{ store.textbooks.filter(b => b.status === 'ready').length }} 本就绪
        · {{ parsedCount }} 待抽取
      </div>
    </div>

    <!-- 上传拖拽区 -->
    <div
      class="drop"
      :class="{ over: dragOver }"
      @click="onPick"
      @dragover.prevent="dragOver = true"
      @dragleave="dragOver = false"
      @drop="onDrop"
    >
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
        stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      <div class="drop-title">拖拽文件到此处</div>
      <div class="sub">PDF / Markdown / TXT / DOCX</div>
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
        :class="['status-' + b.status, { active: store.selectedBookId === b.textbook_id }]"
        @click="selectBook(b.textbook_id)"
      >
        <!-- 左侧细色条,根据状态变色;ready 墨绿、parsed 暖棕、parsing/extracting 进度色 -->
        <span class="status-bar" aria-hidden="true"></span>

        <div class="row1">
          <span class="title" :title="b.filename">{{ b.title || b.filename }}</span>
          <span class="status-text">{{ statusLabel(b.status) }}</span>
        </div>
        <div class="meta">
          {{ b.total_pages }}<span class="u">页</span>
          ·
          {{ b.chapter_count }}<span class="u">章</span>
          ·
          {{ (b.total_chars / 1000).toFixed(1) }}k<span class="u">字</span>
        </div>

        <!-- 抽取按钮:hover 时浮现于卡片右下角 -->
        <div class="row-btns" v-if="b.status === 'parsed'" @click.stop>
          <button class="mini secondary" @click="buildGraph(b.textbook_id)">
            抽取知识点
          </button>
        </div>

        <div v-if="b.error" class="err-msg">{{ b.error }}</div>
      </div>
    </div>

    <!-- 底部 pinned 全局操作:hackathon 一键流水线 -->
    <div class="quick-ops" v-if="store.textbooks.length">
      <div class="quick-label">全局操作</div>
      <button
        class="quick-btn secondary"
        :disabled="!parsedCount || store.busy"
        @click="extractAll"
        :title="parsedCount ? `对 ${parsedCount} 本待抽取教材批量抽取知识点` : '没有待抽取的教材'"
      >
        <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor"
          stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M2 4h12M2 8h12M2 12h8" />
        </svg>
        <span>批量抽取知识点</span>
        <span class="quick-num" v-if="parsedCount">{{ parsedCount }}</span>
      </button>
      <button
        class="quick-btn secondary"
        :disabled="store.busy"
        @click="runIntegration"
      >
        <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor"
          stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M3 3v3a3 3 0 0 0 3 3h4a3 3 0 0 1 3 3v1" />
          <path d="M11 11l2 2-2 2" />
        </svg>
        <span>{{ store.integrationStats ? '重新整合' : '一键整合' }}</span>
      </button>
      <button
        class="quick-btn secondary"
        :disabled="store.busy"
        @click="buildIndex"
      >
        <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor"
          stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="2" y="3" width="12" height="3" rx="1" />
          <rect x="2" y="7.5" width="12" height="3" rx="1" />
          <rect x="2" y="12" width="12" height="2" rx="1" />
        </svg>
        <span>建立 RAG 索引</span>
        <span class="quick-num accent" v-if="store.ragStatus?.indexed">已建</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.upload {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-height: 100%;
}

/* —— 顶部 Notion 风标题区 —— */
.header-block {
  padding: 2px var(--space-1) 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.title-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.title-main {
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.01em;
}
.title-sub {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.count {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  background: var(--panel);
  border: 1px solid var(--border);
  padding: 1px 8px;
  border-radius: var(--r-pill);
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

/* —— 上传拖拽区 —— */
.drop {
  padding: var(--space-4) var(--space-3);
  border: 1px dashed var(--border-strong);
  border-radius: var(--r-md);
  background: var(--panel);
  text-align: center;
  cursor: pointer;
  transition:
    border-color var(--t-fast) var(--ease-out),
    background-color var(--t-fast) var(--ease-out),
    color var(--t-fast) var(--ease-out);
  color: var(--text-dim);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.drop svg { color: var(--text-muted); transition: color var(--t-fast) var(--ease-out); }
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

/* 待整合时的脉动:墨绿光晕 */
.actions .pulse {
  animation: pulse 2.4s var(--ease-soft) infinite;
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

/* —— 教材卡片 ——
   状态:左侧 3px 色条 + 右上角文字标签;
   hover:微浮 1px + 浅阴影 + 边框略深;
   ready:左侧墨绿条暗示「完成感」 */
.item {
  position: relative;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: var(--space-2) var(--space-3) var(--space-2) 14px;
  font-size: var(--fs-sm);
  cursor: pointer;
  transition:
    border-color var(--t-fast) var(--ease-out),
    background-color var(--t-fast) var(--ease-out),
    transform var(--t-fast) var(--ease-out),
    box-shadow var(--t-fast) var(--ease-out);
  overflow: hidden;
}
.item:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
  box-shadow: var(--shadow-hover);
}
.item.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
/* 状态色条:左侧 3px,根据状态变色 */
.status-bar {
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: var(--border-strong);
  transition: background-color var(--t-fast) var(--ease-out);
}
.item.status-ready .status-bar      { background: var(--accent); }
.item.status-parsed .status-bar     { background: var(--warn); }
.item.status-parsing .status-bar,
.item.status-extracting .status-bar { background: var(--accent); opacity: 0.6; }
.item.status-failed .status-bar     { background: var(--err); }
.item.active .status-bar            { background: var(--accent); }

.row1 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.title {
  font-weight: 500;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
  font-size: var(--fs-sm);
  letter-spacing: -0.005em;
}
/* 右上状态文字:小字、颜色随状态色 */
.status-text {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}
.item.status-ready .status-text     { color: var(--ok); }
.item.status-parsed .status-text    { color: var(--warn); }
.item.status-parsing .status-text,
.item.status-extracting .status-text { color: var(--accent); }
.item.status-failed .status-text    { color: var(--err); }

.meta {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  margin-top: 3px;
  font-variant-numeric: tabular-nums;
}
.meta .u {
  font-size: 10px;
  color: var(--text-muted);
  margin-left: 1px;
}

/* 抽取按钮:平时不显示,卡片 hover 时浮现于右下 */
.row-btns {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
  opacity: 0;
  transform: translateY(-2px);
  transition:
    opacity var(--t-fast) var(--ease-out),
    transform var(--t-fast) var(--ease-out);
}
.item:hover .row-btns,
.item.status-parsed .row-btns {
  opacity: 1;
  transform: translateY(0);
}
.mini { font-size: var(--fs-xs); padding: 4px 10px; }

.err-msg {
  color: var(--err);
  font-size: var(--fs-xs);
  margin-top: 4px;
  background: var(--err-soft);
  padding: 4px 8px;
  border-radius: 4px;
}

/* —— 底部 pinned 全局操作 —— */
.quick-ops {
  margin-top: auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.quick-label {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0 var(--space-1);
  margin-bottom: 4px;
}
.quick-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  justify-content: flex-start;
  font-size: var(--fs-sm);
  padding: 7px 10px;
  font-weight: 500;
  color: var(--text);
}
.quick-btn svg { color: var(--text-dim); flex-shrink: 0; }
.quick-btn:hover svg { color: var(--accent); }
.quick-btn span:nth-of-type(1) { flex: 1; text-align: left; }
.quick-num {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--bg-soft);
  padding: 1px 6px;
  border-radius: var(--r-pill);
  font-variant-numeric: tabular-nums;
}
.quick-num.accent {
  color: var(--accent);
  background: var(--accent-soft);
}
.quick-btn:disabled { opacity: 0.5; }
</style>
