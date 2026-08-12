// Data models & interfaces for Aether Platform UI

export type ResearchDepth = 'quick' | 'standard' | 'deep_dive';

export type AgentName = 
  | 'supervisor'
  | 'research'
  | 'analysis'
  | 'verify'
  | 'graph_builder'
  | 'report';

export type AgentStatus = 'idle' | 'running' | 'completed' | 'interrupted' | 'failed';

export interface AgentInfo {
  id: AgentName;
  name: string;
  description: string;
  status: AgentStatus;
  progressPct: number;
  currentActivity?: string;
  lastToolCall?: string;
}

export interface ResearchJobRequest {
  target_company: string;
  research_depth: ResearchDepth;
  focus_areas: string[];
  data_sources: string[];
  output_format: string;
  human_review_gates: string[];
}

export interface ResearchJobResponse {
  job_id: string;
  status: string;
  estimated_duration_seconds: number;
  poll_endpoint: string;
  created_at: string;
}

export interface WebSocketFrame {
  job_id: string;
  agent_name: AgentName;
  activity_type: 'start' | 'tool_call' | 'thought' | 'state_update' | 'hitl_interrupt' | 'complete' | 'error';
  description: string;
  timestamp: string;
  progress_pct: number;
  payload?: Record<string, any>;
}

export interface FinancialMetric {
  label: string;
  value: string;
  change?: string;
  trend?: 'up' | 'down' | 'neutral';
  status?: 'good' | 'warning' | 'critical' | 'neutral';
  subtext?: string;
}

export interface ResearchReport {
  job_id: string;
  target_company: string;
  company_name: string;
  generated_at: string;
  metrics: FinancialMetric[];
  markdown_content: string;
  citations: Array<{
    id: string;
    source: string;
    filing_type: string;
    fiscal_year: number;
    passage_text: string;
  }>;
  risk_score: number; // 0-100
}

export interface GraphNode {
  id: string;
  name: string;
  type: 'Company' | 'Executive' | 'Disclosure' | 'Metric' | 'RiskFactor';
  properties: Record<string, any>;
  x?: number;
  y?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
  properties?: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface DocumentUploadResponse {
  filename: string;
  total_chunks: number;
  document_type: string;
  company_ticker: string;
  fiscal_year: number;
  status: string;
}

export interface RAGQueryResult {
  chunk_id: string;
  company_ticker: string;
  document_type: string;
  fiscal_year: number;
  passage_text: string;
  dense_score: number;
  sparse_score: number;
  rrf_score: number;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'down';
  version: string;
  services: {
    qdrant: 'healthy' | 'down';
    neo4j: 'healthy' | 'down';
    postgres: 'healthy' | 'down';
    redis: 'healthy' | 'down';
    celery: 'healthy' | 'down';
  };
}

export interface HITLReviewPayload {
  job_id: string;
  claim_id: string;
  agent_name: string;
  claim_text: string;
  flagged_reason: string;
  metric_name?: string;
  proposed_value?: string;
  timestamp: string;
}
