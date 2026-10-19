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
} from '../types';

const API_BASE = '/api/v1';

class ApiClient {
  private token: string | null = null;
  private userId: string = 'user_dev_researcher_001';

  setAuth(token: string | null, userId?: string) {
    this.token = token;
    if (userId) this.userId = userId;
  }

  getUserId(): string {
    return this.userId;
  }

  private getHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
    const headers: Record<string, string> = {
      'X-User-Id': this.userId,
      ...customHeaders,
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
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
    });
    return this.handleResponse(res);
  }

  async getDocument(documentId: string): Promise<DocumentItem> {
    const res = await fetch(`${API_BASE}/documents/${documentId}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  async uploadDocument(file: File, collectionId?: string): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append('file', file);

    const query = collectionId ? `?collection_id=${encodeURIComponent(collectionId)}` : '';
    const res = await fetch(`${API_BASE}/documents${query}`, {
      method: 'POST',
      headers: this.getHeaders(),
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
    });
    return this.handleResponse(res);
  }

  async deleteDocument(documentId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${documentId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  async retryIngestion(documentId: string): Promise<DocumentItem> {
    const res = await fetch(`${API_BASE}/documents/${documentId}/retry`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  // --- Collections API ---

  async listCollections(): Promise<{ total: number; items: CollectionItem[] }> {
    const res = await fetch(`${API_BASE}/collections`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  async createCollection(name: string, description?: string): Promise<CollectionItem> {
    const res = await fetch(`${API_BASE}/collections`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ name, description }),
    });
    return this.handleResponse(res);
  }

  async deleteCollection(collectionId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/collections/${collectionId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
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
    warnings: string[];
    session_id?: string;
    message_id?: string;
    latency_ms: Record<string, number>;
  }> {
    const res = await fetch(`${API_BASE}/research/ask`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(params),
    });
    return this.handleResponse(res);
  }

  async comparePapers(documentIds: string[]): Promise<PaperComparisonResult> {
    const res = await fetch(`${API_BASE}/research/compare`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ document_ids: documentIds }),
    });
    return this.handleResponse(res);
  }

  async listSessions(): Promise<{ total: number; items: ResearchSessionItem[] }> {
    const res = await fetch(`${API_BASE}/research/sessions`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  async createSession(title: string = 'New Research Session'): Promise<ResearchSessionItem> {
    const res = await fetch(`${API_BASE}/research/sessions`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ title }),
    });
    return this.handleResponse(res);
  }

  async getSession(sessionId: string): Promise<ResearchSessionItem & { messages: ChatMessageItem[] }> {
    const res = await fetch(`${API_BASE}/research/sessions/${sessionId}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  async deleteSession(sessionId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/research/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  // --- Notes API ---

  async listNotes(): Promise<{ total: number; items: ResearchNoteItem[] }> {
    const res = await fetch(`${API_BASE}/notes`, {
      headers: this.getHeaders(),
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
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(note),
    });
    return this.handleResponse(res);
  }

  async deleteNote(noteId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/notes/${noteId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  async exportNote(noteId: string): Promise<{ note_id: string; title: string; markdown_content: string; filename: string }> {
    const res = await fetch(`${API_BASE}/notes/${noteId}/export`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  // --- Settings & Usage ---

  async getSettings(): Promise<SystemSettings> {
    const res = await fetch(`${API_BASE}/settings`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  async getUsage(): Promise<UserUsage> {
    const res = await fetch(`${API_BASE}/usage`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }
}

export const api = new ApiClient();
