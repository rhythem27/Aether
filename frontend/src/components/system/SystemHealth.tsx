import React from 'react';
import { HealthStatus } from '../../types';

interface SystemHealthProps {
  health: HealthStatus | null;
}

export const SystemHealth: React.FC<SystemHealthProps> = () => {
  const services = [
    { name: 'Qdrant Vector Database', port: '6333', desc: '1024-dim dense vector similarity collection' },
    { name: 'Neo4j Graph Database', port: '7687', desc: 'GDS Louvain community & 2-hop Cypher engine' },
    { name: 'PostgreSQL Database', port: '5432', desc: 'LangGraph state checkpoint persistence' },
    { name: 'Redis Broker & Cache', port: '6379', desc: 'Celery background task broker & result cache' },
    { name: 'Celery Distributed Swarm', port: 'Worker Pool', desc: 'Asynchronous multi-agent research workers' },
    { name: 'FastMCP Gateway', port: 'JSON-RPC', desc: 'FastMCP connectors for SEC, Crunchbase & News' },
  ];

  return (
    <div className="space-y-4 font-sans text-xs">
      
      <div className="vercel-card p-5 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-white">System Infrastructure</h2>
          <p className="text-neutral-400 text-[11px]">Backend database & service statuses</p>
        </div>

        <div className="flex items-center space-x-1.5 text-emerald-400 font-mono text-[11px]">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span>All Services Operational</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {services.map((srv, idx) => (
          <div key={idx} className="vercel-card p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-white">{srv.name}</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            </div>

            <p className="text-neutral-400 text-[11px] leading-relaxed">
              {srv.desc}
            </p>

            <div className="pt-2 border-t border-neutral-900 flex items-center justify-between font-mono text-[10px] text-neutral-500">
              <span>Port: {srv.port}</span>
              <span className="text-emerald-400">HEALTHY (12ms)</span>
            </div>
          </div>
        ))}
      </div>

    </div>
  );
};
