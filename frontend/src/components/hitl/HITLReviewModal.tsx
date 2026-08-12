import React, { useState } from 'react';
import { AlertCircle, CheckCircle, XCircle, Edit3 } from 'lucide-react';
import { HITLReviewPayload } from '../../types';

interface HITLReviewModalProps {
  payload: HITLReviewPayload | null;
  onApprove: (claimId: string) => void;
  onReject: (claimId: string, feedback: string) => void;
  onOverride: (claimId: string, newValue: string) => void;
}

export const HITLReviewModal: React.FC<HITLReviewModalProps> = ({
  payload,
  onApprove,
  onReject,
  onOverride,
}) => {
  const [feedback, setFeedback] = useState('');
  const [overrideVal, setOverrideVal] = useState(payload?.proposed_value || '');

  if (!payload) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="max-w-lg w-full fin-card border border-amber-800/80 bg-[#0f172a] shadow-2xl overflow-hidden">
        
        {/* Header */}
        <div className="px-5 py-3.5 bg-amber-950/40 border-b border-amber-800/60 flex items-center justify-between">
          <div className="flex items-center space-x-2 text-amber-400 font-bold text-xs">
            <AlertCircle className="w-4 h-4" />
            <span>Human-in-the-Loop Analyst Verification Gate</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-900/60 text-amber-300 border border-amber-700">
            High Risk Claim
          </span>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 font-sans text-xs">
          <div>
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Flagged Financial Claim
            </span>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 italic leading-relaxed">
              "{payload.claim_text}"
            </div>
          </div>

          <div>
            <span className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider block mb-1">
              Audit Gate Reason
            </span>
            <p className="text-slate-300 bg-slate-900 p-2.5 rounded-lg border border-slate-800">
              {payload.flagged_reason}
            </p>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Corrected Value / Numerical Override
            </label>
            <input
              type="text"
              value={overrideVal}
              onChange={(e) => setOverrideVal(e.target.value)}
              placeholder="e.g. Corrected Gross Margin: 72.1%"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 font-mono text-xs focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="px-5 py-3.5 bg-slate-950 border-t border-slate-800 flex items-center justify-between gap-2">
          <button
            onClick={() => onReject(payload.claim_id, feedback)}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-rose-950/80 text-rose-300 border border-rose-800 text-xs font-semibold hover:bg-rose-900"
          >
            <XCircle className="w-4 h-4" />
            <span>Reject Claim</span>
          </button>

          <div className="flex items-center space-x-2">
            {overrideVal.trim() && (
              <button
                onClick={() => onOverride(payload.claim_id, overrideVal)}
                className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-slate-800 text-slate-200 border border-slate-700 text-xs font-semibold"
              >
                <Edit3 className="w-4 h-4" />
                <span>Submit Override</span>
              </button>
            )}

            <button
              onClick={() => onApprove(payload.claim_id)}
              className="flex items-center space-x-1 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-sm"
            >
              <CheckCircle className="w-4 h-4" />
              <span>Approve & Release Report</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
