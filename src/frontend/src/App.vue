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
  await Promise.all([
    store.refreshTextbooks(),
    store.loadRagStatus(),
    store.loadStats(),
    store.loadDecisions(),
  ])
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
      <div class="brand">
        <span class="logo" aria-hidden="true">
          <!-- 简洁图谱图标 -->
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
            stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="6" cy="6" r="2.2" />
            <circle cx="18" cy="6" r="2.2" />
            <circle cx="12" cy="18" r="2.2" />
            <path d="M7.6 7.4l3 8.4M16.4 7.4l-3 8.4M8 6h8" />
          </svg>
        </span>
        <span class="brand-name">学科知识整合智能体</span>
        <span class="ver">v0.2</span>
      </div>
      <div class="status">
        <span class="chip-stat" v-if="totalsLine">{{ totalsLine }}</span>
        <span class="chip-stat" v-if="tokenLine">{{ tokenLine }}</span>
        <span class="chip-run" v-if="store.busy">
          <span class="dot"></span>{{ store.statusText || '处理中' }}
        </span>
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
            整合
          </button>
          <button :class="{ active: store.activeTab === 'rag' }" @click="store.activeTab = 'rag'">
            RAG 问答
          </button>
          <button :class="{ active: store.activeTab === 'chat' }" @click="store.activeTab = 'chat'">
            对话修正
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
.layout { display: flex; flex-direction: column; height: 100%; background: var(--bg); }

/* —— 顶栏:纯米白 + 1px 底边,完全不用渐变 —— */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-5);
  height: 52px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text);
}
.logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--r-sm);
  background: var(--accent);
  color: var(--text-inverse);
}
.brand-name { font-weight: 600; font-size: var(--fs-md); letter-spacing: -0.01em; }
.ver {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-weight: 400;
  padding: 1px 6px;
  border: 1px solid var(--border);
  border-radius: var(--r-pill);
  margin-left: var(--space-1);
}

.status { display: flex; gap: var(--space-2); align-items: center; }

/* 顶栏统计 chip:灰底灰字小圆角 */
.chip-stat {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  font-size: var(--fs-xs);
  color: var(--text-dim);
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--r-chip);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.chip-run {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  font-size: var(--fs-xs);
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: var(--r-chip);
  white-space: nowrap;
}
.chip-run .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent);
  animation: blink 1.2s ease-in-out infinite;
}
@keyframes blink {
  0%, 100% { opacity: 0.4; }
  50%      { opacity: 1; }
}

/* —— 三栏 —— */
.main { display: flex; flex: 1; overflow: hidden; min-height: 0; }
.left {
  width: 280px;
  padding: var(--space-4);
  overflow-y: auto;
  border-right: 1px solid var(--border);
  background: var(--bg-soft);
  flex-shrink: 0;
}
.center { flex: 1; min-width: 0; display: flex; background: var(--panel); }
.right {
  width: 400px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border);
  background: var(--bg);
  flex-shrink: 0;
}

/* —— Tabs:Linear 风,极细底线 —— */
.tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  padding: 0 var(--space-3);
  flex-shrink: 0;
}
.tabs button {
  flex: 1;
  background: transparent;
  color: var(--text-dim);
  border: none;
  border-radius: 0;
  padding: 12px 8px;
  border-bottom: 2px solid transparent;
  font-size: var(--fs-base);
  font-weight: 500;
  margin-bottom: -1px;
}
.tabs button:hover { color: var(--text); background: transparent; }
.tabs button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  background: transparent;
}
.tab-body { flex: 1; overflow: hidden; display: flex; min-height: 0; }
.tab-body > * { flex: 1; }
</style>
