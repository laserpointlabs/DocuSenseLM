'use client';

import { Citation } from '@/lib/api';
import Link from 'next/link';

interface CitationChipProps {
  citation: Citation;
}

export default function CitationChip({ citation }: CitationChipProps) {
  return (
    <Link
      href={`/documents/${citation.doc_id}?page=${citation.page_num}&start=${citation.span_start}&end=${citation.span_end}`}
      className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors"
    >
      <span>
        Doc {citation.doc_id.substring(0, 8)}
        {citation.clause_number && `, Clause ${citation.clause_number}`}
        {citation.page_num && `, Page ${citation.page_num}`}
      </span>
    </Link>
  );
}
