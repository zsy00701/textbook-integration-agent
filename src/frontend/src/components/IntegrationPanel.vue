<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api/client'
import { useAppStore } from '../stores'
import type { Decision } from '../types'

const store = useAppStore()
const filter = ref<'all' | 'merge' | 'remove' | 'keep'>('all')

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
  <div class="ip">
    <div class="head">
      <h3>跨教材整合</h3>
      <button @click="runIntegration" :disabled="store.busy">
        {{ store.integrationStats ? '重新整合' : '一键整合' }}
      </button>
    </div>

    <div v-if="store.integrationStats" class="stats">
      <div class="stat-row">
        <div class="stat-cell">
          <div class="k">原始字数</div>
          <div class="v">{{ (store.integrationStats.orig_chars / 1000).toFixed(1) }}<span class="unit">k</span></div>
        </div>
        <div class="stat-cell">
          <div class="k">整合后</div>
          <div class="v">{{ (store.integrationStats.final_chars / 1000).toFixed(1) }}<span class="unit">k</span></div>
        </div>
        <div class="stat-cell">
          <div class="k">压缩比</div>
          <div class="v ratio" :class="{ ok: store.integrationStats.ratio <= 0.30, warn: store.integrationStats.ratio > 0.30 }">
            {{ (store.integrationStats.ratio * 100).toFixed(1) }}<span class="unit">%</span>
          </div>
        </div>
      </div>
      <div class="stat-row small">
        <span class="small-item">
          节点 <b>{{ store.integrationStats.orig_node_count }}</b> → <b>{{ store.integrationStats.final_node_count }}</b>
        </span>
        <span class="dot-sep"></span>
        <span class="small-item">合并 {{ store.integrationStats.decisions_count.merge || 0 }}</span>
        <span class="small-item">保留 {{ store.integrationStats.decisions_count.keep || 0 }}</span>
        <span class="small-item">删除 {{ store.integrationStats.decisions_count.remove || 0 }}</span>
      </div>
      <div class="ratio-note">
        整合后字数 = 知识点定义合计;原始字数 = 教材正文总字数。压缩 = 把每本几百页教材浓缩为高质量定义集。
      </div>
    </div>

    <div class="filters">
      <button :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</button>
      <button :class="{ active: filter === 'merge' }" @click="filter = 'merge'">合并</button>
      <button :class="{ active: filter === 'keep' }" @click="filter = 'keep'">保留</button>
      <button :class="{ active: filter === 'remove' }" @click="filter = 'remove'">删除</button>
    </div>

    <div class="dlist">
      <div v-if="!store.decisions.length" class="empty">尚未整合,或无重复知识点</div>
      <div v-for="d in filtered()" :key="d.decision_id" class="d">
        <div class="d-head">
          <span :class="actionClass(d.action)">
            {{ actionLabel(d.action) }}
          </span>
          <span class="conf">置信 {{ (d.confidence * 100).toFixed(0) }}%</span>
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
h3 { font-size: var(--fs-md); font-weight: 600; color: var(--text); }

/* —— 统计卡 —— */
.stats {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: var(--space-3);
}
.stat-row { display: flex; justify-content: space-between; gap: var(--space-2); }
.stat-cell { flex: 1; min-width: 0; }
.k {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 500;
  margin-bottom: 2px;
}
.v {
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
  line-height: 1.2;
}
.v .unit {
  font-size: var(--fs-sm);
  color: var(--text-muted);
  font-weight: 500;
  margin-left: 1px;
}
.ratio.ok { color: var(--ok); }
.ratio.warn { color: var(--warn); }

.stat-row.small {
  color: var(--text-dim);
  font-size: var(--fs-xs);
  margin-top: var(--space-2);
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
.dot-sep {
  width: 3px; height: 3px; border-radius: 50%;
  background: var(--text-muted);
  display: inline-block;
}
.ratio-note {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  margin-top: var(--space-2);
  line-height: 1.6;
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-subtle);
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
.d {
  padding: var(--space-2) var(--space-3);
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  font-size: var(--fs-sm);
  transition: border-color 0.15s ease;
}
.d:hover { border-color: var(--border-strong); }
.d-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.conf {
  color: var(--text-muted);
  font-size: var(--fs-xs);
  font-variant-numeric: tabular-nums;
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
