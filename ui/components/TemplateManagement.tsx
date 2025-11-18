'use client';

import { useState, useEffect } from 'react';
import { templateAPI, Template } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import TemplateVersionManager from './TemplateVersionManager';
import TemplatePreview from './TemplatePreview';

export default function TemplateManagement() {
  const { user } = useAuth();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showNewVersionModal, setShowNewVersionModal] = useState(false);
  const [selectedTemplateForVersion, setSelectedTemplateForVersion] = useState<Template | null>(null);
  const [selectedTemplateKey, setSelectedTemplateKey] = useState<string | null>(null);
  const [previewTemplate, setPreviewTemplate] = useState<Template | null>(null);
  const [showAllVersions, setShowAllVersions] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [archiving, setArchiving] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    loadTemplates();
  }, [showAllVersions, showArchived]);

  const loadTemplates = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await templateAPI.list(!showArchived, !showAllVersions);
      setTemplates(response.templates);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSuccess = () => {
    setShowCreateModal(false);
    setShowNewVersionModal(false);
    setSelectedTemplateForVersion(null);
    loadTemplates();
  };

  const handleViewVersions = (templateKey: string) => {
    setSelectedTemplateKey(templateKey);
  };

  const handleCloseVersions = () => {
    setSelectedTemplateKey(null);
    loadTemplates();
  };

  const handleCreateNewVersion = (template: Template) => {
    setSelectedTemplateForVersion(template);
    setShowNewVersionModal(true);
  };

  const handleDelete = async (template: Template) => {
    if (!confirm(`Are you sure you want to delete "${template.name}"${template.version ? ` version ${template.version}` : ''}? This action cannot be undone.`)) {
      return;
    }

    setDeleting(template.id);
    try {
      await templateAPI.delete(template.id, template.version);
      await loadTemplates();
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete template');
      console.error(err);
    } finally {
      setDeleting(null);
    }
  };

  const handleArchive = async (templateId: string, archive: boolean) => {
    setArchiving(templateId);
    setError(null);
    try {
      await templateAPI.update(templateId, { is_active: !archive });
      await loadTemplates();
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to ${archive ? 'archive' : 'unarchive'} template`);
    } finally {
      setArchiving(null);
    }
  };

  if (!user || user.role !== 'admin') {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-gray-600">Admin access required to manage templates.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-6 border-b">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Template Management</h2>
            <p className="text-sm text-gray-600 mt-1">
              Create, version, and manage NDA templates
            </p>
          </div>
          <div className="flex gap-3 items-center">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={showAllVersions}
                onChange={(e) => setShowAllVersions(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-gray-700">Show all versions</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-gray-700">Show archived</span>
            </label>
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
            >
              + Create Template
            </button>
          </div>
        </div>
      </div>

      <div className="p-6">
        {loading ? (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            <p className="mt-2 text-gray-600">Loading templates...</p>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
          </div>
        ) : templates.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-600">No templates found.</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="mt-4 px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
            >
              Create Your First Template
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {templates.map((template) => (
              <div
                key={template.id}
                className="border rounded-lg p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold text-gray-900">
                        {template.name}
                      </h3>
                      {template.is_current && (
                        <span className="px-2 py-1 text-xs font-medium bg-primary-600 text-white rounded">
                          Current
                        </span>
                      )}
                      {template.version && (
                        <span className="px-2 py-1 text-xs font-medium bg-gray-200 text-gray-700 rounded">
                          v{template.version}
                        </span>
                      )}
                      {!template.is_active && (
                        <span className="px-2 py-1 text-xs font-medium bg-gray-400 text-white rounded">
                          Inactive
                        </span>
                      )}
                    </div>
                    {template.description && (
                      <p className="text-sm text-gray-600 mt-1">{template.description}</p>
                    )}
                    {template.template_key && (
                      <p className="text-xs text-gray-500 mt-1">
                        Key: <code className="bg-gray-100 px-1 py-0.5 rounded">{template.template_key}</code>
                      </p>
                    )}
                    {template.change_notes && (
                      <div className="mt-2 p-2 bg-gray-50 rounded text-sm text-gray-700">
                        <strong>Changes:</strong> {template.change_notes}
                      </div>
                    )}
                    <div className="mt-2 text-xs text-gray-500">
                      Created: {new Date(template.created_at).toLocaleString()}
                      {template.created_by && ` • Created by: ${template.created_by}`}
                    </div>
                  </div>
                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => setPreviewTemplate(template)}
                      className="px-3 py-1.5 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                    >
                      View PDF
                    </button>
                    <a
                      href={templateAPI.downloadFile(template.id, template.version, 'docx')}
                      download
                      className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                      onClick={(e) => {
                        // Add auth token to download
                        e.preventDefault();
                        const token = localStorage.getItem('auth_token');
                        const url = templateAPI.downloadFile(template.id, template.version, 'docx');
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
                            a.download = `${template.name}_v${template.version || 1}.docx`;
                            document.body.appendChild(a);
                            a.click();
                            window.URL.revokeObjectURL(downloadUrl);
                            document.body.removeChild(a);
                          })
                          .catch(err => {
                            setError('Failed to download template');
                            console.error(err);
                          });
                      }}
                    >
                      Download DOCX
                    </a>
                    {template.template_key && (
                      <>
                        <button
                          onClick={() => handleViewVersions(template.template_key!)}
                          className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                        >
                          View Versions
                        </button>
                        <button
                          onClick={() => handleCreateNewVersion(template)}
                          className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded hover:bg-primary-700"
                        >
                          New Version
                        </button>
                      </>
                    )}
                    {user?.role === 'admin' && (
                      <>
                        <button
                          onClick={() => handleArchive(template.id, template.is_active)}
                          disabled={archiving === template.id}
                          className={`px-3 py-1.5 text-sm rounded ${
                            template.is_active
                              ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                              : 'bg-green-100 text-green-700 hover:bg-green-200'
                          } disabled:opacity-50 disabled:cursor-not-allowed`}
                        >
                          {archiving === template.id
                            ? '...'
                            : template.is_active
                            ? 'Archive'
                            : 'Unarchive'}
                        </button>
                        <button
                          onClick={() => handleDelete(template)}
                          disabled={deleting === template.id}
                          className="px-3 py-1.5 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {deleting === template.id ? 'Deleting...' : 'Delete'}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showCreateModal && (
        <CreateTemplateModal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleCreateSuccess}
        />
      )}

      {showNewVersionModal && selectedTemplateForVersion && (
        <CreateTemplateModal
          isOpen={showNewVersionModal}
          onClose={() => {
            setShowNewVersionModal(false);
            setSelectedTemplateForVersion(null);
          }}
          onSuccess={handleCreateSuccess}
          existingTemplate={selectedTemplateForVersion}
        />
      )}

      {selectedTemplateKey && (
        <TemplateVersionManager
          templateKey={selectedTemplateKey}
          onClose={handleCloseVersions}
        />
      )}

      {previewTemplate && (
        <TemplatePreview
          template={previewTemplate}
          onClose={() => setPreviewTemplate(null)}
        />
      )}
    </div>
  );
}

interface CreateTemplateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  existingTemplate?: Template;
}

function CreateTemplateModal({ isOpen, onClose, onSuccess, existingTemplate }: CreateTemplateModalProps) {
  const isNewVersion = !!existingTemplate;
  const [name, setName] = useState(existingTemplate?.name || '');
  const [description, setDescription] = useState(existingTemplate?.description || '');
  const [templateKey, setTemplateKey] = useState(existingTemplate?.template_key || '');
  const [changeNotes, setChangeNotes] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when modal opens/closes or existingTemplate changes
  useEffect(() => {
    if (isOpen && existingTemplate) {
      setName(existingTemplate.name);
      setDescription(existingTemplate.description || '');
      setTemplateKey(existingTemplate.template_key || '');
      setChangeNotes('');
      setFile(null);
    } else if (isOpen && !existingTemplate) {
      setName('');
      setDescription('');
      setTemplateKey('');
      setChangeNotes('');
      setFile(null);
    }
  }, [isOpen, existingTemplate]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (!selectedFile.name.endsWith('.docx')) {
        setError('Please select a .docx file');
        return;
      }
      setFile(selectedFile);
      setError(null);
      
      // Auto-generate template_key from name if not provided
      if (!templateKey && name) {
        const key = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        setTemplateKey(key);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a template file');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', name);
      if (description) formData.append('description', description);
      if (templateKey) formData.append('template_key', templateKey);
      if (changeNotes) formData.append('change_notes', changeNotes);

      const API_URL = process.env.NEXT_PUBLIC_API_URL 
        ? (process.env.NEXT_PUBLIC_API_URL.startsWith('http') 
            ? process.env.NEXT_PUBLIC_API_URL 
            : `https://${process.env.NEXT_PUBLIC_API_URL}`)
        : 'http://localhost:8000';

      const response = await fetch(`${API_URL}/templates`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create template');
      }

      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Failed to create template');
    } finally {
      setUploading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold text-gray-900">
              {isNewVersion ? 'Create New Version' : 'Create Template'}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
            >
              ×
            </button>
          </div>
          <p className="text-sm text-gray-600 mt-1">
            {isNewVersion
              ? `Creating version ${(existingTemplate?.version || 0) + 1} of ${existingTemplate?.name}`
              : 'Upload a new template or create a new version of an existing template'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800">{error}</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Template Name *
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                // Auto-generate template_key if empty and not creating new version
                if (!templateKey && !isNewVersion) {
                  const key = e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
                  setTemplateKey(key);
                }
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="e.g., Standard Mutual NDA"
              disabled={isNewVersion}
            />
            {isNewVersion && (
              <p className="text-xs text-gray-500 mt-1">
                Name is inherited from the existing template
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Template Key *
            </label>
            <input
              type="text"
              required
              value={templateKey}
              onChange={(e) => setTemplateKey(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-gray-50"
              placeholder="e.g., standard-mutual-nda"
              disabled={isNewVersion}
            />
            <p className="text-xs text-gray-500 mt-1">
              {isNewVersion
                ? 'Template key is locked - using the same key creates a new version'
                : 'Unique identifier for this template. Use the same key to create new versions.'}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Brief description of this template"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Change Notes
            </label>
            <textarea
              value={changeNotes}
              onChange={(e) => setChangeNotes(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="What changed in this version? (only for new versions)"
            />
            <p className="text-xs text-gray-500 mt-1">
              Optional: Describe changes if creating a new version of an existing template
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Template File (.docx) *
            </label>
            <input
              type="file"
              required
              accept=".docx"
              onChange={handleFileChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            {file && (
              <p className="text-sm text-gray-600 mt-1">
                Selected: {file.name} ({(file.size / 1024).toFixed(2)} KB)
              </p>
            )}
          </div>

          <div className="flex gap-3 pt-4 border-t">
            <button
              type="submit"
              disabled={uploading}
              className="flex-1 px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading
                ? 'Uploading...'
                : isNewVersion
                ? `Create Version ${(existingTemplate?.version || 0) + 1}`
                : 'Create Template'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

