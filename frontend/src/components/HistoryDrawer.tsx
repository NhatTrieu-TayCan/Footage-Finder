import React from 'react';
import { X, History, Clock } from 'lucide-react';
import type { RunSummary } from '../types';

interface HistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  runs: RunSummary[];
  onSelectRun: (runId: string) => void;
}

export const HistoryDrawer: React.FC<HistoryDrawerProps> = ({
  isOpen,
  onClose,
  runs,
  onSelectRun,
}) => {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '650px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <History size={20} color="var(--accent-primary)" />
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.25rem' }}>
              Saved Runs & Project History
            </h2>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {runs.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No saved runs found in <code>output/</code>.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {runs.map((r) => (
              <div
                key={r.run_id}
                style={{
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '1rem',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  transition: 'background 0.2s',
                }}
                onClick={() => {
                  onSelectRun(r.run_id);
                  onClose();
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                    {r.script_name || r.run_id}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                    <Clock size={12} style={{ display: 'inline', marginRight: '4px' }} />
                    {r.run_id}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <span className="status-pill ok">
                    {r.total_segments ? `${r.total_segments} Beats` : 'Completed'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
