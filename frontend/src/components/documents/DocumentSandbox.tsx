import React, { useState } from 'react';
import { UploadCloud, FileText, CheckCircle2 } from 'lucide-react';
import { queryDocumentRAG } from '../../api/client';
import { RAGQueryResult } from '../../types';

export const DocumentSandbox: React.FC = () => {
  const [ticker, setTicker] = useState('NVDA');
  const [fiscalYear, setFiscalYear] = useState('2025');
  const [docType, setDocType] = useState('10-K');
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  
  const [searchQuery, setSearchQuery] = useState('What are the key gross margin drivers and supply risks?');
  const [ragResults, setRagResults] = useState<RAGQueryResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const handleSimulatedUpload = (e: React.FormEvent) => {
    e.preventDefault();
    setUploadStatus('Processing document...');
    setTimeout(() => {
      setUploadStatus(`Indexed 42 chunks for ${ticker.toUpperCase()} FY${fiscalYear} into Qdrant.`);
    }, 1200);
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const results = await queryDocumentRAG(searchQuery, ticker);
      setRagResults(results);
    } catch (e) {
      console.error(e);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-4 font-sans text-xs">
      
      {/* Upload */}
      <div className="vercel-card p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
          <span className="font-semibold text-white">SEC Document Ingestion</span>
          <span className="font-mono text-neutral-500 text-[11px]">Qdrant Vector DB</span>
        </div>

        <form onSubmit={handleSimulatedUpload} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <div>
              <label className="block text-neutral-400 mb-1">Ticker</label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                className="w-full px-3 py-1.5 bg-black border border-neutral-800 rounded text-white font-mono"
                required
              />
            </div>
            <div>
              <label className="block text-neutral-400 mb-1">Fiscal Year</label>
              <input
                type="number"
                value={fiscalYear}
                onChange={(e) => setFiscalYear(e.target.value)}
                className="w-full px-3 py-1.5 bg-black border border-neutral-800 rounded text-white font-mono"
                required
              />
            </div>
            <div>
              <label className="block text-neutral-400 mb-1">Filing Type</label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className="w-full px-3 py-1.5 bg-black border border-neutral-800 rounded text-white"
              >
                <option value="10-K">10-K Annual Report</option>
                <option value="10-Q">10-Q Quarterly Report</option>
                <option value="8-K">8-K Current Event</option>
              </select>
            </div>
          </div>

          <div className="p-5 rounded border border-dashed border-neutral-800 bg-black text-center cursor-pointer">
            <FileText className="w-5 h-5 text-neutral-500 mx-auto mb-1" />
            <p className="text-neutral-300">Drag & drop SEC filing PDF, or click to browse</p>
          </div>

          <div className="flex items-center justify-between">
            {uploadStatus ? (
              <span className="text-emerald-400 flex items-center space-x-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>{uploadStatus}</span>
              </span>
            ) : <span />}

            <button
              type="submit"
              className="px-4 py-1.5 bg-white text-black hover:bg-neutral-200 rounded font-semibold"
            >
              Upload & Index
            </button>
          </div>
        </form>
      </div>

      {/* Query */}
      <div className="vercel-card p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
          <span className="font-semibold text-white">Hybrid RAG Query Simulator</span>
          <span className="font-mono text-neutral-500 text-[11px]">Dense Vector + BM25</span>
        </div>

        <form onSubmit={handleQuery} className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Query passages..."
            className="flex-1 px-3 py-2 bg-black border border-neutral-800 rounded text-white font-mono"
          />
          <button
            type="submit"
            disabled={isSearching}
            className="px-4 py-2 bg-white text-black hover:bg-neutral-200 rounded font-semibold"
          >
            {isSearching ? 'Searching...' : 'Execute Search'}
          </button>
        </form>

        <div className="space-y-2">
          {ragResults.map((res, idx) => (
            <div key={idx} className="p-3 bg-black rounded border border-neutral-800 space-y-1">
              <div className="flex items-center justify-between text-white font-mono text-[11px]">
                <span>${res.company_ticker} {res.document_type} FY{res.fiscal_year}</span>
                <span className="text-neutral-500">RRF Score: {res.rrf_score.toFixed(3)}</span>
              </div>
              <p className="text-neutral-300 italic bg-neutral-950 p-2 rounded border border-neutral-900">
                "{res.passage_text}"
              </p>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
