import React from 'react';
import { AgentInfo, AgentName } from '../../types';

interface AgentSwarmTrackerProps {
  agents: AgentInfo[];
  activeAgentId: AgentName | null;
  overallProgress: number;
  jobId: string | null;
  targetCompany: string;
}

export const AgentSwarmTracker: React.FC<AgentSwarmTrackerProps> = ({
  agents,
  activeAgentId,
  overallProgress,
  targetCompany,
}) => {
  return (
    <div className="vercel-card p-5 space-y-4">
      
      {/* Header */}
      <div className="flex items-center justify-between text-xs font-mono">
        <div className="text-neutral-400">
          Execution Pipeline <span className="text-white font-semibold">— ${targetCompany || 'NVDA'}</span>
        </div>
        <div className="text-neutral-400 font-medium">
          {Math.round(overallProgress)}% Complete
        </div>
      </div>

      {/* Thin Progress Bar */}
      <div className="w-full bg-neutral-900 h-1 rounded-full overflow-hidden border border-neutral-800">
        <div
          className="bg-white h-full transition-all duration-300"
          style={{ width: `${overallProgress}%` }}
        />
      </div>

      {/* Steps List */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 pt-1">
        {agents.map((agent, idx) => {
          const isActive = activeAgentId === agent.id;
          const isCompleted = agent.status === 'completed';
          const isRunning = agent.status === 'running';

          let statusDot = <span className="w-1.5 h-1.5 rounded-full bg-neutral-700"></span>;
          if (isCompleted) {
            statusDot = <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>;
          } else if (isRunning || isActive) {
            statusDot = <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>;
          }

          return (
            <div
              key={agent.id}
              className={`p-3 rounded-lg border text-xs font-sans transition-colors ${
                isActive || isRunning
                  ? 'bg-neutral-900 border-neutral-700 text-white'
                  : isCompleted
                  ? 'bg-neutral-950/60 border-neutral-850 text-neutral-300'
                  : 'bg-black/40 border-neutral-900 text-neutral-500'
              }`}
            >
              <div className="flex items-center justify-between font-mono text-[11px] mb-1">
                <span className="text-neutral-500">0{idx + 1}</span>
                {statusDot}
              </div>

              <div className="font-medium text-white text-xs">{agent.name}</div>
              <div className="text-[11px] text-neutral-400 font-mono truncate mt-0.5">
                {agent.currentActivity || agent.description}
              </div>
            </div>
          );
        })}
      </div>

    </div>
  );
};
