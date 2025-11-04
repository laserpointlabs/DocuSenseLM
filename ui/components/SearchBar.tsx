'use client';

import { useState } from 'react';
import { SearchRequest } from '@/lib/api';

interface SearchBarProps {
  onSearch: (query: string, filters?: SearchRequest['filters']) => void;
  loading?: boolean;
}

const STARTER_QUESTIONS = [
  'What is the confidentiality period?',
  'What information is considered confidential?',
  'What are the exceptions to confidentiality?',
  'What is the term of the NDA?',
  'What is the survival period?',
  'Is this a mutual or unilateral NDA?',
  'What is the governing law?',
  'Who are the parties?',
  'What are the obligations of the receiving party?',
  'What happens if there is a breach?',
  'Are there any carve-outs or exceptions?',
  'What is the return or destruction clause?',
  'Can information be shared with affiliates?',
  'What is the effective date?',
  'What is the expiration date?',
  'Are there any restrictions on use?',
  'What is the return period?',
  'What are the notification requirements?',
  'Can the parties modify the agreement?',
  'What happens upon termination?',
  'Are there any indemnification provisions?',
  'What is the dispute resolution mechanism?',
  'Can the agreement be assigned?',
  'What are the remedies for breach?',
  'What is the scope of confidential information?',
];

export default function SearchBar({ onSearch, loading = false }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  const handleQuestionClick = (question: string) => {
    setQuery(question);
    onSearch(question);
  };

  return (
    <div className="w-full">
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setShowSuggestions(true)}
            placeholder="Search NDAs or ask a question..."
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm py-3 px-4 pr-12"
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
          <h3 className="text-sm font-medium text-gray-700 mb-2">Common Questions:</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {STARTER_QUESTIONS.map((question, idx) => (
              <button
                key={idx}
                onClick={() => handleQuestionClick(question)}
                className="text-left text-sm text-gray-600 hover:text-primary-600 hover:bg-primary-50 px-3 py-2 rounded-md border border-gray-200 hover:border-primary-300 transition-colors"
              >
                {question}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
