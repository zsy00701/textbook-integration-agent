"""统一数据模型(后端 Pydantic + 与前端 TS 对应)。"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ==================== 教材解析 ====================
class Chapter(BaseModel):
    chapter_id: str
    title: str
    page_start: int
    page_end: int
    content: str
    char_count: int


class TextbookDoc(BaseModel):
    textbook_id: str
    filename: str
    title: str
    total_pages: int
    total_chars: int
    chapters: list[Chapter]


class TextbookMeta(BaseModel):
    textbook_id: str
    filename: str
    title: str
    total_pages: int
    total_chars: int
    chapter_count: int
    status: Literal["parsing", "parsed", "extracting", "ready", "failed"]
    error: str | None = None


# ==================== 知识图谱 ====================
RelationType = Literal["prerequisite", "parallel", "contains", "applies_to"]


class KnowledgeNode(BaseModel):
    id: str
    name: str
    definition: str
    category: str = "核心概念"
    chapter: str
    page: int
    source_book: str  # textbook_id


class Relation(BaseModel):
    source: str
    target: str
    relation_type: RelationType
    description: str = ""


class BookGraph(BaseModel):
    book_id: str
    book_title: str
    nodes: list[KnowledgeNode]
    edges: list[Relation]


# ==================== 跨教材整合 ====================
class Decision(BaseModel):
    decision_id: str
    action: Literal["merge", "keep", "remove"]
    affected_nodes: list[str]
    result_node: str
    reason: str
    confidence: float


class IntegrationStats(BaseModel):
    orig_books: int
    orig_chars: int
    final_chars: int
    ratio: float
    orig_node_count: int
    final_node_count: int
    decisions_count: dict[str, int]  # {merge:.., keep:.., remove:..}


class IntegrationResult(BaseModel):
    master_graph: BookGraph
    decisions: list[Decision]
    stats: IntegrationStats


# ==================== RAG ====================
class Citation(BaseModel):
    textbook: str
    chapter: str
    page: int
    relevance_score: float


class QAResponse(BaseModel):
    answer: str
    citations: list[Citation]
    source_chunks: list[str]


class RagStatus(BaseModel):
    indexed_books: int
    total_chunks: int
    books: list[str]


# ==================== 多轮对话 ====================
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: float


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    decisions_changed: list[str] = []  # decision_id 列表
    history: list[ChatMessage]
