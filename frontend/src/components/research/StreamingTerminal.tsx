import React, { useState, useEffect, useRef } from 'react';
import { Copy, Trash2, ArrowDownCircle, Check, ChevronRight, ChevronDown } from 'lucide-react';
import { WebSocketFrame } from '../../types';

interface StreamingTerminalProps {
  frames: WebSocketFrame[];
  onClear: () => void;
}

export const StreamingTerminal: React.FC<StreamingTerminalProps> = ({ frames, onClear }) => {
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [frames, autoScroll]);

  const handleCopy = () => {
    const text = frames
      .map((f) => `[${f.timestamp}] [${f.agent_name.toUpperCase()}] ${f.description}`)
      .join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="vercel-card border border-neutral-800 overflow-hidden flex flex-col h-72">
      
      {/* Top Header */}
      <div className="px-4 py-2.5 bg-black border-b border-neutral-800 flex items-center justify-between font-mono text-xs text-neutral-400">
        <div className="flex items-center space-x-2">
          <span className="text-white font-medium">Activity Stream</span>
          <span className="text-[10px] text-neutral-500">({frames.length} events)</span>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-2 py-0.5 rounded text-[10px] flex items-center space-x-1 ${
              autoScroll ? 'bg-neutral-900 text-white border border-neutral-800' : 'text-neutral-500'
            }`}
          >
            <ArrowDownCircle className="w-3 h-3" />
            <span>Auto-scroll</span>
          </button>

          <button onClick={handleCopy} className="p-1 text-neutral-500 hover:text-white" title="Copy log">
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          <button onClick={onClear} className="p-1 text-neutral-500 hover:text-rose-400" title="Clear log">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Log Feed */}
      <div className="flex-1 p-3 overflow-y-auto font-mono text-[11px] space-y-1 bg-[#000000]">
        {frames.length === 0 ? (
          <div className="text-neutral-600 text-center py-10 font-sans text-xs">
            No stream events. Run research to observe live activity.
          </div>
        ) : (
          frames.map((frame, idx) => {
            const isExpanded = expandedIndex === idx;
            const timeStr = new Date(frame.timestamp).toLocaleTimeString();

            return (
              <div key={idx} className="border-b border-neutral-900/60 pb-1 pt-0.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-neutral-300">
                    <span className="text-neutral-600 text-[10px]">{timeStr}</span>
                    <span className="text-white font-medium text-[10px]">[{frame.agent_name}]</span>
                    <span className="text-neutral-300 font-sans text-xs">{frame.description}</span>
                  </div>

                  {frame.payload && (
                    <button
                      onClick={() => setExpandedIndex(isExpanded ? null : idx)}
                      className="text-neutral-500 hover:text-white"
                    >
                      {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    </button>
                  )}
                </div>

                {isExpanded && frame.payload && (
                  <pre className="mt-1 p-2 rounded bg-neutral-950 border border-neutral-800 text-[10px] text-neutral-300 overflow-x-auto">
                    {JSON.stringify(frame.payload, null, 2)}
                  </pre>
                )}
              </div>
            );
          })
        )}
        <div ref={terminalEndRef} />
      </div>

    </div>
  );
};
