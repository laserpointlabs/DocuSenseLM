'use client';

import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';
import { documentAPI } from '@/lib/api';

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

interface DocumentViewerProps {
  documentId: string;
  highlightPage?: number;
  highlightStart?: number;
  highlightEnd?: number;
}

interface Chunk {
  id: string;
  chunk_index: number;
  section_type: string | null;
  clause_number: string | null;
  clause_title: string | null;  // Extracted clause title
  text: string;
  page_num: number;
  span_start: number;
  span_end: number;
}

export default function DocumentViewer({
  documentId,
  highlightPage,
  highlightStart,
  highlightEnd,
}: DocumentViewerProps) {
  const [clauses, setClauses] = useState<Chunk[]>([]);
  const [selectedClause, setSelectedClause] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDocument();
  }, [documentId]);

  const loadDocument = async () => {
    setLoading(true);
    setError(null);
    try {
      // Get PDF URL
      const fileUrl = documentAPI.getFileUrl(documentId);
      setPdfUrl(fileUrl);

      // Load chunks/clauses
      try {
        const chunksData = await documentAPI.getChunks(documentId);
        setClauses(chunksData.chunks || []);

        // If we have highlight params, navigate to that page
        if (highlightPage) {
          setPageNumber(highlightPage);
        }
      } catch (err) {
        console.warn('Failed to load chunks:', err);
        // Chunks might not be available yet if document is still processing
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load document');
    } finally {
      setLoading(false);
    }
  };

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    if (highlightPage && highlightPage <= numPages) {
      setPageNumber(highlightPage);
    }
  };

  const onDocumentLoadError = (error: Error) => {
    setError(`Failed to load PDF: ${error.message}`);
  };

  if (loading) {
    return (
      <div className="flex gap-6 h-[calc(100vh-200px)]">
        <div className="w-64 flex-shrink-0 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
            <p className="mt-2 text-sm text-gray-600">Loading...</p>
          </div>
        </div>
        <div className="flex-1 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            <p className="mt-2 text-sm text-gray-600">Loading document...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex gap-6 h-[calc(100vh-200px)]">
        <div className="w-64 flex-shrink-0 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Table of Contents</h2>
          <p className="text-sm text-gray-600">No clauses available</p>
        </div>
        <div className="flex-1 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-6 h-[calc(100vh-200px)]">
      {/* Left sidebar - TOC */}
      <div className="w-64 flex-shrink-0 bg-white rounded-lg shadow-sm border border-gray-200 p-4 overflow-y-auto">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Table of Contents</h2>
        {clauses.length === 0 ? (
          <p className="text-sm text-gray-600">No clauses available. Document may still be processing.</p>
        ) : (
          <nav className="space-y-1">
            {clauses.map((clause) => {
              // Simple display - use clause_title if available, otherwise clause_number or section_type
              let displayText = clause.clause_title || clause.clause_number || clause.section_type || 'Untitled Clause';

              return (
                <button
                  key={clause.id}
                  onClick={() => {
                    setSelectedClause(clause.id);
                    setPageNumber(clause.page_num);
                  }}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                    selectedClause === clause.id
                      ? 'bg-primary-100 text-primary-900 font-medium'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-medium">
                    {displayText}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    Page {clause.page_num}
                  </div>
                </button>
              );
            })}
          </nav>
        )}
      </div>

      {/* Right pane - PDF Viewer */}
      <div className="flex-1 bg-white rounded-lg shadow-sm border border-gray-200 p-6 overflow-y-auto">
        {highlightPage && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <p className="text-sm text-blue-800">
              Highlighted: Page {highlightPage}
              {highlightStart && highlightEnd && `, positions ${highlightStart}-${highlightEnd}`}
            </p>
          </div>
        )}

        {/* Page Navigation */}
        {numPages > 0 && (
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPageNumber(Math.max(1, pageNumber - 1))}
                disabled={pageNumber <= 1}
                className="px-3 py-1 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Previous
              </button>
              <span className="text-sm text-gray-600">
                Page {pageNumber} of {numPages}
              </span>
              <button
                onClick={() => setPageNumber(Math.min(numPages, pageNumber + 1))}
                disabled={pageNumber >= numPages}
                className="px-3 py-1 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* PDF Viewer */}
        {pdfUrl && (
          <div className="flex justify-center">
            <Document
              file={pdfUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading={
                <div className="text-center py-8">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                  <p className="mt-2 text-sm text-gray-600">Loading PDF...</p>
                </div>
              }
            >
              <Page
                pageNumber={pageNumber}
                renderTextLayer={true}
                renderAnnotationLayer={true}
                className="shadow-lg"
              />
            </Document>
          </div>
        )}
      </div>
    </div>
  );
}
