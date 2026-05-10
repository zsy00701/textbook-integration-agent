<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { useAppStore } from './stores'
import UploadPanel from './components/UploadPanel.vue'
import GraphView from './components/GraphView.vue'
import IntegrationPanel from './components/IntegrationPanel.vue'
import RagPanel from './components/RagPanel.vue'
import ChatPanel from './components/ChatPanel.vue'

const store = useAppStore()
let statsTimer: number | null = null

const tokenLine = computed(() => {
  const t = store.sysStats?.token_stats
  if (!t || !t.requests) return ''
  return `Σ ${(t.total_tokens / 1000).toFixed(1)}k tok · ${t.requests} 调用 · 均 ${t.avg_latency_s}s`
})

const totalsLine = computed(() => {
  const t = store.sysStats?.totals
  if (!t) return ''
  return `${t.master_nodes || t.total_nodes} 节点 · ${t.total_chunks} 块`
})

onMounted(async () => {
  await store.refreshTextbooks()
  await store.loadRagStatus()
  await store.loadStats()
  await store.tryLoadMaster()
  statsTimer = window.setInterval(() => store.loadStats(), 30_000)
})

onUnmounted(() => {
  if (statsTimer) clearInterval(statsTimer)
})
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="brand">📚 学科知识整合智能体 <span class="ver">v0.2</span></div>
      <div class="status">
        <span class="tag" v-if="totalsLine">📊 {{ totalsLine }}</span>
        <span class="tag" v-if="tokenLine">⚡ {{ tokenLine }}</span>
        <span class="tag run" v-if="store.busy">{{ store.statusText || '处理中…' }}</span>
      </div>
    </header>

    <div class="main">
      <aside class="left">
        <UploadPanel />
      </aside>

      <section class="center">
        <GraphView />
      </section>

      <aside class="right">
        <nav class="tabs">
          <button :class="{ active: store.activeTab === 'integration' }" @click="store.activeTab = 'integration'">
            🔗 整合
          </button>
          <button :class="{ active: store.activeTab === 'rag' }" @click="store.activeTab = 'rag'">
            🔍 RAG 问答
          </button>
          <button :class="{ active: store.activeTab === 'chat' }" @click="store.activeTab = 'chat'">
            💬 对话修正
          </button>
        </nav>
        <div class="tab-body">
          <IntegrationPanel v-show="store.activeTab === 'integration'" />
          <RagPanel v-show="store.activeTab === 'rag'" />
          <ChatPanel v-show="store.activeTab === 'chat'" />
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.layout { display: flex; flex-direction: column; height: 100%; }
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 18px;
  background: linear-gradient(180deg, var(--panel) 0%, var(--bg) 100%);
  border-bottom: 1px solid var(--border);
}
.brand { font-weight: 600; font-size: 15px; }
.ver { font-size: 11px; color: var(--text-dim); margin-left: 4px; font-weight: 400; }
.status { display: flex; gap: 6px; align-items: center; }
.main { display: flex; flex: 1; overflow: hidden; }
.left { width: 290px; padding: 12px; overflow-y: auto; border-right: 1px solid var(--border); }
.center { flex: 1; min-width: 0; display: flex; }
.right { width: 380px; display: flex; flex-direction: column; border-left: 1px solid var(--border); }
.tabs { display: flex; border-bottom: 1px solid var(--border); }
.tabs button {
  flex: 1; background: transparent; color: var(--text-dim);
  border-radius: 0; padding: 10px; border-bottom: 2px solid transparent;
  font-size: 13px;
}
.tabs button.active { color: var(--accent); border-bottom-color: var(--accent); background: rgba(79,158,255,0.05); }
.tab-body { flex: 1; overflow: hidden; display: flex; }
.tab-body > * { flex: 1; }
</style>
