'use client';

import { useState } from 'react';
import Link from 'next/link';

export default function CompetencyPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Competency Question System</h1>
        <p className="mt-2 text-sm text-gray-600">
          Build and test competency questions to validate system effectiveness
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link
          href="/competency/builder"
          className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
        >
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Question Builder</h2>
          <p className="text-sm text-gray-600">
            Create competency questions with LLM assistance and define ground truth
          </p>
        </Link>

        <Link
          href="/competency/tester"
          className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
        >
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Test Runner</h2>
          <p className="text-sm text-gray-600">
            Run competency tests and view accuracy metrics
          </p>
        </Link>
      </div>
    </div>
  );
}
