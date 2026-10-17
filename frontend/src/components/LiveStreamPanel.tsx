import React, { useEffect, useRef } from 'react';
import { ShieldAlert, Cpu, DollarSign, AlertCircle } from 'lucide-react';
import type { UsageStats } from '../types';

export interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  level?: 'info' | 'success' | 'warn' | 'error';
}

interface LiveStreamPanelProps {
  isRunning: boolean;
  isError?: boolean;
  currentStepMessage: string;
  logs: LogEntry[];
  stats?: UsageStats;
  onDismiss?: () => void;
}

export const LiveStreamPanel: React.FC<LiveStreamPanelProps> = ({
  isRunning,
  isError = false,
  currentStepMessage,
  logs,
  stats,
  onDismiss,
}) => {
  const consoleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [logs]);

  if (!isRunning && !isError && logs.length === 0) return null;

  return (
    <section
      className="live-stream-panel"
      style={{
        borderColor: isError ? 'rgba(239, 68, 68, 0.4)' : undefined,
      }}
    >
      <div className="live-stream-header">
        <div className="live-status-indicator">
          {isRunning ? (
            <>
              <div className="pulsing-dot" />
              <span>LIVE PIPELINE EXECUTION</span>
            </>
          ) : isError ? (
            <span
              style={{
                color: '#ef4444',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontWeight: 700,
              }}
            >
              <AlertCircle size={16} /> ✕ PIPELINE FAILED
            </span>
          ) : (
            <span style={{ color: '#10b981' }}>✓ PIPELINE COMPLETED</span>
          )}
          <span
            style={{
              fontSize: '0.8rem',
              color: isError ? '#fca5a5' : 'var(--text-muted)',
              fontWeight: isError ? 600 : 400,
            }}
          >
            — {currentStepMessage || 'Processing beats...'}
          </span>
        </div>

        <div className="live-stats-bar">
          <div className="live-stat-item" title="Tokens used across Gemini models">
            <Cpu size={14} style={{ display: 'inline', marginRight: '4px', verticalAlign: '-2px' }} />
            Tokens: <span>{(stats?.gemini_prompt_tokens || 0) + (stats?.gemini_output_tokens || 0)}</span>
          </div>

          <div className="live-stat-item" title="Estimated cost of API calls">
            <DollarSign size={14} style={{ display: 'inline', marginRight: '2px', verticalAlign: '-2px' }} />
            Cost: <span>${(stats?.estimated_cost_usd || 0).toFixed(4)}</span>
          </div>

          <div className="live-stat-item" title="Watermarks Hard-Dropped across Layers 1, 2, and 3">
            <ShieldAlert size={14} style={{ display: 'inline', marginRight: '4px', verticalAlign: '-2px', color: '#ef4444' }} />
            Watermarks Blocked: <span style={{ color: '#ef4444' }}>
              {(stats?.l1_domain_blocked || 0) + (stats?.l2_url_blocked || 0) + (stats?.l3_vision_watermarked || 0)}
            </span>
          </div>

          {!isRunning && onDismiss && (
            <button className="btn btn-secondary btn-sm" onClick={onDismiss}>
              Hide Log
            </button>
          )}
        </div>
      </div>

      {isError && (
        <div
          style={{
            margin: '0.5rem 0 1rem',
            padding: '0.75rem 1rem',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: 'var(--radius-md)',
            color: '#fca5a5',
            fontSize: '0.82rem',
            lineHeight: 1.5,
          }}
        >
          <strong>Pipeline execution halted:</strong> Review the error log below.
          {logs.some((l) => l.message.includes('429') || l.message.includes('Quota')) ? (
            <span>
              {' '}
              You hit the <strong>Gemini Free-Tier Quota Limit (429)</strong> on <code>gemini-3.8-flash</code>.
              To continue immediately: enable <strong>Offline Mock Mode</strong> in the "New Script Run" dialog,
              process a smaller segment range (e.g. <code>S001-S005</code>), or use a Gemini API key with available quota.
            </span>
          ) : (
            <span> See details in the console logs below.</span>
          )}
        </div>
      )}

      <div className="live-console-log" ref={consoleRef}>
        {logs.map((entry) => (
          <div key={entry.id} className="log-entry">
            <span className="log-time">[{entry.timestamp.split('T')[1]?.slice(0, 8) || '00:00:00'}]</span>
            <span
              style={{
                color:
                  entry.level === 'error'
                    ? '#ef4444'
                    : entry.level === 'warn'
                    ? '#f59e0b'
                    : entry.level === 'success'
                    ? '#34d399'
                    : '#cbd5e1',
              }}
            >
              {entry.message}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
};
