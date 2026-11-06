import {
  DocumentItem,
  CollectionItem,
  ChatMessageItem,
  ResearchSessionItem,
  PaperComparisonResult,
  ResearchNoteItem,
  SystemSettings,
  UserUsage,
  CitationItem,
  ClaimItem,
  DocumentBatchResponse,
  StorageUsageResponse,
  LLMQuotaResponse,
  LLMQuotaConfigUpdate,
  LLMQuestionBudgetEstimate,
  User,
  AuthLoginPayload,
  AuthRegisterPayload,
  AuthSessionResponse,
  AdminOverviewResponse,
  AdminUserListResponse,
  AdminUserDetailResponse,
  AdminTimeSeriesPoint,
  AdminLoginTimeSeriesPoint,
  AdminDailyAIUsagePoint,
  AdminSystemHealth,
  UserSessionItem,
  DemoPaperItem,
  DemoPageResponse,
  DemoExampleQuestion,
  DemoCitation,
  DemoAskRequest,
  DemoAskResponse,
  DemoStatusResponse,
} from '../types';

const VITE_API_URL = (import.meta.env?.VITE_API_BASE_URL as string | undefined) || '';
const API_BASE = VITE_API_URL ? `${VITE_API_URL.replace(/\/$/, '')}/api/v1` : '/api/v1';

class ApiClient {
  private token: string | null = null;
  private userId: string = '';
  private csrfToken: string | null = null;

  setAuth(token: string | null, userId?: string) {
    this.token = token;
    if (userId !== undefined) this.userId = userId;
  }

  setCsrfToken(csrf: string | null) {
    this.csrfToken = csrf;
    if (typeof document !== 'undefined') {
      if (csrf) {
        document.cookie = `orion_csrf=${encodeURIComponent(csrf)}; path=/; SameSite=Lax`;
      } else {
        document.cookie = 'orion_csrf=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax; path=/';
      }
    }
  }

  getCsrfToken(): string | null {
    // 1. Read directly from the browser's document.cookie first to prevent using stale tokens
    if (typeof document !== 'undefined') {
      const match = document.cookie.match(/(?:^|;\s*)orion_csrf=([^;]+)/);
      if (match) {
        const raw = decodeURIComponent(match[1].trim());
        return raw.replace(/^"(.*)"$/, '$1');
      }
    }
    // 2. Fall back to cached token for non-browser or test environments
    return this.csrfToken;
  }

  getUserId(): string {
    return this.userId;
  }

  getHeaders(customHeaders: Record<string, string> = {}, isMutation: boolean = false): Record<string, string> {
    const headers: Record<string, string> = {
      ...customHeaders,
    };
    if (this.userId) {
      headers['X-User-Id'] = this.userId;
    }
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    // Always include CSRF token if available, or if explicitly requested as mutation
    const csrf = this.getCsrfToken();
    if (csrf) {
      headers['X-CSRF-Token'] = csrf;
    }
    return headers;
  }

  private async handleResponse<T>(res: Response): Promise<T> {
    if (!res.ok) {
      let errorDetail = 'API request failed';
      try {
        const errorJson = await res.json();
        errorDetail = errorJson.detail || errorJson.error || errorDetail;
      } catch {
        errorDetail = res.statusText || errorDetail;
      }
      throw new Error(errorDetail);
    }
    if (res.status === 204) {
      return {} as T;
    }
    return res.json();
  }

  // --- Documents API ---

  async listDocuments(params?: { collection_id?: string; status?: string; search?: string }): Promise<{ total: number; items: DocumentItem[] }> {
    const query = new URLSearchParams();
    if (params?.collection_id) query.append('collection_id', params.collection_id);
    if (params?.status) query.append('status', params.status);
    if (params?.search) query.append('search', params.search);

    const res = await fetch(`${API_BASE}/documents?${query.toString()}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async getDocument(documentId: string): Promise<DocumentItem> {
    const res = await fetch(`${API_BASE}/documents/${documentId}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async getStorageUsage(): Promise<StorageUsageResponse> {
    const res = await fetch(`${API_BASE}/documents/storage-usage`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async uploadDocument(file: File, collectionId?: string): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append('file', file);

    const query = collectionId ? `?collection_id=${encodeURIComponent(collectionId)}` : '';
    const res = await fetch(`${API_BASE}/documents${query}`, {
      method: 'POST',
      headers: this.getHeaders({}, true),
      credentials: 'include',
      body: formData,
    });
    return this.handleResponse(res);
  }

  async uploadDocumentsBatch(files: File[], collectionId?: string): Promise<DocumentBatchResponse> {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }

    const query = collectionId ? `?collection_id=${encodeURIComponent(collectionId)}` : '';
    const res = await fetch(`${API_BASE}/documents/batch${query}`, {
      method: 'POST',
      headers: this.getHeaders({}, true),
      credentials: 'include',
      body: formData,
    });
    return this.handleResponse(res);
  }

  async getDocumentStatus(documentId: string): Promise<{
    id: string;
    status: DocumentItem['status'];
    progress_percentage: number;
    page_count: number;
    chunk_count: number;
    error?: string;
    warnings: string[];
  }> {
    const res = await fetch(`${API_BASE}/documents/${documentId}/status`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async getDocumentPage(documentId: string, pageNumber: number): Promise<{
    document_id: string;
    page_number: number;
    text: string;
    character_count: number;
    word_count: number;
    has_text: boolean;
  }> {
    const res = await fetch(`${API_BASE}/documents/${documentId}/pages/${pageNumber}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  getDocumentFileUrl(documentId: string): string {
    return `${API_BASE}/documents/${documentId}/file`;
  }

  getDocumentPageRenderUrl(documentId: string, pageNumber: number, dpi: number = 150): string {
    return `${API_BASE}/documents/${documentId}/pages/${pageNumber}/render?dpi=${dpi}`;
  }

  async getDocumentFileBlob(documentId: string): Promise<Blob> {
    const res = await fetch(this.getDocumentFileUrl(documentId), {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    if (!res.ok) {
      throw new Error(`Failed to load PDF file: ${res.statusText}`);
    }
    return res.blob();
  }

  async deleteDocument(documentId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${documentId}`, {
      method: 'DELETE',
      headers: this.getHeaders({}, true),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async retryIngestion(documentId: string): Promise<DocumentItem> {
    const res = await fetch(`${API_BASE}/documents/${documentId}/retry`, {
      method: 'POST',
      headers: this.getHeaders({}, true),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  // --- Collections API ---

  async listCollections(): Promise<{ total: number; items: CollectionItem[] }> {
    const res = await fetch(`${API_BASE}/collections`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async createCollection(name: string, description?: string): Promise<CollectionItem> {
    const res = await fetch(`${API_BASE}/collections`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ name, description }),
    });
    return this.handleResponse(res);
  }

  async deleteCollection(collectionId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/collections/${collectionId}`, {
      method: 'DELETE',
      headers: this.getHeaders({}, true),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  // --- Research Q&A & Sessions API ---

  async askQuestion(params: {
    question: string;
    document_ids?: string[];
    collection_id?: string;
    session_id?: string;
    top_k?: number;
    enable_reranking?: boolean;
  }): Promise<{
    answer: string;
    claims: ClaimItem[];
    citations: CitationItem[];
    insufficient_evidence: boolean;
    reason_code?: string;
    trace_id?: string;
    diagnostics?: any;
    warnings: string[];
    session_id?: string;
    message_id?: string;
    latency_ms: Record<string, number>;
    model?: string | null;
    answer_path?: 'gemini' | 'deterministic_fallback';
    fallback_reason?: 'QUOTA' | 'MODEL_NOT_FOUND' | 'BAD_KEY' | 'KEY_NOT_LOADED' | 'NETWORK' | 'UNAVAILABLE' | 'OTHER' | null;
  }> {
    const res = await fetch(`${API_BASE}/research/ask`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify(params),
    });
    return this.handleResponse(res);
  }

  async comparePapers(documentIds: string[]): Promise<PaperComparisonResult> {
    const res = await fetch(`${API_BASE}/research/compare`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ document_ids: documentIds }),
    });
    return this.handleResponse(res);
  }

  async listSessions(): Promise<{ total: number; items: ResearchSessionItem[] }> {
    const res = await fetch(`${API_BASE}/research/sessions`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async createSession(title: string = 'New Research Session'): Promise<ResearchSessionItem> {
    const res = await fetch(`${API_BASE}/research/sessions`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ title }),
    });
    return this.handleResponse(res);
  }

  async getSession(sessionId: string): Promise<ResearchSessionItem & { messages: ChatMessageItem[] }> {
    const res = await fetch(`${API_BASE}/research/sessions/${sessionId}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async deleteSession(sessionId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/research/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: this.getHeaders({}, true),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  // --- Notes API ---

  async listNotes(): Promise<{ total: number; items: ResearchNoteItem[] }> {
    const res = await fetch(`${API_BASE}/notes`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async createNote(note: {
    title: string;
    content: string;
    source_citations?: CitationItem[];
    session_id?: string;
  }): Promise<ResearchNoteItem> {
    const res = await fetch(`${API_BASE}/notes`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify(note),
    });
    return this.handleResponse(res);
  }

  async deleteNote(noteId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/notes/${noteId}`, {
      method: 'DELETE',
      headers: this.getHeaders({}, true),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async exportNote(noteId: string): Promise<{ note_id: string; title: string; markdown_content: string; filename: string }> {
    const res = await fetch(`${API_BASE}/notes/${noteId}/export`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  // --- Settings & Usage ---

  async getSettings(): Promise<SystemSettings> {
    const res = await fetch(`${API_BASE}/settings`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async getUsage(): Promise<UserUsage> {
    const res = await fetch(`${API_BASE}/usage`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  // --- LLM Quota & Budget Manager ---

  async getLlmQuota(): Promise<LLMQuotaResponse> {
    const res = await fetch(`${API_BASE}/settings/llm-quota`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  async updateLlmQuota(updates: LLMQuotaConfigUpdate): Promise<LLMQuotaResponse> {
    const res = await fetch(`${API_BASE}/settings/llm-quota`, {
      method: 'PUT',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify(updates),
    });
    return this.handleResponse(res);
  }

  async getLlmQuotaEstimate(): Promise<LLMQuestionBudgetEstimate> {
    const res = await fetch(`${API_BASE}/settings/llm-quota/estimate`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse(res);
  }

  // --- Auth API ---

  async register(payload: AuthRegisterPayload): Promise<AuthSessionResponse> {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    const data = await this.handleResponse<AuthSessionResponse>(res);
    if (data.csrf_token) this.setCsrfToken(data.csrf_token);
    if (data.access_token) this.token = data.access_token;
    if (data.user?.id) this.userId = data.user.id;
    return data;
  }

  async login(payload: AuthLoginPayload): Promise<AuthSessionResponse> {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    const data = await this.handleResponse<AuthSessionResponse>(res);
    if (data.csrf_token) this.setCsrfToken(data.csrf_token);
    if (data.access_token) this.token = data.access_token;
    if (data.user?.id) this.userId = data.user.id;
    return data;
  }

  async getMe(): Promise<User> {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    const csrfHeader = res.headers.get('X-CSRF-Token');
    if (csrfHeader) {
      this.setCsrfToken(csrfHeader);
    }
    const user = await this.handleResponse<User>(res);
    if (user?.id) this.userId = user.id;
    return user;
  }

  async logout(): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      headers: this.getHeaders({}, true),
      credentials: 'include',
    });
    this.token = null;
    this.setCsrfToken(null);
    return this.handleResponse<{ message: string }>(res);
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE}/auth/change-password`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    return this.handleResponse<{ message: string }>(res);
  }

  async updateProfile(data: { display_name?: string; institution?: string }): Promise<User> {
    const res = await fetch(`${API_BASE}/auth/profile`, {
      method: 'PATCH',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify(data),
    });
    return this.handleResponse<User>(res);
  }

  async listAuthSessions(): Promise<UserSessionItem[]> {
    const res = await fetch(`${API_BASE}/auth/sessions`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<UserSessionItem[]>(res);
  }

  async revokeOtherSessions(): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE}/auth/sessions/revoke-others`, {
      method: 'POST',
      headers: this.getHeaders({}, true),
      credentials: 'include',
    });
    return this.handleResponse<{ message: string }>(res);
  }

  // --- Research Access Requests & Invitation Redemption ---

  async submitAccessRequest(payload: {
    institution?: string;
    research_purpose: string;
    intended_data_types?: string;
  }): Promise<any> {
    const res = await fetch(`${API_BASE}/auth/access-request`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    return this.handleResponse<any>(res);
  }

  async getOwnAccessRequest(): Promise<any> {
    const res = await fetch(`${API_BASE}/auth/access-request`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<any>(res);
  }

  async redeemInvitation(invitationToken: string): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE}/auth/invitations/redeem`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, false),
      credentials: 'include',
      body: JSON.stringify({ invitation_token: invitationToken }),
    });
    return this.handleResponse<{ message: string }>(res);
  }

  // --- Admin Dashboard & Researcher Analytics ---

  async getAdminOverview(): Promise<AdminOverviewResponse> {
    const res = await fetch(`${API_BASE}/admin/overview`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<AdminOverviewResponse>(res);
  }

  async getAdminUsers(params: {
    search?: string;
    status?: string;
    role?: string;
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: string;
  } = {}): Promise<AdminUserListResponse> {
    const query = new URLSearchParams();
    if (params.search) query.set('search', params.search);
    if (params.status) query.set('status', params.status);
    if (params.role) query.set('role', params.role);
    if (params.page) query.set('page', String(params.page));
    if (params.page_size) query.set('page_size', String(params.page_size));
    if (params.sort_by) query.set('sort_by', params.sort_by);
    if (params.sort_order) query.set('sort_order', params.sort_order);

    const qs = query.toString();
    const url = `${API_BASE}/admin/users${qs ? `?${qs}` : ''}`;
    const res = await fetch(url, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<AdminUserListResponse>(res);
  }

  async getAdminUserDetail(userId: string): Promise<AdminUserDetailResponse> {
    const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<AdminUserDetailResponse>(res);
  }

  async getAdminUserActivity(userId: string, limit: number = 25): Promise<any[]> {
    const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}/activity?limit=${limit}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<any[]>(res);
  }

  async getAdminUserUsage(userId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}/usage`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<any>(res);
  }

  async getAdminRegistrationAnalytics(days: number = 30): Promise<AdminTimeSeriesPoint[]> {
    const res = await fetch(`${API_BASE}/admin/analytics/registrations?days=${days}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<AdminTimeSeriesPoint[]>(res);
  }

  async getAdminLoginAnalytics(days: number = 30): Promise<AdminLoginTimeSeriesPoint[]> {
    const res = await fetch(`${API_BASE}/admin/analytics/logins?days=${days}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<AdminLoginTimeSeriesPoint[]>(res);
  }

  async getAdminDocumentAnalytics(days: number = 30): Promise<AdminTimeSeriesPoint[]> {
    const res = await fetch(`${API_BASE}/admin/analytics/documents?days=${days}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<AdminTimeSeriesPoint[]>(res);
  }

  async getAdminAIUsageAnalytics(days: number = 30): Promise<AdminDailyAIUsagePoint[]> {
    const res = await fetch(`${API_BASE}/admin/analytics/ai-usage?days=${days}`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<AdminDailyAIUsagePoint[]>(res);
  }

  async getAdminSystemHealth(): Promise<AdminSystemHealth> {
    const res = await fetch(`${API_BASE}/admin/system-health`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<AdminSystemHealth>(res);
  }

  // --- Admin Access Request & Invitation Management ---

  async getAdminAccessRequests(statusFilter?: string): Promise<any[]> {
    const url = `${API_BASE}/admin/access-requests${statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : ''}`;
    const res = await fetch(url, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<any[]>(res);
  }

  async approveAccessRequest(requestId: string, expiresInDays: number = 7): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/access-requests/${encodeURIComponent(requestId)}/approve`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ expires_in_days: expiresInDays }),
    });
    return this.handleResponse<any>(res);
  }

  async rejectAccessRequest(requestId: string, reason: string): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/access-requests/${encodeURIComponent(requestId)}/reject`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ reason }),
    });
    return this.handleResponse<any>(res);
  }

  async getAdminInvitations(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/admin/invitations`, {
      headers: this.getHeaders(),
      credentials: 'include',
    });
    return this.handleResponse<any[]>(res);
  }

  async createAdminInvitation(userId: string, expiresInDays: number = 7): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/invitations`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ user_id: userId, expires_in_days: expiresInDays }),
    });
    return this.handleResponse<any>(res);
  }

  async deleteAdminInvitation(invitationId: string): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE}/admin/invitations/${encodeURIComponent(invitationId)}`, {
      method: 'DELETE',
      headers: this.getHeaders({}, true),
      credentials: 'include',
    });
    return this.handleResponse<{ message: string }>(res);
  }

  async revokeUserAccess(userId: string, reason?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}/revoke`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ reason }),
    });
    return this.handleResponse<any>(res);
  }

  async reactivateUserAccess(userId: string, reason?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}/reactivate`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ reason }),
    });
    return this.handleResponse<any>(res);
  }

  async directActivateUser(userId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}/direct-activate`, {
      method: 'POST',
      headers: this.getHeaders({}, true),
      credentials: 'include',
    });
    return this.handleResponse<any>(res);
  }

  async updateUserRole(userId: string, role: string): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}/role`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }, true),
      credentials: 'include',
      body: JSON.stringify({ role }),
    });
    return this.handleResponse<any>(res);
  }

  // ==========================================
  // Public Demo Mode APIs (Strictly Isolated)
  // ==========================================

  async getDemoStatus(): Promise<DemoStatusResponse> {
    const res = await fetch(`${API_BASE}/demo/status`);
    return this.handleResponse<DemoStatusResponse>(res);
  }

  async getDemoPapers(): Promise<DemoPaperItem[]> {
    const res = await fetch(`${API_BASE}/demo/papers`);
    return this.handleResponse<DemoPaperItem[]>(res);
  }

  async getDemoPaper(documentId: string): Promise<DemoPaperItem> {
    const res = await fetch(`${API_BASE}/demo/papers/${encodeURIComponent(documentId)}`);
    return this.handleResponse<DemoPaperItem>(res);
  }

  getDemoPaperPdfUrl(documentId: string): string {
    return `${API_BASE}/demo/papers/${encodeURIComponent(documentId)}/pdf`;
  }

  async getDemoPaperPage(documentId: string, pageNumber: number): Promise<DemoPageResponse> {
    const res = await fetch(`${API_BASE}/demo/papers/${encodeURIComponent(documentId)}/pages/${pageNumber}`);
    return this.handleResponse<DemoPageResponse>(res);
  }

  async getDemoExamples(): Promise<DemoExampleQuestion[]> {
    const res = await fetch(`${API_BASE}/demo/examples`);
    return this.handleResponse<DemoExampleQuestion[]>(res);
  }

  async askDemoQuestion(question: string, documentIds?: string[]): Promise<DemoAskResponse> {
    const res = await fetch(`${API_BASE}/demo/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, document_ids: documentIds }),
    });
    return this.handleResponse<DemoAskResponse>(res);
  }
}

export const api = new ApiClient();
