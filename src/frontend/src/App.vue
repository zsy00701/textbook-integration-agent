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

// 顶栏数据切片:让数字醒目、单位次级
const totals = computed(() => store.sysStats?.totals)
const tokenStats = computed(() => store.sysStats?.token_stats)

// Tabs 计数徽章(整合决策数 / 引用次数 / 对话轮数)
const integrationCount = computed(() => store.decisions.length)
const ragQueriesCount = computed(() => store.sysStats?.token_stats?.requests || 0)
const chatRounds = computed(() => Math.floor(store.chatHistory.length / 2))

// 系统是否在线(后端返回过 stats 即视为在线)
const systemOnline = computed(() => !!store.sysStats)

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
        <!-- 节点 / 块 chip:数字 tnum 醒目,单位次级 -->
        <span class="chip-stat" v-if="totals" :title="`图谱节点 ${totals.master_nodes || totals.total_nodes} · RAG 文本块 ${totals.total_chunks}`">
          <span class="num">{{ totals.master_nodes || totals.total_nodes }}</span>
          <span class="unit">节点</span>
          <span class="sep">·</span>
          <span class="num">{{ totals.total_chunks }}</span>
          <span class="unit">块</span>
        </span>

        <!-- token 统计 chip -->
        <span class="chip-stat" v-if="tokenStats && tokenStats.requests"
          :title="`累计调用 ${tokenStats.requests} 次 · 平均延迟 ${tokenStats.avg_latency_s}s`">
          <span class="prefix">Σ</span>
          <span class="num">{{ (tokenStats.total_tokens / 1000).toFixed(1) }}k</span>
          <span class="unit">tok</span>
        </span>

        <!-- 处理中:进度色 chip + sweep 高光 -->
        <span class="chip-run" v-if="store.busy">
          <span class="sweep" aria-hidden="true"></span>
          <span class="dot"></span>
          <span class="run-text">{{ store.statusText || '处理中' }}</span>
        </span>

        <!-- 系统状态指示器 -->
        <span class="chip-sys" :class="{ online: systemOnline }" :title="systemOnline ? '系统正常' : '系统离线'">
          <span class="sys-dot"></span>
          <span class="sys-text">{{ systemOnline ? 'Online' : 'Offline' }}</span>
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
            <span>整合</span>
            <span class="badge" :class="{ accent: store.activeTab === 'integration' }" v-if="integrationCount">
              {{ integrationCount }}
            </span>
          </button>
          <button :class="{ active: store.activeTab === 'rag' }" @click="store.activeTab = 'rag'">
            <span>RAG 问答</span>
            <span class="badge" :class="{ accent: store.activeTab === 'rag' }" v-if="ragQueriesCount">
              {{ ragQueriesCount }}
            </span>
          </button>
          <button :class="{ active: store.activeTab === 'chat' }" @click="store.activeTab = 'chat'">
            <span>对话修正</span>
            <span class="badge" :class="{ accent: store.activeTab === 'chat' }" v-if="chatRounds">
              {{ chatRounds }}
            </span>
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

/* —— 顶栏:纯米白 + 1px 底边 —— */
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
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05);
}
.brand-name { font-weight: 600; font-size: var(--fs-md); letter-spacing: -0.01em; }
.ver {
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 500;
  padding: 1px 6px;
  border: 1px solid var(--border);
  border-radius: var(--r-pill);
  margin-left: var(--space-1);
  letter-spacing: 0.04em;
  font-variant-numeric: tabular-nums;
}

.status { display: flex; gap: 6px; align-items: center; }

/* 顶栏统计 chip:数字 tabular-nums + 单位略小,hover 背景轻微变深 */
.chip-stat {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  padding: 4px 10px;
  font-size: var(--fs-xs);
  color: var(--text-dim);
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--r-chip);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  transition: background-color var(--t-fast) var(--ease-out),
    border-color var(--t-fast) var(--ease-out);
  cursor: default;
}
.chip-stat:hover {
  background: var(--surface-hover);
  border-color: var(--border-strong);
}
.chip-stat .num {
  color: var(--text);
  font-weight: 600;
  font-size: var(--fs-sm);
}
.chip-stat .unit {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 500;
  margin-left: 1px;
}
.chip-stat .sep {
  color: var(--text-muted);
  margin: 0 2px;
  opacity: 0.6;
}
.chip-stat .prefix {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
  margin-right: 2px;
}

/* 处理中 chip:进度色 + 内部 sweep 高光 */
.chip-run {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: var(--fs-xs);
  color: var(--accent);
  background: var(--accent-soft);
  border: 1px solid transparent;
  border-radius: var(--r-chip);
  white-space: nowrap;
  font-weight: 500;
  overflow: hidden;
  isolation: isolate;
}
.chip-run .sweep {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.45) 50%,
    transparent 100%);
  width: 40%;
  animation: sweep 1.6s var(--ease-soft) infinite;
  z-index: 0;
}
.chip-run .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent);
  z-index: 1;
}
.chip-run .run-text { z-index: 1; }

/* 系统在线状态:小绿点 + Online 文字,克制脉冲 */
.chip-sys {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 9px 4px 8px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--r-chip);
  white-space: nowrap;
}
.chip-sys .sys-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
}
.chip-sys.online {
  color: var(--ok);
  background: var(--ok-soft);
  border-color: transparent;
}
.chip-sys.online .sys-dot {
  background: var(--ok);
  animation: statusPulse 1.8s var(--ease-soft) infinite;
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

/* —— Tabs:Linear 风,极细底线,内嵌徽章 —— */
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  transition: color var(--t-fast) var(--ease-out),
    border-color var(--t-fast) var(--ease-out);
}
.tabs button:hover { color: var(--text); background: transparent; }
.tabs button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  background: transparent;
}
.tab-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  min-height: 0;
}
.tab-body > * { flex: 1; }
</style>
