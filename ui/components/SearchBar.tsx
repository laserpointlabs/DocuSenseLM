'use client';

import { useState } from 'react';
import { SearchRequest } from '@/lib/api';

interface SearchBarProps {
  onSearch: (query: string, filters?: SearchRequest['filters']) => void;
  loading?: boolean;
  defaultShowSuggestions?: boolean;
}

const KEYWORD_SUGGESTIONS = [
  'confidentiality period',
  'confidential information',
  'exceptions to confidentiality',
  'term of agreement',
  'survival period',
  'mutual agreement',
  'governing law',
  'parties',
  'obligations',
  'breach',
  'exceptions',
  'return of materials',
  'affiliates',
  'effective date',
  'expiration date',
  'restrictions on use',
  'return period',
  'notification requirements',
  'modification',
  'termination',
  'indemnification',
  'dispute resolution',
  'assignment',
  'remedies',
  'scope of confidential information',
];

export default function SearchBar({ onSearch, loading = false, defaultShowSuggestions = true }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(defaultShowSuggestions);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      setShowSuggestions(false); // Collapse when search is performed
      onSearch(query.trim());
    }
  };

  const handleKeywordClick = (keyword: string) => {
    setQuery(keyword);
    setShowSuggestions(false); // Collapse when keyword is clicked
    onSearch(keyword);
  };

  const handleInputFocus = () => {
    setShowSuggestions(true); // Expand when user focuses input
  };

  return (
    <div className="w-full">
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={handleInputFocus}
            placeholder="Search for keywords or phrases in your NDAs..."
            className="block w-full rounded-md border border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm py-3 px-4 pr-12"
            disabled={loading}
          />
          <div className="absolute inset-y-0 right-0 flex items-center pr-3">
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="text-primary-600 hover:text-primary-700 disabled:text-gray-400"
            >
              {loading ? (
                <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </form>

      {showSuggestions && (
        <div className="mt-4">
          <button
            onClick={() => setShowSuggestions(false)}
            className="flex items-center justify-between w-full mb-2 text-left"
          >
            <h3 className="text-sm font-medium text-gray-700">Keyword Suggestions:</h3>
            <svg
              className="w-4 h-4 text-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {KEYWORD_SUGGESTIONS.map((keyword, idx) => (
              <button
                key={idx}
                onClick={() => handleKeywordClick(keyword)}
                className="text-left text-sm text-gray-600 hover:text-primary-600 hover:bg-primary-50 px-3 py-2 rounded-md border border-gray-200 hover:border-primary-300 transition-colors"
              >
                {keyword}
              </button>
            ))}
          </div>
        </div>
      )}

      {!showSuggestions && (
        <div className="mt-2">
          <button
            onClick={() => setShowSuggestions(true)}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <span>Show keyword suggestions</span>
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
