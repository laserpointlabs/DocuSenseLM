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
    // Only highlight if we're on the highlight page
    if (highlightPage && page.pageNumber === highlightPage) {
      console.log('Attempting to highlight on page:', highlightPage);
      try {
        // Get text content from the page
        const textContent = await page.getTextContent();
        console.log('Text content items:', textContent.items.length);
        
        // Get viewport for coordinate conversion
        const viewport = page.getViewport({ scale: 1.5 });
        
        // Strategy: Find matching text items directly by content, not character positions
        let highlightItems: any[] = [];
        
        // Get the text we want to highlight
        let searchText = '';
        if (highlightClause) {
          // Use exact chunk text if we have clause number
          const exactChunk = clauses.find(c => 
            c.page_num === highlightPage && 
            c.clause_number === highlightClause
          );
          if (exactChunk && exactChunk.text) {
            searchText = exactChunk.text;
            console.log(`Using exact chunk text for clause ${highlightClause}`);
          }
        }
        
        // Fallback to highlightText if no chunk found
        if (!searchText && highlightText) {
          // Extract key text from highlightText (remove metadata prefixes)
          searchText = highlightText
            .replace(/^(term|effective date|governing law|expiration date|parties?):\s*/i, '')
            .replace(/\s*\([^)]*\)/g, '')
            .trim();
          
          // If it's a date, extract just the date
          const dateMatch = searchText.match(/(\w+\s+\d{1,2},?\s+\d{4})/i);
          if (dateMatch) {
            searchText = dateMatch[1];
          }
        }
        
        if (searchText) {
          const searchTextLower = searchText.toLowerCase();
          console.log('Searching for text:', searchText.substring(0, 50));
          
          // Find text items that contain the search text
          // Build text progressively to find matches
          let accumulatedText = '';
          let startIndex = -1;
          
          for (let i = 0; i < textContent.items.length; i++) {
            const item = textContent.items[i];
            const itemText = item.str || '';
            accumulatedText += itemText;
            
            // Check if accumulated text contains our search text
            const accumulatedLower = accumulatedText.toLowerCase();
            const foundIndex = accumulatedLower.indexOf(searchTextLower);
            
            if (foundIndex >= 0 && startIndex === -1) {
              // Found the start - now find all items that are part of this match
              startIndex = i;
              
              // Calculate which items are part of the match
              let charCount = 0;
              for (let j = 0; j <= i; j++) {
                const prevItem = textContent.items[j];
                const prevText = prevItem.str || '';
                charCount += prevText.length;
              }
              
              // Now find items that overlap with the match
              let matchCharStart = foundIndex;
              let matchCharEnd = foundIndex + searchText.length;
              let currentCharPos = 0;
              
              for (let j = 0; j < textContent.items.length; j++) {
                const item = textContent.items[j];
                const itemText = item.str || '';
                const itemStart = currentCharPos;
                const itemEnd = currentCharPos + itemText.length;
                
                // Check if this item overlaps with our match
                if (itemEnd > matchCharStart && itemStart < matchCharEnd) {
                  highlightItems.push(item);
                }
                
                currentCharPos = itemEnd;
                
                // Stop if we've passed the match
                if (itemStart >= matchCharEnd) {
                  break;
                }
              }
              
              break; // Found match, stop searching
            }
            
            // Limit accumulated text to avoid memory issues
            if (accumulatedText.length > 500) {
              accumulatedText = accumulatedText.substring(accumulatedText.length - 200);
            }
          }
          
          console.log(`Found ${highlightItems.length} text items matching "${searchText.substring(0, 30)}"`);
        }
        
        console.log('Found highlight items:', highlightItems.length);
        
        if (highlightItems.length > 0) {
          console.log('Creating highlight rectangles from', highlightItems.length, 'text items');
          
          // Group items by Y position (same line) - use transform[5] rounded to group
          const lineGroups: { [key: number]: any[] } = {};
          highlightItems.forEach((item: any) => {
            // Round Y to 0.1 precision to group items on same line
            const yPos = Math.round(item.transform[5] * 10) / 10;
            if (!lineGroups[yPos]) {
              lineGroups[yPos] = [];
            }
            lineGroups[yPos].push(item);
          });
          
          const rects: Array<{ x: number; y: number; width: number; height: number }> = [];
          
          // Create one rectangle per line
          Object.entries(lineGroups).forEach(([yPosStr, items]) => {
            // Sort items by X position
            items.sort((a, b) => a.transform[4] - b.transform[4]);
            
            const firstItem = items[0];
            const lastItem = items[items.length - 1];
            
            // Get X bounds
            const minX = firstItem.transform[4];
            // Calculate width: last item X + its width (transform[0] is horizontal scale)
            const lastItemWidth = Math.abs(lastItem.transform[0]) * (lastItem.str?.length || 0) || 50;
            const maxX = lastItem.transform[4] + lastItemWidth;
            
            // Convert Y from PDF coordinate system (bottom-left origin) to CSS (top-left origin)
            // transform[5] is Y from bottom, transform[3] is height (can be negative)
            const yFromBottom = parseFloat(yPosStr);
            const height = Math.abs(firstItem.transform[3] || 12);
            
            // PDF.js coordinate conversion: y = viewport.height - transform[5] - height
            const y = viewport.height - yFromBottom - height;
            
            rects.push({
              x: minX,
              y: y,
              width: maxX - minX,
              height: Math.max(height, 12),
            });
            
            const textPreview = items.map((i: any) => i.str).join('').substring(0, 50);
            console.log(`Line rect: x=${minX.toFixed(1)}, y=${y.toFixed(1)}, yFromBottom=${yFromBottom.toFixed(1)}, height=${height.toFixed(1)}, text="${textPreview}..."`);
          });
          
          console.log('Created', rects.length, 'highlight rectangles');
          setHighlightRects(rects);
        } else {
          console.warn('No highlight items found - using fallback highlight');
          // Fallback: highlight a general area
          const viewport = page.getViewport({ scale: 1.5 });
          setHighlightRects([{
            x: 50,
            y: 100,
            width: viewport.width - 100,
            height: 150,
          }]);
        }
      } catch (err) {
        console.error('Failed to calculate highlight positions:', err);
        setHighlightRects([]);
      }
    } else {
      setHighlightRects([]);
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
                {/* Highlight overlay - positioned relative to Page component */}
                {highlightRects.length > 0 && pageNumber === highlightPage && (
                  <div 
                    className="absolute top-0 left-0 pointer-events-none z-10"
                    style={{
                      width: '100%',
                      height: '100%',
                    }}
                  >
                    {highlightRects.map((rect, idx) => {
                      console.log('Rendering highlight rect:', rect);
                      return (
                        <div
                          key={idx}
                          className="absolute bg-yellow-300 bg-opacity-60 border border-yellow-500 rounded-sm"
                          style={{
                            left: `${rect.x}px`,
                            top: `${rect.y}px`,
                            width: `${rect.width}px`,
                            height: `${rect.height}px`,
                          }}
                          title="Citation location"
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            </Document>
          </div>
        )}
      </div>
    </div>
  );
}
