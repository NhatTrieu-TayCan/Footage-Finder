import React, { useState } from 'react';
import { X, Play, FileText, Sparkles } from 'lucide-react';

interface NewRunModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLaunch: (params: {
    script_text: string;
    script_name: string;
    mock: boolean;
    youtube: boolean;
    prefer_aspect: string;
    segments_range: string;
  }) => void;
}

const SAMPLE_SCRIPT = `In the spring of 1942, deep in the desert of New Mexico, the United States government began acquiring land for Project Y—a secret laboratory nestled on the isolated Pajarito Plateau.

J. Robert Oppenheimer, a theoretical physicist from Berkeley, was selected to direct the scientific laboratory under the military command of General Leslie Groves.

Thousands of miles to the east in Oak Ridge, Tennessee, the gargantuan K-25 gaseous diffusion plant consumed vast electrical power to separate rare Uranium-235.

At Hanford, Washington, massive nuclear reactors cooled by the Columbia River produced the first plutonium in human history.

By July 1945, scientists assembled the Gadget test device inside the master bedroom of the abandoned McDonald Ranch house in the New Mexico desert.`;

export const NewRunModal: React.FC<NewRunModalProps> = ({ isOpen, onClose, onLaunch }) => {
  const [scriptName, setScriptName] = useState('Manhattan_Project');
  const [scriptText, setScriptText] = useState(SAMPLE_SCRIPT);
  const [mock, setMock] = useState(false);
  const [youtube, setYoutube] = useState(false);
  const [preferAspect, setPreferAspect] = useState('16:9');
  const [segmentsRange, setSegmentsRange] = useState('');

  if (!isOpen) return null;

  const handleLaunch = () => {
    if (!scriptText.trim()) return;
    onLaunch({
      script_text: scriptText,
      script_name: scriptName || 'Script',
      mock,
      youtube,
      prefer_aspect: preferAspect,
      segments_range: segmentsRange.trim(),
    });
    onClose();
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
            <FileText size={22} color="var(--accent-primary)" />
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.25rem' }}>
              Launch Footage Finder Pipeline
            </h2>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="form-group">
          <label className="form-label">Script Title / Project Name</label>
          <input
            type="text"
            className="form-textarea"
            style={{ height: '42px', padding: '0.6rem 0.85rem' }}
            value={scriptName}
            onChange={(e) => setScriptName(e.target.value)}
            placeholder="e.g. History_Of_Silicon_Valley"
          />
        </div>

        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.45rem' }}>
            <label className="form-label" style={{ margin: 0 }}>
              Narration Script (Plain Text or Beats)
            </label>
            <button
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem' }}
              onClick={() => setScriptText(SAMPLE_SCRIPT)}
            >
              <Sparkles size={12} /> Fill Manhattan Sample
            </button>
          </div>
          <textarea
            className="form-textarea"
            value={scriptText}
            onChange={(e) => setScriptText(e.target.value)}
            placeholder="Paste your voiceover script here. Footage Finder automatically chunks it into visual documentary beats..."
          />
        </div>

        {/* Options Row */}
        <div
          style={{
            background: 'rgba(0,0,0,0.3)',
            padding: '1.25rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            marginBottom: '1.5rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '1rem',
          }}
        >
          <div>
            <label className="form-label">Preferred Aspect</label>
            <select
              value={preferAspect}
              onChange={(e) => setPreferAspect(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem',
                background: '#090c14',
                color: '#fff',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
              }}
            >
              <option value="16:9">16:9 (Landscape YouTube)</option>
              <option value="9:16">9:16 (Shorts / Reels)</option>
              <option value="4:3">4:3 (Vintage Documentaries)</option>
            </select>
          </div>

          <div>
            <label className="form-label">Segment Range (Optional)</label>
            <input
              type="text"
              placeholder="e.g. S001-S005"
              value={segmentsRange}
              onChange={(e) => setSegmentsRange(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem',
                background: '#090c14',
                color: '#fff',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <label style={{ fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={mock}
                onChange={(e) => setMock(e.target.checked)}
              />
              <strong>Offline Mock Mode</strong> (Free fixtures)
            </label>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px' }}>
              Zero API calls or token usage
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <label style={{ fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={youtube}
                onChange={(e) => setYoutube(e.target.checked)}
              />
              <strong>YouTube Video Leads</strong>
            </label>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px' }}>
              Labeled "copyrighted – verify"
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.85rem' }}>
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleLaunch}>
            <Play size={16} /> Launch Pipeline
          </button>
        </div>
      </div>
    </div>
  );
};
