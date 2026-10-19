import React from 'react';
import { Loader2, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import { DocumentItem } from '../../types';

interface StatusBadgeProps {
  status: DocumentItem['status'];
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  switch (status) {
    case 'completed':
      return (
        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-forest-50 text-forest-700 border border-forest-200 ${className}`}>
          <CheckCircle2 className="w-3.5 h-3.5 text-forest-600" />
          Indexed
        </span>
      );
    case 'failed':
      return (
        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200 ${className}`}>
          <AlertCircle className="w-3.5 h-3.5 text-red-600" />
          Failed
        </span>
      );
    case 'uploaded':
      return (
        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-parchment-200 text-ink-700 border border-parchment-300 ${className}`}>
          <Clock className="w-3.5 h-3.5 text-ink-500" />
          Queued
        </span>
      );
    default:
      // In-flight ingestion stages: validating, extracting, chunking, embedding, indexing
      return (
        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-navy-50 text-navy-800 border border-navy-200 ${className}`}>
          <Loader2 className="w-3.5 h-3.5 text-navy-600 animate-spin" />
          <span className="capitalize">{status}...</span>
        </span>
      );
  }
};
