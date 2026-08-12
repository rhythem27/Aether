import React, { useState } from 'react';
import { Search, ArrowRight } from 'lucide-react';
import { ResearchDepth, ResearchJobRequest } from '../../types';

interface ResearchLauncherProps {
  onLaunch: (req: ResearchJobRequest) => void;
  isSubmitting: boolean;
}

const PRESETS = ['NVDA', 'AAPL', 'MSFT', 'TSLA'];

export const ResearchLauncher: React.FC<ResearchLauncherProps> = ({ onLaunch, isSubmitting }) => {
  const [targetCompany, setTargetCompany] = useState('NVDA');
  const [researchDepth, setResearchDepth] = useState<ResearchDepth>('standard');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetCompany.trim()) return;

    onLaunch({
      target_company: targetCompany.trim().toUpperCase(),
      research_depth: researchDepth,
      focus_areas: ['financials', 'risk', 'competition'],
      data_sources: ['sec_edgar', 'crunchbase', 'neo4j'],
      output_format: 'markdown',
      human_review_gates: ['high_risk_claims'],
    });
  };

  return (
    <div className="vercel-card p-6 shadow-sm">
      
      <form onSubmit={handleSubmit} className="space-y-4">
        
        <div className="flex items-center justify-between">
          <label className="text-xs font-mono text-neutral-400 font-medium">
            Search Target Company Ticker
          </label>
          <span className="text-[11px] font-mono text-neutral-500">
            SEC EDGAR + GraphRAG
          </span>
        </div>

        {/* Input Bar */}
        <div className="flex items-center space-x-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={targetCompany}
              onChange={(e) => setTargetCompany(e.target.value)}
              placeholder="Search ticker (e.g. NVDA, AAPL)..."
              className="w-full pl-9 pr-4 py-2.5 bg-black border border-neutral-800 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-neutral-600 transition-colors"
              required
            />
            <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-3" />
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !targetCompany.trim()}
            className="px-5 py-2.5 bg-white text-black hover:bg-neutral-200 rounded-lg text-xs font-semibold font-sans transition-colors flex items-center space-x-1.5 disabled:opacity-50"
          >
            <span>{isSubmitting ? 'Initializing...' : 'Run Research'}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Ticker Chips & Scope */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-neutral-900 text-xs">
          
          <div className="flex items-center space-x-2">
            <span className="text-neutral-500 text-[11px] font-mono">Popular:</span>
            <div className="flex space-x-1">
              {PRESETS.map((ticker) => (
                <button
                  key={ticker}
                  type="button"
                  onClick={() => setTargetCompany(ticker)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono border transition-colors ${
                    targetCompany.toUpperCase() === ticker
                      ? 'bg-neutral-900 text-white border-neutral-700'
                      : 'bg-black text-neutral-500 border-neutral-800 hover:text-neutral-300'
                  }`}
                >
                  ${ticker}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-1 bg-black p-1 rounded-md border border-neutral-800 font-mono text-[11px]">
            {[
              { id: 'quick', label: 'Quick (~60s)' },
              { id: 'standard', label: 'Standard (~180s)' },
              { id: 'deep_dive', label: 'Deep-Dive (~300s)' },
            ].map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setResearchDepth(opt.id as ResearchDepth)}
                className={`px-2.5 py-1 rounded transition-colors ${
                  researchDepth === opt.id
                    ? 'bg-neutral-900 text-white font-medium border border-neutral-800'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

        </div>

      </form>
    </div>
  );
};
