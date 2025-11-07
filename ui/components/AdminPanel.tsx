'use client';

import { useState, useEffect, useRef } from 'react';
import { documentAPI, adminAPI } from '@/lib/api';
import { Document } from '@/lib/api';

export default function AdminPanel() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);

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

  return (
    <div className="space-y-6">
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
    </div>
  );
}
