<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api/client'
import { useAppStore } from '../stores'
import type { Decision } from '../types'

const store = useAppStore()
const filter = ref<'all' | 'merge' | 'remove' | 'keep'>('all')

const ACTION_ICON = { merge: '🔗', keep: '📍', remove: '🗑' } as const

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
      <h3>🔗 跨教材整合</h3>
      <button @click="runIntegration" :disabled="store.busy">
        {{ store.integrationStats ? '▶ 重新整合' : '▶ 一键整合' }}
      </button>
    </div>

    <div v-if="store.integrationStats" class="stats card">
      <div class="stat-row">
        <div><div class="k">原始字数</div><div class="v">{{ (store.integrationStats.orig_chars / 1000).toFixed(1) }}k</div></div>
        <div><div class="k">整合后</div><div class="v">{{ (store.integrationStats.final_chars / 1000).toFixed(1) }}k</div></div>
        <div>
          <div class="k">压缩比</div>
          <div class="v" :style="{ color: store.integrationStats.ratio <= 0.30 ? 'var(--ok)' : 'var(--warn)' }">
            {{ (store.integrationStats.ratio * 100).toFixed(1) }}%
          </div>
        </div>
      </div>
      <div class="stat-row small">
        <div>节点 {{ store.integrationStats.orig_node_count }} → {{ store.integrationStats.final_node_count }}</div>
        <div>🔗 {{ store.integrationStats.decisions_count.merge || 0 }}</div>
        <div>📍 {{ store.integrationStats.decisions_count.keep || 0 }}</div>
        <div>🗑 {{ store.integrationStats.decisions_count.remove || 0 }}</div>
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
      <div v-for="d in filtered()" :key="d.decision_id" class="d card">
        <div class="d-head">
          <span :class="actionClass(d.action)">
            {{ ACTION_ICON[d.action as 'merge'] }} {{ actionLabel(d.action) }}
          </span>
          <span class="conf">置信 {{ (d.confidence * 100).toFixed(0) }}%</span>
        </div>
        <div class="d-body">{{ d.reason }}</div>
        <div class="d-nodes">影响:{{ d.affected_nodes.length }} 节点</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ip { padding: 12px; display: flex; flex-direction: column; gap: 10px; height: 100%; overflow: hidden; }
.head { display: flex; justify-content: space-between; align-items: center; }
h3 { font-size: 13px; }
.stats { padding: 10px; }
.stat-row { display: flex; justify-content: space-around; gap: 8px; }
.stat-row.small { color: var(--text-dim); font-size: 11px; margin-top: 6px; padding-top: 6px; border-top: 1px dashed var(--border); }
.ratio-note { color: var(--text-dim); font-size: 11px; margin-top: 8px; line-height: 1.55; }
.k { font-size: 11px; color: var(--text-dim); }
.v { font-size: 18px; font-weight: 600; margin-top: 2px; }
.filters { display: flex; gap: 4px; }
.filters button { background: var(--panel-2); color: var(--text-dim); font-size: 11px; padding: 4px 10px; }
.filters button.active { background: var(--accent); color: white; }
.dlist { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.empty { padding: 20px; text-align: center; color: var(--text-dim); font-size: 12px; }
.d { padding: 8px 10px; font-size: 12px; }
.d-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.conf { color: var(--text-dim); font-size: 11px; }
.d-body { color: var(--text); margin: 4px 0; }
.d-nodes { color: var(--text-dim); font-size: 11px; }
</style>
