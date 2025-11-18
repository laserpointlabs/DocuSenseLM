'use client';

import { useState, useEffect } from 'react';
import { workflowAPI } from '@/lib/api';
import WorkflowDashboard from '@/components/WorkflowDashboard';

export default function WorkflowPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Workflow Management</h1>
        <p className="mt-2 text-sm text-gray-600">
          Monitor and manage NDA review and approval workflows
        </p>
      </div>

      <WorkflowDashboard />
    </div>
  );
}







