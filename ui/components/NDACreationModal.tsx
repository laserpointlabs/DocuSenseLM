'use client';

import { useState, useEffect } from 'react';
import { templateAPI, workflowAPI, Template, NDACreateRequest } from '@/lib/api';

interface NDACreationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface User {
  id: string;
  username: string;
  role: string;
}

export default function NDACreationModal({ isOpen, onClose, onSuccess }: NDACreationModalProps) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [formData, setFormData] = useState<NDACreateRequest>({
    template_id: '',
    counterparty_name: '',
    counterparty_domain: '',
    counterparty_email: '',
    disclosing_party: '',
    receiving_party: '',
    effective_date: '',
    term_months: 12,
    survival_months: 0,
    governing_law: '',
    direction: 'outbound',
    nda_type: 'mutual',
    entity_id: '',
    additional_data: {},
    reviewer_user_id: '',
    approver_user_id: '',
    internal_signer_user_id: '',
    auto_start_workflow: true,
  });

  useEffect(() => {
    if (isOpen) {
      loadTemplates();
      loadUsers();
    }
  }, [isOpen]);

  const loadUsers = async () => {
    setLoadingUsers(true);
    try {
      const userList = await workflowAPI.getUsers();
      setUsers(userList);
    } catch (err: any) {
      console.error('Failed to load users:', err);
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadTemplates = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await templateAPI.list(true);
      setTemplates(response.templates);
      if (response.templates.length > 0 && !formData.template_id) {
        setFormData(prev => ({ ...prev, template_id: response.templates[0].id }));
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      // Prepare request data
      const requestData: NDACreateRequest = {
        ...formData,
        effective_date: formData.effective_date || undefined,
        term_months: formData.term_months || undefined,
        survival_months: formData.survival_months || undefined,
      };

      await workflowAPI.createNDA(requestData);
      onSuccess();
      onClose();
      // Reset form
      setFormData({
        template_id: templates[0]?.id || '',
        counterparty_name: '',
        counterparty_domain: '',
        counterparty_email: '',
        disclosing_party: '',
        receiving_party: '',
        effective_date: '',
        term_months: 12,
        survival_months: 0,
        governing_law: '',
        direction: 'outbound',
        nda_type: 'mutual',
        entity_id: '',
        additional_data: {},
        reviewer_user_id: '',
        approver_user_id: '',
        internal_signer_user_id: '',
        auto_start_workflow: true,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create NDA');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold text-gray-900">Create New NDA</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Template Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Template *
              </label>
              {loading ? (
                <div className="text-gray-500">Loading templates...</div>
              ) : (
                <select
                  required
                  value={formData.template_id}
                  onChange={(e) => setFormData(prev => ({ ...prev, template_id: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select a template</option>
                  {templates.map(template => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Counterparty Information */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Counterparty Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.counterparty_name}
                  onChange={(e) => setFormData(prev => ({ ...prev, counterparty_name: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Counterparty Email
                </label>
                <input
                  type="email"
                  value={formData.counterparty_email}
                  onChange={(e) => setFormData(prev => ({ ...prev, counterparty_email: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Counterparty Domain
                </label>
                <input
                  type="text"
                  value={formData.counterparty_domain}
                  onChange={(e) => setFormData(prev => ({ ...prev, counterparty_domain: e.target.value }))}
                  placeholder="example.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Entity ID
                </label>
                <input
                  type="text"
                  value={formData.entity_id}
                  onChange={(e) => setFormData(prev => ({ ...prev, entity_id: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Party Information */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Disclosing Party
                </label>
                <input
                  type="text"
                  value={formData.disclosing_party}
                  onChange={(e) => setFormData(prev => ({ ...prev, disclosing_party: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Receiving Party
                </label>
                <input
                  type="text"
                  value={formData.receiving_party}
                  onChange={(e) => setFormData(prev => ({ ...prev, receiving_party: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Dates and Terms */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Effective Date
                </label>
                <input
                  type="date"
                  value={formData.effective_date}
                  onChange={(e) => setFormData(prev => ({ ...prev, effective_date: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Term (Months)
                </label>
                <input
                  type="number"
                  min="1"
                  value={formData.term_months}
                  onChange={(e) => setFormData(prev => ({ ...prev, term_months: parseInt(e.target.value) || 12 }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Survival Period (Months)
                </label>
                <input
                  type="number"
                  min="0"
                  value={formData.survival_months}
                  onChange={(e) => setFormData(prev => ({ ...prev, survival_months: parseInt(e.target.value) || 0 }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Additional Fields */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Governing Law
                </label>
                <input
                  type="text"
                  value={formData.governing_law}
                  onChange={(e) => setFormData(prev => ({ ...prev, governing_law: e.target.value }))}
                  placeholder="e.g., Delaware"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Direction
                </label>
                <select
                  value={formData.direction}
                  onChange={(e) => setFormData(prev => ({ ...prev, direction: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="outbound">Outbound</option>
                  <option value="inbound">Inbound</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  NDA Type
                </label>
                <select
                  value={formData.nda_type}
                  onChange={(e) => setFormData(prev => ({ ...prev, nda_type: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="mutual">Mutual</option>
                  <option value="unilateral">Unilateral</option>
                </select>
              </div>
            </div>

            {/* Workflow Signers */}
            <div className="border-t pt-4 mt-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Workflow Signers</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Reviewer
                  </label>
                  {loadingUsers ? (
                    <div className="text-gray-500 text-sm">Loading users...</div>
                  ) : (
                    <select
                      value={formData.reviewer_user_id || ''}
                      onChange={(e) => setFormData(prev => ({ ...prev, reviewer_user_id: e.target.value || undefined }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select reviewer</option>
                      {users.map(user => (
                        <option key={user.id} value={user.id}>
                          {user.username} ({user.role})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Approver
                  </label>
                  {loadingUsers ? (
                    <div className="text-gray-500 text-sm">Loading users...</div>
                  ) : (
                    <select
                      value={formData.approver_user_id || ''}
                      onChange={(e) => setFormData(prev => ({ ...prev, approver_user_id: e.target.value || undefined }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select approver</option>
                      {users.map(user => (
                        <option key={user.id} value={user.id}>
                          {user.username} ({user.role})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Internal Signer
                  </label>
                  {loadingUsers ? (
                    <div className="text-gray-500 text-sm">Loading users...</div>
                  ) : (
                    <select
                      value={formData.internal_signer_user_id || ''}
                      onChange={(e) => setFormData(prev => ({ ...prev, internal_signer_user_id: e.target.value || undefined }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select internal signer</option>
                      {users.map(user => (
                        <option key={user.id} value={user.id}>
                          {user.username} ({user.role})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
              <div className="mt-4">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.auto_start_workflow !== false}
                    onChange={(e) => setFormData(prev => ({ ...prev, auto_start_workflow: e.target.checked }))}
                    className="mr-2"
                  />
                  <span className="text-sm text-gray-700">Automatically start workflow after creation</span>
                </label>
              </div>
            </div>

            {/* Form Actions */}
            <div className="flex justify-end space-x-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Creating...' : 'Create NDA'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}



