<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import * as echarts from 'echarts'
import { useAppStore } from '../stores'
import type { KnowledgeNode } from '../types'

const store = useAppStore()
const chartEl = ref<HTMLDivElement | null>(null)
const selectedNode = ref<KnowledgeNode | null>(null)
const viewMode = ref<'force' | 'tree' | 'sankey'>('force')
const search = ref('')
let chart: echarts.ECharts | null = null

const RELATION_COLOR = {
  prerequisite: '#ef5350',
  parallel: '#4f9eff',
  contains: '#6dd6c1',
  applies_to: '#f5a623',
} as const

// 教材色板(根据 source_book 分配,master 视图区分来源)
const BOOK_PALETTE = ['#4f9eff', '#6dd6c1', '#f5a623', '#ef5350', '#ab47bc', '#26c6da', '#ffca28']

function colorForBook(bookId: string, books: string[]): string {
  const idx = books.indexOf(bookId)
  return BOOK_PALETTE[idx % BOOK_PALETTE.length]
}

const stats = computed(() => {
  const g = store.currentGraph
  if (!g) return null
  return { nodes: g.nodes.length, edges: g.edges.length }
})

function buildOption() {
  const g = store.currentGraph
  if (!g) return null
  const books = Array.from(new Set(g.nodes.map((n) => n.source_book)))
  const freq: Record<string, number> = {}
  g.nodes.forEach((n) => (freq[n.name] = (freq[n.name] || 0) + 1))
  const matchSearch = (n: KnowledgeNode) =>
    !search.value || n.name.toLowerCase().includes(search.value.toLowerCase())

  if (viewMode.value === 'force') {
    return {
      tooltip: {
        formatter: (p: any) =>
          p.dataType === 'node'
            ? `<b>${p.data.name}</b><br/>${p.data.chapter}<br/>${p.data.definition?.slice(0, 100) || ''}`
            : `${p.data.relation_type}: ${p.data.description || ''}`,
      },
      legend: [{
        data: books,
        textStyle: { color: '#e3e8f0' },
        bottom: 5,
      }],
      series: [{
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        focusNodeAdjacency: true,
        categories: books.map((b) => ({ name: b })),
        label: { show: true, color: '#e3e8f0', fontSize: 11 },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 6],
        force: { repulsion: 250, edgeLength: [60, 120], gravity: 0.08 },
        data: g.nodes.map((n) => ({
          id: n.id,
          name: n.name,
          definition: n.definition,
          chapter: n.chapter,
          symbolSize: Math.min(40, 10 + (freq[n.name] || 1) * 6),
          category: books.indexOf(n.source_book),
          itemStyle: {
            color: colorForBook(n.source_book, books),
            opacity: matchSearch(n) ? 1 : 0.15,
          },
          _raw: n,
        })),
        links: g.edges.map((e) => ({
          source: e.source,
          target: e.target,
          relation_type: e.relation_type,
          description: e.description,
          lineStyle: { color: RELATION_COLOR[e.relation_type] || '#888', width: 1.5, opacity: 0.6 },
        })),
      }],
    } as any
  }

  if (viewMode.value === 'tree') {
    // 用 contains 关系构建树;根节点 = 没有入边的节点
    const childrenOf: Record<string, any[]> = {}
    const incoming = new Set<string>()
    g.edges
      .filter((e) => e.relation_type === 'contains')
      .forEach((e) => {
        ;(childrenOf[e.source] ||= []).push(e.target)
        incoming.add(e.target)
      })
    const idMap = Object.fromEntries(g.nodes.map((n) => [n.id, n]))
    function build(id: string, depth = 0): any {
      const n = idMap[id]
      if (!n || depth > 5) return null
      const childIds = childrenOf[id] || []
      return {
        name: n.name,
        value: n.definition,
        itemStyle: { color: colorForBook(n.source_book, books) },
        children: childIds.map((c) => build(c, depth + 1)).filter(Boolean),
        _raw: n,
      }
    }
    const roots = g.nodes.filter((n) => !incoming.has(n.id) && childrenOf[n.id]).slice(0, 30)
    return {
      tooltip: { formatter: (p: any) => `<b>${p.data.name}</b><br/>${(p.data.value || '').slice(0, 120)}` },
      series: [{
        type: 'tree',
        data: roots.map((r) => build(r.id)).filter(Boolean),
        top: '5%', left: '8%', bottom: '5%', right: '15%',
        symbolSize: 8,
        label: { color: '#e3e8f0', fontSize: 11, position: 'left', verticalAlign: 'middle', align: 'right' },
        leaves: { label: { position: 'right', align: 'left' } },
        emphasis: { focus: 'descendant' },
        expandAndCollapse: true,
        initialTreeDepth: 2,
        roam: true,
      }],
    } as any
  }

  // sankey:从教材 → 章节 → 节点
  const links: any[] = []
  const nodeSet = new Set<string>()
  g.nodes.forEach((n) => {
    nodeSet.add(n.source_book)
    nodeSet.add(n.chapter)
    nodeSet.add(n.name)
    links.push({ source: n.source_book, target: n.chapter, value: 1 })
    links.push({ source: n.chapter, target: n.name, value: 1 })
  })
  // 合并重复边
  const linkMap: Record<string, number> = {}
  links.forEach((l) => {
    const k = `${l.source}|${l.target}`
    linkMap[k] = (linkMap[k] || 0) + l.value
  })
  return {
    tooltip: {},
    series: [{
      type: 'sankey',
      data: Array.from(nodeSet).map((n) => ({ name: n })),
      links: Object.entries(linkMap).map(([k, v]) => {
        const [s, t] = k.split('|')
        return { source: s, target: t, value: v }
      }),
      label: { color: '#e3e8f0', fontSize: 11 },
      lineStyle: { color: 'gradient', opacity: 0.5 },
    }],
  } as any
}

function render() {
  if (!chart) return
  const opt = buildOption()
  if (!opt) {
    chart.clear()
    return
  }
  chart.setOption(opt, true)
}

onMounted(() => {
  if (chartEl.value) {
    chart = echarts.init(chartEl.value, 'dark')
    chart.on('click', (p: any) => {
      if (p.dataType === 'node' && p.data?._raw) selectedNode.value = p.data._raw
    })
    window.addEventListener('resize', () => chart?.resize())
    render()
  }
})

watch(() => [store.currentGraph, viewMode.value, search.value], render, { deep: true })
</script>

<template>
  <div class="graph-wrap">
    <div class="toolbar">
      <span class="title">{{ store.currentGraph?.book_title || '请选择教材或整合图谱' }}</span>
      <span class="stat" v-if="stats">{{ stats.nodes }} 节点 · {{ stats.edges }} 关系</span>
      <input v-model="search" placeholder="🔍 搜索知识点" class="search" />
      <div class="views">
        <button :class="{ active: viewMode === 'force' }" @click="viewMode = 'force'">力导向</button>
        <button :class="{ active: viewMode === 'tree' }" @click="viewMode = 'tree'">树状</button>
        <button :class="{ active: viewMode === 'sankey' }" @click="viewMode = 'sankey'">桑基</button>
      </div>
    </div>
    <div class="chart" ref="chartEl"></div>

    <div v-if="selectedNode" class="detail">
      <div class="detail-head">
        <h4>{{ selectedNode.name }}</h4>
        <button class="mini secondary" @click="selectedNode = null">×</button>
      </div>
      <div class="row"><span class="k">所属章节</span>{{ selectedNode.chapter }}</div>
      <div class="row"><span class="k">页码</span>第 {{ selectedNode.page }} 页</div>
      <div class="row"><span class="k">类别</span>{{ selectedNode.category }}</div>
      <div class="row"><span class="k">来源教材</span>{{ selectedNode.source_book }}</div>
      <div class="def"><span class="k">定义</span>{{ selectedNode.definition }}</div>
    </div>
  </div>
</template>

<style scoped>
.graph-wrap { flex: 1; display: flex; flex-direction: column; position: relative; }
.toolbar {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--panel);
}
.title { font-weight: 500; flex-shrink: 0; }
.stat { color: var(--text-dim); font-size: 12px; }
.search { flex: 1; max-width: 220px; }
.views { display: flex; gap: 2px; }
.views button {
  background: var(--panel-2); color: var(--text-dim);
  font-size: 11px; padding: 4px 10px;
}
.views button.active { background: var(--accent); color: white; }
.chart { flex: 1; }
.detail {
  position: absolute; right: 12px; top: 60px;
  width: 280px; max-height: 60%; overflow-y: auto;
  background: var(--panel); border: 1px solid var(--border); border-radius: 6px;
  padding: 12px; font-size: 12px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.3);
}
.detail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail h4 { font-size: 13px; }
.mini { font-size: 11px; padding: 2px 8px; }
.row { margin: 4px 0; }
.k { color: var(--text-dim); display: inline-block; width: 70px; }
.def { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--border); }
.def .k { display: block; margin-bottom: 4px; }
</style>
