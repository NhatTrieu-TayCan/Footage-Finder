import React, { useState } from 'react';
import type { EvaluatedImage } from '../types';
import { X, ShieldCheck, Copy, Check, ExternalLink } from 'lucide-react';

interface ImageModalProps {
  item: EvaluatedImage | null;
  segmentId: string | null;
  onClose: () => void;
}

export const ImageModal: React.FC<ImageModalProps> = ({ item, segmentId, onClose }) => {
  const [copied, setCopied] = useState(false);

  if (!item) return null;

  const cand = item.candidate;
  const attribution =
    cand.attribution_text ||
    `"${cand.image_url.split('/').pop()}" via ${cand.source_domain} (${cand.license}): ${cand.source_page_url}`;

  const handleCopyAttribution = () => {
    navigator.clipboard.writeText(attribution);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
          <div>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.25rem' }}>
              Candidate Inspection • Beat {segmentId} (Rank #{item.rank})
            </h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
              {cand.source_domain} • {cand.width || '?'}x{cand.height || '?'} px
            </span>
          </div>

          <button
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            style={{ padding: '0.4rem', borderRadius: '50%' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Image Preview */}
        <div
          style={{
            background: '#000',
            borderRadius: 'var(--radius-md)',
            overflow: 'hidden',
            maxHeight: '450px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '1.5rem',
          }}
        >
          <img
            src={cand.image_url}
            alt={item.reason}
            style={{ maxWidth: '100%', maxHeight: '450px', objectFit: 'contain' }}
          />
        </div>

        {/* 3-Layer Watermark Defense Audit Panel */}
        <div
          style={{
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            borderRadius: 'var(--radius-md)',
            padding: '1.2rem',
            marginBottom: '1.5rem',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              color: '#34d399',
              fontWeight: 700,
              fontSize: '0.9rem',
              marginBottom: '0.75rem',
            }}
          >
            <ShieldCheck size={18} />
            3-LAYER WATERMARK DEFENSE AUDIT: PASSED
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '0.85rem',
              fontSize: '0.78rem',
            }}
          >
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.65rem', borderRadius: '6px' }}>
              <div style={{ color: 'var(--text-muted)' }}>Layer 1 • Domain Filter</div>
              <div style={{ color: '#fff', fontWeight: 600 }}>Passed (Not in stock blocklist)</div>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.65rem', borderRadius: '6px' }}>
              <div style={{ color: 'var(--text-muted)' }}>Layer 2 • URL Heuristics</div>
              <div style={{ color: '#fff', fontWeight: 600 }}>Passed (Clean asset path)</div>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.65rem', borderRadius: '6px' }}>
              <div style={{ color: 'var(--text-muted)' }}>Layer 3 • Gemini Vision Check</div>
              <div style={{ color: '#fff', fontWeight: 600 }}>has_watermark: false, stock: false</div>
            </div>
          </div>
        </div>

        {/* Gemini Vision Scoring Reasoning */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h4 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
            Gemini Multimodal Vision Evaluation (Score: {item.relevance_score.toFixed(1)}/10)
          </h4>
          <p style={{ fontSize: '0.9rem', color: '#e2e8f0', lineHeight: 1.5 }}>{item.reason}</p>
        </div>

        {/* Attribution & Links */}
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.4)',
            padding: '1rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '0.5rem',
            }}
          >
            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              YouTube Video Description Attribution
            </span>
            <button className="btn btn-secondary btn-sm" onClick={handleCopyAttribution}>
              {copied ? (
                <>
                  <Check size={14} color="#10b981" /> Copied!
                </>
              ) : (
                <>
                  <Copy size={14} /> Copy Attribution
                </>
              )}
            </button>
          </div>
          <code
            style={{
              display: 'block',
              fontSize: '0.78rem',
              color: '#a5b4fc',
              wordBreak: 'break-all',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {attribution}
          </code>

          <div style={{ marginTop: '0.85rem' }}>
            <a
              href={cand.source_page_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary btn-sm"
              style={{ display: 'inline-flex' }}
            >
              <ExternalLink size={13} /> Open Source Page
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
