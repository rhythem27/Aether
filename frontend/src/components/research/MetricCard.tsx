import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { FinancialMetric } from '../../types';

interface MetricCardProps {
  metric: FinancialMetric;
}

export const MetricCard: React.FC<MetricCardProps> = ({ metric }) => {
  return (
    <div className="vercel-card p-4 space-y-1">
      <div className="flex items-center justify-between text-xs text-neutral-400 font-sans font-medium">
        <span>{metric.label}</span>
        {metric.trend === 'up' ? (
          <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
        ) : metric.trend === 'down' ? (
          <TrendingDown className="w-3.5 h-3.5 text-rose-400" />
        ) : (
          <Minus className="w-3.5 h-3.5 text-neutral-500" />
        )}
      </div>

      <div className="text-xl font-bold font-mono text-white tracking-tight">
        {metric.value}
      </div>

      {metric.subtext && (
        <p className="text-[11px] font-mono text-neutral-400">
          {metric.subtext}
        </p>
      )}
    </div>
  );
};
