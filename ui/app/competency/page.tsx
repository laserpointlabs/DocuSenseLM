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
  const [testingAll, setTestingAll] = useState(false);
  const [allTestResults, setAllTestResults] = useState<any | null>(null);
  const [expandedQuestion, setExpandedQuestion] = useState<string | null>(null);
  const [detailedResults, setDetailedResults] = useState<Record<string, any>>({});

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
    if (!questionText.trim() || !expectedAnswer.trim()) {
      alert('Question text and expected answer are required.');
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
      if (editingQuestion === questionId) {
        handleCancelEdit();
      }
      if (expandedQuestion === questionId) {
        setExpandedQuestion(null);
      }
      alert('Question deleted successfully!');
    } catch (error: any) {
      alert(`Failed to delete question: ${error.message}`);
    }
  };

  const loadDetailedResult = async (questionId: string) => {
    if (detailedResults[questionId]) {
      return; // Already loaded
    }

    try {
      const result = await competencyAPI.runTest(questionId);
      const question = questions.find(q => q.id === questionId);
      setDetailedResults({
        ...detailedResults,
        [questionId]: {
          ...result,
          expected_answer: question?.expected_answer_text || '',
          confidence: result.accuracy_score || 0,
          passed: (result.accuracy_score || 0) >= confidenceThreshold
        }
      });
    } catch (error: any) {
      console.error(`Failed to load detailed result for ${questionId}:`, error);
    }
  };

  const toggleExpand = async (questionId: string) => {
    if (expandedQuestion === questionId) {
      setExpandedQuestion(null);
    } else {
      setExpandedQuestion(questionId);
      await loadDetailedResult(questionId);
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
    setDetailedResults({});

    try {
      const results = await competencyAPI.runAllTests();

      const enhancedResults = results.results?.map((result: any) => {
        const question = questions.find(q => q.id === result.question_id);
        const confidence = result.accuracy_score || 0;
        return {
          ...result,
          question_text: result.question_text || question?.question_text,
          expected_answer: question?.expected_answer_text || '',
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

      // Store detailed results
      const detailed: Record<string, any> = {};
      enhancedResults.forEach((result: any) => {
        detailed[result.question_id] = result;
      });
      setDetailedResults(detailed);
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                placeholder="Enter the expected answer..."
                rows={3}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-gray-700">
                  Confidence Threshold:
                </label>
                <span className="text-sm text-gray-600">{(confidenceThreshold * 100).toFixed(0)}%</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                  className="w-32"
                />
              </div>
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

      {/* Test All Button and Summary */}
      {questions.length > 0 && (
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {allTestResults && (
              <div className="flex items-center gap-6 bg-white rounded-lg shadow-sm border border-gray-200 px-6 py-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-gray-900">{allTestResults.total}</div>
                  <div className="text-xs text-gray-600">Total</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{allTestResults.passed}</div>
                  <div className="text-xs text-gray-600">Passed</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-red-600">{allTestResults.failed}</div>
                  <div className="text-xs text-gray-600">Failed</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-primary-600">{allTestResults.passRate?.toFixed(1)}%</div>
                  <div className="text-xs text-gray-600">Pass Rate</div>
                </div>
              </div>
            )}
          </div>
          <button
            onClick={runAllTests}
            disabled={testingAll}
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

      {/* Questions and Test Results Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Questions & Test Results</h2>
          <button
            onClick={loadQuestions}
            disabled={loadingQuestions}
            className="text-sm text-primary-600 hover:text-primary-700 disabled:text-gray-400"
          >
            {loadingQuestions ? 'Loading...' : 'Refresh'}
          </button>
        </div>

        {loadingQuestions ? (
          <div className="p-8 text-center text-gray-600">Loading questions...</div>
        ) : questions.length === 0 ? (
          <div className="p-8 text-center text-gray-600">No questions created yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-8"></th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Question</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Expected Answer</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actual Answer</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Confidence</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Response Time</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {questions.map((q) => {
                  const result = detailedResults[q.id] || allTestResults?.results?.find((r: any) => r.question_id === q.id);
                  const isExpanded = expandedQuestion === q.id;
                  
                  return (
                    <>
                      <tr key={q.id} className={isExpanded ? 'bg-primary-50' : ''}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {result && (
                            <button
                              onClick={() => toggleExpand(q.id)}
                              className="text-gray-400 hover:text-gray-600"
                            >
                              {isExpanded ? '▼' : '▶'}
                            </button>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          {editingQuestion === q.id ? (
                            <textarea
                              value={editQuestionText}
                              onChange={(e) => setEditQuestionText(e.target.value)}
                              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                              rows={2}
                            />
                          ) : (
                            <div className="text-sm text-gray-900">{q.question_text}</div>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          {editingQuestion === q.id ? (
                            <textarea
                              value={editExpectedAnswer}
                              onChange={(e) => setEditExpectedAnswer(e.target.value)}
                              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                              rows={2}
                            />
                          ) : (
                            <div className="text-sm text-gray-700 max-w-md">
                              {q.expected_answer_text || <span className="text-gray-400">Not set</span>}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          {result ? (
                            <div className="text-sm text-gray-900 max-w-md">
                              <div className="truncate" title={result.answer || result.actual_answer || 'No answer'}>
                                {result.answer || result.actual_answer || <span className="text-gray-400">No answer</span>}
                              </div>
                            </div>
                          ) : (
                            <span className="text-gray-400 text-sm">Not tested</span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {result ? (
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              result.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                            }`}>
                              {result.passed ? '✅ Passed' : '❌ Failed'}
                            </span>
                          ) : (
                            <span className="text-gray-400 text-xs">-</span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {result ? (
                            <div className="flex items-center gap-2">
                              <div className="flex-1 bg-gray-200 rounded-full h-2 w-16">
                                <div
                                  className={`h-2 rounded-full ${
                                    result.confidence >= confidenceThreshold ? 'bg-green-500' : 'bg-red-500'
                                  }`}
                                  style={{ width: `${result.confidence * 100}%` }}
                                ></div>
                              </div>
                              <span className={`text-sm font-medium ${
                                result.confidence >= confidenceThreshold ? 'text-green-600' : 'text-red-600'
                              }`}>
                                {(result.confidence * 100).toFixed(1)}%
                              </span>
                            </div>
                          ) : (
                            <span className="text-gray-400 text-xs">-</span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {result?.response_time_ms ? `${result.response_time_ms}ms` : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          {editingQuestion === q.id ? (
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleUpdateQuestion(q.id)}
                                disabled={updatingQuestion || !editQuestionText.trim()}
                                className="text-primary-600 hover:text-primary-900 disabled:text-gray-400"
                              >
                                Save
                              </button>
                              <button
                                onClick={handleCancelEdit}
                                disabled={updatingQuestion}
                                className="text-gray-600 hover:text-gray-900 disabled:text-gray-400"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleEditQuestion(q)}
                                className="text-blue-600 hover:text-blue-900"
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => handleDeleteQuestion(q.id)}
                                className="text-red-600 hover:text-red-900"
                              >
                                Delete
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                      {isExpanded && result && (
                        <tr>
                          <td colSpan={8} className="px-6 py-4 bg-gray-50">
                            <div className="space-y-4">
                              <div className="grid grid-cols-2 gap-4">
                                <div>
                                  <h4 className="text-sm font-medium text-gray-700 mb-2">Expected Answer</h4>
                                  <div className="bg-white p-3 rounded border border-gray-200 text-sm">
                                    {q.expected_answer_text || <span className="text-gray-400">Not set</span>}
                                  </div>
                                </div>
                                <div>
                                  <h4 className="text-sm font-medium text-gray-700 mb-2">Actual Answer (Full)</h4>
                                  <div className="bg-white p-3 rounded border border-gray-200 text-sm">
                                    {result.answer || result.actual_answer || <span className="text-gray-400">No answer</span>}
                                  </div>
                                </div>
                              </div>
                              {result.citations && result.citations.length > 0 && (
                                <div>
                                  <h4 className="text-sm font-medium text-gray-700 mb-2">Citations ({result.citations.length})</h4>
                                  <div className="bg-white p-3 rounded border border-gray-200">
                                    <div className="space-y-2">
                                      {result.citations.map((citation: any, idx: number) => (
                                        <div key={idx} className="text-xs text-gray-600">
                                          • Document: {citation.doc_id?.substring(0, 8)}..., 
                                          Page {citation.page_num}, 
                                          Clause {citation.clause_number || 'N/A'}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </div>
                              )}
                              <div className="grid grid-cols-3 gap-4 text-sm">
                                <div>
                                  <span className="text-gray-600">Confidence:</span>
                                  <span className={`ml-2 font-medium ${
                                    result.confidence >= confidenceThreshold ? 'text-green-600' : 'text-red-600'
                                  }`}>
                                    {(result.confidence * 100).toFixed(1)}%
                                  </span>
                                </div>
                                <div>
                                  <span className="text-gray-600">Response Time:</span>
                                  <span className="ml-2 font-medium">{result.response_time_ms}ms</span>
                                </div>
                                <div>
                                  <span className="text-gray-600">Run At:</span>
                                  <span className="ml-2 font-medium">
                                    {result.run_at ? new Date(result.run_at).toLocaleString() : '-'}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
