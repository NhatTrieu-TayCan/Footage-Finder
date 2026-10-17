import { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { Timeline } from './components/Timeline';
import { LiveStreamPanel } from './components/LiveStreamPanel';
import type { LogEntry } from './components/LiveStreamPanel';
import { SegmentView } from './components/SegmentView';
import { ImageModal } from './components/ImageModal';
import { NewRunModal } from './components/NewRunModal';
import { DaVinciExportModal } from './components/DaVinciExportModal';
import { HistoryDrawer } from './components/HistoryDrawer';
import type { RunData, RunSummary, EvaluatedImage, UsageStats } from './types';

export function App() {
  const [currentRun, setCurrentRun] = useState<RunData | null>(null);
  const [activeSegmentId, setActiveSegmentId] = useState<string | null>(null);
  const [runsList, setRunsList] = useState<RunSummary[]>([]);
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [selectedItems, setSelectedItems] = useState<EvaluatedImage[]>([]);

  // Modals
  const [isNewRunOpen, setIsNewRunOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [inspectedImage, setInspectedImage] = useState<{
    item: EvaluatedImage;
    segmentId: string;
  } | null>(null);

  // Live Stream Execution State
  const [isRunning, setIsRunning] = useState(false);
  const [isError, setIsError] = useState(false);
  const [stepMessage, setStepMessage] = useState('');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [liveStats, setLiveStats] = useState<UsageStats | undefined>(undefined);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  // Fetch initial list of runs and load the latest one
  useEffect(() => {
    fetch('/api/runs')
      .then((res) => res.json())
      .then((data) => {
        if (data.runs && data.runs.length > 0) {
          setRunsList(data.runs);
          loadRunDetails(data.runs[0].run_id);
        }
      })
      .catch((err) => console.error('Failed to fetch runs:', err));
  }, []);

  const loadRunDetails = async (runId: string) => {
    try {
      const res = await fetch(`/api/runs/${runId}`);
      if (!res.ok) throw new Error('Run not found');
      const data = await res.json();
      setCurrentRun(data);
      if (data.segments && data.segments.length > 0) {
        setActiveSegmentId(data.segments[0].segment.id);
      }
      if (data.stats) {
        setLiveStats(data.stats);
      }

      // Pre-select top pick #1 for each segment by default
      const initialUrls = new Set<string>();
      const initialItems: EvaluatedImage[] = [];
      data.segments?.forEach((rep: any) => {
        if (rep.top_picks && rep.top_picks.length > 0) {
          initialUrls.add(rep.top_picks[0].candidate.image_url);
          initialItems.push(rep.top_picks[0]);
        }
      });
      setSelectedUrls(initialUrls);
      setSelectedItems(initialItems);
    } catch (err) {
      console.error('Error loading run details:', err);
    }
  };

  const handleToggleSelect = (item: EvaluatedImage) => {
    const url = item.candidate.image_url;
    const nextUrls = new Set(selectedUrls);
    let nextItems = [...selectedItems];

    if (nextUrls.has(url)) {
      nextUrls.delete(url);
      nextItems = nextItems.filter((i) => i.candidate.image_url !== url);
    } else {
      nextUrls.add(url);
      nextItems.push(item);
    }

    setSelectedUrls(nextUrls);
    setSelectedItems(nextItems);
  };

  const handleLaunchPipeline = async (params: {
    script_text: string;
    script_name: string;
    mock: boolean;
    youtube: boolean;
    prefer_aspect: string;
    segments_range: string;
  }) => {
    setIsRunning(true);
    setIsError(false);
    setLogs([]);
    setStepMessage('Launching pipeline job...');

    // Initialize blank currentRun to stream into
    setCurrentRun({
      run_id: 'pending',
      script_name: params.script_name,
      total_segments: 0,
      segments: [],
    });

    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });

      if (!res.ok) throw new Error('Failed to start pipeline job');
      const { job_id } = await res.json();

      // Connect to SSE stream
      const eventSource = new EventSource(`/api/stream/${job_id}`);

      eventSource.addEventListener('progress', (e) => {
        const payload = JSON.parse(e.data);
        const data = payload.data;
        setStepMessage(data.message || '');
        setLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            timestamp: payload.timestamp,
            message: data.message,
            level: 'info',
          },
        ]);

        if (data.segments) {
          setCurrentRun((prev) =>
            prev
              ? {
                  ...prev,
                  total_segments: data.total_segments,
                  segments: data.segments.map((s: any) => ({
                    segment: s,
                    top_picks: [],
                    alternates: [],
                    status: 'weak_matches',
                  })),
                }
              : prev
          );
        }
      });

      eventSource.addEventListener('intent_generated', (e) => {
        const payload = JSON.parse(e.data);
        const data = payload.data;
        setLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            timestamp: payload.timestamp,
            message: `[${data.segment_id}] Visual intent extracted: ${data.intent.queries.slice(0, 2).join(', ')}`,
            level: 'info',
          },
        ]);
      });

      eventSource.addEventListener('segment_candidates_found', (e) => {
        const payload = JSON.parse(e.data);
        const data = payload.data;
        setLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            timestamp: payload.timestamp,
            message: `[${data.segment_id}] Found ${data.count} candidates (L1 blocked: ${data.l1_dropped}, L2 blocked: ${data.l2_dropped})`,
            level: 'info',
          },
        ]);
      });

      eventSource.addEventListener('segment_completed', (e) => {
        const payload = JSON.parse(e.data);
        const data = payload.data;
        const rep = data.report;

        setCurrentRun((prev) => {
          if (!prev) return prev;
          const updated = [...prev.segments];
          const idx = updated.findIndex((s) => s.segment.id === rep.segment.id);
          if (idx >= 0) {
            updated[idx] = rep;
          } else {
            updated.push(rep);
          }
          return { ...prev, segments: updated };
        });

        setLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            timestamp: payload.timestamp,
            message: `✓ [${data.segment_id}] Evaluated: Status ${data.status.toUpperCase()} (${data.top_picks_count} top picks)`,
            level: 'success',
          },
        ]);
      });

      eventSource.addEventListener('pipeline_finished', (e) => {
        const payload = JSON.parse(e.data);
        const data = payload.data;
        setIsRunning(false);
        setIsError(false);
        setStepMessage('Completed successfully!');
        if (data.stats) {
          setLiveStats(data.stats);
        }
        showToast('✓ Footage Finder run completed successfully!');
        eventSource.close();

        // Refresh runs list
        fetch('/api/runs')
          .then((r) => r.json())
          .then((d) => setRunsList(d.runs || []));
      });

      eventSource.addEventListener('pipeline_error', (e) => {
        const payload = JSON.parse(e.data);
        setIsRunning(false);
        setIsError(true);
        setStepMessage('Error executing pipeline');
        setLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            timestamp: payload.timestamp,
            message: `Error: ${payload.data.error}`,
            level: 'error',
          },
        ]);
        showToast('✕ Pipeline execution error');
        eventSource.close();
      });
    } catch (err: any) {
      setIsRunning(false);
      setIsError(true);
      setStepMessage(`Failed: ${err.message}`);
    }
  };

  const handleTriggerDownload = async () => {
    if (!currentRun) return '';
    const res = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        run_id: currentRun.run_id,
        items: selectedItems.map((item) => ({
          segment_id: item.candidate.candidate_id?.split('_')[0] || 'S001',
          image_url: item.candidate.image_url,
          source_page_url: item.candidate.source_page_url,
          source_domain: item.candidate.source_domain,
          license: item.candidate.license,
          author: item.candidate.author,
          attribution_text: item.candidate.attribution_text,
        })),
      }),
    });

    if (!res.ok) throw new Error('Download failed');
    const data = await res.json();
    showToast('✓ Assets downloaded into DaVinci Resolve media bins!');
    return data.download_dir;
  };

  const scrollToSegment = (segmentId: string) => {
    setActiveSegmentId(segmentId);
    const element = document.getElementById(`segment-${segmentId}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="footage-finder-studio">
      <Navbar
        currentRun={currentRun}
        onOpenNewRun={() => setIsNewRunOpen(true)}
        onOpenHistory={() => setIsHistoryOpen(true)}
        onOpenExport={() => setIsExportOpen(true)}
        selectedCount={selectedUrls.size}
        isRunning={isRunning}
      />

      {currentRun && (
        <Timeline
          segments={currentRun.segments}
          activeSegmentId={activeSegmentId}
          onSelectSegment={scrollToSegment}
        />
      )}

      <LiveStreamPanel
        isRunning={isRunning}
        isError={isError}
        currentStepMessage={stepMessage}
        logs={logs}
        stats={liveStats}
        onDismiss={() => {
          setLogs([]);
          setIsError(false);
        }}
      />

      <main className="studio-main-content">
        {isError && (
          <div
            style={{
              padding: '1rem 1.5rem',
              marginBottom: '1.5rem',
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: 'var(--radius-lg)',
              color: '#fca5a5',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
            }}
          >
            <div>
              <strong>Pipeline Stopped:</strong> The pipeline halted due to an API error before candidate evaluations completed.
            </div>
            <button className="btn btn-primary btn-sm" onClick={() => setIsNewRunOpen(true)}>
              Relaunch Run
            </button>
          </div>
        )}

        {currentRun && currentRun.segments && currentRun.segments.length > 0 ? (
          currentRun.segments.map((rep) => (
            <SegmentView
              key={rep.segment.id}
              report={rep}
              selectedUrls={selectedUrls}
              onToggleSelect={handleToggleSelect}
              onInspectImage={(item, segId) => setInspectedImage({ item, segmentId: segId })}
            />
          ))
        ) : !isRunning ? (
          <div
            style={{
              padding: '5rem 2rem',
              textAlign: 'center',
              background: 'var(--bg-card)',
              borderRadius: 'var(--radius-xl)',
              border: '1px dashed var(--border-subtle)',
            }}
          >
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem', marginBottom: '0.5rem' }}>
              Welcome to Footage Finder Studio
            </h3>
            <p style={{ color: 'var(--text-muted)', maxWidth: '500px', margin: '0 auto 1.5rem' }}>
              Paste your voiceover script or choose a preloaded sample to research archival images, filter watermarks, and generate DaVinci Resolve media bins.
            </p>
            <button className="btn btn-primary" onClick={() => setIsNewRunOpen(true)}>
              Launch Your First Script Run
            </button>
          </div>
        ) : null}
      </main>

      {/* Modals */}
      <ImageModal
        item={inspectedImage ? inspectedImage.item : null}
        segmentId={inspectedImage ? inspectedImage.segmentId : null}
        onClose={() => setInspectedImage(null)}
      />

      <NewRunModal
        isOpen={isNewRunOpen}
        onClose={() => setIsNewRunOpen(false)}
        onLaunch={handleLaunchPipeline}
      />

      <DaVinciExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        currentRun={currentRun}
        selectedItems={selectedItems}
        onTriggerDownload={handleTriggerDownload}
      />

      <HistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        runs={runsList}
        onSelectRun={loadRunDetails}
      />

      {toastMessage && <div className="toast-notification">{toastMessage}</div>}
    </div>
  );
}

export default App;
