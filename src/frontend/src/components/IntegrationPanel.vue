<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api/client'
import { useAppStore } from '../stores'
import type { Decision } from '../types'

const store = useAppStore()
const filter = ref<'all' | 'merge' | 'remove' | 'keep'>('all')
const exporting = ref<'md' | 'pdf' | null>(null)

const ACTION_ICON = { merge: '⟿', keep: '·', remove: '×' } as const

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

async function downloadExport(kind: 'md' | 'pdf') {
  if (exporting.value) return
  exporting.value = kind
  try {
    const url = `/api/export/${kind === 'md' ? 'markdown' : 'pdf'}`
    const resp = await fetch(url)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const blob = await resp.blob()
    // 从 Content-Disposition 提取文件名(优先 filename*=UTF-8'')
    const cd = resp.headers.get('Content-Disposition') || ''
    let filename = `知识整合精华.${kind === 'md' ? 'md' : 'pdf'}`
    const m = cd.match(/filename\*=UTF-8''([^;\n]+)/i)
    if (m) {
      try { filename = decodeURIComponent(m[1]) } catch {}
    }
    const a = document.createElement('a')
    const objUrl = URL.createObjectURL(blob)
    a.href = objUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(objUrl), 0)
  } catch (e: any) {
    alert(`导出失败:${e?.message || e}`)
  } finally {
    exporting.value = null
  }
}

function filtered(): Decision[] {
  if (filter.value === 'all') return store.decisions
  return store.decisions.filter((d) => d.action === filter.value)
}

function actionLabel(a: string): string {
  return ({ merge: '合并', keep: '保留', remove: '删除' } as const)[a as 'merge'] || a
}
function actionClass(a: string): string {
  return ({ merge: 'tag', keep: 'tag ok', remove: 'tag err' } as const)[a as 'merge'] || 'tag'
}
</script>

<template>
  <div class="ip fade-in">
    <div class="head">
      <h3>跨教材整合</h3>
      <button @click="runIntegration" :disabled="store.busy">
        {{ store.integrationStats ? '重新整合' : '一键整合' }}
      </button>
    </div>

    <!-- 整合后:展示统计卡 + 导出 -->
    <div v-if="store.integrationStats" class="stats">
      <!-- 焦点压缩比:大字号 + 紧贴说明小字 -->
      <div class="hero">
        <div class="hero-num"
          :class="{ ok: store.integrationStats.ratio <= 0.30, warn: store.integrationStats.ratio > 0.30 }">
          {{ (store.integrationStats.ratio * 100).toFixed(1) }}<span class="hero-unit">%</span>
        </div>
        <div class="hero-label">
          <span class="hero-title">压缩比</span>
          <span class="hero-sub">7 本教材 · 浓缩为高质量定义集</span>
        </div>
      </div>

      <div class="stat-row">
        <div class="stat-cell">
          <div class="k">原始字数</div>
          <div class="v">{{ (store.integrationStats.orig_chars / 1000).toFixed(1) }}<span class="unit">k</span></div>
        </div>
        <div class="stat-arrow">→</div>
        <div class="stat-cell">
          <div class="k">整合后</div>
          <div class="v accent">{{ (store.integrationStats.final_chars / 1000).toFixed(1) }}<span class="unit">k</span></div>
        </div>
      </div>

      <div class="stat-row small">
        <span class="small-item">
          节点 <b>{{ store.integrationStats.orig_node_count }}</b>
          <span class="micro-arrow">→</span>
          <b>{{ store.integrationStats.final_node_count }}</b>
        </span>
        <span class="dot-sep"></span>
        <span class="small-item">合并 <b>{{ store.integrationStats.decisions_count.merge || 0 }}</b></span>
        <span class="small-item">保留 <b>{{ store.integrationStats.decisions_count.keep || 0 }}</b></span>
        <span class="small-item">删除 <b>{{ store.integrationStats.decisions_count.remove || 0 }}</b></span>
      </div>

      <!-- 导出精华版:加强卖点,变成图文卡 -->
      <div class="export-block">
        <div class="export-head">
          <div class="export-title">导出精华版</div>
          <div class="export-sub">将整合知识图谱浓缩为可查阅的文档</div>
        </div>
        <div class="export-btns">
          <button
            class="secondary export-btn"
            :disabled="exporting !== null"
            @click="downloadExport('md')"
          >
            <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor"
              stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M3 2h7l3 3v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" />
              <path d="M10 2v3h3" />
            </svg>
            <span>{{ exporting === 'md' ? '生成中…' : 'Markdown' }}</span>
          </button>
          <button
            class="secondary export-btn"
            :disabled="exporting !== null"
            @click="downloadExport('pdf')"
          >
            <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor"
              stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M3 2h7l3 3v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" />
              <path d="M10 2v3h3" />
              <path d="M5 9h6M5 12h4" />
            </svg>
            <span>{{ exporting === 'pdf' ? '生成中…' : 'PDF' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 整合前:大字空态,引导一键整合 -->
    <div v-else class="big-empty">
      <div class="big-empty-icon">
        <svg viewBox="0 0 32 32" width="28" height="28" fill="none" stroke="currentColor"
          stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="9" cy="9" r="3" />
          <circle cx="23" cy="9" r="3" />
          <circle cx="16" cy="22" r="3" />
          <path d="M11 11l4 8M21 11l-4 8" />
        </svg>
      </div>
      <div class="big-empty-title">准备整合 {{ store.textbooks.length || 7 }} 本教材</div>
      <div class="big-empty-sub">点击「一键整合」启动跨教材去重与对齐</div>
    </div>

    <div class="filters" v-if="store.decisions.length">
      <button :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</button>
      <button :class="{ active: filter === 'merge' }" @click="filter = 'merge'">合并</button>
      <button :class="{ active: filter === 'keep' }" @click="filter = 'keep'">保留</button>
      <button :class="{ active: filter === 'remove' }" @click="filter = 'remove'">删除</button>
    </div>

    <div class="dlist">
      <div v-if="!store.decisions.length && store.integrationStats" class="empty">无重复知识点决策</div>
      <div v-for="d in filtered()" :key="d.decision_id" class="d">
        <div class="d-head">
          <span :class="actionClass(d.action)">
            <span class="d-icon">{{ ACTION_ICON[d.action as 'merge'] || '·' }}</span>
            {{ actionLabel(d.action) }}
          </span>
          <span class="conf">{{ (d.confidence * 100).toFixed(0) }}<span class="conf-pct">%</span></span>
        </div>
        <div class="d-body">{{ d.reason }}</div>
        <div class="d-nodes">影响 {{ d.affected_nodes.length }} 节点</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ip {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  height: 100%;
  overflow: hidden;
}
.head { display: flex; justify-content: space-between; align-items: center; }
h3 { font-size: var(--fs-md); font-weight: 600; color: var(--text); letter-spacing: -0.01em; }

/* —— 统计卡 —— */
.stats {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* 焦点压缩比:大字号 26px + 紧贴说明小字 */
.hero {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}
.hero-num {
  font-size: var(--fs-display);
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.025em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  min-width: 80px;
}
.hero-num.ok { color: var(--ok); }
.hero-num.warn { color: var(--warn); }
.hero-unit {
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text-muted);
  margin-left: 2px;
  letter-spacing: 0;
}
.hero-label { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.hero-title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text);
}
.hero-sub {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  line-height: 1.5;
}

.stat-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.stat-cell { flex: 1; min-width: 0; }
.stat-arrow {
  color: var(--text-muted);
  font-size: var(--fs-md);
  font-weight: 500;
  flex-shrink: 0;
}
.k {
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 4px;
}
.v {
  font-size: var(--fs-xl);
  font-weight: 600;
  color: var(--text);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
  line-height: 1.2;
}
.v.accent { color: var(--accent); }
.v .unit {
  font-size: var(--fs-sm);
  color: var(--text-muted);
  font-weight: 500;
  margin-left: 2px;
}

.stat-row.small {
  color: var(--text-dim);
  font-size: var(--fs-xs);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-subtle);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  justify-content: flex-start;
}
.small-item { font-variant-numeric: tabular-nums; }
.small-item b { color: var(--text); font-weight: 600; }
.micro-arrow {
  color: var(--text-muted);
  margin: 0 3px;
  font-size: 10px;
}
.dot-sep {
  width: 3px; height: 3px; border-radius: 50%;
  background: var(--text-muted);
  display: inline-block;
  opacity: 0.5;
}

/* —— 导出精华版:卖点强化为图文卡 —— */
.export-block {
  margin-top: var(--space-1);
  padding: var(--space-3);
  background: var(--accent-soft);
  border: 1px solid transparent;
  border-radius: var(--r-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.export-head { display: flex; flex-direction: column; gap: 2px; }
.export-title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--accent);
  letter-spacing: -0.005em;
}
.export-sub {
  font-size: var(--fs-xs);
  color: var(--text-dim);
  line-height: 1.5;
}
.export-btns { display: flex; gap: 6px; }
.export-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 10px;
  font-size: var(--fs-sm);
  font-weight: 500;
  background: var(--panel);
  border-color: var(--accent-soft-2);
}
.export-btn:hover {
  background: var(--panel);
  border-color: var(--accent);
  color: var(--accent);
}
.export-btn:hover svg { color: var(--accent); }

/* —— 大字空态(整合前) —— */
.big-empty {
  padding: var(--space-6) var(--space-4);
  background: var(--panel);
  border: 1px dashed var(--border);
  border-radius: var(--r-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--space-2);
}
.big-empty-icon {
  width: 56px; height: 56px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--space-2);
}
.big-empty-title {
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.01em;
}
.big-empty-sub {
  font-size: var(--fs-sm);
  color: var(--text-muted);
  line-height: 1.6;
}

/* —— 过滤分段控件 —— */
.filters {
  display: flex;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  overflow: hidden;
  background: var(--panel);
  align-self: flex-start;
}
.filters button {
  background: var(--panel);
  color: var(--text-dim);
  font-size: var(--fs-xs);
  padding: 5px 12px;
  border: none;
  border-right: 1px solid var(--border);
  border-radius: 0;
  font-weight: 500;
}
.filters button:last-child { border-right: none; }
.filters button:hover { background: var(--surface-hover); color: var(--text); }
.filters button.active {
  background: var(--accent);
  color: var(--text-inverse);
}

/* —— 决策列表 —— */
.dlist { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.empty {
  padding: var(--space-5) var(--space-4);
  text-align: center;
  color: var(--text-muted);
  font-size: var(--fs-sm);
  background: var(--panel);
  border: 1px dashed var(--border);
  border-radius: var(--r-md);
}

/* 决策卡:hover 微浮 + 浅阴影 */
.d {
  padding: var(--space-2) var(--space-3);
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  font-size: var(--fs-sm);
  transition:
    border-color var(--t-fast) var(--ease-out),
    transform var(--t-fast) var(--ease-out),
    box-shadow var(--t-fast) var(--ease-out);
}
.d:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
  box-shadow: var(--shadow-hover);
}
.d-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  gap: var(--space-2);
}
.d-icon {
  font-weight: 600;
  margin-right: 2px;
}
.conf {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}
.conf-pct {
  font-size: 10px;
  margin-left: 1px;
  opacity: 0.7;
}
.d-body {
  color: var(--text);
  margin: 4px 0;
  line-height: 1.6;
}
.d-nodes {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  margin-top: 4px;
}
</style>
