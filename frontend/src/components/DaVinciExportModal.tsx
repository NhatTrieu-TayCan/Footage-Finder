import React, { useState } from 'react';
import { X, Download, Copy, Check, FolderDown, FileSpreadsheet } from 'lucide-react';
import type { RunData, EvaluatedImage } from '../types';

interface DaVinciExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentRun: RunData | null;
  selectedItems: EvaluatedImage[];
  onTriggerDownload: () => Promise<string>;
}

export const DaVinciExportModal: React.FC<DaVinciExportModalProps> = ({
  isOpen,
  onClose,
  currentRun,
  selectedItems,
  onTriggerDownload,
}) => {
  const [downloading, setDownloading] = useState(false);
  const [downloadPath, setDownloadPath] = useState<string | null>(null);
  const [creditsCopied, setCreditsCopied] = useState(false);

  if (!isOpen || !currentRun) return null;

  // Generate consolidated credits
  const consolidatedCredits = [
    '===========================================================',
    `FOOTAGE FINDER - ATTRIBUTION & CREDITS (${currentRun.script_name})`,
    'Paste necessary lines into your YouTube video description',
    '===========================================================\n',
    ...selectedItems.map((item) => {
      const cand = item.candidate;
      return cand.attribution_text || `[${cand.source_domain}] ${cand.author || 'Unknown'} (${cand.license}) - ${cand.source_page_url}`;
    }),
  ].join('\n');

  const handleCopyCredits = () => {
    navigator.clipboard.writeText(consolidatedCredits);
    setCreditsCopied(true);
    setTimeout(() => setCreditsCopied(false), 2000);
  };

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const path = await onTriggerDownload();
      setDownloadPath(path);
    } finally {
      setDownloading(false);
    }
  };

  const handleExportCSV = () => {
    const headers = ['segment_id', 'rank', 'image_url', 'source_domain', 'license', 'score', 'attribution_text'];
    const rows = selectedItems.map((item) => {
      const cand = item.candidate;
      return [
        cand.candidate_id?.split('_')[0] || 'S001',
        item.rank,
        `"${cand.image_url}"`,
        cand.source_domain,
        cand.license,
        item.relevance_score,
        `"${cand.attribution_text?.replace(/"/g, '""') || ''}"`,
      ].join(',');
    });

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${currentRun.script_name}_selected.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <FolderDown size={22} color="var(--accent-primary)" />
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.25rem' }}>
              DaVinci Resolve Export Hub
            </h2>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
          You have selected <strong>{selectedItems.length} assets</strong> for DaVinci Resolve import.
        </p>

        {/* Action 1: Direct Download into Segment Folders */}
        <div
          style={{
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '1.25rem',
            marginBottom: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>
                1. Download Media Bins (with .credit.txt sidecars)
              </h4>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                Downloads assets partitioned into <code>downloads/{currentRun.run_id}/S001/</code>, ready to drag into DaVinci Resolve.
              </p>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleDownload}
              disabled={downloading}
            >
              <Download size={16} />
              {downloading ? 'Downloading...' : 'Download to Bins'}
            </button>
          </div>

          {downloadPath && (
            <div
              style={{
                marginTop: '0.85rem',
                padding: '0.65rem',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: '6px',
                fontSize: '0.8rem',
                color: '#34d399',
              }}
            >
              ✓ Downloaded to: <code>{downloadPath}</code>
            </div>
          )}
        </div>

        {/* Action 2: Copy YouTube Video Description Credits */}
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.35)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '1.25rem',
            marginBottom: '1.25rem',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '0.65rem',
            }}
          >
            <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>
              2. YouTube Description Credits
            </h4>
            <button className="btn btn-secondary btn-sm" onClick={handleCopyCredits}>
              {creditsCopied ? (
                <>
                  <Check size={14} color="#10b981" /> Copied!
                </>
              ) : (
                <>
                  <Copy size={14} /> Copy to Clipboard
                </>
              )}
            </button>
          </div>

          <textarea
            className="form-textarea"
            readOnly
            style={{ height: '110px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)' }}
            value={consolidatedCredits}
          />
        </div>

        {/* Action 3: CSV Export */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button className="btn btn-secondary" onClick={handleExportCSV}>
            <FileSpreadsheet size={16} /> Export Selected CSV
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
