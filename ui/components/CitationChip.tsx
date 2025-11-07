'use client';

import { Citation } from '@/lib/api';
import Link from 'next/link';

interface CitationChipProps {
  citation: Citation;
}

export default function CitationChip({ citation }: CitationChipProps) {
  // Clean up clause number display (remove "8. T" type artifacts)
  const cleanClauseNumber = citation.clause_number?.replace(/\s*\.\s*T\s*$/, '').trim() || citation.clause_number;

  // Encode excerpt text for URL (truncate to first 200 chars to avoid long URLs)
  const excerptParam = citation.excerpt 
    ? encodeURIComponent(citation.excerpt.substring(0, 200))
    : '';

  return (
    <Link
      href={`/documents/${citation.doc_id}?page=${citation.page_num}&start=${citation.span_start}&end=${citation.span_end}${citation.clause_number ? `&clause=${citation.clause_number}` : ''}${excerptParam ? `&text=${excerptParam}` : ''}`}
      className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors"
      title={citation.excerpt ? citation.excerpt.substring(0, 200) : ''}
    >
      <span>
        Doc {citation.doc_id.substring(0, 8)}
        {cleanClauseNumber && `, Clause ${cleanClauseNumber}`}
        {citation.page_num && citation.page_num > 0 && `, Page ${citation.page_num}`}
      </span>
    </Link>
  );
}
