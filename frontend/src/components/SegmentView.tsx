import React, { useState } from 'react';
import type { SegmentReport, EvaluatedImage } from '../types';
import {
  CheckSquare,
  Square,
  Maximize2,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';

interface SegmentViewProps {
  report: SegmentReport;
  selectedUrls: Set<string>;
  onToggleSelect: (item: EvaluatedImage, segmentId: string) => void;
  onInspectImage: (item: EvaluatedImage, segmentId: string) => void;
}

export const SegmentView: React.FC<SegmentViewProps> = ({
  report,
  selectedUrls,
  onToggleSelect,
  onInspectImage,
}) => {
  const [showAlternates, setShowAlternates] = useState(false);
  const seg = report.segment;

  const renderCandidateCard = (item: EvaluatedImage, isAlternate = false) => {
    const cand = item.candidate;
    const isSelected = selectedUrls.has(cand.image_url);

    return (
      <div
        key={cand.candidate_id || cand.image_url}
        className={`candidate-card ${isSelected ? 'selected' : ''}`}
      >
        <div className="image-thumb-wrapper">
          <img
            src={cand.image_url}
            alt={item.reason}
            loading="lazy"
            onError={(e) => {
              // Graceful fallback if hotlink-blocked
              const target = e.target as HTMLImageElement;
              target.src =
                'https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=600&auto=format&fit=crop&q=60';
            }}
          />

          <div className="thumb-overlay-bar">
            <span className="rank-badge">
              {isAlternate ? `ALT #${item.rank}` : `PICK #${item.rank}`}
            </span>
            <span className="score-badge">
              ★ {item.relevance_score.toFixed(1)}/10
            </span>
          </div>
        </div>

        <div className="candidate-details">
          <p className="reasoning-text" title={item.reason}>
            {item.reason}
          </p>

          {item.concerns && item.concerns.length > 0 && (
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
              {item.concerns.map((c, i) => (
                <span
                  key={i}
                  style={{
                    fontSize: '0.68rem',
                    color: '#f59e0b',
                    background: 'rgba(245, 158, 11, 0.1)',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '3px',
                  }}
                >
                  <AlertTriangle size={10} /> {c}
                </span>
              ))}
            </div>
          )}

          <div className="candidate-meta-row">
            <span
              className={`license-pill ${
                cand.license === 'public_domain' ? 'public_domain' : ''
              }`}
            >
              {cand.license?.replace('_', ' ').toUpperCase() || 'VERIFY'}
            </span>
            <span style={{ fontFamily: 'var(--font-mono)' }}>
              {cand.source_domain}
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              paddingTop: '0.5rem',
              borderTop: '1px solid rgba(255, 255, 255, 0.05)',
            }}
          >
            <button
              className="btn btn-secondary btn-sm"
              style={{
                background: isSelected ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                borderColor: isSelected ? '#6366f1' : 'var(--border-subtle)',
                color: isSelected ? '#a5b4fc' : 'var(--text-muted)',
              }}
              onClick={() => onToggleSelect(item, seg.id)}
            >
              {isSelected ? (
                <>
                  <CheckSquare size={14} color="#6366f1" /> Selected
                </>
              ) : (
                <>
                  <Square size={14} /> Include
                </>
              )}
            </button>

            <button
              className="btn btn-secondary btn-sm"
              onClick={() => onInspectImage(item, seg.id)}
              title="Inspect Full Image & Watermark Defense Audit"
            >
              <Maximize2 size={13} /> Inspect
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <article className="segment-studio-card" id={`segment-${seg.id}`}>
      <div className="segment-header-row">
        <div>
          <span className="segment-id-tag">{seg.id}</span>
          <p className="segment-narration-text">{seg.text}</p>

          {report.intent && (
            <div className="intent-pills-row">
              {report.intent.image_types.map((type, i) => (
                <span key={i} className="intent-pill">
                  📷 {type}
                </span>
              ))}
              {report.intent.queries.map((q, i) => (
                <span
                  key={i}
                  className="intent-pill"
                  style={{ color: '#a5b4fc', borderColor: 'rgba(99, 102, 241, 0.2)' }}
                >
                  🔍 {q}
                </span>
              ))}
            </div>
          )}
        </div>

        <div style={{ textAlign: 'right' }}>
          <span className={`status-pill ${report.status}`}>{report.status}</span>
        </div>
      </div>

      {report.status === 'no_match' && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.08)',
            border: '1px dashed rgba(239, 68, 68, 0.3)',
            borderRadius: 'var(--radius-md)',
            padding: '1rem',
            margin: '1rem 0',
            color: '#fca5a5',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
          }}
        >
          <AlertTriangle size={18} color="#ef4444" />
          <div>
            <strong>No archival matches found:</strong>{' '}
            {report.suggestion ||
              'Consider a custom animated motion graphic, historical map, or archival document scan.'}
          </div>
        </div>
      )}

      {/* Top Picks */}
      {report.top_picks.length > 0 && (
        <div>
          <div
            style={{
              fontSize: '0.85rem',
              fontWeight: 700,
              color: 'var(--text-muted)',
              marginBottom: '0.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Sparkles size={14} color="#10b981" /> TOP RESEARCH PICKS
          </div>
          <div className="candidate-grid">
            {report.top_picks.map((pick) => renderCandidateCard(pick, false))}
          </div>
        </div>
      )}

      {/* Alternates */}
      {report.alternates.length > 0 && (
        <div style={{ marginTop: '1.25rem' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setShowAlternates(!showAlternates)}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {showAlternates ? (
              <>
                <ChevronUp size={14} /> Hide {report.alternates.length} Alternates
              </>
            ) : (
              <>
                <ChevronDown size={14} /> View {report.alternates.length} Additional Alternates
              </>
            )}
          </button>

          {showAlternates && (
            <div className="candidate-grid" style={{ marginTop: '1rem' }}>
              {report.alternates.map((alt) => renderCandidateCard(alt, true))}
            </div>
          )}
        </div>
      )}
    </article>
  );
};
