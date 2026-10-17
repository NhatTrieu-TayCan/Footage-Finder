import React from 'react';
import type { SegmentReport } from '../types';
import { Layers } from 'lucide-react';

interface TimelineProps {
  segments: SegmentReport[];
  activeSegmentId: string | null;
  onSelectSegment: (segmentId: string) => void;
}

export const Timeline: React.FC<TimelineProps> = ({
  segments,
  activeSegmentId,
  onSelectSegment,
}) => {
  if (!segments || segments.length === 0) return null;

  return (
    <section className="timeline-container">
      <div className="timeline-header">
        <div className="timeline-title">
          <Layers size={16} color="var(--accent-primary)" />
          TIMELINE BEATS (DaVinci Marker Navigation)
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
          Click segment to scrub and focus
        </div>
      </div>

      <div className="timeline-track">
        {segments.map((rep) => {
          const seg = rep.segment;
          const isActive = activeSegmentId === seg.id;
          const topScore = rep.top_picks.length > 0 ? rep.top_picks[0].relevance_score : null;

          return (
            <div
              key={seg.id}
              className={`timeline-segment-card ${isActive ? 'active' : ''}`}
              onClick={() => onSelectSegment(seg.id)}
            >
              <div className="timeline-card-header">
                <span className="timeline-card-id">{seg.id}</span>
                <span className={`status-pill ${rep.status}`}>
                  {rep.status === 'ok' ? (topScore ? `${topScore.toFixed(1)}★` : 'OK') : rep.status}
                </span>
              </div>
              <div className="timeline-card-preview">{seg.text}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
