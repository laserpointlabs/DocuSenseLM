'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { searchAPI, SearchResult } from '@/lib/api';
import ResultsList from '@/components/ResultsList';
import SearchBar from '@/components/SearchBar';

export default function ResultsPage() {
  const searchParams = useSearchParams();
  const query = searchParams.get('q') || '';
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (query) {
      performSearch(query);
    }
  }, [query]);

  const performSearch = async (searchQuery: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await searchAPI.search({
        query: searchQuery,
        k: 50,
      });
      setResults(response.results);
    } catch (err: any) {
      setError(err.message || 'Search failed');
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (newQuery: string) => {
    // Update URL and trigger search
    window.location.href = `/results?q=${encodeURIComponent(newQuery)}`;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <SearchBar onSearch={handleSearch} loading={loading} defaultShowSuggestions={false} />
      </div>

      {loading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          <p className="mt-2 text-sm text-gray-600">Searching...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="mb-4">
            <p className="text-sm text-gray-600">
              Found {results.length} results for &quot;{query}&quot;
            </p>
          </div>
          <ResultsList results={results} />
        </>
      )}
    </div>
  );
}
