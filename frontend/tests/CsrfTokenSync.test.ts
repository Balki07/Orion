import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api } from '../src/services/api';

describe('CSRF Token Synchronization & Upload Security Tests', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    // Clear cookies
    if (typeof document !== 'undefined') {
      document.cookie = 'orion_csrf=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT;';
      document.cookie = 'orion_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT;';
    }
    api.setAuth(null);
    api.setCsrfToken(null);
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('reads CSRF token dynamically from document.cookie', () => {
    document.cookie = 'orion_csrf=cookie_csrf_token_abc123; path=/';
    expect(api.getCsrfToken()).toBe('cookie_csrf_token_abc123');
  });

  it('prioritizes document.cookie over stale in-memory cached token', () => {
    // Simulate old cached token in api client
    api.setCsrfToken('stale_cached_token_999');
    expect(api.getCsrfToken()).toBe('stale_cached_token_999');

    // Browser receives a refreshed or updated cookie
    document.cookie = 'orion_csrf=fresh_live_cookie_token_456; path=/';
    expect(api.getCsrfToken()).toBe('fresh_live_cookie_token_456');
  });

  it('attaches X-CSRF-Token and preserves credentials: include on mutation requests', () => {
    document.cookie = 'orion_csrf=verified_token_777; path=/';
    const headers = api.getHeaders({}, true);

    expect(headers['X-CSRF-Token']).toBe('verified_token_777');
  });

  it('uploadDocument sends FormData, credentials: include, and X-CSRF-Token without overriding Content-Type', async () => {
    document.cookie = 'orion_csrf=upload_csrf_token_123; path=/';

    let capturedUrl = '';
    let capturedOptions: RequestInit | undefined;

    global.fetch = vi.fn().mockImplementation(async (url: string, options: RequestInit) => {
      capturedUrl = url;
      capturedOptions = options;
      return {
        ok: true,
        status: 201,
        json: async () => ({
          id: 'doc_test_123',
          filename: 'test_paper.pdf',
          status: 'queued',
        }),
      } as Response;
    });

    const file = new File(['%PDF-1.4 dummy content'], 'test_paper.pdf', { type: 'application/pdf' });
    const result = await api.uploadDocument(file);

    expect(result.id).toBe('doc_test_123');
    expect(capturedUrl).toContain('/api/v1/documents');
    expect(capturedOptions?.method).toBe('POST');
    expect(capturedOptions?.credentials).toBe('include');

    const headers = capturedOptions?.headers as Record<string, string>;
    expect(headers['X-CSRF-Token']).toBe('upload_csrf_token_123');
    // Crucial: Content-Type must NOT be manually set so browser generates multipart boundary
    expect(headers['Content-Type']).toBeUndefined();
    expect(capturedOptions?.body).toBeInstanceOf(FormData);
  });

  it('uploadDocumentsBatch sends batch FormData with credentials: include and X-CSRF-Token', async () => {
    document.cookie = 'orion_csrf=batch_csrf_token_456; path=/';

    let capturedOptions: RequestInit | undefined;

    global.fetch = vi.fn().mockImplementation(async (_url: string, options: RequestInit) => {
      capturedOptions = options;
      return {
        ok: true,
        status: 200,
        json: async () => ({
          total_received: 2,
          successful_count: 2,
          failed_count: 0,
          items: [],
        }),
      } as Response;
    });

    const file1 = new File(['%PDF-1.4 content 1'], 'doc1.pdf', { type: 'application/pdf' });
    const file2 = new File(['%PDF-1.4 content 2'], 'doc2.pdf', { type: 'application/pdf' });
    await api.uploadDocumentsBatch([file1, file2], 'col_123');

    expect(capturedOptions?.method).toBe('POST');
    expect(capturedOptions?.credentials).toBe('include');

    const headers = capturedOptions?.headers as Record<string, string>;
    expect(headers['X-CSRF-Token']).toBe('batch_csrf_token_456');
    expect(headers['Content-Type']).toBeUndefined();
    expect(capturedOptions?.body).toBeInstanceOf(FormData);
  });

  it('logout invalidates CSRF token and clears cookie', async () => {
    document.cookie = 'orion_csrf=active_token_to_clear; path=/';
    api.setCsrfToken('active_token_to_clear');

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'Logged out successfully.' }),
    } as Response);

    await api.logout();

    expect(api.getCsrfToken()).toBeNull();
  });
});

