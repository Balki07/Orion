export interface User {
  id: string;
  email: string;
  role: string;
  access_status?: 'pending_request' | 'request_submitted' | 'approved_invitation_pending' | 'active' | 'rejected' | 'revoked';
  display_name?: string;
  institution?: string | null;
  status?: string;
  is_active?: boolean;
  created_at?: string;
}

export interface AccessRequestItem {
  id: string;
  user_id: string;
  user_email?: string | null;
  user_display_name?: string | null;
  institution?: string | null;
  research_purpose: string;
  intended_data_types?: string | null;
  status: 'pending' | 'approved' | 'rejected';
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvitationItem {
  id: string;
  user_id: string;
  user_email?: string | null;
  invitation_token?: string | null;
  expires_at: string;
  is_redeemed: boolean;
  redeemed_at?: string | null;
  created_at: string;
}

export interface AuthLoginPayload {
  email: string;
  password?: string;
}

export interface AuthRegisterPayload {
  email: string;
  password?: string;
  display_name: string;
  institution?: string | null;
}

export interface AuthSessionResponse {
  user: User;
  access_token: string;
  token_type: string;
  expires_in: number;
  csrf_token: string;
}

export interface UserSessionItem {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  expires_at: string;
  is_active: boolean;
  is_current: boolean;
}

export interface ResearchPreferences {
  preferredAnswerStyle: 'comprehensive' | 'concise' | 'bulleted';
  citationDisplayPreference: 'inline_chips' | 'footnotes' | 'provenance_drawer';
  defaultResearchScope: 'all_documents' | 'active_selection';
  defaultTopK: number;
}

export interface DocumentItem {
  id: string;
  owner_id: string;
  filename: string;
  file_size: number;
  page_count: number;
  chunk_count: number;
  status: 'queued' | 'uploaded' | 'processing' | 'validating' | 'extracting' | 'chunking' | 'embedding' | 'indexing' | 'ready' | 'completed' | 'failed';
  processing_error?: string | null;
  extraction_warnings?: string[];
  content_hash?: string | null;
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
  reason_code?: string;
  trace_id?: string;
  warnings?: string[];
  latency_ms?: {
    retrieval?: number;
    generation?: number;
    total?: number;
  };
  model?: string | null;
  answer_path?: 'gemini' | 'deterministic_fallback';
  fallback_reason?: 'QUOTA' | 'MODEL_NOT_FOUND' | 'BAD_KEY' | 'KEY_NOT_LOADED' | 'NETWORK' | 'UNAVAILABLE' | 'OTHER' | null;
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
  storage_mb_used?: number;
  storage_quota_mb?: number;
  storage_pct_used?: number;
  llm_queries_executed?: number;
  llm_tokens_consumed?: number;
  llm_prompt_tokens?: number;
  llm_completion_tokens?: number;
}

export interface BatchItemResult {
  filename: string;
  file_size: number;
  status: 'queued' | 'completed' | 'rejected';
  document?: DocumentItem | null;
  error?: string | null;
}

export interface DocumentBatchResponse {
  total: number;
  successful_count: number;
  failed_count: number;
  items: BatchItemResult[];
}

export interface StorageUsageResponse {
  total_quota_bytes: number;
  used_storage_bytes: number;
  remaining_storage_bytes: number;
  usage_percentage: number;
  document_count: number;
  quota_mb: number;
  total_storage_mb?: number;
  storage_quota_mb?: number;
  remaining_storage_mb?: number;
  quota_usage_percent?: number;
  quota_exceeded?: boolean;
  quota_warning?: boolean;
}

export interface LLMRollingUsage {
  rolling_60s_requests: number;
  rolling_60s_tokens: number;
  rpm_limit: number;
  tpm_limit: number;
  rpm_utilization_percent: number;
  tpm_utilization_percent: number;
}

export interface LLMDailyUsage {
  quota_timezone: string;
  today_start_utc: string;
  unique_questions_today: number;
  total_provider_attempts_today: number;
  successful_generations_today: number;
  failed_provider_attempts_today: number;
  fallback_events_today: number;
  prompt_tokens_today: number;
  completion_tokens_today: number;
  total_tokens_today: number;
  rpd_limit: number;
  rpd_utilization_percent: number;
}

export interface LLMQuotaResponse {
  model_id: string;
  is_active_model: boolean;
  is_reference_quota: boolean;
  quota_source_disclaimer: string;
  rpm_limit: number;
  tpm_limit: number;
  rpd_limit: number;
  quota_timezone: string;
  warning_threshold_percent: number;
  safety_margin_percent: number;
  last_updated_at: string;
  rolling_usage: LLMRollingUsage;
  daily_usage: LLMDailyUsage;
}

export interface LLMQuotaConfigUpdate {
  rpm_limit: number;
  tpm_limit: number;
  rpd_limit: number;
  quota_timezone: string;
  warning_threshold_percent: number;
  safety_margin_percent: number;
}

export interface LLMQuestionBudgetEstimate {
  model_id: string;
  is_active_model: boolean;
  daily_questions_remaining: number;
  daily_questions_typical: number;
  daily_questions_optimistic: number;
  daily_limiting_quota: string;
  immediate_questions_conservative: number;
  immediate_questions_typical: number;
  immediate_questions_optimistic: number;
  immediate_limiting_quota: string;
  estimated_questions_remaining: number;
  estimated_questions_typical: number;
  estimated_questions_optimistic: number;
  limiting_quota: string;
  rolling_questions_remaining: number;
  remaining_requests_today: number;
  remaining_tokens_today: number | null;
  rolling_requests_remaining: number;
  rolling_tokens_remaining: number;
  average_prompt_tokens: number;
  average_completion_tokens: number;
  average_total_tokens: number;
  attempts_per_question: number;
  sample_size: number;
  confidence: 'low' | 'medium' | 'high';
  is_fallback_estimate: boolean;
  safety_margin_percent: number;
  estimation_disclaimer: string;
}

export interface AdminUserOverviewStats {
  total_users: number;
  active_users_24h: number;
  active_users_7d: number;
  active_users_30d: number;
  new_users_today: number;
  new_users_this_week: number;
  new_users_this_month: number;
}

export interface AdminLoginOverviewStats {
  total_logins: number;
  logins_today: number;
  logins_this_week: number;
  failed_logins_today: number;
  failed_logins_total: number;
  unique_users_logged_in_7d: number;
}

export interface AdminDocumentOverviewStats {
  total_documents: number;
  total_storage_bytes: number;
  total_storage_mb: number;
  average_storage_per_user_mb: number;
  failed_documents: number;
  uploaded_today: number;
  uploaded_this_month: number;
}

export interface AdminAIModelBreakdown {
  model_name: string;
  request_count: number;
  total_tokens: number;
}

export interface AdminAIUsageOverviewStats {
  total_requests: number;
  requests_today: number;
  requests_this_month: number;
  total_prompt_tokens: number;
  total_response_tokens: number;
  total_tokens: number;
  failed_requests: number;
  estimated_cost_usd: number;
  models: AdminAIModelBreakdown[];
}

export interface AdminOverviewResponse {
  users: AdminUserOverviewStats;
  logins: AdminLoginOverviewStats;
  documents: AdminDocumentOverviewStats;
  ai_usage: AdminAIUsageOverviewStats;
  server_time: string;
}

export interface AdminUserSummary {
  id: string;
  email: string;
  display_name: string;
  institution?: string | null;
  status: string;
  is_active: boolean;
  role: string;
  access_status?: string;
  created_at: string;
  last_login_at?: string | null;
  login_count: number;
  document_count: number;
  storage_used_bytes: number;
  storage_used_mb: number;
  storage_quota_mb: number;
  ai_request_count: number;
  ai_total_tokens: number;
}

export interface AdminUserListResponse {
  users: AdminUserSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdminRecentLoginItem {
  id: string;
  event_type: string;
  success: boolean;
  ip_address?: string | null;
  user_agent?: string | null;
  failure_reason?: string | null;
  created_at: string;
}

export interface AdminUserDocumentSummary {
  id: string;
  title: string;
  file_size_bytes: number;
  status: string;
  created_at: string;
}

export interface AdminUserSessionSummary {
  id: string;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
  expires_at: string;
  is_active: boolean;
}

export interface AdminUserDetailResponse {
  user: AdminUserSummary;
  recent_logins: AdminRecentLoginItem[];
  recent_documents: AdminUserDocumentSummary[];
  active_sessions_count: number;
  recent_sessions: AdminUserSessionSummary[];
}

export interface AdminTimeSeriesPoint {
  date: string;
  count: number;
  extra?: Record<string, any> | null;
}

export interface AdminLoginTimeSeriesPoint {
  date: string;
  success_count: number;
  failure_count: number;
}

export interface AdminDailyAIUsagePoint {
  date: string;
  requests: number;
  tokens: number;
  estimated_cost_usd: number;
}

export interface AdminSystemHealth {
  status: string;
  environment: string;
  version: string;
  database: {
    healthy: boolean;
    dialect: string;
    pgvector_ready: boolean;
  };
  storage: {
    provider: string;
    user_quota_mb: number;
    ready: boolean;
  };
  ingestion: {
    durable_worker_enabled: boolean;
    concurrency: number;
    status: string;
  };
  gemini: {
    model: string;
    api_key_configured: boolean;
    rpm_limit: number;
    status: string;
  };
  timestamp: string;
}

// ==========================================
// Public Demo Mode Types
// ==========================================

export interface DemoPaperItem {
  id: string;
  filename: string;
  title: string;
  authors: string;
  year: number;
  journal: string;
  doi?: string | null;
  license: string;
  license_url: string;
  abstract: string;
  total_pages: number;
  file_size_bytes: number;
}

export interface DemoPageResponse {
  document_id: string;
  page_number: number;
  total_pages: number;
  text: string;
  has_content: boolean;
}

export interface DemoExampleQuestion {
  id: string;
  question: string;
  category: string;
  description: string;
  target_papers: string[];
}

export interface DemoCitation {
  document_id: string;
  filename: string;
  paper_title: string;
  page_number: number;
  exact_passage: string;
  relevance_score: number;
}

export interface DemoAskRequest {
  question: string;
  document_ids?: string[] | null;
}

export interface DemoAskResponse {
  answer: string;
  citations: DemoCitation[];
  grounding_score: number;
  is_cached: boolean;
  insufficient_evidence: boolean;
  trace_id: string;
  latency_ms: number;
  selected_papers: string[];
}

export interface DemoStatusResponse {
  enabled: boolean;
  total_papers: number;
  daily_budget_total: number;
  daily_budget_remaining: number;
  visitor_daily_limit: number;
  ip_rate_limit_per_minute: number;
}



