'use client';

import { useState, useEffect } from 'react';
import { competencyAPI } from '@/lib/api';

export default function CompetencyPage() {
  const [questions, setQuestions] = useState<any[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(true);

  // Question creation
  const [questionText, setQuestionText] = useState('');
  const [expectedAnswer, setExpectedAnswer] = useState('');
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.7);
  const [creatingQuestion, setCreatingQuestion] = useState(false);

  // Question editing
  const [editingQuestion, setEditingQuestion] = useState<string | null>(null);
  const [editQuestionText, setEditQuestionText] = useState('');
  const [editExpectedAnswer, setEditExpectedAnswer] = useState('');
  const [updatingQuestion, setUpdatingQuestion] = useState(false);

  // Testing
  const [selectedQuestion, setSelectedQuestion] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<any | null>(null);
  const [testing, setTesting] = useState(false);
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

  const handleCreateQuestion = async () => {
    if (!questionText.trim()) {
      alert('Please enter a question');
      return;
    }
    if (!expectedAnswer.trim()) {
      alert('Please enter the expected answer');
      return;
    }

    setCreatingQuestion(true);
    try {
      await competencyAPI.createQuestion(questionText, undefined, expectedAnswer);
      setQuestionText('');
      setExpectedAnswer('');
      await loadQuestions();
      alert('Question created successfully!');
    } catch (error: any) {
      alert(`Failed to create question: ${error.message}`);
    } finally {
      setCreatingQuestion(false);
    }
  };

  const handleEditQuestion = (question: any) => {
    setEditingQuestion(question.id);
    setEditQuestionText(question.question_text);
    setEditExpectedAnswer(question.expected_answer_text || '');
  };

  const handleCancelEdit = () => {
    setEditingQuestion(null);
    setEditQuestionText('');
    setEditExpectedAnswer('');
  };

  const handleUpdateQuestion = async (questionId: string) => {
    if (!editQuestionText.trim()) {
      alert('Question text is required');
      return;
    }

    setUpdatingQuestion(true);
    try {
      await competencyAPI.updateQuestion(questionId, {
        question_text: editQuestionText,
        expected_answer_text: editExpectedAnswer || undefined,
      });
      await loadQuestions();
      handleCancelEdit();
      alert('Question updated successfully!');
    } catch (error: any) {
      alert(`Failed to update question: ${error.message}`);
    } finally {
      setUpdatingQuestion(false);
    }
  };

  const handleDeleteQuestion = async (questionId: string) => {
    if (!confirm('Are you sure you want to delete this question?')) {
      return;
    }

    try {
      await competencyAPI.deleteQuestion(questionId);
      await loadQuestions();
      if (selectedQuestion === questionId) {
        setSelectedQuestion(null);
        setTestResult(null);
      }
      if (editingQuestion === questionId) {
        handleCancelEdit();
      }
      alert('Question deleted successfully!');
    } catch (error: any) {
      alert(`Failed to delete question: ${error.message}`);
    }
  };

  const runTest = async (questionId: string) => {
    setTesting(true);
    setTestResult(null);
    setSelectedQuestion(questionId);

    try {
      const result = await competencyAPI.runTest(questionId);

      // Use accuracy_score from API (calculated server-side)
      const confidence = result.accuracy_score || 0;
      const passed = confidence >= confidenceThreshold;

      const question = questions.find(q => q.id === questionId);
      const expected = question?.expected_answer_text || '';
      const actual = result.answer || '';

      setTestResult({
        ...result,
        confidence,
        passed,
        expectedAnswer: expected,
        actualAnswer: actual
      });
    } catch (error: any) {
      alert(`Test failed: ${error.message}`);
    } finally {
      setTesting(false);
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

      // Use accuracy_score from API results (calculated server-side)
      const enhancedResults = results.results?.map((result: any) => {
        const confidence = result.accuracy_score || 0;
        return {
          ...result,
          confidence,
          passed: confidence >= confidenceThreshold
        };
      }) || [];

      const passed = enhancedResults.filter(r => r.passed).length;
      const failed = enhancedResults.filter(r => !r.passed).length;
      const passRate = (passed / enhancedResults.length) * 100;

      setAllTestResults({
        ...results,
        results: enhancedResults,
        passed,
        failed,
        passRate
      });
    } catch (error: any) {
      alert(`Failed to run all tests: ${error.message}`);
    } finally {
      setTestingAll(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Competency Questions</h1>
        <p className="mt-2 text-sm text-gray-600">
          Build questions, set expected answers, and test system accuracy
        </p>
      </div>

      {/* Create Question Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Create New Question</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Question Text *
            </label>
            <textarea
              value={questionText}
              onChange={(e) => setQuestionText(e.target.value)}
              placeholder="Enter your question..."
              rows={3}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Expected Answer *
            </label>
            <textarea
              value={expectedAnswer}
              onChange={(e) => setExpectedAnswer(e.target.value)}
              placeholder="Enter the expected answer for this question..."
              rows={3}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Confidence Threshold: {(confidenceThreshold * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={confidenceThreshold}
                onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                className="w-full"
              />
              <p className="text-xs text-gray-500 mt-1">
                Tests must meet this confidence level to pass
              </p>
            </div>
            <button
              onClick={handleCreateQuestion}
              disabled={creatingQuestion || !questionText.trim() || !expectedAnswer.trim()}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400"
            >
              {creatingQuestion ? 'Creating...' : 'Create Question'}
            </button>
          </div>
        </div>
      </div>

      {/* Test All Button */}
      {questions.length > 0 && (
        <div className="mb-6 flex justify-end">
          <button
            onClick={runAllTests}
            disabled={testingAll || testing}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400"
          >
            {testingAll ? (
              <>
                <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Testing All...
              </>
            ) : (
              `Test All (${questions.length})`
            )}
          </button>
        </div>
      )}

      {/* Test All Results */}
      {allTestResults && (
        <div className="mb-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Test All Results</h2>
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{allTestResults.total}</div>
              <div className="text-sm text-gray-600">Total</div>
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
              <div className="text-2xl font-bold text-primary-600">{allTestResults.passRate?.toFixed(1)}%</div>
              <div className="text-sm text-gray-600">Pass Rate</div>
            </div>
          </div>
          <div className="max-h-96 overflow-y-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Question</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Response Time</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {allTestResults.results?.map((result: any, idx: number) => (
                  <tr key={idx}>
                    <td className="px-4 py-3 text-sm text-gray-900 max-w-md">
                      <div className="truncate">{result.question_text}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        result.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {result.passed ? 'Passed' : 'Failed'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-sm font-medium ${
                        result.confidence >= confidenceThreshold ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {(result.confidence * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {result.response_time_ms ? `${result.response_time_ms}ms` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Questions List and Test Results */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Questions List */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Questions ({questions.length})</h2>
            <button
              onClick={loadQuestions}
              disabled={loadingQuestions}
              className="text-sm text-primary-600 hover:text-primary-700 disabled:text-gray-400"
            >
              {loadingQuestions ? 'Loading...' : 'Refresh'}
            </button>
          </div>
          {loadingQuestions ? (
            <p className="text-sm text-gray-600">Loading...</p>
          ) : questions.length === 0 ? (
            <p className="text-sm text-gray-600">No questions created yet.</p>
          ) : (
            <div className="space-y-2">
              {questions.map((q) => (
                <div
                  key={q.id}
                  className={`p-3 rounded-md border transition-colors ${
                    selectedQuestion === q.id
                      ? 'bg-primary-50 border-primary-300'
                      : 'bg-gray-50 border-gray-200'
                  }`}
                >
                  {editingQuestion === q.id ? (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Question Text
                        </label>
                        <textarea
                          value={editQuestionText}
                          onChange={(e) => setEditQuestionText(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                          rows={2}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Expected Answer
                        </label>
                        <textarea
                          value={editExpectedAnswer}
                          onChange={(e) => setEditExpectedAnswer(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                          rows={2}
                        />
                      </div>
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={handleCancelEdit}
                          disabled={updatingQuestion}
                          className="text-xs px-3 py-1 text-gray-600 hover:text-gray-700 hover:bg-gray-100 rounded border border-gray-300"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleUpdateQuestion(q.id)}
                          disabled={updatingQuestion || !editQuestionText.trim()}
                          className="text-xs px-3 py-1 text-white bg-primary-600 hover:bg-primary-700 rounded disabled:bg-gray-400"
                        >
                          {updatingQuestion ? 'Saving...' : 'Save'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <p className="text-sm text-gray-900 font-medium">{q.question_text}</p>
                          {q.expected_answer_text && (
                            <p className="text-xs text-gray-500 mt-1">
                              Expected: {q.expected_answer_text.substring(0, 60)}...
                            </p>
                          )}
                        </div>
                        <div className="flex gap-2 ml-2">
                          <button
                            onClick={() => runTest(q.id)}
                            disabled={testing}
                            className="text-xs px-2 py-1 text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded"
                          >
                            Test
                          </button>
                          <button
                            onClick={() => handleEditQuestion(q)}
                            className="text-xs px-2 py-1 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDeleteQuestion(q.id)}
                            className="text-xs px-2 py-1 text-red-600 hover:text-red-700 hover:bg-red-50 rounded"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Test Results */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Test Results</h2>
          {testing ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <p className="mt-2 text-sm text-gray-600">Running test...</p>
            </div>
          ) : testResult ? (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Status</h3>
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                  testResult.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }`}>
                  {testResult.passed ? '✅ Passed' : '❌ Failed'}
                </span>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Confidence Score</h3>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-4">
                    <div
                      className={`h-4 rounded-full ${
                        testResult.confidence >= confidenceThreshold ? 'bg-green-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${testResult.confidence * 100}%` }}
                    ></div>
                  </div>
                  <span className={`text-sm font-bold ${
                    testResult.confidence >= confidenceThreshold ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {(testResult.confidence * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Threshold: {(confidenceThreshold * 100).toFixed(0)}%
                </p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Expected Answer</h3>
                <p className="text-sm text-gray-900 bg-gray-50 p-3 rounded-md">{testResult.expectedAnswer || 'Not set'}</p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">System Answer</h3>
                <p className="text-sm text-gray-900 bg-gray-50 p-3 rounded-md">{testResult.actualAnswer || testResult.answer || 'No answer generated'}</p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Response Time</h3>
                <p className="text-sm text-gray-900">{testResult.response_time_ms}ms</p>
              </div>

              {testResult.citations && testResult.citations.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Citations ({testResult.citations.length})</h3>
                  <ul className="space-y-1 max-h-32 overflow-y-auto">
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
            </div>
          ) : (
            <p className="text-sm text-gray-600">Select a question and click "Test" to see results</p>
          )}
        </div>
      </div>
    </div>
  );
}
