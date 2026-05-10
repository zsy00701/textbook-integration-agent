import { defineStore } from 'pinia'
import { api } from '../api/client'
import type {
  TextbookMeta,
  BookGraph,
  Decision,
  IntegrationStats,
  RagStatus,
  ChatMessage,
} from '../types'

export const useAppStore = defineStore('app', {
  state: () => ({
    textbooks: [] as TextbookMeta[],
    selectedBookId: '' as string, // '' or 'master' or book_id
    currentGraph: null as BookGraph | null,
    decisions: [] as Decision[],
    integrationStats: null as IntegrationStats | null,
    ragStatus: null as RagStatus | null,
    sessionId: '',
    chatHistory: [] as ChatMessage[],
    busy: false,
    statusText: '',
  }),
  actions: {
    async refreshTextbooks() {
      const { data } = await api.get<TextbookMeta[]>('/textbooks')
      this.textbooks = data
    },
    async loadGraph(bookId: string) {
      this.busy = true
      this.statusText = `加载图谱 ${bookId}...`
      try {
        const { data } = await api.get<BookGraph>(`/graph/${bookId}`)
        this.currentGraph = data
        this.selectedBookId = bookId
      } finally {
        this.busy = false
        this.statusText = ''
      }
    },
    async loadDecisions() {
      const { data } = await api.get<{ decisions: Decision[]; stats: IntegrationStats }>(
        '/integration/decisions'
      )
      this.decisions = data.decisions
      this.integrationStats = data.stats
    },
    async loadRagStatus() {
      try {
        const { data } = await api.get<RagStatus>('/rag/status')
        this.ragStatus = data
      } catch {
        this.ragStatus = null
      }
    },
  },
})
