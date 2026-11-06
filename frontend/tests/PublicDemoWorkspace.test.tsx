import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import App from '../src/App';
import { AuthProvider } from '../src/context/AuthContext';
import { PublicDemoWorkspace } from '../src/features/demo/PublicDemoWorkspace';
import { DemoPdfViewer } from '../src/features/demo/DemoPdfViewer';
import { api } from '../src/services/api';
import {
  DemoPaperItem,
  DemoExampleQuestion,
  DemoAskResponse,
  DemoStatusResponse,
} from '../src/types';

const mockDemoPapers: DemoPaperItem[] = [
  {
    id: 'demo_doc_s40726_epr',
    filename: 's40726-025-00392-4.pdf',
    title: 'Current State of Extended Producer Responsibility in Waste Management',
    authors: 'Schuch, R., Schmidt, M., & Weber, K.',
    year: 2025,
    journal: 'Current Pollution Reports',
    doi: '10.1007/s40726-025-00392-4',
    license: 'CC BY 4.0',
    license_url: 'https://creativecommons.org/licenses/by/4.0/',
    abstract: 'Overview of EPR across European waste management.',
    total_pages: 5,
    file_size_bytes: 18500,
  },
  {
    id: 'demo_doc_shukla_epr',
    filename: 'Saurabh Shukla.pdf',
    title: 'Plastic Waste Management Rules and Extended Producer Responsibility in Emerging Economies',
    authors: 'Shukla, S., et al.',
    year: 2022,
    journal: 'Environmental Pollution',
    doi: '10.1016/j.envpol.2022.109842',
    license: 'CC BY 4.0',
    license_url: 'https://creativecommons.org/licenses/by/4.0/',
    abstract: 'Field analysis of EPR in India.',
    total_pages: 4,
    file_size_bytes: 16000,
  },
  {
    id: 'demo_doc_somantri_epr',
    filename: 'Somantri.pdf',
    title: 'A Data-Driven Information Platform for Extended Producer Responsibility Compliance',
    authors: 'Somantri, A., & Budiman, C.',
    year: 2022,
    journal: 'Journal of Cleaner Production',
    doi: '10.1016/j.jclepro.2022.133215',
    license: 'CC BY 4.0',
    license_url: 'https://creativecommons.org/licenses/by/4.0/',
    abstract: 'Platform architecture connecting informal collectors.',
    total_pages: 4,
    file_size_bytes: 17200,
  },
  {
    id: 'demo_doc_garcia_epr',
    filename: 'Rita Garcia.pdf',
    title: 'Extended Producer Responsibility Schemes for Packaging in the European Union',
    authors: 'Garcia, R., Marques, R. C., & Cunha Marques, I.',
    year: 2020,
    journal: 'Resources, Conservation and Recycling',
    doi: '10.1016/j.resconrec.2020.104921',
    license: 'CC BY 4.0',
    license_url: 'https://creativecommons.org/licenses/by/4.0/',
    abstract: 'Comparative analysis across Belgium, Germany, France, and Portugal.',
    total_pages: 5,
    file_size_bytes: 19400,
  },
];

const mockDemoExamples: DemoExampleQuestion[] = [
  {
    id: 'ex_01',
    question: 'What is Extended Producer Responsibility (EPR) and what is its primary objective?',
    category: 'Policy Foundations',
    description: 'Explores environmental economics rationale of EPR.',
    target_papers: ['demo_doc_s40726_epr', 'demo_doc_shukla_epr'],
  },
  {
    id: 'ex_02',
    question: 'What are the key policy instruments used to implement Extended Producer Responsibility?',
    category: 'Instrument Design',
    description: 'Examines take-back mandates, deposit-refund mechanisms, and modulated fees.',
    target_papers: ['demo_doc_s40726_epr', 'demo_doc_garcia_epr'],
  },
];

const mockStatusResponse: DemoStatusResponse = {
  enabled: true,
  total_papers: 4,
  daily_budget_total: 200,
  daily_budget_remaining: 185,
  visitor_daily_limit: 20,
  ip_rate_limit_per_minute: 5,
};

describe('Public Demo Frontend Integration Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.location.hash = '';

    // Mock API defaults
    vi.spyOn(api, 'getMe').mockRejectedValue(new Error('Unauthenticated'));
    vi.spyOn(api, 'getDemoStatus').mockResolvedValue(mockStatusResponse);
    vi.spyOn(api, 'getDemoPapers').mockResolvedValue(mockDemoPapers);
    vi.spyOn(api, 'getDemoExamples').mockResolvedValue(mockDemoExamples);
  });

  it('renders dual-mode landing page with Option A (Demo) and Option B (Private Workspace)', async () => {
    render(<App />);

    await waitFor(() => {
      // Option A: Public Demo Gateway
      expect(screen.getAllByText('Explore Public Demo').length).toBeGreaterThan(0);
      expect(screen.getByText('Launch Public Demo Workspace')).toBeDefined();
      expect(screen.getByText(/No Login Required/i)).toBeDefined();

      // Option B: Private Authentication
      expect(screen.getByText('Enter your orbit')).toBeDefined();
      expect(screen.getByRole('tab', { name: 'Sign in' })).toBeDefined();
      expect(screen.getByRole('tab', { name: 'Create account' })).toBeDefined();
    });
  });

  it('transitions into Public Demo Workspace when clicking Option A', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Launch Public Demo Workspace')).toBeDefined();
    });

    fireEvent.click(screen.getByText('Launch Public Demo Workspace'));

    // Verify Public Demo Workspace appears
    await waitFor(() => {
      expect(screen.getByText('PUBLIC DEMO MODE')).toBeDefined();
      expect(screen.getByText(/4 Curated EPR Papers/i)).toBeDefined();
      expect(screen.getByText(/Explore Public Research Intelligence/i)).toBeDefined();
      expect(screen.getByText('Sign In to Private')).toBeDefined();
    });
  });

  it('lists the 4 curated open-access papers and suggested questions in demo workspace', async () => {
    render(
      <PublicDemoWorkspace
        onExitDemo={vi.fn()}
        onOpenLogin={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Current State of Extended Producer Responsibility in Waste Management')).toBeDefined();
      expect(screen.getByText('A Data-Driven Information Platform for Extended Producer Responsibility Compliance')).toBeDefined();
      expect(screen.getAllByText('Policy Foundations').length).toBeGreaterThan(0);
      expect(screen.getAllByText(/What is Extended Producer Responsibility/i).length).toBeGreaterThan(0);
    });
  });

  it('executes evidence-grounded demo Q&A and renders citations and grounding badge', async () => {
    const mockAnswerResponse: DemoAskResponse = {
      answer: 'Extended Producer Responsibility transfers post-consumer lifecycle costs to manufacturers.',
      citations: [
        {
          document_id: 'demo_doc_s40726_epr',
          filename: 's40726-025-00392-4.pdf',
          paper_title: 'Current State of Extended Producer Responsibility in Waste Management',
          page_number: 1,
          exact_passage: 'First formally conceptualized by Thomas Lindhqvist in 1990.',
          relevance_score: 0.98,
        },
      ],
      grounding_score: 0.98,
      is_cached: true,
      insufficient_evidence: false,
      trace_id: 'demo_test_123',
      latency_ms: 12.5,
      selected_papers: ['demo_doc_s40726_epr'],
    };

    vi.spyOn(api, 'askDemoQuestion').mockResolvedValue(mockAnswerResponse);

    render(
      <PublicDemoWorkspace
        onExitDemo={vi.fn()}
        onOpenLogin={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Ask a question on Extended Producer Responsibility/i)).toBeDefined();
    });

    const textarea = screen.getByPlaceholderText(/Ask a question on Extended Producer Responsibility/i);
    fireEvent.change(textarea, { target: { value: 'What is EPR?' } });
    fireEvent.click(screen.getByLabelText('Send Inquiry'));

    await waitFor(() => {
      expect(api.askDemoQuestion).toHaveBeenCalledWith('What is EPR?', undefined);
      expect(screen.getByText(/transfers post-consumer lifecycle costs/i)).toBeDefined();
      expect(screen.getByText('⚡ Verified Cache')).toBeDefined();
      expect(screen.getByText('98% Grounded')).toBeDefined();
      expect(screen.getByText(/First formally conceptualized by Thomas Lindhqvist/i)).toBeDefined();
      expect(screen.getByText('Inspect Source Page →')).toBeDefined();
    });
  });

  it('opens DemoPdfViewer on citation click with highlighted passage and page text', async () => {
    vi.spyOn(api, 'getDemoPaperPage').mockResolvedValue({
      document_id: 'demo_doc_s40726_epr',
      page_number: 2,
      total_pages: 5,
      text: 'The theoretical underpinning rests on the polluter-pays principle.',
      has_content: true,
    });

    render(
      <DemoPdfViewer
        paper={mockDemoPapers[0]}
        initialPage={2}
        highlightPassage="polluter-pays principle"
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Current State of Extended Producer Responsibility in Waste Management')).toBeDefined();
      expect(screen.getByText(/polluter-pays principle/i)).toBeDefined();
      expect(screen.getByText('Verified Ground Truth Text')).toBeDefined();
      expect(screen.getByText('Extracted Text')).toBeDefined();
      expect(screen.getByText('PDF Binary')).toBeDefined();
    });
  });

  it('displays offline fallback when public demo feature flag is disabled', async () => {
    vi.spyOn(api, 'getDemoStatus').mockResolvedValue({
      enabled: false,
      total_papers: 0,
      daily_budget_total: 0,
      daily_budget_remaining: 0,
      visitor_daily_limit: 0,
      ip_rate_limit_per_minute: 0,
    });

    render(
      <PublicDemoWorkspace
        onExitDemo={vi.fn()}
        onOpenLogin={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Public Demo Offline')).toBeDefined();
      expect(screen.getByText('Sign In to Private Workspace')).toBeDefined();
    });
  });

  it('exits demo mode back to landing page when clicking Exit Demo', async () => {
    const handleExit = vi.fn();
    render(
      <PublicDemoWorkspace
        onExitDemo={handleExit}
        onOpenLogin={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Exit Demo')).toBeDefined();
    });

    fireEvent.click(screen.getByText('Exit Demo'));
    expect(handleExit).toHaveBeenCalledTimes(1);
  });
});

