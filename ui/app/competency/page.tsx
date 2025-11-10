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
  const [editConfidenceThreshold, setEditConfidenceThreshold] = useState(0.7);
  const [updatingQuestion, setUpdatingQuestion] = useState(false);

  // Testing
  const [testingAll, setTestingAll] = useState(false);
  const [testingQuestion, setTestingQuestion] = useState<string | null>(null);
  const [allTestResults, setAllTestResults] = useState<any | null>(null);
  const [expandedQuestion, setExpandedQuestion] = useState<string | null>(null);
  const [detailedResults, setDetailedResults] = useState<Record<string, any>>({});

  // Global threshold
  const [globalThreshold, setGlobalThreshold] = useState(0.7);
  const [updatingGlobalThreshold, setUpdatingGlobalThreshold] = useState(false);
  
  // Loading/Clearing
  const [loadingFromJson, setLoadingFromJson] = useState(false);
  const [clearingAll, setClearingAll] = useState(false);
  
  // Test Progress
  const [testProgress, setTestProgress] = useState<any | null>(null);

  useEffect(() => {
    loadQuestions();
    loadGlobalThreshold();
  }, []);

  // Load test results after questions are loaded (so we have question thresholds)
  useEffect(() => {
    if (questions.length > 0) {
      loadLatestTestResults();
    }
  }, [questions]);

  const loadGlobalThreshold = async () => {
    try {
      const response = await competencyAPI.getGlobalThreshold();
      setGlobalThreshold(response.threshold || 0.7);
    } catch (error) {
      console.error('Failed to load global threshold:', error);
    }
  };

  const handleGlobalThresholdChange = async (newThreshold: number) => {
    setGlobalThreshold(newThreshold);
    setUpdatingGlobalThreshold(true);
    try {
      await competencyAPI.setGlobalThreshold(newThreshold);
      // Reload questions to get updated thresholds
      await loadQuestions();
      // Reload test results to recalculate with new threshold
      await loadLatestTestResults();
      alert(`Global confidence threshold updated to ${(newThreshold * 100).toFixed(0)}% for all questions`);
    } catch (error: any) {
      alert(`Failed to update global threshold: ${error.message}`);
      // Revert on error
      await loadGlobalThreshold();
    } finally {
      setUpdatingGlobalThreshold(false);
    }
  };

  const loadQuestions = async () => {
    setLoadingQuestions(true);
    try {
      const response = await competencyAPI.listQuestions();
      console.log('Loaded questions:', response.questions?.map((q: any) => ({
        id: q.id.substring(0, 8),
        threshold: q.confidence_threshold
      })));
      setQuestions(response.questions || []);
    } catch (error) {
      console.error('Failed to load questions:', error);
    } finally {
      setLoadingQuestions(false);
    }
  };

  const loadLatestTestResults = async () => {
    try {
      const results = await competencyAPI.getLatestTestResults();

      // Build detailed results map, recalculating pass/fail using each question's threshold
      const detailed: Record<string, any> = {};
      results.results?.forEach((result: any) => {
        const question = questions.find(q => q.id === result.question_id);
        const questionThreshold = question?.confidence_threshold || 0.7;
        detailed[result.question_id] = {
          ...result,
          confidence: result.accuracy_score || 0,
          passed: (result.accuracy_score || 0) >= questionThreshold
        };
      });
      setDetailedResults(detailed);

      // Recalculate summary stats using updated pass/fail status
      const updatedResults = results.results?.map((r: any) => {
        const question = questions.find(q => q.id === r.question_id);
        const questionThreshold = question?.confidence_threshold || 0.7;
        return {
          ...r,
          confidence: r.accuracy_score || 0,
          passed: (r.accuracy_score || 0) >= questionThreshold
        };
      }) || [];

      const passed = updatedResults.filter((r: any) => r.passed).length;
      const failed = updatedResults.length - passed;
      const passRate = updatedResults.length > 0 ? (passed / updatedResults.length) * 100 : 0;

      // Set all test results for summary display
      if (updatedResults.length > 0) {
        setAllTestResults({
          total: updatedResults.length,
          passed,
          failed,
          passRate,
          results: updatedResults
        });
      }
    } catch (error) {
      console.error('Failed to load latest test results:', error);
      // Don't show error to user, just silently fail
    }
  };

  const handleCreateQuestion = async () => {
    if (!questionText.trim() || !expectedAnswer.trim()) {
      alert('Question text and expected answer are required.');
      return;
    }

    setCreatingQuestion(true);
    try {
      await competencyAPI.createQuestion(questionText, undefined, expectedAnswer, confidenceThreshold);
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
    console.log('Editing question:', question.id, 'confidence_threshold:', question.confidence_threshold);
    setEditingQuestion(question.id);
    setEditQuestionText(question.question_text);
    setEditExpectedAnswer(question.expected_answer_text || '');
    const threshold = question.confidence_threshold ?? 0.7;
    console.log('Setting editConfidenceThreshold to:', threshold);
    setEditConfidenceThreshold(threshold);
  };

  const handleCancelEdit = () => {
    setEditingQuestion(null);
    setEditQuestionText('');
    setEditExpectedAnswer('');
    setEditConfidenceThreshold(0.7);
  };

  const handleUpdateQuestion = async (questionId: string) => {
    if (!editQuestionText.trim()) {
      alert('Question text is required');
      return;
    }

    setUpdatingQuestion(true);
    try {
      console.log('Updating question with confidence_threshold:', editConfidenceThreshold);
      const result = await competencyAPI.updateQuestion(questionId, {
        question_text: editQuestionText,
        expected_answer_text: editExpectedAnswer || undefined,
        confidence_threshold: editConfidenceThreshold,
      });
      console.log('Update result:', result);
      await loadQuestions();
      // Reload test results to recalculate pass/fail with new threshold
      await loadLatestTestResults();
      handleCancelEdit();
      alert('Question updated successfully!');
    } catch (error: any) {
      console.error('Update error:', error);
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
      const questionThreshold = question?.confidence_threshold || 0.7;
      setDetailedResults({
        ...detailedResults,
        [questionId]: {
          ...result,
          expected_answer: question?.expected_answer_text || '',
          confidence: result.accuracy_score || 0,
          passed: (result.accuracy_score || 0) >= questionThreshold
        }
      });
    } catch (error: any) {
      console.error(`Failed to load detailed result for ${questionId}:`, error);
    }
  };

  const handleTestQuestion = async (questionId: string) => {
    setTestingQuestion(questionId);
    try {
      const result = await competencyAPI.runTest(questionId);
      const question = questions.find(q => q.id === questionId);
      const questionThreshold = question?.confidence_threshold || 0.7;

      const testResult = {
        ...result,
        expected_answer: question?.expected_answer_text || '',
        confidence: result.accuracy_score || 0,
        passed: (result.accuracy_score || 0) >= questionThreshold
      };

      // Update detailed results
      setDetailedResults({
        ...detailedResults,
        [questionId]: testResult
      });

      // Update allTestResults if it exists
      if (allTestResults) {
        const updatedResults = allTestResults.results.map((r: any) =>
          r.question_id === questionId ? {
            ...testResult,
            question_id: questionId,
            question_text: question?.question_text || '',
            actual_answer: result.answer,
            citations_count: result.citations?.length || 0
          } : r
        );
        setAllTestResults({
          ...allTestResults,
          results: updatedResults
        });
      }

      // Reload latest test results to ensure consistency
      await loadLatestTestResults();
    } catch (error: any) {
      alert(`Failed to test question: ${error.message}`);
    } finally {
      setTestingQuestion(null);
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

  const handleLoadFromJson = async () => {
    const clearFirst = confirm('Clear existing questions before loading? (Click OK to clear, Cancel to add to existing)');
    
    setLoadingFromJson(true);
    try {
      const result = await competencyAPI.loadQuestionsFromJson(clearFirst);
      await loadQuestions();
      alert(`Successfully loaded ${result.loaded_count} questions from JSON file${result.errors ? `\n\nErrors: ${result.errors.length}` : ''}`);
    } catch (error: any) {
      alert(`Failed to load questions from JSON: ${error.message}`);
    } finally {
      setLoadingFromJson(false);
    }
  };

  const handleClearAllQuestions = async () => {
    if (!confirm(`⚠️  This will delete ALL ${questions.length} questions and all test data. This cannot be undone. Continue?`)) {
      return;
    }

    setClearingAll(true);
    try {
      const result = await competencyAPI.deleteAllQuestions();
      await loadQuestions();
      setAllTestResults(null);
      setDetailedResults({});
      alert(`Successfully deleted ${result.questions_deleted} questions, ${result.test_runs_deleted} test runs, and ${result.feedback_deleted} feedback records.`);
    } catch (error: any) {
      alert(`Failed to clear questions: ${error.message}`);
    } finally {
      setClearingAll(false);
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
    setTestProgress(null); // Reset progress before starting

    // Start polling for progress
    const progressInterval = setInterval(async () => {
      try {
        const progress = await competencyAPI.getTestProgress();
        setTestProgress(progress);
        if (!progress.is_running) {
          clearInterval(progressInterval);
        }
      } catch (error) {
        console.error('Failed to get test progress:', error);
      }
    }, 500); // Poll every 500ms

    try {
      const results = await competencyAPI.runAllTests();
      clearInterval(progressInterval);

      const enhancedResults = results.results?.map((result: any) => {
        const question = questions.find(q => q.id === result.question_id);
        const confidence = result.accuracy_score || 0;
        const questionThreshold = question?.confidence_threshold || 0.7;
        return {
          ...result,
          question_text: result.question_text || question?.question_text,
          expected_answer: question?.expected_answer_text || '',
          confidence,
          passed: confidence >= questionThreshold
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

      // Reload test results from database to ensure we have the latest saved results
      await loadLatestTestResults();
      // They will persist and be loaded on refresh
      setTestProgress(null); // Clear progress on completion
    } catch (error: any) {
      clearInterval(progressInterval);
      setTestProgress(null); // Clear progress on error
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

      {/* Global Confidence Threshold */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Global Confidence Threshold (applies to all questions)
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={globalThreshold}
                onChange={(e) => {
                  const newValue = parseFloat(e.target.value);
                  setGlobalThreshold(newValue);
                }}
                onMouseUp={(e) => {
                  const newValue = parseFloat((e.target as HTMLInputElement).value);
                  handleGlobalThresholdChange(newValue);
                }}
                onTouchEnd={(e) => {
                  const newValue = parseFloat((e.target as HTMLInputElement).value);
                  handleGlobalThresholdChange(newValue);
                }}
                disabled={updatingGlobalThreshold}
                className="flex-1 max-w-md"
              />
              <span className="text-lg font-semibold text-gray-900 min-w-[4rem]">
                {(globalThreshold * 100).toFixed(0)}%
              </span>
              {updatingGlobalThreshold && (
                <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600"></div>
              )}
            </div>
            <p className="mt-2 text-xs text-gray-500">
              This threshold applies to all questions. Tests must meet this confidence level to pass.
            </p>
          </div>
        </div>
      </div>

      {/* Create Question Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Create New Question</h2>
          <button
            onClick={handleLoadFromJson}
            disabled={loadingFromJson}
            className="inline-flex items-center px-4 py-2 border border-primary-300 text-sm font-medium rounded-md text-primary-700 bg-primary-50 hover:bg-primary-100 disabled:bg-gray-100 disabled:text-gray-400"
          >
            {loadingFromJson ? 'Loading...' : '📥 Load from JSON'}
          </button>
        </div>
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

      {/* Test Progress Bar */}
      {testProgress && testProgress.is_running && (
        <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-300 rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <svg className="animate-spin h-6 w-6 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="text-lg font-semibold text-blue-900">
                Testing Competency Questions in Progress
              </span>
            </div>
            <span className="text-lg font-bold text-blue-700">
              {testProgress.completed || 0} / {testProgress.total || 0} ({testProgress.progress_percent?.toFixed(0) || 0}%)
            </span>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-4 mb-3 shadow-inner">
            <div 
              className="bg-gradient-to-r from-blue-600 to-indigo-600 h-4 rounded-full transition-all duration-500 shadow-sm"
              style={{ width: `${testProgress.progress_percent || 0}%` }}
            />
          </div>
          {testProgress.current && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-blue-800">Currently testing:</span>
              <span className="text-sm text-blue-700 font-mono bg-white px-2 py-1 rounded border border-blue-200">
                {testProgress.current}
              </span>
            </div>
          )}
          {testProgress.errors > 0 && (
            <div className="mt-2 text-sm text-red-600">
              ⚠️ {testProgress.errors} error(s) encountered
            </div>
          )}
          <div className="mt-2 flex gap-4 text-sm">
            <span className="text-green-600 font-medium">✅ Passed: {testProgress.passed || 0}</span>
            <span className="text-red-600 font-medium">❌ Failed: {testProgress.failed || 0}</span>
          </div>
        </div>
      )}

      {/* Test All Button and Summary */}
      {questions.length > 0 && (
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={handleClearAllQuestions}
              disabled={clearingAll || testingAll}
              className="inline-flex items-center px-4 py-2 border border-red-300 text-sm font-medium rounded-md text-red-700 bg-red-50 hover:bg-red-100 disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed"
            >
              {clearingAll ? 'Clearing...' : 'Clear All'}
            </button>
          </div>
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
            <table className="w-full divide-y divide-gray-200 table-fixed">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-8"></th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">Question</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">Expected Answer</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">Threshold</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-64">Actual Answer</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">Confidence</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">Response Time</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">Actions</th>
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
                        <td className="px-6 py-4 max-w-xs">
                          {editingQuestion === q.id ? (
                            <textarea
                              value={editQuestionText}
                              onChange={(e) => setEditQuestionText(e.target.value)}
                              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                              rows={2}
                            />
                          ) : (
                            <div className="text-sm text-gray-900 break-words whitespace-normal">{q.question_text}</div>
                          )}
                        </td>
                        <td className="px-6 py-4 max-w-md">
                          {editingQuestion === q.id ? (
                            <textarea
                              value={editExpectedAnswer}
                              onChange={(e) => setEditExpectedAnswer(e.target.value)}
                              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                              rows={2}
                            />
                          ) : (
                            <div className="text-sm text-gray-700 break-words whitespace-normal">
                              {q.expected_answer_text || <span className="text-gray-400">Not set</span>}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {editingQuestion === q.id ? (
                            <div className="flex items-center gap-2">
                              <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={editConfidenceThreshold}
                                onChange={(e) => setEditConfidenceThreshold(parseFloat(e.target.value))}
                                className="w-24"
                              />
                              <span className="text-sm text-gray-600 min-w-[3rem]">
                                {(editConfidenceThreshold * 100).toFixed(0)}%
                              </span>
                            </div>
                          ) : (
                            <div className="text-sm text-gray-700">
                              {((q.confidence_threshold ?? 0.7) * 100).toFixed(0)}%
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 max-w-md">
                          {result ? (
                            <div className="text-sm text-gray-900 break-words whitespace-normal">
                              {result.answer || result.actual_answer || <span className="text-gray-400">No answer</span>}
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
                                    result.confidence >= (q.confidence_threshold || 0.7) ? 'bg-green-500' : 'bg-red-500'
                                  }`}
                                  style={{ width: `${result.confidence * 100}%` }}
                                ></div>
                              </div>
                              <span className={`text-sm font-medium ${
                                result.confidence >= (q.confidence_threshold || 0.7) ? 'text-green-600' : 'text-red-600'
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
                                onClick={() => handleTestQuestion(q.id)}
                                disabled={testingQuestion === q.id}
                                className="text-green-600 hover:text-green-900 disabled:text-gray-400 text-sm"
                                title="Test this question"
                              >
                                {testingQuestion === q.id ? (
                                  <span className="flex items-center gap-1">
                                    <div className="inline-block animate-spin rounded-full h-3 w-3 border-b-2 border-green-600"></div>
                                    Testing...
                                  </span>
                                ) : (
                                  'Test'
                                )}
                              </button>
                              <button
                                onClick={() => handleEditQuestion(q)}
                                className="text-blue-600 hover:text-blue-900 text-sm"
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => handleDeleteQuestion(q.id)}
                                className="text-red-600 hover:text-red-900 text-sm"
                              >
                                Delete
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                      {isExpanded && result && (
                        <tr>
                          <td colSpan={9} className="px-6 py-4 bg-gray-50">
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
                                          • Document: {citation.doc_id?.substring(0, 8)}...
                                          {citation.page_num && citation.page_num > 0 && `, Page ${citation.page_num}`}
                                          {citation.clause_number ? `, Clause ${citation.clause_number}` : ', Clause N/A'}
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
                                    result.confidence >= (q.confidence_threshold || 0.7) ? 'text-green-600' : 'text-red-600'
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
