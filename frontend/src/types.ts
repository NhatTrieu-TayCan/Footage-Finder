export interface Candidate {
  candidate_id: string;
  image_url: string;
  source_page_url: string;
  source_domain: string;
  width?: number | null;
  height?: number | null;
  license: string;
  author?: string;
  attribution_text?: string;
  local_thumb_path?: string;
  full_image_local_path?: string;
  has_watermark?: boolean;
}

export interface EvaluatedImage {
  rank: number;
  relevance_score: number;
  reason: string;
  concerns: string[];
  candidate: Candidate;
  has_watermark?: boolean;
  has_text_overlay_or_logo?: boolean;
  looks_ai_generated?: boolean;
  is_stock_preview?: boolean;
}

export interface Segment {
  id: string;
  text: string;
  index: number;
}

export interface SegmentIntent {
  segment_id: string;
  image_types: string[];
  queries: string[];
  key_elements: string[];
  mood_and_tone?: string;
  avoid?: string[];
}

export interface SegmentReport {
  segment: Segment;
  intent?: SegmentIntent;
  top_picks: EvaluatedImage[];
  alternates: EvaluatedImage[];
  status: 'ok' | 'weak_matches' | 'no_match';
  suggestion?: string;
}

export interface UsageStats {
  gemini_text_calls: number;
  gemini_vision_calls: number;
  gemini_prompt_tokens: number;
  gemini_output_tokens: number;
  serper_queries: number;
  wikimedia_queries: number;
  youtube_queries: number;
  l1_domain_blocked: number;
  l2_url_blocked: number;
  l3_vision_watermarked: number;
  estimated_cost_usd: number;
}

export interface RunData {
  run_id: string;
  script_name: string;
  total_segments: number;
  stats?: UsageStats;
  segments: SegmentReport[];
}

export interface RunSummary {
  run_id: string;
  script_name?: string;
  total_segments?: number;
  has_html: boolean;
  has_csv: boolean;
  has_json: boolean;
  stats?: UsageStats;
  timestamp: string;
}
