'use client';

import { useState, useEffect } from 'react';
import { competencyAPI } from '@/lib/api';

export default function QuestionBuilderPage() {
  const [questionText, setQuestionText] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [questions, setQuestions] = useState<any[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(true);

  useEffect(() => {
    loadQuestions();
  }, []);

  const loadQuestions = async () => {
    setLoadingQuestions(true);
    try {
      const response = await competencyAPI.listQuestions();
      setQuestions(response.questions || []);
    } catch (error) {
      console.error('Failed to load questions:', error);
    } finally {
      setLoadingQuestions(false);
    }
  };

  const handleCreateQuestion = async () => {
    if (!questionText.trim()) return;

    setLoading(true);
    try {
      const question = await competencyAPI.createQuestion(questionText);
      setQuestionText('');
      // Reload questions to get the updated list
      await loadQuestions();
      alert('Question created successfully!');
    } catch (error: any) {
      alert(`Failed to create question: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Question Builder</h1>
        <p className="mt-2 text-sm text-gray-600">
          Create competency questions to test your NDA search system
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Create New Question</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Question Text
            </label>
            <textarea
              value={questionText}
              onChange={(e) => setQuestionText(e.target.value)}
              placeholder="Enter your question..."
              rows={4}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>
          <button
            onClick={handleCreateQuestion}
            disabled={loading || !questionText.trim()}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400"
          >
            {loading ? 'Creating...' : 'Create Question'}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Your Questions</h2>
          <button
            onClick={loadQuestions}
            disabled={loadingQuestions}
            className="text-sm text-primary-600 hover:text-primary-700 disabled:text-gray-400"
          >
            {loadingQuestions ? 'Loading...' : 'Refresh'}
          </button>
        </div>
        {loadingQuestions ? (
          <p className="text-sm text-gray-600">Loading questions...</p>
        ) : questions.length === 0 ? (
          <p className="text-sm text-gray-600">No questions created yet.</p>
        ) : (
          <ul className="space-y-2">
            {questions.map((q) => (
              <li key={q.id} className="p-3 bg-gray-50 rounded-md">
                <p className="text-sm text-gray-900">{q.question_text}</p>
                <p className="text-xs text-gray-500 mt-1">
                  Created: {new Date(q.created_at).toLocaleDateString()}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
