'use client';

import { useState, useEffect } from 'react';
import { competencyAPI } from '@/lib/api';

export default function TesterPage() {
  const [questions, setQuestions] = useState<any[]>([]);
  const [selectedQuestion, setSelectedQuestion] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingQuestions, setLoadingQuestions] = useState(true);
  const [testingAll, setTestingAll] = useState(false);
  const [allTestResults, setAllTestResults] = useState<any | null>(null);

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

  const runAllTests = async () => {
    if (questions.length === 0) {
      alert('No questions available to test');
      return;
    }

    if (!confirm(`Run tests for all ${questions.length} questions? This may take a few minutes.`)) {
      return;
    }

    setTestingAll(true);
    setAllTestResults(null);
    setTestResult(null);

    try {
      const results = await competencyAPI.runAllTests();
      setAllTestResults(results);

      // Show summary alert
      const passRate = results.pass_rate?.toFixed(1) || '0';
      alert(`Testing complete!\n\nTotal: ${results.total}\nPassed: ${results.passed}\nFailed: ${results.failed}\nPass Rate: ${passRate}%`);
    } catch (error: any) {
      alert(`Failed to run all tests: ${error.message}`);
    } finally {
      setTestingAll(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Test Runner</h1>
          <p className="mt-2 text-sm text-gray-600">
            Run competency tests and view results
          </p>
        </div>
        <button
          onClick={runAllTests}
          disabled={testingAll || loadingQuestions || questions.length === 0}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {testingAll ? (
            <>
              <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Testing All...
            </>
          ) : (
            'Test All'
          )}
        </button>
      </div>

      {allTestResults && (
        <div className="mb-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Test All Results</h2>
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{allTestResults.total}</div>
              <div className="text-sm text-gray-600">Total Questions</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{allTestResults.passed}</div>
              <div className="text-sm text-gray-600">Passed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{allTestResults.failed}</div>
              <div className="text-sm text-gray-600">Failed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600">{allTestResults.pass_rate?.toFixed(1)}%</div>
              <div className="text-sm text-gray-600">Pass Rate</div>
            </div>
          </div>
          <div className="max-h-96 overflow-y-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Question</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Response Time</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Citations</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {allTestResults.results?.map((result: any, idx: number) => (
                  <tr key={idx}>
                    <td className="px-4 py-3 text-sm text-gray-900 max-w-md truncate">
                      {result.question_text}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        result.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {result.passed ? 'Passed' : 'Failed'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {result.response_time_ms ? `${result.response_time_ms}ms` : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {result.citations_count || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Questions ({questions.length})</h2>
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
                  <p className="text-sm text-gray-900 font-medium">{q.question_text}</p>
                  {q.document_id && (
                    <p className="text-xs text-gray-500 mt-1">
                      📄 Document-specific question
                    </p>
                  )}
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
                        <a
                          href={`/documents/${citation.doc_id}`}
                          className="text-primary-600 hover:text-primary-700"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Doc {citation.doc_id?.substring(0, 8)}...
                        </a>
                        {citation.clause_number && `, Clause ${citation.clause_number}`}
                        {citation.page_num && `, Page ${citation.page_num}`}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {questions.find(q => q.id === selectedQuestion)?.verification_hint && (
                <div className="mt-4 p-3 bg-blue-50 rounded-md border border-blue-200">
                  <h3 className="text-sm font-medium text-blue-900 mb-1">Verification Hint</h3>
                  <p className="text-xs text-blue-700">
                    {questions.find(q => q.id === selectedQuestion)?.verification_hint}
                  </p>
                  {questions.find(q => q.id === selectedQuestion)?.document_id && (
                    <a
                      href={`/documents/${questions.find(q => q.id === selectedQuestion)?.document_id}`}
                      className="text-xs text-blue-600 hover:text-blue-700 underline mt-2 inline-block"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View Source Document →
                    </a>
                  )}
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
