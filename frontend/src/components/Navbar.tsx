import React from 'react';
import { Film, Play, History, Download, Sparkles, CheckCircle2 } from 'lucide-react';
import type { RunData } from '../types';

interface NavbarProps {
  currentRun: RunData | null;
  onOpenNewRun: () => void;
  onOpenHistory: () => void;
  onOpenExport: () => void;
  selectedCount: number;
  isRunning: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentRun,
  onOpenNewRun,
  onOpenHistory,
  onOpenExport,
  selectedCount,
  isRunning,
}) => {
  return (
    <header className="studio-navbar">
      <div className="brand-section">
        <div className="brand-icon-wrapper">
          <Film size={22} />
        </div>
        <div>
          <h1 className="brand-title">FOOTAGE FINDER</h1>
          <div className="brand-subtitle">
            DaVinci Resolve Archival Footage Studio • Gemini Multimodal Vision
          </div>
        </div>
      </div>

      <div className="navbar-controls">
        {currentRun && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginRight: '0.5rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              Active Script: <strong style={{ color: '#fff' }}>{currentRun.script_name}</strong>
            </span>
            <span className="status-pill ok" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
              <CheckCircle2 size={12} /> {currentRun.total_segments} Beats
            </span>
          </div>
        )}

        <button className="btn btn-secondary" onClick={onOpenHistory} title="Browse Previous Runs">
          <History size={16} />
          History
        </button>

        <button
          className="btn btn-secondary"
          onClick={onOpenExport}
          disabled={!currentRun || selectedCount === 0}
          title="Download footage to DaVinci Resolve bins and copy YouTube credits"
        >
          <Download size={16} />
          DaVinci Export ({selectedCount})
        </button>

        <button
          className="btn btn-primary"
          onClick={onOpenNewRun}
          disabled={isRunning}
        >
          {isRunning ? (
            <>
              <Sparkles size={16} className="pulsing-dot" />
              Running Pipeline...
            </>
          ) : (
            <>
              <Play size={16} />
              New Script Run
            </>
          )}
        </button>
      </div>
    </header>
  );
};
