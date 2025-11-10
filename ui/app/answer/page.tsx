'use client';

import { useState } from 'react';
import { answerAPI, AnswerResponse } from '@/lib/api';
import CitationChip from '@/components/CitationChip';

// Question suggestions organized by category
const questionSuggestions = [
  {
    category: 'Effective Date',
    questions: [
      'what is the effective date for Fanuc America Corporation?',
      'what is the effective date for Fanuc?',
      'what is the effective date for KGS Fire?',
      'what is the effective date for Vallen Distribution?',
      'what is the effective date for Boston Green?',
      'what is the effective date for McGill Hose?',
      'what is the effective date for Central Coating?',
      'what is the effective date for Norris Cylinder?',
      'what is the effective date for Delva Tool?',
      'when did the Fanuc NDA become effective?',
    ],
  },
  {
    category: 'Term',
    questions: [
      'what is the term for Fanuc?',
      'what is the term for KGS Fire?',
      'what is the term for Vallen Distribution?',
      'what is the term for Boston Green?',
      'what is the term for Central Coating?',
      'what is the term for Delva Tool?',
      'how long does the Fanuc NDA last?',
      'how long is the Vallen NDA valid?',
      'what is the duration of the Central Coating NDA?',
      'how many years does the McGill Hose NDA run?',
    ],
  },
  {
    category: 'Governing Law',
    questions: [
      'What is the governing law for Fanuc?',
      'What is the governing law for KGS Fire?',
      'What is the governing law for Vallen Distribution?',
      'What is the governing law for Boston Green?',
      'What is the governing law for McGill Hose?',
      'What is the governing law for Norris Cylinder?',
      'What state law applies to Central Coating?',
      'What jurisdiction governs the Fanuc NDA?',
      'What state laws govern the Vallen NDA?',
      'Which state law applies to the McGill Hose NDA?',
    ],
  },
  {
    category: 'Expiration Date',
    questions: [
      'What date does the Fanuc NDA expire?',
      'What date does the KGS Fire NDA expire?',
      'What date does the Vallen Distribution NDA expire?',
      'What date does the Boston Green NDA expire?',
      'What date does the Central Coating NDA expire?',
      'What date does the McGill Hose NDA expire?',
      'What date does the Norris Cylinder NDA expire?',
      'When does the Fanuc NDA expire?',
      'When does the Vallen NDA expire?',
      'How many days until the Fanuc NDA expires?',
    ],
  },
  {
    category: 'Parties',
    questions: [
      'Who are the parties to the Fanuc NDA?',
      'Who are the parties to the KGS Fire NDA?',
      'Who are the parties to the Vallen Distribution NDA?',
      'Who are the parties to the Boston Green NDA?',
      'Who are the parties to the McGill Hose NDA?',
      'Who are the parties to the Central Coating NDA?',
      'Who are the parties to the Norris Cylinder NDA?',
      'Who signed the Fanuc NDA?',
      'What companies are parties to the Vallen NDA?',
    ],
  },
  {
    category: 'Mutual Status',
    questions: [
      'Is the Fanuc NDA mutual or one-way?',
      'Is the KGS Fire NDA mutual or one-way?',
      'Is the Vallen Distribution NDA mutual or one-way?',
      'Is the Boston Green NDA mutual or one-way?',
      'Is the Central Coating NDA mutual or one-way?',
      'Is the McGill Hose NDA mutual or one-way?',
      'Is the Norris Cylinder NDA mutual or one-way?',
      'Is the Fanuc NDA unilateral or bilateral?',
      'Does the Vallen NDA protect both parties equally?',
    ],
  },
  {
    category: 'Location',
    questions: [
      'Where is Fanuc America located?',
      'Where is Boston Green located?',
      'Where is McGill Hose located?',
      'Where is Norris Cylinder located?',
      'Where is Vallen Distribution located?',
      'Where is Central Coating located?',
      'Where is KGS Fire located?',
    ],
  },
  {
    category: 'Confidentiality',
    questions: [
      "What's confidential in the Central Coating NDA?",
      'What information is considered confidential in the Fanuc NDA?',
      'What does the Vallen NDA define as confidential information?',
      'What types of information are protected under the McGill Hose NDA?',
      'What constitutes confidential information in the Boston Green NDA?',
    ],
  },
  {
    category: 'Obligations',
    questions: [
      'What are the obligations in the Unique Fire NDA?',
      'What must parties do under the Fanuc NDA?',
      'What are the duties of the receiving party in the Vallen NDA?',
      'What obligations does the Central Coating NDA require?',
      'What are the requirements in the McGill Hose NDA?',
    ],
  },
  {
    category: 'Exceptions',
    questions: [
      'What are the exceptions to confidentiality in the Fanuc NDA?',
      'When can confidential information be disclosed under the Vallen NDA?',
      'What information is excluded from confidentiality in the Central Coating NDA?',
      'Are there any exceptions to the confidentiality obligations in the McGill Hose NDA?',
    ],
  },
  {
    category: 'Return/Destruction',
    questions: [
      'What happens to confidential information when the Fanuc NDA ends?',
      'Does the Vallen NDA require return or destruction of confidential information?',
      'What are the requirements for returning confidential information in the Central Coating NDA?',
      'When must confidential information be destroyed under the McGill Hose NDA?',
    ],
  },
  {
    category: 'Remedies',
    questions: [
      'What remedies are available for breach of the Fanuc NDA?',
      'What happens if someone breaches the Vallen NDA?',
      'What are the consequences of violating the Central Coating NDA?',
      'What legal remedies exist for breach of the McGill Hose NDA?',
    ],
  },
  {
    category: 'Multi-NDA Comparison',
    questions: [
      'What NDAs expire in September 2028?',
      'Do Fanuc and Norris expire in the same month?',
      'What NDAs expire in August 2028?',
      'What NDAs expire in July 2028?',
      'Which NDAs expire first?',
      'What NDAs expire in June 2028?',
      'What NDAs have a term of 3 years?',
      'What NDAs are governed by California law?',
      'Which companies have NDAs expiring in September 2028?',
      'What NDAs expire in October 2028?',
    ],
  },
];

export default function AnswerPage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const response = await answerAPI.answer({
        question: question.trim(),
        max_context_chunks: 10,  // Increased back to 10 for better context
      });
      setAnswer(response);
    } catch (err: any) {
      setError(err.message || 'Failed to generate answer');
      console.error('Answer error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setQuestion(suggestion);
    // Scroll to top of textarea
    document.querySelector('textarea')?.focus();
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

      {/* Answer Section - Moved above suggestions for better visibility */}
      {error && (
        <div className="bg-red-50 border-2 border-red-300 rounded-lg p-4 mb-6">
          <p className="text-sm text-red-800 font-medium">{error}</p>
        </div>
      )}

      {answer && (
        <div className="bg-white rounded-lg shadow-md border-2 border-primary-300 p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Answer</h2>
          <div className="prose max-w-none mb-6">
            <p className="text-gray-800 whitespace-pre-wrap text-base leading-relaxed">{answer.answer}</p>
          </div>

          {answer.citations.length > 0 && (
            <div className="mt-6 pt-6 border-t border-gray-200">
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

      {/* Question Suggestions - Compressed with thin outlines */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Question Suggestions</h2>
        <p className="text-sm text-gray-600 mb-3">
          Click on any question below to use it as a starting point
        </p>
        <div className="space-y-2">
          {questionSuggestions.map((category) => (
            <div key={category.category} className="border border-gray-300 rounded overflow-hidden">
              <button
                onClick={() => setExpandedCategory(
                  expandedCategory === category.category ? null : category.category
                )}
                className="w-full px-3 py-2 bg-gray-50 hover:bg-gray-100 flex items-center justify-between text-left transition-colors"
              >
                <span className="font-medium text-gray-900 text-sm">{category.category}</span>
                <svg
                  className={`w-4 h-4 text-gray-500 transform transition-transform ${
                    expandedCategory === category.category ? 'rotate-180' : ''
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {expandedCategory === category.category && (
                <div className="p-2 bg-white border-t border-gray-200">
                  <div className="flex flex-wrap gap-1">
                    {category.questions.map((suggestion, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSuggestionClick(suggestion)}
                        className="px-2 py-1 text-xs text-gray-700 bg-white hover:bg-primary-50 hover:text-primary-700 border border-gray-300 rounded transition-colors text-left"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
