import React, { useState, useEffect } from 'react';
import { Search, Info } from 'lucide-react';
import { fetchGraphData } from '../../api/client';
import { GraphData, GraphNode } from '../../types';

export const GraphExplorer: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('NVDA');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadGraph('NVDA');
  }, []);

  const loadGraph = async (ticker: string) => {
    setLoading(true);
    try {
      const data = await fetchGraphData(ticker);
      setGraphData(data);
      if (data.nodes.length > 0) {
        setSelectedNode(data.nodes[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const filteredNodes = graphData?.nodes.filter((node) => {
    if (selectedCategory !== 'ALL' && node.type !== selectedCategory) return false;
    if (searchTerm && !node.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  }) || [];

  return (
    <div className="space-y-6 font-sans text-xs">
      
      {/* Search Toolbar */}
      <div className="vercel-card p-4 border border-neutral-800 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center space-x-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && loadGraph(searchTerm)}
              placeholder="Search ticker or entity (e.g. NVDA)..."
              className="w-full pl-9 pr-3 py-2 bg-black border border-neutral-800 rounded-md text-white font-mono text-xs focus:outline-none focus:border-neutral-600"
            />
            <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-2.5" />
          </div>

          <button
            onClick={() => loadGraph(searchTerm)}
            disabled={loading}
            className="px-3.5 py-2 bg-white text-black hover:bg-neutral-200 rounded-md text-xs font-semibold"
          >
            {loading ? 'Searching...' : 'Query Neo4j'}
          </button>
        </div>

        {/* Categories */}
        <div className="flex flex-wrap gap-1 font-mono text-[11px]">
          {['ALL', 'Company', 'Disclosure', 'Metric', 'Executive', 'RiskFactor'].map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-2.5 py-1 rounded transition-colors ${
                selectedCategory === cat
                  ? 'bg-neutral-800 text-white font-medium border border-neutral-700'
                  : 'bg-black text-neutral-500 border border-neutral-800 hover:text-neutral-300'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Grid Canvas & Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        
        {/* Canvas Grid */}
        <div className="lg:col-span-2 vercel-card p-5 border border-neutral-800 space-y-3">
          <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
            <span className="font-semibold text-white">Neo4j GraphRAG Entity Canvas</span>
            <span className="font-mono text-neutral-500 text-[11px]">2-Hop Traversal</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 py-3 bg-black p-3 rounded-lg border border-neutral-800 min-h-[300px]">
            {filteredNodes.map((node) => {
              const isSelected = selectedNode?.id === node.id;
              return (
                <button
                  key={node.id}
                  onClick={() => setSelectedNode(node)}
                  className={`p-3 rounded border text-left flex flex-col justify-between transition-colors ${
                    isSelected
                      ? 'bg-neutral-900 border-neutral-600 text-white'
                      : 'bg-neutral-950 border-neutral-850 text-neutral-400 hover:border-neutral-800'
                  }`}
                >
                  <span className="text-[10px] font-mono text-neutral-500 uppercase block mb-1">
                    {node.type}
                  </span>
                  <span className="text-xs font-medium text-white truncate block">
                    {node.name}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Node Inspector */}
        <div className="vercel-card p-5 border border-neutral-800 space-y-3">
          <div className="flex items-center space-x-2 border-b border-neutral-800 pb-2">
            <Info className="w-3.5 h-3.5 text-neutral-400" />
            <span className="font-semibold text-white">Entity Inspector</span>
          </div>

          {selectedNode ? (
            <div className="space-y-3 text-xs">
              <div className="p-3 bg-black rounded border border-neutral-800 space-y-1">
                <span className="text-neutral-500 text-[10px] uppercase font-mono">Entity</span>
                <div className="text-sm font-semibold text-white">{selectedNode.name}</div>
                <div className="text-neutral-400 text-[11px]">Type: {selectedNode.type}</div>
              </div>

              <div>
                <span className="text-[11px] font-mono text-neutral-400 uppercase block mb-1.5">Properties</span>
                <div className="space-y-1 bg-black p-3 rounded border border-neutral-800 font-mono text-[11px]">
                  {Object.entries(selectedNode.properties).map(([k, v]) => (
                    <div key={k} className="flex justify-between border-b border-neutral-900 pb-1">
                      <span className="text-neutral-500">{k}:</span>
                      <span className="text-white font-medium">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-neutral-500 text-xs">
              Select an entity node to inspect attributes.
            </div>
          )}
        </div>

      </div>

    </div>
  );
};
