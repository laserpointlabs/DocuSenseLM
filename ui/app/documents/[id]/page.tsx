'use client';

import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { documentAPI } from '@/lib/api';
import DocumentViewer from '@/components/DocumentViewer';

export default function DocumentPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const documentId = params.id as string;
  const [document, setDocument] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (documentId) {
      loadDocument();
    }
  }, [documentId]);

  // Log query params for debugging
  useEffect(() => {
    const page = searchParams.get('page');
    const start = searchParams.get('start');
    const end = searchParams.get('end');
    console.log('Document page query params:', { page, start, end });
  }, [searchParams]);

  const loadDocument = async () => {
    setLoading(true);
    setError(null);
    try {
      const doc = await documentAPI.get(documentId);
      setDocument(doc);
    } catch (err: any) {
      setError(err.message || 'Failed to load document');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          <p className="mt-2 text-sm text-gray-600">Loading document...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      </div>
    );
  }

    const highlightPage = searchParams.get('page') ? parseInt(searchParams.get('page')!) : undefined;
    const highlightStart = searchParams.get('start') ? parseInt(searchParams.get('start')!) : undefined;
    const highlightEnd = searchParams.get('end') ? parseInt(searchParams.get('end')!) : undefined;
    const highlightText = searchParams.get('text') || undefined;
    const highlightClause = searchParams.get('clause') || undefined; // Get clause number from URL

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{document?.filename}</h1>
        <p className="text-sm text-gray-600 mt-1">
          Status: <span className="font-medium">{document?.status}</span>
        </p>
      </div>

        <DocumentViewer
          documentId={documentId}
          highlightPage={highlightPage}
          highlightStart={highlightStart}
          highlightEnd={highlightEnd}
          highlightText={highlightText}
          highlightClause={highlightClause}
        />
    </div>
  );
}
