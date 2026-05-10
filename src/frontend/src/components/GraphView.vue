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
const showAll = ref(false)
let chart: echarts.ECharts | null = null

const RELATION_COLOR = {
  prerequisite: '#ef5350',
  parallel: '#4f9eff',
  contains: '#6dd6c1',
  applies_to: '#f5a623',
} as const

const BOOK_PALETTE = ['#4f9eff', '#6dd6c1', '#f5a623', '#ef5350', '#ab47bc', '#26c6da', '#ffca28']
const SAMPLE_THRESHOLD = 800
const SAMPLE_TOP_N = 300

function colorForBook(bookId: string, books: string[]): string {
  const idx = books.indexOf(bookId)
  return BOOK_PALETTE[idx % BOOK_PALETTE.length]
}

const stats = computed(() => {
  const g = store.currentGraph
  if (!g) return null
  return { nodes: g.nodes.length, edges: g.edges.length }
})

const isSampled = computed(() => {
  const g = store.currentGraph
  return !!g && g.nodes.length > SAMPLE_THRESHOLD && !showAll.value
})

function sampleByDegree(nodes: KnowledgeNode[], edges: any[], topN: number, mustInclude: Set<string>) {
  const deg: Record<string, number> = {}
  edges.forEach((e) => {
    deg[e.source] = (deg[e.source] || 0) + 1
    deg[e.target] = (deg[e.target] || 0) + 1
  })
  const sorted = [...nodes].sort((a, b) => (deg[b.id] || 0) - (deg[a.id] || 0))
  const kept = new Set<string>()
  for (const n of sorted) {
    if (kept.size >= topN && !mustInclude.has(n.id)) continue
    kept.add(n.id)
  }
  // 强制纳入搜索命中的节点
  mustInclude.forEach((id) => kept.add(id))
  return kept
}

function buildOption() {
  const g = store.currentGraph
  if (!g) return null
  const allNodes = g.nodes
  const allEdges = g.edges
  const books = Array.from(new Set(allNodes.map((n) => n.source_book)))
  const freq: Record<string, number> = {}
  allNodes.forEach((n) => (freq[n.name] = (freq[n.name] || 0) + 1))
  const matchSearch = (n: KnowledgeNode) =>
    !search.value || n.name.toLowerCase().includes(search.value.toLowerCase()) ||
    (n.definition || '').toLowerCase().includes(search.value.toLowerCase())

  // 采样
  let nodes = allNodes
  let edges = allEdges
  if (viewMode.value === 'force' && allNodes.length > SAMPLE_THRESHOLD && !showAll.value) {
    const must = new Set<string>()
    if (search.value) {
      allNodes.forEach((n) => { if (matchSearch(n)) must.add(n.id) })
    }
    const keep = sampleByDegree(allNodes, allEdges, SAMPLE_TOP_N, must)
    nodes = allNodes.filter((n) => keep.has(n.id))
    edges = allEdges.filter((e) => keep.has(e.source) && keep.has(e.target))
  }

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
        data: nodes.map((n) => ({
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
        links: edges.map((e) => ({
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
    const childrenOf: Record<string, any[]> = {}
    const incoming = new Set<string>()
    allEdges
      .filter((e) => e.relation_type === 'contains')
      .forEach((e) => {
        ;(childrenOf[e.source] ||= []).push(e.target)
        incoming.add(e.target)
      })
    const idMap = Object.fromEntries(allNodes.map((n) => [n.id, n]))
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
    const roots = allNodes.filter((n) => !incoming.has(n.id) && childrenOf[n.id]).slice(0, 30)
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

  // sankey:教材 → 章节 → 节点;限流避免炸
  const chapterCount: Record<string, number> = {}
  allNodes.forEach((n) => { chapterCount[n.chapter] = (chapterCount[n.chapter] || 0) + 1 })
  const topChapters = new Set(
    Object.entries(chapterCount).sort((a, b) => b[1] - a[1]).slice(0, 30).map((x) => x[0])
  )
  const nodeNameLimit = 80
  const sankeyNodes: KnowledgeNode[] = []
  const seenName = new Set<string>()
  allNodes.forEach((n) => {
    if (!topChapters.has(n.chapter)) return
    if (sankeyNodes.length >= nodeNameLimit) return
    if (seenName.has(n.name)) return
    seenName.add(n.name)
    sankeyNodes.push(n)
  })

  const links: any[] = []
  const nodeSet = new Set<string>()
  sankeyNodes.forEach((n) => {
    nodeSet.add(n.source_book)
    nodeSet.add(n.chapter)
    nodeSet.add(n.name)
    links.push({ source: n.source_book, target: n.chapter, value: 1 })
    links.push({ source: n.chapter, target: n.name, value: 1 })
  })
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

function askAboutNode() {
  if (!selectedNode.value) return
  store.askInRag(`什么是${selectedNode.value.name}?请基于教材详细说明其定义、机制与临床意义。`)
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

watch(() => [store.currentGraph, viewMode.value, search.value, showAll.value], render, { deep: true })
</script>

<template>
  <div class="graph-wrap">
    <div class="toolbar">
      <span class="title">
        {{ store.currentGraph?.book_title || '请选择教材或整合图谱' }}
      </span>
      <span class="stat" v-if="stats">{{ stats.nodes }} 节点 · {{ stats.edges }} 关系</span>
      <span class="sample-tag" v-if="isSampled">采样显示前 {{ SAMPLE_TOP_N }} 高度数节点</span>
      <input v-model="search" placeholder="🔍 搜索知识点 / 定义" class="search" />
      <button class="mini secondary" v-if="(stats?.nodes || 0) > SAMPLE_THRESHOLD && viewMode === 'force'"
        @click="showAll = !showAll">
        {{ showAll ? '只看核心' : '显示全部' }}
      </button>
      <div class="views">
        <button :class="{ active: viewMode === 'force' }" @click="viewMode = 'force'">力导向</button>
        <button :class="{ active: viewMode === 'tree' }" @click="viewMode = 'tree'">树状</button>
        <button :class="{ active: viewMode === 'sankey' }" @click="viewMode = 'sankey'">桑基</button>
      </div>
    </div>
    <div class="chart" ref="chartEl"></div>

    <div v-if="!stats" class="placeholder">
      <div class="ph-card">
        <h2>🚀 快速开始</h2>
        <ol>
          <li>左侧已加载 7 本教材 → 点击 <b>"刷新"</b> 验证</li>
          <li>每本"已解析"状态后 → 点 <b>"抽取知识点"</b> 或调 <code>POST /api/graph/extract_all</code></li>
          <li>右侧"整合"面板 → <b>▶ 一键整合</b> 出主图谱</li>
          <li>右侧"RAG 问答" → <b>建立索引</b> → 提问</li>
        </ol>
        <p class="ph-hint">完成后,左侧"查看整合图谱"按钮即可在此渲染图谱。</p>
      </div>
    </div>

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
      <div class="actions">
        <button class="full" @click="askAboutNode">🔍 用 RAG 深入了解</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.graph-wrap { flex: 1; display: flex; flex-direction: column; position: relative; }
.toolbar {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--panel);
  flex-wrap: wrap;
}
.title { font-weight: 500; flex-shrink: 0; }
.stat { color: var(--text-dim); font-size: 12px; }
.sample-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: rgba(245,166,35,0.15); color: var(--warn);
}
.search { flex: 1; max-width: 220px; min-width: 140px; }
.mini { font-size: 11px; padding: 3px 10px; }
.views { display: flex; gap: 2px; }
.views button {
  background: var(--panel-2); color: var(--text-dim);
  font-size: 11px; padding: 4px 10px;
}
.views button.active { background: var(--accent); color: white; }
.chart { flex: 1; }
.placeholder {
  position: absolute; inset: 50px 0 0 0;
  display: flex; align-items: center; justify-content: center;
  pointer-events: none;
}
.ph-card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  padding: 24px 32px; max-width: 480px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.3);
  pointer-events: auto;
}
.ph-card h2 { font-size: 16px; margin-bottom: 12px; }
.ph-card ol { margin: 0 0 12px 18px; line-height: 1.85; color: var(--text-dim); font-size: 13px; }
.ph-card ol li b { color: var(--text); }
.ph-card code { background: var(--panel-2); padding: 1px 6px; border-radius: 3px; font-size: 11px; }
.ph-hint { color: var(--text-dim); font-size: 12px; }
.detail {
  position: absolute; right: 12px; top: 60px;
  width: 280px; max-height: 70%; overflow-y: auto;
  background: var(--panel); border: 1px solid var(--border); border-radius: 6px;
  padding: 12px; font-size: 12px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.3);
}
.detail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail h4 { font-size: 13px; }
.row { margin: 4px 0; }
.k { color: var(--text-dim); display: inline-block; width: 70px; }
.def { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--border); }
.def .k { display: block; margin-bottom: 4px; }
.actions { margin-top: 10px; }
.actions .full { width: 100%; }
</style>
