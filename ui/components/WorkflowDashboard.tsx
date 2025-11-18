'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { workflowAPI } from '@/lib/api';
import TaskManagement from './TaskManagement';
import NDACreationModal from './NDACreationModal';

interface WorkflowInstance {
  id: string | null;
  nda_record_id: string;
  camunda_process_instance_id: string | null;
  current_status: string;
  actual_state?: string;  // From Camunda (ACTIVE, COMPLETED, TERMINATED, etc.)
  display_status?: string;  // Primary status for UI display
  started_at: string | null;
  completed_at?: string | null;
  has_workflow: boolean;
}

interface NDARecord {
  id: string;
  counterparty_name: string;
  status: string;
  effective_date?: string;
  term_months?: number;
}

export default function WorkflowDashboard() {
  const [workflows, setWorkflows] = useState<WorkflowInstance[]>([]);
  const [ndaRecords, setNdaRecords] = useState<Record<string, NDARecord>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);
  const [selectedWorkflowDetails, setSelectedWorkflowDetails] = useState<any>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const loadingRef = useRef(false);

  const loadWorkflows = useCallback(async () => {
    if (loadingRef.current) return; // Prevent concurrent loads
    
    try {
      loadingRef.current = true;
      setLoading(true);
      const response = await workflowAPI.listWorkflows(statusFilter === 'all' ? undefined : statusFilter);
      setWorkflows(response.workflows || []);
      
      // Load NDA records for each workflow
      const ndaIds = [...new Set(response.workflows?.map((w: any) => w.nda_record_id) || [])];
      const ndaMap: Record<string, NDARecord> = {};
      for (const ndaId of ndaIds) {
        try {
          const statusData = await workflowAPI.getNDAStatus(ndaId);
          ndaMap[ndaId] = statusData as any;
        } catch (e) {
          // Ignore errors for individual NDAs
        }
      }
      setNdaRecords(ndaMap);
    } catch (err: any) {
      setError(err.message || 'Failed to load workflows');
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  }, [statusFilter]);

  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  // Auto-refresh workflow status every 5 seconds (only if there are active workflows)
  useEffect(() => {
    // Check if there are any active workflows that need polling
    const hasActiveWorkflows = workflows.some(w => {
      const status = w.display_status || w.current_status || '';
      return status !== 'completed' && 
             status !== 'approved' && 
             status !== 'rejected' &&
             !status.includes('failed') &&
             !status.includes('rejected') &&
             w.has_workflow;
    });

    // Only poll if there are active workflows and no modals are open
    if (!hasActiveWorkflows || showCreateModal || showDetailsModal || selectedWorkflow) {
      return;
    }

    const interval = setInterval(() => {
      // Don't poll if already loading
      if (!loadingRef.current) {
        loadWorkflows();
      }
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [workflows, showCreateModal, showDetailsModal, selectedWorkflow, loadWorkflows]);

  const handleCreateNDA = () => {
    setShowCreateModal(true);
  };

  const handleNDACreated = () => {
    setShowCreateModal(false);
    loadWorkflows();
  };

  const handleViewTasks = (workflowId: string) => {
    setSelectedWorkflow(workflowId);
  };

  const handleViewDetails = async (workflowId: string) => {
    try {
      const details = await workflowAPI.getWorkflowDetails(workflowId);
      setSelectedWorkflowDetails(details);
      setShowDetailsModal(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load workflow details');
    }
  };

  const handleStartWorkflow = async (ndaId: string) => {
    try {
      await workflowAPI.startWorkflow(ndaId);
      await loadWorkflows();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start workflow');
    }
  };

  const handleRestartWorkflow = async (workflowId: string) => {
    if (!confirm('Are you sure you want to restart this workflow? This will delete the current workflow and start a new one.')) {
      return;
    }
    try {
      await workflowAPI.restartWorkflow(workflowId);
      await loadWorkflows();
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to restart workflow');
    }
  };

  const handleDeleteWorkflow = async (workflowId: string) => {
    if (!confirm('Are you sure you want to delete this workflow? This action cannot be undone.')) {
      return;
    }
    try {
      await workflowAPI.deleteWorkflow(workflowId);
      await loadWorkflows();
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete workflow');
    }
  };

  const handleDeleteNDA = async (ndaId: string) => {
    if (!confirm('Are you sure you want to delete this NDA? This will also delete any associated workflow. This action cannot be undone.')) {
      return;
    }
    try {
      await workflowAPI.deleteNDA(ndaId);
      await loadWorkflows();
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete NDA');
    }
  };

  const handleOverrideWorkflow = async (workflowId: string, action: 'approve' | 'reject' | 'retry') => {
    const actionText = action === 'approve' ? 'approve' : action === 'reject' ? 'reject' : 'retry';
    const reason = prompt(`Reason for ${actionText} (optional):`);
    if (reason === null) return; // User cancelled
    
    try {
      await workflowAPI.overrideWorkflow(workflowId, action, reason || undefined);
      await loadWorkflows();
      setError(null);
      if (showDetailsModal) {
        // Reload details if modal is open
        const details = await workflowAPI.getWorkflowDetails(workflowId);
        setSelectedWorkflowDetails(details);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to ${actionText} workflow`);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-gray-900 mb-3 sm:mb-0">Active Workflows</h2>
            {/* Filters */}
            <div className="flex flex-wrap gap-2 mt-2 sm:mt-0">
              <label className="text-sm font-medium text-gray-700 flex items-center">
                Filter by Status:
              </label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="all">All</option>
                <option value="started">Started</option>
                <option value="completed">Completed</option>
                <option value="rejected">Rejected</option>
                <option value="created">Created (No Workflow)</option>
                <option value="customer_signed">Customer Signed</option>
                <option value="llm_reviewed_approved">LLM Approved</option>
                <option value="llm_reviewed_rejected">LLM Rejected</option>
                <option value="reviewed">Reviewed</option>
                <option value="approved">Approved</option>
              </select>
            </div>
          </div>
          <button
            onClick={handleCreateNDA}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Create New NDA
          </button>
        </div>
      </div>

      {/* Workflows List */}
      {workflows.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No active workflows</h3>
          <p className="mt-1 text-sm text-gray-500">Get started by creating a new NDA.</p>
          <div className="mt-6">
            <button
              onClick={handleCreateNDA}
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
            >
              Create NDA
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-white shadow-sm rounded-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  NDA
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Started
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {workflows.map((workflow) => {
                const nda = ndaRecords[workflow.nda_record_id];
                return (
                  <tr key={workflow.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {nda?.counterparty_name || workflow.nda_record_id.substring(0, 8)}
                      </div>
                      <div className="text-sm text-gray-500">{nda?.status || 'Unknown'}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-col gap-1">
                        {/* Prioritize current_status for display, use actual_state as secondary info */}
                        {(() => {
                          const displayStatus = workflow.display_status || workflow.current_status || workflow.actual_state || 'unknown';
                          const isFailed = displayStatus.includes('failed') || displayStatus.includes('rejected') || displayStatus.includes('terminated');
                          const isCompleted = displayStatus === 'completed' || displayStatus === 'COMPLETED';
                          const isActive = displayStatus === 'started' || displayStatus === 'ACTIVE' || displayStatus === 'llm_review_passed';
                          const isNoWorkflow = displayStatus === 'NO_WORKFLOW';
                          
                          // Format status for display
                          const formatStatus = (status: string) => {
                            return status
                              .replace(/_/g, ' ')
                              .replace(/\b\w/g, l => l.toUpperCase())
                              .replace('Llm', 'LLM')
                              .replace('Failed ', 'Failed: ');
                          };
                          
                          return (
                            <>
                              <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                                isFailed ? 'bg-red-100 text-red-800' :
                                isCompleted && !isFailed ? 'bg-green-100 text-green-800' :
                                isActive ? 'bg-blue-100 text-blue-800' :
                                isNoWorkflow ? 'bg-gray-100 text-gray-800' :
                                'bg-yellow-100 text-yellow-800'
                              }`}>
                                {formatStatus(displayStatus)}
                              </span>
                              {workflow.actual_state && workflow.actual_state !== displayStatus && workflow.actual_state !== 'COMPLETED' && (
                                <span className="text-xs text-gray-500">Camunda: {workflow.actual_state}</span>
                              )}
                            </>
                          );
                        })()}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {workflow.started_at ? new Date(workflow.started_at).toLocaleDateString() : 'Not started'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center gap-2">
                        {workflow.has_workflow && workflow.id ? (
                          <>
                            <button
                              onClick={() => handleViewTasks(workflow.id!)}
                              className="text-primary-600 hover:text-primary-900"
                              title="View Tasks"
                            >
                              Tasks
                            </button>
                            <button
                              onClick={() => handleViewDetails(workflow.id!)}
                              className="text-blue-600 hover:text-blue-900"
                              title="View Details & Diagnostics"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            </button>
                            {((workflow.display_status || workflow.current_status)?.includes('failed') || 
                              (workflow.display_status || workflow.current_status)?.includes('rejected') ||
                              (workflow.display_status || workflow.current_status) === 'completed' ||
                              workflow.actual_state === 'COMPLETED') && (
                              <div className="relative group">
                                <button
                                  className="text-orange-600 hover:text-orange-900"
                                  title="Mitigation Options"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                  </svg>
                                </button>
                                <div className="hidden group-hover:block absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg z-10 border border-gray-200">
                                  <div className="py-1">
                                    <button
                                      onClick={() => handleOverrideWorkflow(workflow.id!, 'retry')}
                                      className="block w-full text-left px-4 py-2 text-sm text-blue-600 hover:bg-blue-50"
                                    >
                                      Retry Workflow
                                    </button>
                                    <button
                                      onClick={() => handleOverrideWorkflow(workflow.id!, 'approve')}
                                      className="block w-full text-left px-4 py-2 text-sm text-green-600 hover:bg-green-50"
                                    >
                                      Override: Approve
                                    </button>
                                    <button
                                      onClick={() => handleOverrideWorkflow(workflow.id!, 'reject')}
                                      className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                                    >
                                      Override: Reject
                                    </button>
                                  </div>
                                </div>
                              </div>
                            )}
                            <button
                              onClick={() => handleRestartWorkflow(workflow.id!)}
                              className="text-blue-600 hover:text-blue-900"
                              title="Restart Workflow"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                              </svg>
                            </button>
                            <button
                              onClick={() => handleDeleteWorkflow(workflow.id!)}
                              className="text-red-600 hover:text-red-900"
                              title="Delete Workflow"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => handleStartWorkflow(workflow.nda_record_id)}
                              className="text-green-600 hover:text-green-900"
                            >
                              Start Workflow
                            </button>
                            <button
                              onClick={() => handleDeleteNDA(workflow.nda_record_id)}
                              className="text-red-600 hover:text-red-900"
                              title="Delete NDA"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Task Management Modal */}
      {selectedWorkflow && (
        <TaskManagement
          workflowInstanceId={selectedWorkflow}
          onClose={() => setSelectedWorkflow(null)}
        />
      )}

      {/* NDA Creation Modal */}
      {showCreateModal && (
        <NDACreationModal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleNDACreated}
        />
      )}

      {/* Workflow Details Modal */}
      {showDetailsModal && selectedWorkflowDetails && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-10 mx-auto p-5 border w-11/12 md:w-4/5 lg:w-3/4 shadow-lg rounded-md bg-white max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900">Workflow Details & Diagnostics</h2>
              <button
                onClick={() => {
                  setShowDetailsModal(false);
                  setSelectedWorkflowDetails(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-6">
              {/* Status Section */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-semibold mb-3">Status</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">State</p>
                    <p className={`font-semibold ${
                      selectedWorkflowDetails.state === 'ACTIVE' ? 'text-green-600' :
                      selectedWorkflowDetails.state === 'COMPLETED' ? 'text-blue-600' :
                      'text-red-600'
                    }`}>
                      {selectedWorkflowDetails.state}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Current Status</p>
                    <p className="font-semibold">{selectedWorkflowDetails.current_status}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Started</p>
                    <p className="font-semibold">
                      {selectedWorkflowDetails.started_at ? new Date(selectedWorkflowDetails.started_at).toLocaleString() : 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Completed</p>
                    <p className="font-semibold">
                      {selectedWorkflowDetails.completed_at ? new Date(selectedWorkflowDetails.completed_at).toLocaleString() : 'N/A'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Diagnostics Section */}
              {selectedWorkflowDetails.diagnostics && (
                <div className="bg-blue-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold mb-3">Diagnostics</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {Object.entries(selectedWorkflowDetails.diagnostics).map(([key, value]) => (
                      <div key={key}>
                        <p className="text-sm text-gray-600 capitalize">{key.replace(/_/g, ' ')}</p>
                        <p className={`font-semibold ${value ? 'text-green-600' : 'text-gray-400'}`}>
                          {String(value)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Incidents Section */}
              {selectedWorkflowDetails.incidents && selectedWorkflowDetails.incidents.length > 0 && (
                <div className="bg-red-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold mb-3 text-red-800">Errors / Incidents</h3>
                  {selectedWorkflowDetails.incidents.map((incident: any, idx: number) => (
                    <div key={idx} className="mb-2 p-2 bg-white rounded">
                      <p className="font-semibold text-red-800">{incident.message || incident.errorMessage}</p>
                      <p className="text-sm text-gray-600">Type: {incident.incidentType}</p>
                      {incident.activityId && <p className="text-sm text-gray-600">Activity: {incident.activityId}</p>}
                    </div>
                  ))}
                </div>
              )}

              {/* Variables Section */}
              {selectedWorkflowDetails.variables && Object.keys(selectedWorkflowDetails.variables).length > 0 && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold mb-3">Process Variables</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {Object.entries(selectedWorkflowDetails.variables).map(([key, value]) => (
                      <div key={key} className="flex justify-between p-2 bg-white rounded">
                        <span className="font-medium text-gray-700">{key}:</span>
                        <span className="text-gray-600">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tasks Section */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-semibold mb-3">Tasks</h3>
                <div className="space-y-2">
                  <div>
                    <p className="font-medium text-sm text-gray-700">Active Tasks: {selectedWorkflowDetails.active_tasks?.length || 0}</p>
                    {selectedWorkflowDetails.active_tasks?.map((task: any, idx: number) => (
                      <div key={idx} className="ml-4 p-2 bg-white rounded mt-1">
                        <p className="font-medium">{task.name}</p>
                        <p className="text-sm text-gray-600">Assignee: {task.assignee || 'Unassigned'}</p>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="font-medium text-sm text-gray-700">Completed Tasks: {selectedWorkflowDetails.historic_tasks?.length || 0}</p>
                    {selectedWorkflowDetails.historic_tasks?.slice(0, 5).map((task: any, idx: number) => (
                      <div key={idx} className="ml-4 p-2 bg-white rounded mt-1">
                        <p className="font-medium">{task.name || task.taskName}</p>
                        {task.endTime && (
                          <p className="text-sm text-gray-600">Completed: {new Date(task.endTime).toLocaleString()}</p>
                        )}
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="font-medium text-sm text-gray-700">External Tasks: {selectedWorkflowDetails.external_tasks?.length || 0}</p>
                    {selectedWorkflowDetails.external_tasks?.map((task: any, idx: number) => (
                      <div key={idx} className="ml-4 p-2 bg-white rounded mt-1">
                        <p className="font-medium">Topic: {task.topicName}</p>
                        <p className="text-sm text-gray-600">Worker: {task.workerId || 'Unassigned'}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Mitigation Actions for Failed/Completed Workflows */}
              {(selectedWorkflowDetails.state === 'COMPLETED' || 
                selectedWorkflowDetails.current_status?.includes('failed') || 
                selectedWorkflowDetails.current_status?.includes('rejected')) && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <h3 className="text-lg font-semibold mb-3 text-yellow-800">Mitigation Options</h3>
                  <p className="text-sm text-yellow-700 mb-3">
                    This workflow has completed or failed. You can:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => handleOverrideWorkflow(selectedWorkflowDetails.workflow_instance_id, 'retry')}
                      className="px-3 py-2 border border-blue-300 rounded-md text-sm font-medium text-blue-700 bg-white hover:bg-blue-50"
                    >
                      Retry Workflow
                    </button>
                    <button
                      onClick={() => handleOverrideWorkflow(selectedWorkflowDetails.workflow_instance_id, 'approve')}
                      className="px-3 py-2 border border-green-300 rounded-md text-sm font-medium text-green-700 bg-white hover:bg-green-50"
                    >
                      Override: Approve
                    </button>
                    <button
                      onClick={() => handleOverrideWorkflow(selectedWorkflowDetails.workflow_instance_id, 'reject')}
                      className="px-3 py-2 border border-red-300 rounded-md text-sm font-medium text-red-700 bg-white hover:bg-red-50"
                    >
                      Override: Reject
                    </button>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => {
                    if (selectedWorkflowDetails.workflow_instance_id) {
                      handleDeleteWorkflow(selectedWorkflowDetails.workflow_instance_id);
                      setShowDetailsModal(false);
                    }
                  }}
                  className="px-4 py-2 border border-red-300 rounded-md shadow-sm text-sm font-medium text-red-700 bg-white hover:bg-red-50"
                >
                  Delete Workflow
                </button>
                <button
                  onClick={() => {
                    setShowDetailsModal(false);
                    setSelectedWorkflowDetails(null);
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

