'use client';

import { SearchResult } from '@/lib/api';
import Link from 'next/link';

interface ResultsListProps {
  results: SearchResult[];
}

export default function ResultsList({ results }: ResultsListProps) {
  if (results.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">No results found. Try a different search query.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {results.map((result) => (
        <div
          key={result.chunk_id}
          className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
                  {result.section_type}
                </span>
                {result.clause_number && (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                    Clause {result.clause_number}
                  </span>
                )}
                <span className="text-xs text-gray-500">Page {result.page_num}</span>
                <span className="text-xs text-gray-500">Score: {result.score.toFixed(3)}</span>
              </div>
              <p className="text-sm text-gray-700 mb-3 line-clamp-3">
                {result.text}
              </p>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <Link
                  href={`/documents/${result.doc_id}`}
                  className="text-primary-600 hover:text-primary-700 font-medium"
                >
                  View Document →
                </Link>
                <span>Document ID: {result.doc_id.substring(0, 8)}...</span>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
