'use client';

import { useEffect, useState } from 'react';
import { SearchResult, documentAPI } from '@/lib/api';
import Link from 'next/link';

interface ResultsListProps {
  results: SearchResult[];
}

interface DocumentMetadata {
  filename: string;
  companyName?: string;
}

// Extract company name from filename (similar to dashboard logic)
function extractCompanyName(filename: string): string {
  // Remove common suffixes and extensions
  let name = filename
    .replace(/\.pdf$/i, '')
    .replace(/\.docx?$/i, '')
    .replace(/\s*NDA\s*/gi, '')
    .replace(/\s*-\s*\d{4}/, '') // Remove dates like "-2024"
    .trim();
  
  // If it's still long, take first meaningful part
  const parts = name.split(/[\s_-]+/);
  if (parts.length > 3) {
    name = parts.slice(0, 3).join(' ');
  }
  
  return name || filename;
}

export default function ResultsList({ results }: ResultsListProps) {
  const [documentMetadata, setDocumentMetadata] = useState<Record<string, DocumentMetadata>>({});
  const [loadingMetadata, setLoadingMetadata] = useState(true);

  useEffect(() => {
    const fetchMetadata = async () => {
      if (results.length === 0) {
        setLoadingMetadata(false);
        return;
      }

      // Get unique document IDs
      const uniqueDocIds = [...new Set(results.map(r => r.doc_id))];
      
      try {
        const metadataMap: Record<string, DocumentMetadata> = {};
        
        // Fetch metadata for each unique document
        await Promise.all(
          uniqueDocIds.map(async (docId) => {
            try {
              const doc = await documentAPI.get(docId);
              const companyName = extractCompanyName(doc.filename);
              metadataMap[docId] = {
                filename: doc.filename,
                companyName: companyName,
              };
            } catch (error) {
              console.error(`Failed to fetch metadata for ${docId}:`, error);
              // Fallback: extract from source_uri if available
              const result = results.find(r => r.doc_id === docId);
              if (result?.source_uri) {
                const filename = result.source_uri.split('/').pop() || docId;
                metadataMap[docId] = {
                  filename: filename,
                  companyName: extractCompanyName(filename),
                };
              } else {
                metadataMap[docId] = {
                  filename: docId.substring(0, 8) + '...',
                  companyName: docId.substring(0, 8) + '...',
                };
              }
            }
          })
        );
        
        setDocumentMetadata(metadataMap);
      } catch (error) {
        console.error('Error fetching document metadata:', error);
      } finally {
        setLoadingMetadata(false);
      }
    };

    fetchMetadata();
  }, [results]);

  if (results.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">No results found. Try a different search query.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {results.map((result) => {
        const metadata = documentMetadata[result.doc_id];
        const companyName = metadata?.companyName || result.doc_id.substring(0, 8) + '...';

        return (
          <div
            key={result.chunk_id}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  {metadata && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
                      {companyName}
                    </span>
                  )}
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
                  {loadingMetadata && (
                    <span className="text-gray-400">Loading metadata...</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
