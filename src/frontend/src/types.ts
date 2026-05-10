export interface TextbookMeta {
  textbook_id: string
  filename: string
  title: string
  total_pages: number
  total_chars: number
  chapter_count: number
  status: 'parsing' | 'parsed' | 'extracting' | 'ready' | 'failed'
  error?: string
}

export interface KnowledgeNode {
  id: string
  name: string
  definition: string
  category: string
  chapter: string
  page: number
  source_book: string
}

export interface Relation {
  source: string
  target: string
  relation_type: 'prerequisite' | 'parallel' | 'contains' | 'applies_to'
  description: string
}

export interface BookGraph {
  book_id: string
  book_title: string
  nodes: KnowledgeNode[]
  edges: Relation[]
}

export interface Decision {
  decision_id: string
  action: 'merge' | 'keep' | 'remove'
  affected_nodes: string[]
  result_node: string
  reason: string
  confidence: number
}

export interface IntegrationStats {
  orig_books: number
  orig_chars: number
  final_chars: number
  ratio: number
  orig_node_count: number
  final_node_count: number
  decisions_count: { merge: number; keep: number; remove: number }
}

export interface Citation {
  textbook: string
  chapter: string
  page: number
  relevance_score: number
}

export interface QAResponse {
  answer: string
  citations: Citation[]
  source_chunks: string[]
  latency_ms?: { retrieval: number; generation: number; total: number }
}

export interface SystemStats {
  token_stats: {
    requests: number
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    avg_latency_s: number
  }
  totals: {
    textbooks_uploaded: number
    parsed: number
    graphs: number
    total_nodes: number
    master_nodes: number
    master_edges: number
    total_chunks: number
    indexed_books: number
  }
  uptime_s: number
}

export interface RagStatus {
  indexed_books: number
  total_chunks: number
  books: string[]
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
}
