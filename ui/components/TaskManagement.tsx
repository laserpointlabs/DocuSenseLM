'use client';

import { useState, useEffect } from 'react';
import { workflowAPI } from '@/lib/api';

interface TaskManagementProps {
  workflowInstanceId: string;
  onClose: () => void;
}

interface CamundaTask {
  id: string;
  name: string;
  assignee?: string;
  created: string;
  due?: string;
  processInstanceId: string;
}

interface DatabaseTask {
  id: string;
  task_id: string;
  task_name: string;
  status: string;
  assignee_user_id?: string;
  due_date?: string;
  completed_at?: string;
}

interface WorkflowTasks {
  workflow_instance_id: string;
  workflow_status?: string;
  camunda_process_instance_id?: string;
  camunda_tasks: (CamundaTask & { completed?: boolean; endTime?: string })[];
  database_tasks: DatabaseTask[];
}

export default function TaskManagement({ workflowInstanceId, onClose }: TaskManagementProps) {
  const [tasks, setTasks] = useState<WorkflowTasks | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completingTask, setCompletingTask] = useState<string | null>(null);
  const [taskStatusFilter, setTaskStatusFilter] = useState<string>('all');

  useEffect(() => {
    loadTasks();
    // Poll for updates every 5 seconds
    const interval = setInterval(loadTasks, 5000);
    return () => clearInterval(interval);
  }, [workflowInstanceId]);

  const loadTasks = async () => {
    try {
      const data = await workflowAPI.getWorkflowTasks(workflowInstanceId);
      setTasks(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteTask = async (taskId: string, approved: boolean) => {
    try {
      setCompletingTask(taskId);
      await workflowAPI.completeTask(taskId, approved);
      await loadTasks();
    } catch (err: any) {
      setError(err.message || 'Failed to complete task');
    } finally {
      setCompletingTask(null);
    }
  };

  if (loading && !tasks) {
    return (
      <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
        <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-md bg-white">
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          </div>
        </div>
      </div>
    );
  }

  const allTasks = tasks?.camunda_tasks || [];
  const allDbTasks = tasks?.database_tasks || [];
  
  // Combine tasks and filter by status
  type CombinedTask = (CamundaTask & { type: 'camunda'; dbStatus?: undefined }) | 
                      (DatabaseTask & { type: 'database'; id: string; name: string; created: string; assignee?: string });
  
  const combinedTasks: CombinedTask[] = [
    ...allTasks.map(t => ({ ...t, type: 'camunda' as const, dbStatus: undefined })),
    ...allDbTasks.map(t => ({ 
      ...t, 
      type: 'database' as const, 
      id: t.task_id, 
      name: t.task_name, 
      created: t.due_date || '', 
      assignee: t.assignee_user_id 
    }))
  ];
  
  const filteredTasks = combinedTasks.filter(task => {
    if (taskStatusFilter === 'all') return true;
    if (taskStatusFilter === 'pending') {
      return task.type === 'camunda' || (task.type === 'database' && task.status === 'pending');
    }
    if (taskStatusFilter === 'completed') {
      return task.type === 'database' && task.status === 'completed';
    }
    return true;
  });

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-2/3 shadow-lg rounded-md bg-white">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-gray-900">Workflow Tasks</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {/* Task Filters */}
        <div className="mb-4 flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Filter:</label>
          <select
            value={taskStatusFilter}
            onChange={(e) => setTaskStatusFilter(e.target.value)}
            className="px-3 py-1.5 border border-gray-300 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="all">All Tasks</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
          </select>
          <span className="text-sm text-gray-500 ml-2">
            ({filteredTasks.length} {filteredTasks.length === 1 ? 'task' : 'tasks'})
          </span>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {tasks && tasks.workflow_status && (
          <div className="mb-4">
            <span className={`inline-flex px-3 py-1 text-sm font-semibold rounded-full ${
              tasks.workflow_status === 'completed' ? 'bg-green-100 text-green-800' :
              tasks.workflow_status === 'rejected' ? 'bg-red-100 text-red-800' :
              'bg-yellow-100 text-yellow-800'
            }`}>
              Workflow Status: {tasks.workflow_status}
            </span>
          </div>
        )}

        {filteredTasks.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 mb-2">No tasks found for this filter.</p>
            {tasks && tasks.workflow_status && (
              <p className="text-sm text-gray-400">
                {tasks.workflow_status === 'completed' || tasks.workflow_status === 'rejected' 
                  ? 'This workflow has completed. All tasks have been finished.'
                  : 'This workflow may still be processing. Tasks will appear here when available.'}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {filteredTasks.map((task) => {
              const isCamundaTask = task.type === 'camunda';
              const isDatabaseTask = task.type === 'database';
              
              return (
                <div
                  key={task.id}
                  className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-gray-900">{task.name}</h3>
                      <div className="mt-2 space-y-1">
                        {task.assignee && (
                          <p className="text-sm text-gray-600">
                            <span className="font-medium">Assignee:</span> {task.assignee}
                          </p>
                        )}
                        <p className="text-sm text-gray-600">
                          <span className="font-medium">Created:</span>{' '}
                          {new Date(task.created).toLocaleString()}
                        </p>
                        {isCamundaTask && task.due && (
                          <p className="text-sm text-gray-600">
                            <span className="font-medium">Due:</span>{' '}
                            {new Date(task.due).toLocaleString()}
                          </p>
                        )}
                        {isCamundaTask && task.completed && task.endTime && (
                          <p className="text-sm text-gray-600">
                            <span className="font-medium">Completed:</span>{' '}
                            {new Date(task.endTime).toLocaleString()}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2 ml-4">
                      {isCamundaTask ? (
                        task.completed ? (
                          <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                            Completed
                          </span>
                        ) : (
                          <>
                            <button
                              onClick={() => handleCompleteTask(task.id, true)}
                              disabled={completingTask === task.id}
                              className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                            {completingTask === task.id ? (
                              <>
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                Processing...
                              </>
                            ) : (
                              <>
                                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                                Approve
                              </>
                            )}
                          </button>
                          <button
                            onClick={() => handleCompleteTask(task.id, false)}
                            disabled={completingTask === task.id}
                            className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {completingTask === task.id ? (
                              'Processing...'
                            ) : (
                              <>
                                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              Reject
                            </>
                          )}
                        </button>
                          </>
                        )
                      ) : (
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          isDatabaseTask && task.status === 'completed' ? 'bg-green-100 text-green-800' :
                          isDatabaseTask && task.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {isDatabaseTask ? (task.status || 'Active') : 'Active'}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}


