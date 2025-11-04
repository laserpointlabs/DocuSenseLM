'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { searchAPI, SearchRequest } from '@/lib/api';
import SearchBar from '@/components/SearchBar';

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSearch = async (searchQuery: string, filters?: SearchRequest['filters']) => {
    setLoading(true);
    try {
      // Navigate to results page with query
      router.push(`/results?q=${encodeURIComponent(searchQuery)}`);
    } catch (error) {
      console.error('Search error:', error);
      setLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Search NDA Documents</h1>
        <p className="mt-2 text-sm text-gray-600">
          Find information across your NDA collection using hybrid search
        </p>
      </div>

      <SearchBar
        onSearch={handleSearch}
        loading={loading}
      />

      <div className="mt-12">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Or ask a question</h2>
        <div className="mt-4">
          <a
            href="/answer"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
          >
            Ask Question
          </a>
        </div>
      </div>
    </div>
  );
}
