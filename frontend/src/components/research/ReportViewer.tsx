import React, { useState } from 'react';
import { Copy, Download, Check, ShieldCheck } from 'lucide-react';
import { ResearchReport } from '../../types';
import { MetricCard } from './MetricCard';

interface ReportViewerProps {
  report: ResearchReport;
}

export const ReportViewer: React.FC<ReportViewerProps> = ({ report }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(report.markdown_content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([report.markdown_content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Aether_Research_${report.target_company}_${new Date().toISOString().split('T')[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="vercel-card p-6 shadow-sm space-y-6">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-800 pb-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-neutral-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            <span>Verified Due Diligence Report</span>
            <span>•</span>
            <span>{new Date(report.generated_at).toLocaleDateString()}</span>
          </div>
          <h2 className="text-lg font-bold text-white font-sans mt-1">
            {report.company_name} <span className="font-mono text-neutral-400">(${report.target_company})</span>
          </h2>
        </div>

        <div className="flex items-center space-x-2 text-xs font-sans">
          <button
            onClick={handleCopy}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-neutral-900 text-neutral-300 hover:text-white border border-neutral-800"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>

          <button
            onClick={handleDownload}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-white text-black hover:bg-neutral-200 font-semibold shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div>
        <h4 className="text-xs font-mono text-neutral-400 uppercase tracking-wider mb-3">
          Key Metrics
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {report.metrics.map((metric, idx) => (
            <MetricCard key={idx} metric={metric} />
          ))}
        </div>
      </div>

      {/* Markdown Document Content */}
      <div className="bg-black p-6 rounded-lg border border-neutral-800 text-neutral-300 text-xs font-sans leading-relaxed space-y-3">
        {report.markdown_content.split('\n').map((line, idx) => {
          if (line.startsWith('# ')) {
            return <h1 key={idx} className="text-base font-bold text-white border-b border-neutral-800 pb-2">{line.replace('# ', '')}</h1>;
          }
          if (line.startsWith('## ')) {
            return <h2 key={idx} className="text-sm font-bold text-white mt-4">{line.replace('## ', '')}</h2>;
          }
          if (line.startsWith('### ')) {
            return <h3 key={idx} className="text-xs font-bold text-neutral-200 uppercase tracking-wider mt-3">{line.replace('### ', '')}</h3>;
          }
          if (line.startsWith('* ') || line.startsWith('1. ') || line.startsWith('2. ') || line.startsWith('3. ')) {
            return <div key={idx} className="flex items-start space-x-2 pl-2 text-neutral-300"><span className="text-white">•</span><span>{line.replace(/^(\*|\d+\.)\s*/, '')}</span></div>;
          }
          if (line.trim() === '---') {
            return <hr key={idx} className="border-neutral-800 my-3" />;
          }
          if (!line.trim()) return null;
          return <p key={idx} className="text-neutral-300">{line}</p>;
        })}
      </div>

      {/* SEC Citations */}
      <div className="border-t border-neutral-800 pt-4">
        <h4 className="text-xs font-mono text-neutral-400 uppercase tracking-wider mb-3 flex items-center space-x-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>SEC Disclosure Footnote Citations ({report.citations.length})</span>
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 font-sans text-xs">
          {report.citations.map((citation) => (
            <div key={citation.id} className="p-3 rounded-lg bg-black border border-neutral-800">
              <div className="flex items-center justify-between text-white font-semibold mb-1 text-[11px]">
                <span>{citation.source}</span>
                <span className="text-neutral-500 font-mono">{citation.filing_type} FY{citation.fiscal_year}</span>
              </div>
              <p className="text-neutral-400 italic text-[11px]">"{citation.passage_text}"</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
