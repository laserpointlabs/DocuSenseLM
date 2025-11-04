'use client';

import { useState } from 'react';
import { answerAPI, AnswerResponse } from '@/lib/api';
import CitationChip from '@/components/CitationChip';

export default function AnswerPage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const response = await answerAPI.answer({
        question: question.trim(),
        max_context_chunks: 10,
      });
      setAnswer(response);
    } catch (err: any) {
      setError(err.message || 'Failed to generate answer');
      console.error('Answer error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Ask a Question</h1>
        <p className="mt-2 text-sm text-gray-600">
          Get AI-powered answers with citations from your NDA documents
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mb-8">
        <div className="relative">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your NDAs..."
            rows={4}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-4"
            disabled={loading}
          />
        </div>
        <div className="mt-4">
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Generating answer...
              </>
            ) : (
              'Get Answer'
            )}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {answer && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Answer</h2>
          <div className="prose max-w-none mb-6">
            <p className="text-gray-700 whitespace-pre-wrap">{answer.answer}</p>
          </div>

          {answer.citations.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-medium text-gray-900 mb-3">Citations</h3>
              <div className="flex flex-wrap gap-2">
                {answer.citations.map((citation, idx) => (
                  <CitationChip key={idx} citation={citation} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
