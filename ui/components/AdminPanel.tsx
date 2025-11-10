'use client';

import { useState, useEffect, useRef } from 'react';
import { documentAPI, adminAPI } from '@/lib/api';
import { Document } from '@/lib/api';
import Toast from '@/components/Toast';

export default function AdminPanel() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState<string | null>(null);
  const [reindexProgress, setReindexProgress] = useState<{
    is_running: boolean;
    total: number;
    completed: number;
    current: string | null;
    errors: number;
    progress_percent: number;
  } | null>(null);
  const [toast, setToast] = useState<{
    show: boolean;
    message: string;
    type: 'success' | 'error' | 'info';
  }>({ show: false, message: '', type: 'info' });

  useEffect(() => {
    loadDocuments();
    loadStats();
  }, []);

  const loadDocuments = async (showSpinner: boolean = true) => {
    if (showSpinner) {
      setLoading(true);
    }
    try {
      const response = await documentAPI.list();
      setDocuments(response.documents);
      
      // Debug: Log status changes during reindexing
      if (reindexing) {
        const processingDocs = response.documents.filter(doc => 
          doc.status?.toLowerCase() === 'processing'
        );
        if (processingDocs.length > 0) {
          console.log(`[Reindex] Found ${processingDocs.length} documents with status "processing":`, 
            processingDocs.map(d => ({ id: d.id, filename: d.filename, status: d.status }))
          );
        }
      }
      
      setSelectedDocuments((prev) =>
        prev.filter((id) => response.documents.some((doc) => doc.id === id))
      );
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      if (showSpinner) {
        setLoading(false);
      }
    }
  };

  const loadStats = async () => {
    try {
      const response = await adminAPI.getStats();
      setStats(response);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const selectAllRef = useRef<HTMLInputElement | null>(null);
  const POLL_INTERVAL_MS = 5000;

  useEffect(() => {
    const hasProcessing = documents.some((doc) => {
      const status = doc.status?.toLowerCase() ?? '';
      return status === 'processing' || status === 'uploaded';
    });

    if (hasProcessing) {
      if (!refreshIntervalRef.current) {
        refreshIntervalRef.current = setInterval(() => {
          loadDocuments(false);
          loadStats();
        }, POLL_INTERVAL_MS);
      }
    } else if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
        refreshIntervalRef.current = null;
      }
    };
  }, [documents]);

  useEffect(() => {
    if (selectAllRef.current) {
      const total = documents.length;
      const selected = selectedDocuments.length;
      selectAllRef.current.indeterminate =
        selected > 0 && selected < total;
      selectAllRef.current.checked = total > 0 && selected === total;
    }
  }, [selectedDocuments, documents]);

  const handleToggleDocument = (id: string) => {
    setSelectedDocuments((prev) =>
      prev.includes(id) ? prev.filter((docId) => docId !== id) : [...prev, id]
    );
  };

  const handleToggleSelectAll = () => {
    if (selectedDocuments.length === documents.length) {
      setSelectedDocuments([]);
    } else {
      setSelectedDocuments(documents.map((doc) => doc.id));
    }
  };

  const handleDeleteSelected = async () => {
    if (!selectedDocuments.length) {
      return;
    }
    const count = selectedDocuments.length;
    if (
      !confirm(
        `Delete ${count} document${count === 1 ? '' : 's'}? This removes files, chunks, and metadata.`
      )
    ) {
      return;
    }

    setDeleting(true);
    try {
      await Promise.all(
        selectedDocuments.map((id) => documentAPI.delete(id))
      );
      alert(`Deleted ${count} document${count === 1 ? '' : 's'}.`);
      setSelectedDocuments([]);
      await loadDocuments(false);
      await loadStats();
    } catch (error: any) {
      console.group('[AdminPanel] Delete selected failed');
      console.error(error);
      if (error?.response) {
        console.error('Response status:', error.response.status);
        console.error('Response data:', error.response.data);
      }
      console.groupEnd();
      alert(`Failed to delete documents: ${error.message}`);
    } finally {
      setDeleting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    console.groupCollapsed('[AdminPanel] Upload triggered');
    console.table(
      Array.from(files).map(file => ({
        name: file.name,
        sizeBytes: file.size,
        type: file.type || 'n/a',
        lastModified: new Date(file.lastModified).toISOString(),
      }))
    );
    console.groupEnd();

    setUploading(true);
    try {
      const fileArray = Array.from(files);
      const results = await documentAPI.uploadMultiple(fileArray);

      const successCount = results.filter(r => r.status === 'uploaded').length;
      const failCount = results.filter(r => r.status === 'failed').length;

      console.groupCollapsed('[AdminPanel] Upload results');
      console.table(results.map(r => ({
        filename: r.filename,
        status: r.status,
        message: r.message ?? '',
        documentId: r.document_id ?? '',
      })));
      console.groupEnd();

      if (failCount === 0) {
        alert(`Successfully uploaded ${successCount} file(s)! Processing in background...`);
      } else {
        alert(`Uploaded ${successCount} file(s), ${failCount} failed. Check console for details.`);
      }

      loadDocuments();
      loadStats();
    } catch (error: any) {
      console.group('[AdminPanel] Upload exception');
      console.error(error);
      if (error?.response) {
        console.error('Response status:', error.response.status);
        console.error('Response data:', error.response.data);
      }
      console.groupEnd();
      alert(`Upload failed: ${error.message}`);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const renderStatusBadge = (status: string) => {
    const normalized = status?.toLowerCase();
    let label = 'Unknown';
    let classes = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ';

    switch (normalized) {
      case 'processed':
        label = 'Processed';
        classes += 'bg-green-100 text-green-800';
        break;
      case 'processing':
      case 'uploaded':
        label = 'Processing…';
        classes += 'bg-yellow-100 text-yellow-800';
        break;
      case 'failed':
        label = 'Failed';
        classes += 'bg-red-100 text-red-800';
        break;
      default:
        label = status || 'Unknown';
        classes += 'bg-gray-100 text-gray-800';
    }

    return <span className={classes}>{label}</span>;
  };

  const handleDeleteDocument = async (documentId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"? This will permanently delete the document and all associated data (chunks, parties, metadata, search indices, and files).`)) {
      return;
    }

    try {
      await documentAPI.delete(documentId);
      alert('Document deleted successfully');
      loadDocuments();
      loadStats();
    } catch (error: any) {
      alert(`Failed to delete document: ${error.message}`);
    }
  };

  const handleReindexAll = async () => {
    if (!confirm('Re-index all documents? This will rebuild search indexes for all processed documents. This may take a few minutes.')) {
      return;
    }

    setReindexing(true);
    setReindexMessage(null);
    // Initialize progress immediately so the progress bar shows right away
    setReindexProgress({
      is_running: true,
      total: 0,
      completed: 0,
      current: 'Initializing...',
      errors: 0,
      progress_percent: 0
    });
    
    // Start polling progress endpoint AND refresh documents to show status changes
    const progressInterval = setInterval(async () => {
      try {
        const progress = await adminAPI.getReindexProgress();
        setReindexProgress(progress);
        
        // ALSO refresh the documents list (don't await - let it run in background)
        // This ensures the polling loop isn't blocked by slow document queries
        loadDocuments(false).catch(err => console.error('Failed to load documents:', err));
        
        // Stop polling if reindexing is complete
        if (!progress.is_running) {
          clearInterval(progressInterval);
          // Do final refresh
          await loadDocuments();
          await loadStats();
          setReindexing(false);
          setReindexProgress(null);
          
          // Show completion toast
          const hasErrors = progress.errors > 0;
          const completionMessage = hasErrors 
            ? `Re-indexing completed with ${progress.errors} error(s). ${progress.completed} document(s) successfully processed.`
            : `Re-indexing completed successfully! All ${progress.completed} document(s) processed.`;
          
          setToast({
            show: true,
            message: completionMessage,
            type: hasErrors ? 'info' : 'success'
          });
        }
      } catch (error) {
        console.error('Failed to get reindex progress:', error);
      }
    }, 500); // Poll every 500ms
    
    // Fire-and-forget the reindex API call - don't wait for it
    // The polling interval will continue and stop naturally when is_running becomes false
    adminAPI.reindex()
      .catch(error => {
        // Only show error toast if the initial API call fails
        // (not the reindexing process itself, which is monitored by polling)
        const errorMessage = error.response?.data?.detail || error.message || 'Failed to start re-indexing';
        
        setToast({
          show: true,
          message: errorMessage,
          type: 'error'
        });
        
        setReindexMessage(`Error: ${errorMessage}`);
        console.error('Failed to start re-indexing:', error);
        
        // Clean up on error
        setReindexing(false);
        setReindexProgress(null);
      });
    
    // Note: Polling will continue until progress.is_running becomes false
    // Final refresh will happen when polling stops naturally (see lines 286-293)
  };

  return (
    <div className="space-y-6">
      {/* Reindexing Progress Bar - Prominent at top */}
      {reindexProgress && reindexProgress.is_running && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-300 rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <svg className="animate-spin h-6 w-6 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="text-lg font-semibold text-blue-900">
                Re-indexing Documents in Progress
              </span>
            </div>
            <span className="text-lg font-bold text-blue-700">
              {reindexProgress.completed} / {reindexProgress.total} ({reindexProgress.progress_percent.toFixed(0)}%)
            </span>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-4 mb-3 shadow-inner">
            <div 
              className="bg-gradient-to-r from-blue-600 to-indigo-600 h-4 rounded-full transition-all duration-500 shadow-sm"
              style={{ width: `${reindexProgress.progress_percent}%` }}
            />
          </div>
          {reindexProgress.current && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-blue-800">Currently processing:</span>
              <span className="text-sm text-blue-700 font-mono bg-white px-2 py-1 rounded border border-blue-200">
                {reindexProgress.current}
              </span>
            </div>
          )}
          {reindexProgress.errors > 0 && (
            <div className="mt-2 text-sm text-orange-700 font-medium">
              ⚠️ {reindexProgress.errors} error(s) occurred
            </div>
          )}
        </div>
      )}
      
      {/* Statistics */}
      {stats && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Statistics</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-600">Total Documents</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_documents}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Chunks</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_chunks}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Indexed Documents</p>
              <p className="text-2xl font-bold text-gray-900">{stats.indexed_documents}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Competency Questions</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_questions}</p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">OpenSearch:</span>
              <span className={`text-sm font-medium ${stats.opensearch_status === 'healthy' ? 'text-green-600' : 'text-red-600'}`}>
                {stats.opensearch_status}
              </span>
              <span className="text-sm text-gray-600">Qdrant:</span>
              <span className={`text-sm font-medium ${stats.qdrant_status === 'healthy' ? 'text-green-600' : 'text-red-600'}`}>
                {stats.qdrant_status}
              </span>
            </div>
              <button
                type="button"
                onClick={handleReindexAll}
                disabled={reindexing}
                className={`inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm ${
                  reindexing
                    ? 'bg-gray-400 text-white cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {reindexing ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Re-indexing...
                  </>
                ) : (
                  'Re-index All Documents'
                )}
              </button>
            </div>
            {reindexMessage && (
              <div className={`mt-3 p-3 rounded-md text-sm ${
                reindexMessage.startsWith('Error') 
                  ? 'bg-red-50 text-red-800 border border-red-200' 
                  : 'bg-green-50 text-green-800 border border-green-200'
              }`}>
                {reindexMessage}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Upload Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Document</h2>
        <div className="flex items-center gap-4">
          <label className="cursor-pointer">
            <span className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700">
              {uploading ? 'Uploading...' : 'Choose Files'}
            </span>
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={handleFileUpload}
              disabled={uploading}
              multiple
              className="hidden"
            />
          </label>
          <p className="text-sm text-gray-500">Supported formats: PDF, DOCX (You can select multiple files)</p>
        </div>
      </div>

      {/* Documents List */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Documents</h2>
          <button
            type="button"
            onClick={handleDeleteSelected}
            disabled={selectedDocuments.length === 0 || deleting}
            className={`inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm ${
              selectedDocuments.length === 0 || deleting
                ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                : 'bg-red-600 text-white hover:bg-red-700'
            }`}
          >
            {deleting ? 'Deleting…' : `Delete Selected${selectedDocuments.length ? ` (${selectedDocuments.length})` : ''}`}
          </button>
        </div>
        {loading ? (
          <p className="text-sm text-gray-600">Loading...</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-gray-600">No documents uploaded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <input
                      type="checkbox"
                      ref={selectAllRef}
                      onChange={handleToggleSelectAll}
                      disabled={documents.length === 0 || deleting}
                      className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Filename
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Upload Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {documents.map((doc) => (
                  <tr key={doc.id}>
                    <td className="px-4 py-4 whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={selectedDocuments.includes(doc.id)}
                        onChange={() => handleToggleDocument(doc.id)}
                        disabled={deleting}
                        className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {doc.filename}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {renderStatusBadge(doc.status)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(doc.upload_date).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center gap-3">
                        <a
                          href={`/documents/${doc.id}`}
                          className="text-primary-600 hover:text-primary-700"
                        >
                          View
                        </a>
                        <button
                          onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                          className="text-red-600 hover:text-red-700"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Toast Notification */}
      {toast.show && (
        <Toast
          key={toast.message}
          message={toast.message}
          type={toast.type}
          onClose={() => setToast({ show: false, message: '', type: 'info' })}
        />
      )}
    </div>
  );
}
