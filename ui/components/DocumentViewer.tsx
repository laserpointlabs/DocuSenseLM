'use client';

import { useState, useEffect, useRef } from 'react';
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
  highlightText?: string; // Optional: text excerpt to highlight
  highlightClause?: string; // Optional: clause number for precise matching
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
  highlightText,
  highlightClause,
}: DocumentViewerProps) {
  const [clauses, setClauses] = useState<Chunk[]>([]);
  const [selectedClause, setSelectedClause] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [highlightRects, setHighlightRects] = useState<Array<{ x: number; y: number; width: number; height: number }>>([]);
  const [viewportSize, setViewportSize] = useState<{ width: number; height: number } | null>(null);
  const pageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadDocument();
  }, [documentId]);

  // Update page number when highlightPage changes
  useEffect(() => {
    if (highlightPage && highlightPage > 0) {
      setPageNumber(highlightPage);
      setHighlightRects([]); // Clear previous highlights
      
      // Clean up any existing highlight overlays
      const existingHighlights = document.querySelectorAll('.pdf-highlight');
      existingHighlights.forEach(el => el.remove());
    }
  }, [highlightPage, highlightStart, highlightEnd, highlightText]);

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

  const onPageLoadSuccess = async (page: any) => {
    if (highlightPage && page.pageNumber === highlightPage) {
      console.log('=== HIGHLIGHTING PAGE ===', highlightPage);
      
      // Wait for text layer to render
      setTimeout(async () => {
        try {
          // Get text to match
          let chunkText = '';
          if (highlightClause) {
            const chunks = await documentAPI.getChunks(documentId);
            const clauses = chunks.chunks || [];
            const targetChunk = clauses.find((c: Chunk) =>
              c.page_num === highlightPage && c.clause_number === highlightClause
            );
            if (!targetChunk) {
              setHighlightRects([]);
              return;
            }
            chunkText = targetChunk.text;
          } else if (highlightText) {
            chunkText = highlightText.replace(/^(Effective Date|Governing Law|Term|Parties):\s*/i, '').trim();
          } else {
            setHighlightRects([]);
            return;
          }
          
          // Get text content
          const textContent = await page.getTextContent();
          
          // Direct text matching - search for the exact text in PDF items
          const searchText = chunkText.toLowerCase().trim();
          // Normalize: remove extra spaces, keep punctuation for dates
          const searchNormalized = searchText.replace(/\s+/g, ' ').trim();
          let matchedIndices: number[] = [];
          
          // Build a normalized version of all PDF text for searching
          const pdfTextNormalized = textContent.items.map((item: any) => {
            const str = (item.str || '').toLowerCase();
            return str;
          });
          
          // Find where the search text appears in the normalized PDF text
          // Try different window sizes to account for text splitting
          for (let windowSize = 2; windowSize <= 10; windowSize++) {
            for (let start = 0; start <= pdfTextNormalized.length - windowSize; start++) {
              const window = pdfTextNormalized.slice(start, start + windowSize);
              const combined = window.join('').replace(/\s+/g, ' ').trim();
              
              // Check if this window contains our search text (normalized)
              const searchNoSpaces = searchNormalized.replace(/\s+/g, '');
              const combinedNoSpaces = combined.replace(/\s+/g, '');
              
              if (combinedNoSpaces.includes(searchNoSpaces)) {
                // Found a potential match - verify it's the right one
                // Check if the combined text ends with or contains our search text
                const searchWords = searchNormalized.split(/\s+/).filter(w => w.length > 0);
                const combinedWords = combined.split(/\s+/).filter(w => w.length > 0);
                
                // Try to find where searchWords appear in combinedWords
                for (let wordStart = 0; wordStart <= combinedWords.length - searchWords.length; wordStart++) {
                  const windowWords = combinedWords.slice(wordStart, wordStart + searchWords.length);
                  const windowText = windowWords.join(' ');
                  
                  if (windowText === searchNormalized || 
                      windowText.replace(/[^\w\s]/g, '') === searchNormalized.replace(/[^\w\s]/g, '')) {
                    // Found exact match - calculate which PDF items correspond to these words
                    // This is approximate - we'll use the window indices
                    matchedIndices = Array.from({ length: windowSize }, (_, idx) => start + idx);
                    console.log(`Found exact match at indices ${matchedIndices[0]}-${matchedIndices[matchedIndices.length - 1]}`);
                    break;
                  }
                }
                
                if (matchedIndices.length > 0) break;
              }
            }
            if (matchedIndices.length > 0) break;
          }
          
          // If direct match failed, try LLM
          if (matchedIndices.length === 0) {
            console.log('Direct match failed, trying LLM...');
            const pdfItemsForLLM = textContent.items.slice(0, 200).map((item: any, idx: number) => ({
              str: item.str || '',
              index: idx
            }));
            
            try {
              const matchResult = await documentAPI.findTextMatch(documentId, chunkText, pdfItemsForLLM);
              matchedIndices = matchResult.indices || [];
            } catch (err) {
              console.error('LLM matching failed:', err);
            }
          }
          
          if (matchedIndices.length === 0) {
            console.warn('No matches found for:', chunkText);
            setHighlightRects([]);
            return;
          }
          
          const llmIndices = matchedIndices;
          
          // Find the Page component wrapper (react-pdf renders it)
          const pageWrapper = pageRef.current?.querySelector('.react-pdf__Page') as HTMLElement;
          const textLayer = pageWrapper?.querySelector('.react-pdf__Page__textContent') as HTMLElement;
          
          if (!pageWrapper || !textLayer) {
            setTimeout(() => onPageLoadSuccess(page), 500);
            return;
          }
          
          const textSpans = Array.from(textLayer.querySelectorAll('span')) as HTMLElement[];
          if (textSpans.length === 0) {
            setTimeout(() => onPageLoadSuccess(page), 500);
            return;
          }
          
          // Highlight spans directly with CSS - much simpler and more reliable!
          // Based on article: "Highlighting source spans in PDFs" - use DOM directly
          const validIndices = llmIndices.filter(idx => idx >= 0 && idx < textSpans.length).sort((a, b) => a - b);
          
          if (validIndices.length === 0) {
            setHighlightRects([]);
            return;
          }
          
          // Clear any existing highlights first
          textSpans.forEach(span => {
            (span as HTMLElement).style.backgroundColor = '';
            (span as HTMLElement).style.borderRadius = '';
          });
          
          // Highlight matched spans directly - PDF.js text layer spans
          const highlightedTexts: string[] = [];
          validIndices.forEach((idx: number) => {
            const span = textSpans[idx] as HTMLElement;
            const spanText = span.textContent || '';
            highlightedTexts.push(spanText);
            span.style.backgroundColor = 'rgba(255, 255, 0, 0.4)'; // Yellow highlight
            span.style.borderRadius = '2px';
            span.style.padding = '1px 2px';
          });
          
          console.log(`✅ Highlighted ${validIndices.length} text spans:`, validIndices);
          console.log(`Highlighted text: "${highlightedTexts.join('')}"`);
          
          // Clear overlay rects since we're using direct CSS highlighting
          setHighlightRects([]);
          
          const scale = 1.5;
          const viewport = page.getViewport({ scale });
          setViewportSize({ width: viewport.width, height: viewport.height });
          
        } catch (err) {
          console.error('Highlighting failed:', err);
          setHighlightRects([]);
        }
      }, 500);
    } else {
      setHighlightRects([]);
      setViewportSize(null);
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
            {clauses.map((clause: Chunk) => {
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
          <div className="flex justify-center relative" ref={pageRef}>
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
              <div className="relative inline-block">
                <Page
                  pageNumber={pageNumber}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  className="shadow-lg"
                  onLoadSuccess={onPageLoadSuccess}
                  scale={1.5}
                />
              </div>
            </Document>
          </div>
        )}
      </div>
    </div>
  );
}
