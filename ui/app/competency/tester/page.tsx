'use client';

import { useState, useEffect } from 'react';
import { competencyAPI } from '@/lib/api';

export default function TesterPage() {
  const [questions, setQuestions] = useState<any[]>([]);
  const [selectedQuestion, setSelectedQuestion] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
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

  const runTest = async (questionId: string) => {
    setLoading(true);
    setTestResult(null);
    try {
      const result = await competencyAPI.runTest(questionId);
      setTestResult(result);
    } catch (error: any) {
      alert(`Test failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Test Runner</h1>
        <p className="mt-2 text-sm text-gray-600">
          Run competency tests and view results
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Questions</h2>
          {loadingQuestions ? (
            <p className="text-sm text-gray-600">Loading...</p>
          ) : questions.length === 0 ? (
            <p className="text-sm text-gray-600">No questions available. Create some in the Question Builder.</p>
          ) : (
            <div className="space-y-2">
              {questions.map((q) => (
                <button
                  key={q.id}
                  onClick={() => {
                    setSelectedQuestion(q.id);
                    runTest(q.id);
                  }}
                  disabled={loading}
                  className={`w-full text-left p-3 rounded-md border transition-colors ${
                    selectedQuestion === q.id
                      ? 'bg-primary-50 border-primary-300'
                      : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                  }`}
                >
                  <p className="text-sm text-gray-900">{q.question_text}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Test Results</h2>
          {loading ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <p className="mt-2 text-sm text-gray-600">Running test...</p>
            </div>
          ) : testResult ? (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Answer</h3>
                <p className="text-sm text-gray-900 bg-gray-50 p-3 rounded-md">{testResult.answer}</p>
              </div>
              {testResult.accuracy_score !== null && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Accuracy Score</h3>
                  <p className="text-2xl font-bold text-primary-600">{testResult.accuracy_score.toFixed(2)}</p>
                </div>
              )}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Response Time</h3>
                <p className="text-sm text-gray-900">{testResult.response_time_ms}ms</p>
              </div>
              {testResult.citations && testResult.citations.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Citations</h3>
                  <ul className="space-y-1">
                    {testResult.citations.map((citation: any, idx: number) => (
                      <li key={idx} className="text-xs text-gray-600">
                        Doc {citation.doc_id?.substring(0, 8)}...
                        {citation.clause_number && `, Clause ${citation.clause_number}`}
                        {citation.page_num && `, Page ${citation.page_num}`}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-600">Select a question to run a test</p>
          )}
        </div>
      </div>
    </div>
  );
}
