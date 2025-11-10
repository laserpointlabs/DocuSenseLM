'use client';

import { useState, useEffect } from 'react';
import { documentAPI, adminAPI } from '@/lib/api';
import AdminPanel from '@/components/AdminPanel';
import Link from 'next/link';

export default function AdminPage() {
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

      <AdminPanel />
    </div>
  );
}
