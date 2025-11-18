'use client';

import { useState, useEffect } from 'react';
import { templateAPI, Template } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import TemplatePreview from './TemplatePreview';

interface TemplateVersionManagerProps {
  templateKey: string;
  onClose: () => void;
}

export default function TemplateVersionManager({ templateKey, onClose }: TemplateVersionManagerProps) {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [versions, setVersions] = useState<Template[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [previewTemplate, setPreviewTemplate] = useState<Template | null>(null);

  useEffect(() => {
    if (templateKey) {
      loadVersions();
    }
  }, [templateKey]);

  const loadVersions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await templateAPI.listVersions(templateKey);
      setVersions(response.templates);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load template versions');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteVersion = async (version: number) => {
    if (!confirm(`Are you sure you want to delete version ${version}? This action cannot be undone.`)) {
      return;
    }

    setDeleting(version);
    try {
      await templateAPI.deleteVersion(templateKey, version);
      await loadVersions();
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete version');
      console.error(err);
    } finally {
      setDeleting(null);
    }
  };

  const handleSetCurrent = async (version: number) => {
    if (!user || user.role !== 'admin') {
      setError('Admin access required');
      return;
    }

    setUpdating(`${version}`);
    setError(null);
    try {
      await templateAPI.setCurrentVersion(templateKey, version);
      await loadVersions(); // Reload to update is_current flags
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to set current version');
    } finally {
      setUpdating(null);
    }
  };

  if (!templateKey) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold text-gray-900">Template Versions</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
            >
              ×
            </button>
          </div>
          <p className="text-sm text-gray-600 mt-1">Template Key: <code className="bg-gray-100 px-2 py-1 rounded">{templateKey}</code></p>
        </div>

        <div className="p-6">
          {loading ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <p className="mt-2 text-gray-600">Loading versions...</p>
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800">{error}</p>
            </div>
          ) : versions.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-600">No versions found for this template.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {versions.map((version) => (
                <div
                  key={version.id}
                  className={`border rounded-lg p-4 ${
                    version.is_current ? 'border-primary-500 bg-primary-50' : 'border-gray-200'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="text-lg font-semibold text-gray-900">
                          Version {version.version}
                        </h3>
                        {version.is_current && (
                          <span className="px-2 py-1 text-xs font-medium bg-primary-600 text-white rounded">
                            Current
                          </span>
                        )}
                        {!version.is_active && (
                          <span className="px-2 py-1 text-xs font-medium bg-gray-400 text-white rounded">
                            Inactive
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{version.name}</p>
                      {version.description && (
                        <p className="text-sm text-gray-500 mt-1">{version.description}</p>
                      )}
                      {version.change_notes && (
                        <div className="mt-2 p-2 bg-gray-50 rounded text-sm text-gray-700">
                          <strong>Change Notes:</strong> {version.change_notes}
                        </div>
                      )}
                      <div className="mt-2 text-xs text-gray-500">
                        Created: {new Date(version.created_at).toLocaleString()}
                        {version.created_by && ` by ${version.created_by}`}
                      </div>
                    </div>
                    <div className="flex gap-2 ml-4">
                      <button
                        onClick={() => setPreviewTemplate(version)}
                        className="px-3 py-1.5 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                      >
                        View PDF
                      </button>
                      <a
                        href={templateAPI.downloadFile(version.id, version.version, 'docx')}
                        download
                        className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                        onClick={(e) => {
                          e.preventDefault();
                          const token = localStorage.getItem('auth_token');
                          const url = templateAPI.downloadFile(version.id, version.version, 'docx');
                          fetch(url, {
                            headers: {
                              'Authorization': `Bearer ${token}`,
                            },
                          })
                            .then(res => res.blob())
                            .then(blob => {
                              const downloadUrl = window.URL.createObjectURL(blob);
                              const a = document.createElement('a');
                              a.href = downloadUrl;
                              a.download = `${version.name}_v${version.version || 1}.docx`;
                              document.body.appendChild(a);
                              a.click();
                              window.URL.revokeObjectURL(downloadUrl);
                              document.body.removeChild(a);
                            })
                            .catch(err => {
                              console.error('Failed to download template:', err);
                            });
                        }}
                      >
                        Download DOCX
                      </a>
                      {user?.role === 'admin' && (
                        <div className="flex gap-2">
                          {!version.is_current && (
                            <button
                              onClick={() => handleSetCurrent(version.version || 1)}
                              disabled={updating === `${version.version}`}
                              className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                            >
                              {updating === `${version.version}` ? 'Setting...' : 'Set as Current'}
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteVersion(version.version || 1)}
                            disabled={deleting === version.version}
                            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                          >
                            {deleting === version.version ? 'Deleting...' : 'Delete'}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-6 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
          >
            Close
          </button>
        </div>
      </div>

      {previewTemplate && (
        <TemplatePreview
          template={previewTemplate}
          onClose={() => setPreviewTemplate(null)}
        />
      )}
    </div>
  );
}

