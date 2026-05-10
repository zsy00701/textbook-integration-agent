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

// 关系连线色:在白底上低饱和、可辨识
const RELATION_COLOR = {
  prerequisite: '#b94545', // 红:前置依赖
  parallel:     '#4f6b8a', // 蓝灰:并列
  contains:     '#1f4e3d', // 墨绿:包含(主色,呼应整体气质)
  applies_to:   '#b88a2c', // 暖棕:应用于
} as const

// 教材配色:Tableau 10 风,低饱和、白底友好
const BOOK_PALETTE = [
  '#4e79a7', // 蓝
  '#59a14f', // 绿
  '#e15759', // 红
  '#b07aa1', // 紫
  '#f28e2b', // 橙
  '#76b7b2', // 青
  '#edc948', // 黄
]
// 多教材融合节点 → 墨绿色实底,与主色一致(克制但显眼)
const MERGED_COLOR = '#1f4e3d'
const MERGED_LABEL = '多教材融合'
const SAMPLE_THRESHOLD = 800
const SAMPLE_TOP_N = 300

function isMerged(bookId: string): boolean {
  return bookId.includes(',')
}

function colorForBook(bookId: string, books: string[]): string {
  if (isMerged(bookId)) return MERGED_COLOR
  const idx = books.indexOf(bookId)
  return BOOK_PALETTE[idx % BOOK_PALETTE.length]
}

function bookCategoryName(bookId: string): string {
  if (isMerged(bookId)) return MERGED_LABEL
  return bookId
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
  // 把 "A,B,C" 这种多源 source_book 归到一个"多教材融合"类别
  const bookCategoryByNode = (b: string) => bookCategoryName(b)
  const bookCategories = Array.from(new Set(allNodes.map((n) => bookCategoryByNode(n.source_book))))
  // 单本教材列表(给 colorForBook 用)
  const books = Array.from(new Set(allNodes.map((n) => isMerged(n.source_book) ? '' : n.source_book).filter(Boolean)))
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
    const hasSearch = !!search.value
    return {
      backgroundColor: 'transparent',
      tooltip: {
        backgroundColor: '#ffffff',
        borderColor: '#e7e5e0',
        borderWidth: 1,
        padding: [10, 12],
        textStyle: { color: '#2a2a2a', fontSize: 12 },
        extraCssText: 'box-shadow: 0 6px 16px rgba(0,0,0,0.08); border-radius: 8px; max-width: 340px;',
        formatter: (p: any) =>
          p.dataType === 'node'
            ? `<div style="font-weight:600;color:#1f4e3d;margin-bottom:4px;font-size:13px">${p.data.name}</div>
               <div style="color:#6b6b6b;font-size:11px;margin-bottom:6px;letter-spacing:0.02em">${p.data.chapter || ''}</div>
               <div style="color:#2a2a2a;line-height:1.6;white-space:normal;font-size:12px">${(p.data.definition || '').slice(0, 140)}${(p.data.definition || '').length > 140 ? '…' : ''}</div>`
            : `<div style="color:#2a2a2a;font-size:12px"><b>${p.data.relation_type}</b>${p.data.description ? '：' + p.data.description : ''}</div>`,
      },
      legend: [{
        data: bookCategories,
        textStyle: { color: '#6b6b6b', fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10,
        itemGap: 14,
        bottom: 8,
        icon: 'circle',
      }],
      series: [{
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        focusNodeAdjacency: true,
        categories: bookCategories.map((b) => ({ name: b })),
        label: {
          show: true,
          color: '#2a2a2a',
          fontSize: 11,
          fontWeight: 500,
          position: 'right',
          distance: 5,
        },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 6],
        force: { repulsion: 260, edgeLength: [60, 130], gravity: 0.08 },
        // 强化的 emphasis:hover 节点 + 邻居高亮,其它节点降到 0.15;边变粗变深
        emphasis: {
          focus: 'adjacency',
          scale: 1.05,
          label: { fontWeight: 700, color: '#1f4e3d', fontSize: 12 },
          itemStyle: {
            borderColor: '#1f4e3d',
            borderWidth: 2.5,
            shadowBlur: 12,
            shadowColor: 'rgba(31, 78, 61, 0.35)',
          },
          lineStyle: { width: 2, opacity: 0.85 },
        },
        blur: {
          itemStyle: { opacity: 0.12 },
          label: { color: '#bbbbbb' },
          lineStyle: { opacity: 0.05 },
        },
        data: nodes.map((n) => {
          const merged = isMerged(n.source_book)
          const matched = matchSearch(n)
          // 搜索命中:加深描边 + 光晕
          const searchHit = hasSearch && matched
          return {
            id: n.id,
            name: n.name,
            definition: n.definition,
            chapter: n.chapter,
            // 融合节点稍大;非融合节点白色描边让其在白底中清爽
            symbolSize: merged
              ? Math.min(48, 18 + (freq[n.name] || 1) * 4)
              : Math.min(38, 10 + (freq[n.name] || 1) * 5),
            category: bookCategories.indexOf(bookCategoryByNode(n.source_book)),
            itemStyle: {
              color: colorForBook(n.source_book, books),
              opacity: matched ? 0.95 : 0.16,
              borderColor: searchHit ? '#1f4e3d' : '#ffffff',
              borderWidth: searchHit ? 3 : (merged ? 2.5 : 1),
              shadowBlur: searchHit ? 14 : 0,
              shadowColor: searchHit ? 'rgba(31, 78, 61, 0.55)' : 'transparent',
            },
            _raw: n,
          }
        }),
        links: edges.map((e) => ({
          source: e.source,
          target: e.target,
          relation_type: e.relation_type,
          description: e.description,
          lineStyle: {
            color: RELATION_COLOR[e.relation_type] || '#cfcdc7',
            width: 1,
            opacity: 0.45,
            curveness: 0.08,
          },
        })),
      }],
    } as any
  }

  if (viewMode.value === 'tree') {
    // 用 contains 关系构建森林,然后挂在虚拟根下展示成单棵大树
    const childrenOf: Record<string, string[]> = {}
    const incomingCount: Record<string, number> = {}
    allEdges
      .filter((e) => e.relation_type === 'contains' && e.source !== e.target)
      .forEach((e) => {
        ;(childrenOf[e.source] ||= []).push(e.target)
        incomingCount[e.target] = (incomingCount[e.target] || 0) + 1
      })
    const idMap = Object.fromEntries(allNodes.map((n) => [n.id, n]))

    // 全局 visited:保证每个节点在树里只出现一次,避免 echarts 报"id 重复"
    const visited = new Set<string>()
    const MAX_DEPTH = 4
    const MAX_CHILDREN_PER_NODE = 12

    function build(id: string, depth: number): any {
      if (visited.has(id)) return null
      const n = idMap[id]
      if (!n) return null
      visited.add(id)
      const merged = isMerged(n.source_book)
      let children: any[] = []
      if (depth < MAX_DEPTH) {
        const childIds = (childrenOf[id] || []).slice(0, MAX_CHILDREN_PER_NODE)
        children = childIds.map((c) => build(c, depth + 1)).filter(Boolean)
      }
      return {
        name: n.name,
        value: n.definition,
        itemStyle: {
          color: colorForBook(n.source_book, books),
          borderColor: merged ? '#173b2e' : '#ffffff',
          borderWidth: merged ? 2 : 1,
        },
        label: { color: merged ? '#1f4e3d' : '#2a2a2a', fontWeight: merged ? 600 : 400 },
        // 不带子时不显示折叠图标
        collapsed: depth >= 2 && children.length > 0, // 默认折叠到第 2 层以下
        children,
        _raw: n,
      }
    }

    // 候选根:contains 出度 ≥ 2 的节点,优先无 incoming(纯根),再按出度排
    const candidates = Object.entries(childrenOf)
      .map(([id, kids]) => ({ id, deg: kids.length, hasIn: !!incomingCount[id] }))
      .filter((x) => x.deg >= 2)
      .sort((a, b) => {
        if (a.hasIn !== b.hasIn) return a.hasIn ? 1 : -1 // 纯根优先
        return b.deg - a.deg
      })

    // 搜索:命中节点祖先优先,以保证搜索到的根仍可见
    const matchedNames = search.value
      ? new Set(allNodes.filter((n) => matchSearch(n)).map((n) => n.id))
      : null

    const ROOT_LIMIT = 14
    const roots: any[] = []
    for (const c of candidates) {
      if (roots.length >= ROOT_LIMIT) break
      if (matchedNames && !matchedNames.has(c.id)) {
        // 如果有搜索,优先包含至少一个命中后代的根
        const ids = childrenOf[c.id] || []
        const hasMatchedDescendant = ids.some((x) => matchedNames!.has(x))
        if (!hasMatchedDescendant) continue
      }
      const t = build(c.id, 1)
      if (t) roots.push(t)
    }

    if (roots.length === 0) {
      return {
        backgroundColor: 'transparent',
        title: {
          text: '当前图谱中没有足够的 contains(包含)关系来构建树状视图',
          subtext: '试试切换到「力导向」或「桑基」视图',
          left: 'center', top: 'center',
          textStyle: { color: '#6b6b6b', fontSize: 14, fontWeight: 500 },
          subtextStyle: { color: '#9b9b9b', fontSize: 12 },
        },
      } as any
    }

    const virtualRoot = {
      // 虚拟根节点加 ◆ 装饰符,呼应"整合"语义
      name: store.currentGraph?.book_id === 'master' ? '◆ 整合知识图谱' : (store.currentGraph?.book_title || '知识体系'),
      value: `共 ${roots.length} 个核心知识根 · ${visited.size} 个节点`,
      itemStyle: {
        color: '#1f4e3d',
        borderColor: '#ffffff',
        borderWidth: 2,
        shadowBlur: 8,
        shadowColor: 'rgba(31, 78, 61, 0.25)',
      },
      label: { color: '#1f4e3d', fontWeight: 700, fontSize: 13 },
      collapsed: false,
      children: roots,
    }

    return {
      backgroundColor: 'transparent',
      tooltip: {
        backgroundColor: '#ffffff',
        borderColor: '#e7e5e0',
        borderWidth: 1,
        padding: [10, 12],
        textStyle: { color: '#2a2a2a', fontSize: 12 },
        extraCssText: 'box-shadow: 0 6px 16px rgba(0,0,0,0.08); border-radius: 8px; max-width: 340px;',
        formatter: (p: any) =>
          `<div style="font-weight:600;color:#1f4e3d;margin-bottom:4px;font-size:13px">${p.data.name}</div>
           <div style="color:#2a2a2a;line-height:1.6;white-space:normal;font-size:12px">${(p.data.value || '').slice(0, 160)}</div>`,
      },
      series: [{
        type: 'tree',
        data: [virtualRoot],
        // 更舒展的留白:右侧给 leaf label 更多空间
        top: '6%', left: '8%', bottom: '6%', right: '18%',
        symbol: 'circle',
        symbolSize: (_val: any, p: any) => {
          // 根 14,二级 10,三级 7,叶 5 —— 形成清晰梯度
          const depth = (p?.treeAncestors?.length || 1) - 1
          if (depth === 0) return 14
          if (depth === 1) return 10
          if (depth === 2) return 7
          return 5
        },
        orient: 'LR',
        layout: 'orthogonal',
        edgeShape: 'curve',
        lineStyle: { color: '#d8d5cf', width: 1, curveness: 0.5 },
        label: {
          // 字号梯度:根 13、二级 12、叶 11 —— 通过 formatter 不灵活,改用 leaves
          color: '#2a2a2a',
          fontSize: 12,
          fontWeight: 500,
          position: 'left',
          verticalAlign: 'middle',
          align: 'right',
          distance: 7,
        },
        leaves: {
          label: {
            position: 'right',
            align: 'left',
            color: '#6b6b6b',
            fontSize: 11,
            fontWeight: 400,
          }
        },
        emphasis: {
          focus: 'descendant',
          itemStyle: {
            borderColor: '#1f4e3d',
            borderWidth: 2,
            shadowBlur: 6,
            shadowColor: 'rgba(31, 78, 61, 0.25)',
          },
          label: { color: '#1f4e3d', fontWeight: 700 },
          lineStyle: { color: '#1f4e3d', width: 1.4 },
        },
        expandAndCollapse: true,
        initialTreeDepth: 2,
        roam: true,
        animationDuration: 400,
        animationEasing: 'cubicOut',
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
  // 给桑基节点分配三种视觉层级:
  // 教材(level 0):深墨绿、字大粗;章节(level 1):中等墨绿、字中;知识点(level 2):浅墨绿、字小
  const bookSet = new Set(sankeyNodes.map((n) => n.source_book))
  const chapterSet = new Set(sankeyNodes.map((n) => n.chapter))
  const sankeyNodeData = Array.from(nodeSet).map((n) => {
    if (bookSet.has(n)) {
      return {
        name: n,
        itemStyle: { color: '#1f4e3d', borderColor: 'transparent' },
        label: { color: '#1f4e3d', fontSize: 12, fontWeight: 600 },
      }
    }
    if (chapterSet.has(n)) {
      return {
        name: n,
        itemStyle: { color: '#5a8a76', borderColor: 'transparent' },
        label: { color: '#3d6b58', fontSize: 11, fontWeight: 500 },
      }
    }
    // 叶子(知识点)
    return {
      name: n,
      itemStyle: { color: '#a8c4b6', borderColor: 'transparent' },
      label: { color: '#6b6b6b', fontSize: 10, fontWeight: 400 },
    }
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: '#ffffff',
      borderColor: '#e7e5e0',
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: '#2a2a2a', fontSize: 12 },
      extraCssText: 'box-shadow: 0 6px 16px rgba(0,0,0,0.08); border-radius: 8px;',
    },
    series: [{
      type: 'sankey',
      data: sankeyNodeData,
      links: Object.entries(linkMap).map(([k, v]) => {
        const [s, t] = k.split('|')
        return { source: s, target: t, value: v }
      }),
      itemStyle: { borderWidth: 0 },
      // 单色低饱和墨绿,不再用 source 渐变彩色,克制专业
      lineStyle: { color: '#7da695', opacity: 0.32, curveness: 0.55 },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { opacity: 0.7, color: '#1f4e3d' },
        itemStyle: { borderColor: '#1f4e3d', borderWidth: 1.5 },
      },
      nodeWidth: 14,
      nodeGap: 10,
      animationDuration: 500,
      animationEasing: 'cubicOut',
      left: '4%', right: '12%', top: '4%', bottom: '4%',
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

const RELATION_LABEL = {
  prerequisite: '前置依赖',
  parallel: '并列',
  contains: '包含',
  applies_to: '应用于',
} as const

const neighbors = computed(() => {
  const n = selectedNode.value
  const g = store.currentGraph
  if (!n || !g) return null
  const idMap = Object.fromEntries(g.nodes.map((x) => [x.id, x]))
  const out: { kind: string; node: any; rel: any }[] = []
  const inn: { kind: string; node: any; rel: any }[] = []
  for (const e of g.edges) {
    if (e.source === n.id && idMap[e.target]) {
      out.push({ kind: RELATION_LABEL[e.relation_type] || e.relation_type, node: idMap[e.target], rel: e })
    }
    if (e.target === n.id && idMap[e.source]) {
      inn.push({ kind: RELATION_LABEL[e.relation_type] || e.relation_type, node: idMap[e.source], rel: e })
    }
  }
  return { out: out.slice(0, 8), inn: inn.slice(0, 8) }
})

function selectByName(name: string) {
  const g = store.currentGraph
  if (!g) return
  const found = g.nodes.find((x) => x.name === name)
  if (found) selectedNode.value = found
}

onMounted(() => {
  if (chartEl.value) {
    // 浅色主题:不再 init('dark')。背景透明,由父容器决定底色
    chart = echarts.init(chartEl.value, undefined, { renderer: 'canvas' })
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
      <span class="sample-tag" v-if="isSampled">采样前 {{ SAMPLE_TOP_N }} 高度节点</span>
      <div class="spacer"></div>
      <div class="search-wrap">
        <svg class="s-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
        </svg>
        <input v-model="search" placeholder="搜索知识点 / 定义" class="search" />
      </div>
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
        <h2>快速开始</h2>
        <ol>
          <li>左侧已加载 7 本教材 → 点击 <b>"刷新"</b> 验证</li>
          <li>每本"已解析"状态后 → 点 <b>"抽取知识点"</b> 或调 <code>POST /api/graph/extract_all</code></li>
          <li>右侧"整合"面板 → <b>一键整合</b> 出主图谱</li>
          <li>右侧"RAG 问答" → <b>建立索引</b> → 提问</li>
        </ol>
        <p class="ph-hint">完成后,左侧"整合图谱"按钮即可在此渲染图谱。</p>
      </div>
    </div>

    <div v-if="selectedNode" class="detail fade-in">
      <div class="detail-head">
        <div class="head-left">
          <span
            class="book-dot"
            :style="{ background: colorForBook(selectedNode.source_book, [...new Set((store.currentGraph?.nodes || []).map(n => isMerged(n.source_book) ? '' : n.source_book).filter(Boolean))]) }"
            aria-hidden="true"
          ></span>
          <h4>{{ selectedNode.name }}</h4>
        </div>
        <button class="close-btn" aria-label="关闭" @click="selectedNode = null">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
            <path d="M3 3l10 10M13 3L3 13" />
          </svg>
        </button>
      </div>

      <div class="kv-grid">
        <div class="kv"><span class="k">章节</span><span class="v" :title="selectedNode.chapter">{{ selectedNode.chapter }}</span></div>
        <div class="kv"><span class="k">页码</span><span class="v">第 {{ selectedNode.page }} 页</span></div>
        <div class="kv"><span class="k">类别</span><span class="v">{{ selectedNode.category }}</span></div>
        <div class="kv"><span class="k">来源</span><span class="v" :title="selectedNode.source_book">{{ selectedNode.source_book }}</span></div>
      </div>

      <div class="def">
        <div class="k def-k">定义</div>
        <p class="def-text">{{ selectedNode.definition }}</p>
      </div>

      <div v-if="neighbors && (neighbors.out.length || neighbors.inn.length)" class="neighbors">
        <div class="ng-section" v-if="neighbors.out.length">
          <div class="ng-title">
            <span class="ng-arrow ng-out" aria-hidden="true">→</span>
            出边
            <span class="ng-count">{{ neighbors.out.length }}</span>
          </div>
          <div class="ng-row" v-for="(item, i) in neighbors.out" :key="'o'+i" @click="selectByName(item.node.name)">
            <span class="rel-tag">{{ item.kind }}</span>
            <a class="ng-name">{{ item.node.name }}</a>
          </div>
        </div>
        <div class="ng-section" v-if="neighbors.inn.length">
          <div class="ng-title">
            <span class="ng-arrow ng-in" aria-hidden="true">←</span>
            入边
            <span class="ng-count">{{ neighbors.inn.length }}</span>
          </div>
          <div class="ng-row" v-for="(item, i) in neighbors.inn" :key="'i'+i" @click="selectByName(item.node.name)">
            <span class="rel-tag">{{ item.kind }}</span>
            <a class="ng-name">{{ item.node.name }}</a>
          </div>
        </div>
      </div>

      <div class="actions">
        <button class="full" @click="askAboutNode">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor"
            stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="7" cy="7" r="5" /><path d="M11 11l3 3" />
          </svg>
          <span>用 RAG 深入了解</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.graph-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background: var(--panel);
}

/* —— 工具栏:纯白底,1px 浅灰底边 —— */
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--border);
  background: var(--panel);
  flex-wrap: wrap;
  flex-shrink: 0;
  min-height: 48px;
}
.title {
  font-weight: 600;
  font-size: var(--fs-md);
  color: var(--text);
  flex-shrink: 0;
}
.stat {
  color: var(--text-dim);
  font-size: var(--fs-xs);
  font-variant-numeric: tabular-nums;
  padding: 2px 8px;
  background: var(--bg-soft);
  border-radius: var(--r-chip);
}
.sample-tag {
  font-size: var(--fs-xs);
  padding: 2px 8px;
  border-radius: var(--r-chip);
  background: var(--warn-soft);
  color: var(--warn);
}
.spacer { flex: 1; }

/* 带图标的搜索框 */
.search-wrap { position: relative; display: flex; align-items: center; }
.search-wrap .s-icon {
  position: absolute;
  left: 9px;
  color: var(--text-muted);
  pointer-events: none;
}
.search {
  width: 220px;
  padding: 5px 10px 5px 28px;
  font-size: var(--fs-sm);
}

.mini { font-size: var(--fs-xs); padding: 4px 10px; }

/* 视图切换:分段控件,白底+灰边,active 墨绿 */
.views {
  display: flex;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  overflow: hidden;
  background: var(--panel);
}
.views button {
  background: var(--panel);
  color: var(--text-dim);
  font-size: var(--fs-xs);
  padding: 5px 12px;
  border: none;
  border-radius: 0;
  border-right: 1px solid var(--border);
  font-weight: 500;
}
.views button:last-child { border-right: none; }
.views button:hover { background: var(--surface-hover); color: var(--text); }
.views button.active {
  background: var(--accent);
  color: var(--text-inverse);
  border-color: var(--accent);
}

/* —— 图谱画布 —— */
.chart { flex: 1; min-height: 0; background: var(--panel); }

/* —— 占位卡 —— */
.placeholder {
  position: absolute;
  inset: 50px 0 0 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.ph-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: var(--space-5) var(--space-6);
  max-width: 480px;
  box-shadow: var(--shadow-2);
  pointer-events: auto;
}
.ph-card h2 {
  font-size: var(--fs-lg);
  font-weight: 600;
  margin-bottom: var(--space-3);
  color: var(--text);
}
.ph-card ol {
  margin: 0 0 var(--space-3) 18px;
  line-height: 1.85;
  color: var(--text-dim);
  font-size: var(--fs-base);
}
.ph-card ol li b { color: var(--text); font-weight: 600; }
.ph-card code {
  background: var(--bg-soft);
  border: 1px solid var(--border);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: var(--fs-xs);
  font-family: ui-monospace, Menlo, Consolas, monospace;
  color: var(--accent);
}
.ph-hint { color: var(--text-muted); font-size: var(--fs-sm); }

/* —— 节点详情卡(右上 sticky panel) —— */
.detail {
  position: absolute;
  right: var(--space-4);
  top: 60px;
  width: 320px;
  max-height: calc(100% - 80px);
  overflow-y: auto;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: var(--space-4);
  font-size: var(--fs-sm);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04);
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}
.head-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
}
.book-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.9);
}
.detail h4 {
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
  letter-spacing: -0.01em;
  word-break: break-word;
}
.close-btn {
  width: 24px;
  height: 24px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--text-muted);
  border: 1px solid transparent;
  border-radius: var(--r-sm);
  flex-shrink: 0;
}
.close-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
  border-color: var(--border);
}

/* KV 网格:label 11px upper-tracked,value 13px */
.kv-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
}
.kv {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.k {
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.v {
  color: var(--text);
  font-size: var(--fs-base);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.def {
  margin-top: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.def-k { display: block; margin-bottom: 6px; }
.def-text {
  color: var(--text);
  line-height: 1.7;
  font-size: var(--fs-base);
  text-indent: 0;
}

.actions { margin-top: var(--space-4); }
.actions .full {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 14px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

/* —— 邻居:出边/入边分组,标题清晰 —— */
.neighbors {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.ng-section { margin-bottom: var(--space-3); }
.ng-section:last-child { margin-bottom: 0; }
.ng-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 6px;
}
.ng-arrow {
  font-size: 11px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 0;
}
.ng-count {
  margin-left: auto;
  font-size: 10px;
  color: var(--text-muted);
  background: var(--bg-soft);
  padding: 1px 6px;
  border-radius: var(--r-pill);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}
.ng-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  margin: 0 -6px;
  font-size: var(--fs-xs);
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: background-color var(--t-fast) var(--ease-out);
}
.ng-row:hover { background: var(--surface-hover); }
.rel-tag {
  color: var(--text-dim);
  flex-shrink: 0;
  background: var(--bg-soft);
  padding: 1px 7px;
  border-radius: var(--r-chip);
  font-size: 10px;
  font-weight: 500;
  border: 1px solid var(--border-subtle);
}
.ng-name {
  color: var(--text);
  cursor: pointer;
  text-decoration: none;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-sm);
  flex: 1;
  min-width: 0;
}
.ng-row:hover .ng-name { color: var(--accent); }
</style>
