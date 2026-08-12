import React, { useState, useEffect, useRef } from 'react';
import { Navbar } from './components/layout/Navbar';
import { ResearchLauncher } from './components/research/ResearchLauncher';
import { AgentSwarmTracker } from './components/research/AgentSwarmTracker';
import { StreamingTerminal } from './components/research/StreamingTerminal';
import { ReportViewer } from './components/research/ReportViewer';
import { HITLReviewModal } from './components/hitl/HITLReviewModal';
import { GraphExplorer } from './components/graph/GraphExplorer';
import { DocumentSandbox } from './components/documents/DocumentSandbox';
import { SystemHealth } from './components/system/SystemHealth';

import { HealthStatus, AgentInfo, AgentName, WebSocketFrame, ResearchJobRequest, ResearchReport, HITLReviewPayload } from './types';
import { getSystemHealth, launchResearchJob, ResearchStreamManager, generateMockReport } from './api/client';

const INITIAL_AGENTS: AgentInfo[] = [
  { id: 'supervisor', name: 'Supervisor Router', description: 'Orchestrates graph state transitions & agent routing', status: 'idle', progressPct: 0 },
  { id: 'research', name: 'Research Agent', description: 'Queries SEC EDGAR & retrieves Qdrant vector passages', status: 'idle', progressPct: 0 },
  { id: 'analysis', name: 'Financial Analysis Agent', description: 'Computes margins, debt ratios & liquidity risk metrics', status: 'idle', progressPct: 0 },
  { id: 'verify', name: 'Verification Agent', description: 'Audits claims against source SEC disclosures & citations', status: 'idle', progressPct: 0 },
  { id: 'graph_builder', name: 'Graph Builder Agent', description: 'Extracts entities & executes Neo4j Cypher writes', status: 'idle', progressPct: 0 },
  { id: 'report', name: 'Synthesis Report Agent', description: 'Compiles institutional Markdown report & metric cards', status: 'idle', progressPct: 0 },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<'research' | 'graph' | 'documents' | 'system'>('research');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  
  // Research Job State
  const [targetCompany, setTargetCompany] = useState<string>('NVDA');
  const [jobId, setJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [overallProgress, setOverallProgress] = useState<number>(0);
  const [activeAgentId, setActiveAgentId] = useState<AgentName | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>(INITIAL_AGENTS);
  const [frames, setFrames] = useState<WebSocketFrame[]>([]);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [hitlPayload, setHitlPayload] = useState<HITLReviewPayload | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const streamManagerRef = useRef<ResearchStreamManager | null>(null);

  useEffect(() => {
    getSystemHealth().then(setHealth).catch(console.error);
    const interval = setInterval(() => {
      getSystemHealth().then(setHealth).catch(console.error);
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleLaunchResearch = async (req: ResearchJobRequest) => {
    setIsSubmitting(true);
    setTargetCompany(req.target_company);
    setReport(null);
    setFrames([]);
    setOverallProgress(0);
    setAgents(INITIAL_AGENTS.map((a) => ({ ...a, status: 'idle', progressPct: 0 })));

    try {
      const res = await launchResearchJob(req);
      setJobId(res.job_id);
      triggerToast(`Dispatched Multi-Agent Swarm Job ${res.job_id} for $${req.target_company}`);

      // Subscribe to WebSocket Stream
      if (streamManagerRef.current) {
        streamManagerRef.current.unsubscribe();
      }

      const streamMgr = new ResearchStreamManager();
      streamManagerRef.current = streamMgr;

      streamMgr.subscribe(
        res.job_id,
        req.target_company,
        (frame: WebSocketFrame) => {
          setFrames((prev) => [...prev, frame]);
          setOverallProgress(frame.progress_pct);
          setActiveAgentId(frame.agent_name);

          // Check for HITL Interrupt
          if (frame.activity_type === 'hitl_interrupt') {
            setHitlPayload({
              job_id: frame.job_id,
              claim_id: `claim_${Math.random().toString(36).substring(2, 8)}`,
              agent_name: frame.agent_name,
              claim_text: frame.description,
              flagged_reason: 'Valuation gross margin assertion exceeds historical range without SEC 10-K citation match.',
              proposed_value: '75.3%',
              timestamp: frame.timestamp,
            });
          }

          // Update Agent Status Cards
          setAgents((prevAgents) =>
            prevAgents.map((agent) => {
              if (agent.id === frame.agent_name) {
                return {
                  ...agent,
                  status: frame.activity_type === 'complete' ? 'completed' : 'running',
                  progressPct: frame.progress_pct,
                  currentActivity: frame.description,
                  lastToolCall: frame.payload?.tool || frame.payload?.cypher ? 'Cypher Write' : undefined,
                };
              }
              if (agent.progressPct > 0 && agent.id !== frame.agent_name) {
                return { ...agent, status: 'completed' };
              }
              return agent;
            })
          );
        },
        (finalReport: ResearchReport) => {
          setReport(finalReport);
          setIsSubmitting(false);
          setActiveAgentId(null);
          setAgents((prev) => prev.map((a) => ({ ...a, status: 'completed', progressPct: 100 })));
          triggerToast(`Synthesis Report finalized for $${req.target_company}!`);
        }
      );

    } catch (e) {
      console.error(e);
      setIsSubmitting(false);
    }
  };

  // HITL Handlers
  const handleApproveHitl = (claimId: string) => {
    setHitlPayload(null);
    triggerToast(`HITL Claim ${claimId} Approved by Analyst.`);
  };

  const handleRejectHitl = (claimId: string, feedback: string) => {
    setHitlPayload(null);
    triggerToast(`HITL Claim ${claimId} Rejected. Re-routing to Supervisor.`);
  };

  const handleOverrideHitl = (claimId: string, newValue: string) => {
    setHitlPayload(null);
    triggerToast(`HITL Claim ${claimId} Overridden with value: ${newValue}`);
  };

  return (
    <div className="min-h-screen bg-[#070a11] text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      
      {/* Top Navigation Bar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
        activeJobCount={isSubmitting ? 1 : 0}
        isDemoMode={isDemoMode}
        setIsDemoMode={setIsDemoMode}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        
        {/* Toast Alert Banner */}
        {toastMessage && (
          <div className="mb-4 p-3 rounded-xl bg-cyan-950/90 border border-cyan-500/50 text-cyan-200 text-xs font-mono flex items-center justify-between shadow-glow-cyan animate-fade-in">
            <span>{toastMessage}</span>
            <button onClick={() => setToastMessage(null)} className="text-cyan-400 font-bold">×</button>
          </div>
        )}

        {/* Tab 1: Executive Research Hub */}
        {activeTab === 'research' && (
          <div className="space-y-6">
            <ResearchLauncher onLaunch={handleLaunchResearch} isSubmitting={isSubmitting} />

            <AgentSwarmTracker
              agents={agents}
              activeAgentId={activeAgentId}
              overallProgress={overallProgress}
              jobId={jobId}
              targetCompany={targetCompany}
            />

            <StreamingTerminal frames={frames} onClear={() => setFrames([])} />

            {report && <ReportViewer report={report} />}
          </div>
        )}

        {/* Tab 2: Knowledge Graph Explorer */}
        {activeTab === 'graph' && <GraphExplorer />}

        {/* Tab 3: Document RAG Sandbox */}
        {activeTab === 'documents' && <DocumentSandbox />}

        {/* Tab 4: System Health Monitor */}
        {activeTab === 'system' && <SystemHealth health={health} />}

      </main>

      {/* HITL Safety Review Intercept Modal */}
      <HITLReviewModal
        payload={hitlPayload}
        onApprove={handleApproveHitl}
        onReject={handleRejectHitl}
        onOverride={handleOverrideHitl}
      />

      {/* Footer Status Bar */}
      <footer className="border-t border-slate-800/80 py-3 bg-slate-950/80 text-[11px] font-mono text-slate-500 mt-8">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <span className="flex items-center space-x-1.5 text-cyan-400">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping"></span>
              <span>Aether Multi-Agent Platform v0.1.0</span>
            </span>
            <span>|</span>
            <span>LangGraph Supervisor Router</span>
            <span>|</span>
            <span>Qdrant + Neo4j GraphRAG</span>
          </div>
          <div>
            <span>Obsidian Dark Mode Design System</span>
          </div>
        </div>
      </footer>

    </div>
  );
}
