import React, { useState } from 'react';
import { PAPER_INKS, getPaperInk, getPaperInitial } from '../../utils/paperInks';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Chip } from '../../components/ui/Chip';
import { Tooltip } from '../../components/ui/Tooltip';
import { Skeleton } from '../../components/ui/Skeleton';
import { ThemeToggle } from '../../components/ui/ThemeToggle';
import { useTheme } from '../../context/ThemeContext';
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../../components/ui/Dialog';
import { BookOpen, ShieldCheck, AlertCircle, FileText, CheckCircle2, Bookmark, ExternalLink } from 'lucide-react';

export const DesignPreview: React.FC = () => {
  const { theme, resolvedTheme } = useTheme();
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const samplePapers = [
    { title: 'Rita Garcia.pdf', id: 'doc_1' },
    { title: 'Somantri.pdf', id: 'doc_2' },
    { title: 'Saurabh Shukla.pdf', id: 'doc_3' },
    { title: 'Mariana Gonçalves.pdf', id: 'doc_4' },
    { title: 'isi_31.07_22.pdf', id: 'doc_5' },
    { title: 's40726-025-00392-4.pdf', id: 'doc_6' },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 bg-paper-bg text-ink min-h-screen">
      <div className="max-w-5xl mx-auto space-y-10 pb-16">
        
        {/* Header Bar */}
        <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-6 border-b border-border-hairline gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs uppercase tracking-widest font-mono text-ink-muted">Design System</span>
              <Badge variant="verified">The Reading Room</Badge>
            </div>
            <h1 className="text-2xl sm:text-3xl font-serif font-medium tracking-tight text-ink">
              Design Tokens &amp; Component Kit
            </h1>
            <p className="text-sm text-ink-secondary mt-1">
              Warm, scholarly, calm aesthetic inspired by quiet academic archives. No purple gradients, no stock sparkles.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-ink-secondary">Theme: {theme} ({resolvedTheme})</span>
            <ThemeToggle />
          </div>
        </header>

        {/* 1. Theme Color Tokens */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-reading-primary" />
            <h2 className="text-lg font-semibold font-sans">1. Semantic Theme Tokens ({resolvedTheme === 'dark' ? 'Midnight Library' : 'Paper'})</h2>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
            <Card className="p-3 text-center space-y-1.5 bg-paper-bg">
              <div className="h-10 rounded border border-border-hairline bg-paper-bg shadow-inner flex items-center justify-center text-xs font-mono text-ink">
                bg
              </div>
              <div className="text-xs font-medium">Background</div>
              <div className="text-[10px] font-mono text-ink-muted">{resolvedTheme === 'dark' ? '#0E1514' : '#F6F1E7'}</div>
            </Card>

            <Card className="p-3 text-center space-y-1.5 bg-paper-surface">
              <div className="h-10 rounded border border-border-hairline bg-paper-surface flex items-center justify-center text-xs font-mono text-ink">
                surface
              </div>
              <div className="text-xs font-medium">Surface</div>
              <div className="text-[10px] font-mono text-ink-muted">{resolvedTheme === 'dark' ? '#151F1E' : '#FFFCF5'}</div>
            </Card>

            <Card className="p-3 text-center space-y-1.5 bg-paper-card">
              <div className="h-10 rounded border border-border-hairline bg-paper-card flex items-center justify-center text-xs font-mono text-ink">
                card
              </div>
              <div className="text-xs font-medium">Card Surface</div>
              <div className="text-[10px] font-mono text-ink-muted">{resolvedTheme === 'dark' ? '#1B2625' : '#FFFFFF'}</div>
            </Card>

            <Card className="p-3 text-center space-y-1.5 bg-paper-surface">
              <div
                className="h-10 rounded flex items-center justify-center text-xs font-mono font-bold shadow-subtle"
                style={{ backgroundColor: 'var(--color-primary)', color: 'var(--color-primary-fg)' }}
              >
                primary
              </div>
              <div className="text-xs font-medium text-ink">Primary Accent</div>
              <div className="text-[10px] font-mono text-ink-muted">{resolvedTheme === 'dark' ? '#F0B35A' : '#0F3D3E'}</div>
            </Card>

            <Card className="p-3 text-center space-y-1.5 bg-paper-surface">
              <div
                className="h-10 rounded flex items-center justify-center text-xs font-mono font-bold text-white shadow-subtle"
                style={{ backgroundColor: 'var(--color-verified)' }}
              >
                verified
              </div>
              <div className="text-xs font-medium text-ink">Verified Evidence</div>
              <div className="text-[10px] font-mono text-ink-muted">{resolvedTheme === 'dark' ? '#3E9B73' : '#2F7D5B'}</div>
            </Card>

            <Card className="p-3 text-center space-y-1.5 bg-paper-surface">
              <div
                className="h-10 rounded flex items-center justify-center text-xs font-mono font-bold text-white shadow-subtle"
                style={{ backgroundColor: 'var(--color-warning)' }}
              >
                warning
              </div>
              <div className="text-xs font-medium text-ink">Warning / Gap</div>
              <div className="text-[10px] font-mono text-ink-muted">{resolvedTheme === 'dark' ? '#E05A3B' : '#D2492A'}</div>
            </Card>
          </div>
        </section>

        {/* 2. Deterministic Per-Paper Ink Colors */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-paperink-amber" />
            <h2 className="text-lg font-semibold font-sans">2. Per-Paper Ink Palette (Deterministic by Document)</h2>
          </div>
          <p className="text-sm text-ink-secondary">
            Every document receives a consistent ink color used across sidebar indicators, citation chips, PDF highlights, and sentence underlines. The initial is always displayed alongside color to ensure accessibility without relying purely on color vision.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {PAPER_INKS.map((ink) => (
              <Card key={ink.hex} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-xs"
                    style={{ backgroundColor: ink.hex }}
                  >
                    {String.fromCharCode(65 + ink.index)}
                  </span>
                  <div>
                    <div className="text-sm font-medium text-ink">{ink.name}</div>
                    <div className="text-xs font-mono text-ink-muted">{ink.hex}</div>
                  </div>
                </div>

                <div
                  className="px-2.5 py-1 rounded text-xs font-mono font-medium border"
                  style={{
                    backgroundColor: ink.bgLight,
                    borderColor: ink.borderLight,
                    color: ink.hex,
                  }}
                >
                  [cite:{ink.index + 1}]
                </div>
              </Card>
            ))}
          </div>
        </section>

        {/* 3. Typography Hierarchy */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-paperink-indigo" />
            <h2 className="text-lg font-semibold font-sans">3. Scholarly Typography</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="p-5 space-y-2">
              <span className="text-[11px] font-mono text-ink-muted uppercase tracking-wider">Serif Body &bull; Newsreader</span>
              <h3 className="text-lg font-serif font-medium text-ink">Longform Evidence Synthesis</h3>
              <p className="text-sm font-serif leading-relaxed text-ink-secondary">
                Designed for comfortable continuous reading across research answers. Line lengths are constrained between 65–75ch to prevent eye fatigue.
              </p>
            </Card>

            <Card className="p-5 space-y-2">
              <span className="text-[11px] font-mono text-ink-muted uppercase tracking-wider">Sans UI &bull; Instrument Sans</span>
              <h3 className="text-lg font-sans font-semibold text-ink">Navigation &amp; Controls</h3>
              <p className="text-sm font-sans leading-relaxed text-ink-secondary">
                Crisp geometric sans designed for interface headers, buttons, labels, and structured data tables.
              </p>
            </Card>

            <Card className="p-5 space-y-2">
              <span className="text-[11px] font-mono text-ink-muted uppercase tracking-wider">Monospace &bull; JetBrains Mono</span>
              <h3 className="text-lg font-mono font-medium text-ink">p. 14 &bull; [cite:2]</h3>
              <p className="text-sm font-mono leading-relaxed text-ink-secondary">
                High-legibility code font for provenance citations, chunk IDs, page indicators, and file hashes.
              </p>
            </Card>
          </div>
        </section>

        {/* 4. Reading Room Prose Sample (Real Scholarly Synthesized Text) */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-paperink-teal" />
            <h2 className="text-lg font-semibold font-sans">4. Scholarly Answer Prose &amp; Inline Citations (65–75ch Line Length)</h2>
          </div>

          <Card className="p-6 md:p-8 bg-paper-surface">
            <div className="reading-prose">
              <div className="flex items-center gap-2 mb-3">
                <Badge variant="verified">
                  <CheckCircle2 className="w-3 h-3 mr-1" /> Grounded Evidence
                </Badge>
                <span className="text-xs font-mono text-ink-muted">Latency: 1,420ms &bull; Gemini 3.5 flash-lite</span>
              </div>

              <h3 className="text-xl">Evaluation of Circular Packaging Metrics</h3>

              <p>
                The empirical analysis in Portugal reveals that plastic packaging exhibits low circularity, driven primarily by short lifespans and low recycling rates{' '}
                <Chip
                  filename="Rita Garcia.pdf"
                  citationId="cite:1"
                  pageNumber={1}
                />
                . Specifically, evaluation utilizing the Material Circularity Indicator (MCI) yielded an average circularity level of 16.1 %, substantiating the brief retention period of plastic packaging in the economic loop{' '}
                <Chip
                  filename="Rita Garcia.pdf"
                  citationId="cite:2"
                  pageNumber={7}
                />
                .
              </p>

              <p>
                When accounting for production process losses of approximately 14 %, improved iterations of circularity metrics yield even lower retention values{' '}
                <Chip
                  filename="Rita Garcia.pdf"
                  citationId="cite:3"
                  pageNumber={8}
                />
                . Furthermore, Recycled Plastic Proportion (RPP) metrics demonstrate an expansion in open-loop recycling—where recycled resin is redeployed into general durable goods—while closed-loop bottle-to-bottle recycling remains constrained.
              </p>

              {/* Grounding Strip Preview */}
              <div className="not-prose mt-6 pt-4 border-t border-border-hairline flex flex-wrap items-center justify-between text-xs text-ink-secondary gap-3">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-reading-verified" />
                  <span className="font-medium text-ink">3 of 3 claims supported by cited evidence</span>
                </div>
                <div className="flex items-center gap-1.5 font-mono">
                  <span>Sources:</span>
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getPaperInk('Rita Garcia.pdf').hex }} />
                  <span className="text-ink">Rita Garcia.pdf</span>
                </div>
              </div>
            </div>
          </Card>
        </section>

        {/* 5. Interactive Component Kit Showcase */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-paperink-plum" />
            <h2 className="text-lg font-semibold font-sans">5. Interactive Component Kit</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Buttons & Badges */}
            <Card className="p-6 space-y-5">
              <h3 className="text-sm font-semibold font-sans text-ink uppercase tracking-wider">Buttons &amp; Badges</h3>
              
              <div className="flex flex-wrap gap-2.5 items-center">
                <Button variant="primary">Primary Scholar</Button>
                <Button variant="secondary">Secondary Paper</Button>
                <Button variant="outline">Outline</Button>
                <Button variant="ghost">Ghost</Button>
                <Button variant="danger">Warning</Button>
                <Button variant="primary" isLoading={true}>Running</Button>
              </div>

              <div className="flex flex-wrap gap-2 items-center pt-2 border-t border-border-subtle">
                <Badge variant="default">Indexed</Badge>
                <Badge variant="verified">Verified Provenance</Badge>
                <Badge variant="warning">Data Gap</Badge>
                <Badge variant="highlight">Scope Focus</Badge>
                <Badge variant="outline">p. 12</Badge>
              </div>
            </Card>

            {/* Tooltips & Dialog */}
            <Card className="p-6 space-y-5">
              <h3 className="text-sm font-semibold font-sans text-ink uppercase tracking-wider">Modals &amp; Tooltips</h3>
              
              <div className="flex flex-wrap items-center gap-3">
                <Tooltip content="Direct sentence excerpt verified against page 7 of Rita Garcia.pdf">
                  <Button variant="outline">
                    Hover for Tooltip
                  </Button>
                </Tooltip>

                <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                  <DialogTrigger asChild>
                    <Button variant="secondary">
                      Open Scholarly Dialog
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Document Provenance Verification</DialogTitle>
                      <DialogDescription>
                        Every factual claim is verified against indexed PDF chunk embeddings and page bounding boxes.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="py-3 text-sm text-ink-secondary space-y-2 font-serif">
                      <p>
                        "The MCI evaluation yields an average circularity level of 16.1 %, substantiating the brief lifespan of packaging."
                      </p>
                      <div className="text-xs font-mono text-ink-muted pt-2 border-t border-border-hairline">
                        Document: Rita Garcia.pdf &bull; Page: 7 &bull; Chunk: chunk_3a362199
                      </div>
                    </div>
                    <div className="flex justify-end gap-2 pt-4">
                      <Button variant="secondary" onClick={() => setIsDialogOpen(false)}>Dismiss</Button>
                      <Button variant="primary" onClick={() => setIsDialogOpen(false)}>Confirm Source</Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>

              <div className="space-y-2 pt-2 border-t border-border-subtle">
                <div className="text-xs font-mono text-ink-muted">Skeleton Loading State:</div>
                <div className="space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-1/2" />
                </div>
              </div>
            </Card>

            {/* Document Sources Chips */}
            <Card className="p-6 space-y-4 md:col-span-2">
              <h3 className="text-sm font-semibold font-sans text-ink uppercase tracking-wider">Per-Paper Citation Chips</h3>
              <p className="text-sm text-ink-secondary">
                Hover to preview metadata; clicking links directly to the cited page in the evidence inspector.
              </p>

              <div className="flex flex-wrap gap-2.5">
                {samplePapers.map((p, idx) => (
                  <Chip
                    key={p.id}
                    filename={p.title}
                    docKey={p.title}
                    paperIndex={idx}
                    citationId={`cite:${idx + 1}`}
                    pageNumber={idx + 1}
                  >
                    <span>{p.title}</span>
                  </Chip>
                ))}
              </div>
            </Card>

          </div>
        </section>

      </div>
    </div>
  );
};
