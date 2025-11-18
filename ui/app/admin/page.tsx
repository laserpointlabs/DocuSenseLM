'use client';

import { useState } from 'react';
import { documentAPI, adminAPI } from '@/lib/api';
import AdminPanel from '@/components/AdminPanel';
import TemplateManagement from '@/components/TemplateManagement';
import Link from 'next/link';

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<'documents' | 'templates'>('documents');

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
        <p className="mt-2 text-sm text-gray-600">
          Manage documents, view statistics, and configure the system
        </p>
      </div>

      <div className="mb-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Administrative Functions</h2>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/competency"
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Competency Testing
            </Link>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('documents')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'documents'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Document Management
          </button>
          <button
            onClick={() => setActiveTab('templates')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'templates'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Template Management
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'documents' && <AdminPanel />}
      {activeTab === 'templates' && <TemplateManagement />}
    </div>
  );
}
