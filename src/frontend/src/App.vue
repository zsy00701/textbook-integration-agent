<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAppStore } from './stores'
import UploadPanel from './components/UploadPanel.vue'
import GraphView from './components/GraphView.vue'
import IntegrationPanel from './components/IntegrationPanel.vue'
import RagPanel from './components/RagPanel.vue'
import ChatPanel from './components/ChatPanel.vue'

const store = useAppStore()
const tab = ref<'integration' | 'rag' | 'chat'>('integration')

onMounted(async () => {
  await store.refreshTextbooks()
  await store.loadRagStatus()
})
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="brand">📚 学科知识整合智能体</div>
      <div class="status">
        <span class="tag" v-if="store.ragStatus">
          已索引 {{ store.ragStatus.indexed_books }} 本 / {{ store.ragStatus.total_chunks }} 块
        </span>
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
          <button :class="{ active: tab === 'integration' }" @click="tab = 'integration'">整合</button>
          <button :class="{ active: tab === 'rag' }" @click="tab = 'rag'">RAG 问答</button>
          <button :class="{ active: tab === 'chat' }" @click="tab = 'chat'">对话修正</button>
        </nav>
        <div class="tab-body">
          <IntegrationPanel v-show="tab === 'integration'" />
          <RagPanel v-show="tab === 'rag'" />
          <ChatPanel v-show="tab === 'chat'" />
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
  background: var(--panel);
  border-bottom: 1px solid var(--border);
}
.brand { font-weight: 600; font-size: 15px; }
.status { display: flex; gap: 8px; }
.main { display: flex; flex: 1; overflow: hidden; }
.left { width: 290px; padding: 12px; overflow-y: auto; border-right: 1px solid var(--border); }
.center { flex: 1; min-width: 0; display: flex; }
.right { width: 380px; display: flex; flex-direction: column; border-left: 1px solid var(--border); }
.tabs { display: flex; border-bottom: 1px solid var(--border); }
.tabs button {
  flex: 1; background: transparent; color: var(--text-dim);
  border-radius: 0; padding: 10px; border-bottom: 2px solid transparent;
}
.tabs button.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-body { flex: 1; overflow: hidden; display: flex; }
.tab-body > * { flex: 1; }
</style>
