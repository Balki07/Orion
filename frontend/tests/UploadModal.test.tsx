import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { UploadModal } from '../src/features/documents/UploadModal';
import { api } from '../src/services/api';

describe('UploadModal Multi-Document Batch Upload Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const createDummyFile = (name: string, size: number, type = 'application/pdf') => {
    const file = new File(['%PDF-1.4 dummy content'], name, { type });
    Object.defineProperty(file, 'size', { value: size });
    return file;
  };

  it('renders modal with official heading and multi-file instructions', () => {
    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    expect(screen.getByText('Upload Research Papers')).toBeDefined();
    expect(
      screen.getByText(/Select or drop multiple technical PDFs/i)
    ).toBeDefined();
    expect(screen.getByText('No files selected')).toBeDefined();
  });

  it('supports selecting multiple valid PDFs simultaneously and displays total batch size', async () => {
    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    const file1 = createDummyFile('paper_alpha.pdf', 2 * 1024 * 1024);
    const file2 = createDummyFile('paper_beta.pdf', 3 * 1024 * 1024);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file1, file2] } });

    expect(screen.getByText('paper_alpha.pdf')).toBeDefined();
    expect(screen.getByText('paper_beta.pdf')).toBeDefined();
    expect(screen.getByText(/files selected \(5\.0 MB\)/i)).toBeDefined();
    expect(screen.getByText('Upload & Index 2 Papers')).toBeDefined();
  });

  it('validates invalid file types and oversized files', async () => {
    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    const textFile = createDummyFile('notes.txt', 1024, 'text/plain');
    const hugeFile = createDummyFile('huge_dataset.pdf', 35 * 1024 * 1024); // >32MB

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [textFile, hugeFile] } });

    expect(screen.getByText('Not a PDF (.pdf required)')).toBeDefined();
    expect(screen.getByText(/Exceeds 32.0 MB limit/i)).toBeDefined();

    // Button should be disabled because zero valid files exist
    const submitBtn = screen.getByRole('button', { name: /Upload & Index/i });
    expect(submitBtn.hasAttribute('disabled')).toBe(true);
  });

  it('allows removing individual files before ingestion', async () => {
    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    const file1 = createDummyFile('keep_me.pdf', 1024 * 1024);
    const file2 = createDummyFile('remove_me.pdf', 1024 * 1024);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file1, file2] } });

    expect(screen.getByText('remove_me.pdf')).toBeDefined();
    const removeBtn = screen.getByLabelText('Remove remove_me.pdf');
    fireEvent.click(removeBtn);

    expect(screen.queryByText('remove_me.pdf')).toBeNull();
    expect(screen.getByText('keep_me.pdf')).toBeDefined();
    expect(screen.getByText('Upload & Index 1 Paper')).toBeDefined();
  });

  it('allows clearing all files via Clear All action', async () => {
    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    const file1 = createDummyFile('doc1.pdf', 1024 * 1024);
    const file2 = createDummyFile('doc2.pdf', 1024 * 1024);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file1, file2] } });

    const clearAllBtn = screen.getByText('Clear All');
    fireEvent.click(clearAllBtn);

    expect(screen.queryByText('doc1.pdf')).toBeNull();
    expect(screen.getByText('No files selected')).toBeDefined();
  });

  it('prevents duplicate selections within a batch', async () => {
    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    const file1 = createDummyFile('unique.pdf', 1024 * 1024);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    // Add first time
    fireEvent.change(input, { target: { files: [file1] } });
    expect(screen.getByText('unique.pdf')).toBeDefined();

    // Add same file again
    fireEvent.change(input, { target: { files: [file1] } });
    expect(screen.getByText(/Ignored duplicate file/i)).toBeDefined();
  });

  it('supports drag-and-drop of multiple files into dropzone', async () => {
    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    const file1 = createDummyFile('drop1.pdf', 1024 * 1024);
    const file2 = createDummyFile('drop2.pdf', 2 * 1024 * 1024);

    const dropzone = screen.getByText(/Drag and drop your PDF research papers here/i).closest('div')!;
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file1, file2],
      },
    });

    expect(screen.getByText('drop1.pdf')).toBeDefined();
    expect(screen.getByText('drop2.pdf')).toBeDefined();
    expect(screen.getByText('Upload & Index 2 Papers')).toBeDefined();
  });

  it('submits batch and tracks processing states with live backend status', async () => {
    const onUploadSuccess = vi.fn();
    const uploadBatchSpy = vi.spyOn(api, 'uploadDocumentsBatch').mockResolvedValue({
      total: 2,
      successful_count: 2,
      failed_count: 0,
      items: [
        {
          filename: 'paper_one.pdf',
          file_size: 1024 * 1024,
          status: 'queued',
          document: {
            id: 'doc_101',
            owner_id: 'user_dev',
            filename: 'paper_one.pdf',
            file_size: 1024 * 1024,
            page_count: 10,
            chunk_count: 0,
            status: 'validating',
            created_at: '2026-10-20T10:00:00Z',
            updated_at: '2026-10-20T10:00:00Z',
          },
        },
        {
          filename: 'paper_two.pdf',
          file_size: 2 * 1024 * 1024,
          status: 'completed', // duplicate already indexed
          document: {
            id: 'doc_102',
            owner_id: 'user_dev',
            filename: 'paper_two.pdf',
            file_size: 2 * 1024 * 1024,
            page_count: 8,
            chunk_count: 24,
            status: 'completed',
            created_at: '2026-10-20T10:00:00Z',
            updated_at: '2026-10-20T10:00:00Z',
          },
        },
      ],
    });

    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={onUploadSuccess}
      />
    );

    const file1 = createDummyFile('paper_one.pdf', 1024 * 1024);
    const file2 = createDummyFile('paper_two.pdf', 2 * 1024 * 1024);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file1, file2] } });

    const submitBtn = screen.getByText('Upload & Index 2 Papers');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(uploadBatchSpy).toHaveBeenCalledWith([file1, file2], undefined);
    });

    // Check status renders
    await waitFor(() => {
      expect(screen.getByText('Indexed with citations')).toBeDefined();
    });
    expect(onUploadSuccess).toHaveBeenCalled();
  });

  it('handles partial batch failure and enables per-file retry', async () => {
    vi.spyOn(api, 'uploadDocumentsBatch').mockResolvedValue({
      total: 2,
      successful_count: 1,
      failed_count: 1,
      items: [
        {
          filename: 'success.pdf',
          file_size: 1024 * 1024,
          status: 'completed',
          document: {
            id: 'doc_success',
            owner_id: 'user_dev',
            filename: 'success.pdf',
            file_size: 1024 * 1024,
            page_count: 5,
            chunk_count: 15,
            status: 'completed',
            created_at: '2026-10-20T10:00:00Z',
            updated_at: '2026-10-20T10:00:00Z',
          },
        },
        {
          filename: 'failed_corrupt.pdf',
          file_size: 512,
          status: 'rejected',
          error: 'File content does not match standard PDF header signature',
        },
      ],
    });

    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    const file1 = createDummyFile('success.pdf', 1024 * 1024);
    const file2 = createDummyFile('failed_corrupt.pdf', 512);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file1, file2] } });

    fireEvent.click(screen.getByText('Upload & Index 2 Papers'));

    await waitFor(() => {
      expect(screen.getByText(/File content does not match/i)).toBeDefined();
    });

    expect(screen.getByText('Retry')).toBeDefined();
  });
});
