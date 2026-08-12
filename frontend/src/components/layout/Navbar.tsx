import React from 'react';
import { HealthStatus } from '../../types';

interface NavbarProps {
  activeTab: 'research' | 'graph' | 'documents' | 'system';
  setActiveTab: (tab: 'research' | 'graph' | 'documents' | 'system') => void;
  health: HealthStatus | null;
  activeJobCount: number;
  isDemoMode: boolean;
  setIsDemoMode: (val: boolean) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  health,
  activeJobCount,
  isDemoMode,
  setIsDemoMode,
}) => {
  const isHealthy = health?.status === 'healthy';

  return (
    <header className="border-b border-neutral-800 bg-black/80 backdrop-blur-md sticky top-0 z-50 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto flex items-center justify-between h-14">
        
        {/* Logo */}
        <div 
          onClick={() => setActiveTab('research')}
          className="flex items-center space-x-2.5 cursor-pointer"
        >
          <div className="w-6 h-6 rounded-md bg-white text-black font-mono font-bold flex items-center justify-center text-xs">
            Æ
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-sm font-semibold tracking-tight text-white">Aether</span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-900 text-neutral-400 border border-neutral-800">
              Multi-Agent
            </span>
          </div>
        </div>

        {/* Minimal Navigation */}
        <nav className="flex items-center space-x-1">
          {[
            { id: 'research', label: 'Research' },
            { id: 'graph', label: 'Knowledge Graph' },
            { id: 'documents', label: 'Documents' },
            { id: 'system', label: 'System' },
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-neutral-900 text-white border border-neutral-800'
                    : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/50'
                }`}
              >
                <span>{tab.label}</span>
                {tab.id === 'research' && activeJobCount > 0 && (
                  <span className="ml-1.5 w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block"></span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Status & Demo Mode */}
        <div className="flex items-center space-x-3 text-xs">
          <div className="hidden sm:flex items-center space-x-1.5 text-neutral-400 font-mono text-[11px]">
            <span className={`w-1.5 h-1.5 rounded-full ${isHealthy ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
            <span>{isHealthy ? 'Online' : 'Offline'}</span>
          </div>

          <button
            onClick={() => setIsDemoMode(!isDemoMode)}
            className={`px-2.5 py-1 rounded-md text-[11px] font-mono transition-colors border ${
              isDemoMode
                ? 'bg-neutral-900 text-neutral-200 border-neutral-700'
                : 'bg-black text-neutral-400 border-neutral-800 hover:text-neutral-200'
            }`}
          >
            {isDemoMode ? 'Demo Mode' : 'Live Mode'}
          </button>
        </div>

      </div>
    </header>
  );
};
