export interface User {
  id: string;
  email: string;
  role: string;
}

export interface DocumentItem {
  id: string;
  owner_id: string;
  filename: string;
  file_size: number;
  page_count: number;
  chunk_count: number;
  status: 'uploaded' | 'validating' | 'extracting' | 'chunking' | 'embedding' | 'indexing' | 'completed' | 'failed';
  processing_error?: string | null;
  extraction_warnings?: string[];
  created_at: string;
  updated_at: string;
}

export interface CollectionItem {
  id: string;
  owner_id: string;
  name: string;
  description?: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface CitationItem {
  citation_id: string;
  document_id: string;
  filename: string;
  page_numbers: number[];
  chunk_ids: string[];
  excerpt: string;
}

export interface ClaimItem {
  text: string;
  citation_ids: string[];
  support_status: 'supported' | 'partially_supported' | 'unsupported';
}

export interface ChatMessageItem {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  claims?: ClaimItem[];
  citations?: CitationItem[];
  insufficient_evidence?: boolean;
  warnings?: string[];
  latency_ms?: {
    retrieval?: number;
    generation?: number;
    total?: number;
  };
  created_at: string;
}

export interface ResearchSessionItem {
  id: string;
  owner_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ComparisonField {
  field_name: string;
  extracted_text: string;
  citations: CitationItem[];
  is_missing: boolean;
}

export interface ComparisonDocumentResult {
  document_id: string;
  filename: string;
  fields: Record<string, ComparisonField>;
}

export interface PaperComparisonResult {
  documents: ComparisonDocumentResult[];
  synthesis: string;
  contradictions: string[];
  research_gaps: string[];
  latency_ms: Record<string, number>;
}

export interface ResearchNoteItem {
  id: string;
  owner_id: string;
  session_id?: string;
  title: string;
  content: string;
  source_citations: CitationItem[];
  created_at: string;
  updated_at: string;
}

export interface SystemSettings {
  app_name: string;
  app_version: string;
  environment: string;
  active_gemini_model: string;
  active_embedding_model: string;
  embedding_dimensions: number;
  storage_provider: string;
  max_upload_size_mb: number;
  max_pdf_pages: number;
  chunk_size: number;
  chunk_overlap: number;
  retrieval_top_k: number;
  hybrid_fusion_alpha: number;
  reranker_enabled: boolean;
}

export interface UserUsage {
  user_id: string;
  document_count: number;
  completed_document_count: number;
  total_pages_ingested: number;
  total_chunks_indexed: number;
  total_storage_bytes: number;
  collection_count: number;
  session_count: number;
  note_count: number;
}
