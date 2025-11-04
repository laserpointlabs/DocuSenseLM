'use client';

import { useState, useEffect } from 'react';
import { documentAPI, adminAPI } from '@/lib/api';
import AdminPanel from '@/components/AdminPanel';

export default function AdminPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
        <p className="mt-2 text-sm text-gray-600">
          Manage documents, view statistics, and configure the system
        </p>
      </div>

      <AdminPanel />
    </div>
  );
}
