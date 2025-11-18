/**
 * API client for NDA Dashboard with verbose debugging helpers.
 */
import axios, { AxiosInstance } from 'axios';

// Support both HTTP and HTTPS URLs for Cloudflare Tunnel
const API_URL = process.env.NEXT_PUBLIC_API_URL 
  ? (process.env.NEXT_PUBLIC_API_URL.startsWith('http') 
      ? process.env.NEXT_PUBLIC_API_URL 
      : `https://${process.env.NEXT_PUBLIC_API_URL}`)
  : 'http://localhost:8000';
const DEBUG_ENABLED =
  process.env.NEXT_PUBLIC_DEBUG_API === 'true' ||
  process.env.NODE_ENV !== 'production';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token interceptor
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle 401 errors (unauthorized)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      // Clear token and redirect to login
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

const summarisePayload = (data: unknown) => {
  if (typeof FormData !== 'undefined' && data instanceof FormData) {
    try {
      return {
        type: 'FormData',
        fields: Array.from(data.keys()),
      };
    } catch (error) {
      return {
        type: 'FormData',
        detail: 'Unable to inspect entries',
        error: String(error),
      };
    }
  }
  return data;
};

const attachDebugInterceptors = (client: AxiosInstance, label: string) => {
  client.interceptors.request.use(
    (config) => {
      const method = (config.method || 'GET').toUpperCase();
      const url = `${config.baseURL || ''}${config.url || ''}`;
      console.groupCollapsed(`[${label}] ➡️ ${method} ${url}`);
      console.debug('Headers:', config.headers);
      console.debug('Params:', config.params);
      if (config.data !== undefined) {
        console.debug('Payload:', summarisePayload(config.data));
      }
      console.groupEnd();
      return config;
    },
    (error) => {
      console.group(`[${label}] ❌ request error`);
      console.error(error);
      console.groupEnd();
      return Promise.reject(error);
    }
  );

  client.interceptors.response.use(
    (response) => {
      const method = (response.config.method || 'GET').toUpperCase();
      const url = `${response.config.baseURL || ''}${response.config.url || ''}`;
      console.groupCollapsed(
        `[${label}] ✅ ${method} ${url} (${response.status})`
      );
      console.debug('Data:', response.data);
      console.debug('Headers:', response.headers);
      console.groupEnd();
      return response;
    },
    (error) => {
      const cfg = error.config || {};
      const method = cfg.method ? cfg.method.toUpperCase() : 'REQUEST';
      const url = cfg.url ? `${cfg.baseURL || ''}${cfg.url}` : '<unknown>';
      console.group(`[${label}] ❌ ${method} ${url}`);
      if (error.response) {
        console.error('Status:', error.response.status);
        console.error('Headers:', error.response.headers);
        console.error('Data:', error.response.data);
      } else {
        console.error('Error:', error.message);
      }
      console.groupEnd();
      return Promise.reject(error);
    }
  );
};

if (DEBUG_ENABLED) {
  attachDebugInterceptors(api, 'API');
  attachDebugInterceptors(axios, 'AXIOS');
  if (typeof window !== 'undefined') {
    (window as any).__ndaDebugEnabled = true;
    console.info(
      '[NDA Debug] Verbose API logging is enabled. Set NEXT_PUBLIC_DEBUG_API=false to disable.'
    );
  }
}

// Types ----------------------------------------------------------------------
export interface SearchRequest {
  query: string;
  k?: number;
  filters?: {
    party?: string;
    date_range?: { start: string; end: string };
    governing_law?: string;
    is_mutual?: boolean;
  };
}

export interface SearchResult {
  chunk_id: string;
  score: number;
  text: string;
  doc_id: string;
  section_type: string;
  clause_number?: string;
  page_num: number;
  span_start: number;
  span_end: number;
  source_uri: string;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

export interface AnswerRequest {
  question: string;
  filters?: SearchRequest['filters'];
  max_context_chunks?: number;
}

export interface Citation {
  doc_id: string;
  clause_number?: string;
  page_num: number;
  span_start: number;
  span_end: number;
  source_uri: string;
  excerpt: string;
}

export interface AnswerResponse {
  answer: string;
  citations: Citation[];
  question: string;
}

export interface Document {
  id: string;
  filename: string;
  upload_date: string;
  status: string;
  metadata?: Record<string, any>;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

// API functions --------------------------------------------------------------
export const searchAPI = {
  search: async (request: SearchRequest): Promise<SearchResponse> => {
    const response = await api.post<SearchResponse>('/search', request);
    return response.data;
  },
};

export const answerAPI = {
  answer: async (request: AnswerRequest): Promise<AnswerResponse> => {
    const response = await api.post<AnswerResponse>('/answer', request);
    return response.data;
  },
};

export const documentAPI = {
  list: async (skip = 0, limit = 100): Promise<DocumentListResponse> => {
    const response = await api.get<DocumentListResponse>('/documents', {
      params: { skip, limit },
    });
    return response.data;
  },
  get: async (id: string): Promise<Document> => {
    const response = await api.get<Document>(`/documents/${id}`);
    return response.data;
  },
  getFileUrl: (id: string): string => {
    return `${API_URL}/documents/${id}/file`;
  },
  getChunks: async (id: string): Promise<any> => {
    const response = await api.get(`/documents/${id}/chunks`);
    return response.data;
  },
  findTextMatch: async (id: string, chunkText: string, pdfTextItems: Array<{str: string, index?: number}>): Promise<{indices: number[]}> => {
    const response = await api.post(`/documents/${id}/find-text-match`, {
      chunk_text: chunkText,
      pdf_text_items: pdfTextItems.map((item, idx) => ({ str: item.str, index: item.index ?? idx }))
    });
    return response.data;
  },
  upload: async (file: File): Promise<{ document_id: string; filename: string; status: string }> => {
    const formData = new FormData();
    formData.append('files', file);
    if (DEBUG_ENABLED) {
      console.groupCollapsed('[Upload] single file');
      console.debug('Filename:', file.name, 'Size(bytes):', file.size);
      console.groupEnd();
    }
    const response = await api.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    const results = Array.isArray(response.data) ? response.data : [response.data];
    return results[0];
  },
  uploadMultiple: async (files: File[]): Promise<Array<{ document_id: string; filename: string; status: string; message?: string }>> => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });
    if (DEBUG_ENABLED) {
      console.groupCollapsed('[Upload] batch');
      console.table(
        files.map((file) => ({
          name: file.name,
          sizeBytes: file.size,
          type: file.type || 'n/a',
        }))
      );
      console.groupEnd();
    }
    const response = await api.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  delete: async (id: string): Promise<{ message: string; document_id: string }> => {
    const response = await api.delete(`/documents/${id}`);
    return response.data;
  },
};

export interface ReindexProgress {
  is_running: boolean;
  total: number;
  completed: number;
  current: string | null;
  errors: number;
  progress_percent: number;
}

export const adminAPI = {
  getStats: async () => {
    const response = await api.get('/admin/stats');
    return response.data;
  },
  getReindexProgress: async (): Promise<ReindexProgress> => {
    const response = await api.get('/admin/reindex/progress');
    return response.data;
  },
  reindex: async (documentId?: string) => {
    if (documentId) {
      return api.post(`/admin/reindex/${documentId}`);
    }
    return api.post('/admin/reindex/all');
  },
};

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
  role: string;
}

export interface UserInfo {
  id: string;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export const authAPI = {
  login: async (request: LoginRequest): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>('/auth/login', request);
    return response.data;
  },
  getMe: async (): Promise<UserInfo> => {
    const response = await api.get<UserInfo>('/auth/me');
    return response.data;
  },
};

export interface Template {
  id: string;
  name: string;
  description?: string;
  file_path: string;
  is_active: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
  version?: number;
  template_key?: string;
  is_current?: boolean;
  change_notes?: string;
}

export interface TemplateListResponse {
  templates: Template[];
  total: number;
}

export interface NDACreateRequest {
  template_id: string;
  counterparty_name: string;
  counterparty_domain?: string;
  counterparty_email?: string;
  disclosing_party?: string;
  receiving_party?: string;
  effective_date?: string;
  term_months?: number;
  survival_months?: number;
  governing_law?: string;
  direction?: string;
  nda_type?: string;
  entity_id?: string;
  additional_data?: Record<string, any>;
  // Workflow signers
  reviewer_user_id?: string;
  approver_user_id?: string;
  internal_signer_user_id?: string;
  // Workflow options
  auto_start_workflow?: boolean;
}

export interface NDARecordSummary {
  id: string;
  document_id?: string;
  counterparty_name: string;
  counterparty_domain?: string;
  status: string;
  direction?: string;
  nda_type?: string;
  entity_id?: string;
  owner_user_id?: string;
  effective_date?: string;
  expiry_date?: string;
  term_months?: number;
  survival_months?: number;
  tags?: Record<string, any>;
  file_uri: string;
}

export const templateAPI = {
  list: async (activeOnly = true, currentOnly = true): Promise<TemplateListResponse> => {
    const response = await api.get<TemplateListResponse>('/templates', {
      params: { active_only: activeOnly, current_only: currentOnly },
    });
    return response.data;
  },
  get: async (id: string, version?: number): Promise<Template> => {
    const response = await api.get<Template>(`/templates/${id}`, {
      params: version ? { version } : {},
    });
    return response.data;
  },
  getVariables: async (id: string): Promise<{ variables: string[] }> => {
    const response = await api.get(`/templates/${id}/variables`);
    return response.data;
  },
  listVersions: async (templateKey: string): Promise<TemplateListResponse> => {
    const response = await api.get<TemplateListResponse>(`/templates/${templateKey}/versions`);
    return response.data;
  },
  setCurrentVersion: async (templateKey: string, version: number): Promise<Template> => {
    const response = await api.post<Template>(`/templates/${templateKey}/versions/${version}/set-current`);
    return response.data;
  },
  update: async (templateId: string, updates: { name?: string; description?: string; is_active?: boolean }): Promise<Template> => {
    const response = await api.put<Template>(`/templates/${templateId}`, updates);
    return response.data;
  },
  downloadFile: (templateId: string, version?: number, format: 'docx' | 'pdf' = 'docx'): string => {
    const params = new URLSearchParams();
    if (version) params.append('version', version.toString());
    params.append('format', format);
    return `${API_URL}/templates/${templateId}/file?${params.toString()}`;
  },
  getPdfUrl: (templateId: string, version?: number): string => {
    return templateAPI.downloadFile(templateId, version, 'pdf');
  },
  delete: async (templateId: string, version?: number): Promise<void> => {
    const params = version ? `?version=${version}` : '';
    await api.delete(`/templates/${templateId}${params}`);
  },
  deleteVersion: async (templateKey: string, version: number): Promise<void> => {
    await api.delete(`/templates/${templateKey}/versions/${version}`);
  },
};

export interface NDASendEmailRequest {
  to_addresses: string[];
  cc_addresses?: string[];
  subject?: string;
  message?: string;
}

export interface WorkflowTasks {
  workflow_instance_id: string;
  camunda_tasks: Array<{
    id: string;
    name: string;
    assignee?: string;
    created: string;
    due?: string;
    processInstanceId: string;
  }>;
  database_tasks: Array<{
    id: string;
    task_id: string;
    task_name: string;
    status: string;
    assignee_user_id?: string;
    due_date?: string;
    completed_at?: string;
  }>;
}

export const workflowAPI = {
  createNDA: async (request: NDACreateRequest): Promise<NDARecordSummary> => {
    const response = await api.post<NDARecordSummary>('/workflow/nda/create', request);
    return response.data;
  },
  sendNDAEmail: async (ndaId: string, request: NDASendEmailRequest) => {
    const response = await api.post(`/workflow/nda/${ndaId}/send`, request);
    return response.data;
  },
  getNDAStatus: async (ndaId: string) => {
    const response = await api.get(`/workflow/nda/${ndaId}/status`);
    return response.data;
  },
  updateNDAStatus: async (ndaId: string, status: string) => {
    const response = await api.post(`/workflow/nda/${ndaId}/update-status`, null, {
      params: { status },
    });
    return response.data;
  },
  startWorkflow: async (ndaId: string, reviewerUserId?: string, approverUserId?: string, finalApproverUserId?: string) => {
    const response = await api.post(`/workflow/nda/${ndaId}/start-workflow`, null, {
      params: {
        reviewer_user_id: reviewerUserId,
        approver_user_id: approverUserId,
        final_approver_user_id: finalApproverUserId,
      },
    });
    return response.data;
  },
  getWorkflowTasks: async (workflowInstanceId: string): Promise<WorkflowTasks> => {
    const response = await api.get<WorkflowTasks>(`/workflow/workflow/${workflowInstanceId}/tasks`);
    return response.data;
  },
  completeTask: async (taskId: string, approved: boolean, comments?: string) => {
    const response = await api.post(`/workflow/workflow/task/${taskId}/complete`, null, {
      params: { approved, comments },
    });
    return response.data;
  },
  listWorkflows: async (status?: string) => {
    const response = await api.get('/workflow/workflows', {
      params: { status },
    });
    return response.data;
  },
  restartWorkflow: async (workflowInstanceId: string, reviewerUserId?: string, approverUserId?: string, finalApproverUserId?: string) => {
    const response = await api.post(`/workflow/workflow/${workflowInstanceId}/restart`, null, {
      params: {
        reviewer_user_id: reviewerUserId,
        approver_user_id: approverUserId,
        final_approver_user_id: finalApproverUserId,
      },
    });
    return response.data;
  },
  deleteWorkflow: async (workflowInstanceId: string) => {
    const response = await api.delete(`/workflow/workflow/${workflowInstanceId}`);
    return response.data;
  },
  getWorkflowDetails: async (workflowInstanceId: string) => {
    const response = await api.get(`/workflow/workflow/${workflowInstanceId}/details`);
    return response.data;
  },
  deleteNDA: async (ndaId: string) => {
    const response = await api.delete(`/workflow/nda/${ndaId}`);
    return response.data;
  },
  overrideWorkflow: async (workflowInstanceId: string, action: 'approve' | 'reject' | 'retry', reason?: string) => {
    const response = await api.post(`/workflow/workflow/${workflowInstanceId}/override`, null, {
      params: { action, reason },
    });
    return response.data;
  },
  updateWorkflow: async (workflowInstanceId: string, reviewerUserId?: string, approverUserId?: string, internalSignerUserId?: string) => {
    const response = await api.put(`/workflow/workflow/${workflowInstanceId}`, null, {
      params: {
        reviewer_user_id: reviewerUserId,
        approver_user_id: approverUserId,
        internal_signer_user_id: internalSignerUserId,
      },
    });
    return response.data;
  },
  getUsers: async () => {
    const response = await api.get('/workflow/users');
    return response.data;
  },
};

export const competencyAPI = {
  createQuestion: async (questionText: string, categoryId?: string, expectedAnswer?: string, confidenceThreshold?: number) => {
    const response = await api.post('/competency/questions', {
      question_text: questionText,
      category_id: categoryId,
      expected_answer_text: expectedAnswer,
      confidence_threshold: confidenceThreshold,
    });
    return response.data;
  },
  listQuestions: async (categoryId?: string, skip = 0, limit = 500) => {
    const response = await api.get('/competency/questions', {
      params: { category_id: categoryId, skip, limit },
    });
    return response.data;
  },
  runTest: async (questionId: string, documentId?: string) => {
    const response = await api.post('/competency/test/run', {
      question_id: questionId,
      document_id: documentId,
    });
    return response.data;
  },
  submitFeedback: async (testRunId: string, feedback: 'correct' | 'incorrect', feedbackText?: string) => {
    const response = await api.post('/competency/test/feedback', {
      test_run_id: testRunId,
      user_feedback: feedback,
      feedback_text: feedbackText,
    });
    return response.data;
  },
  runAllTests: async () => {
    const response = await api.post('/competency/test/run-all');
    return response.data;
  },
  getTestResults: async (questionId?: string, skip = 0, limit = 100) => {
    const response = await api.get('/competency/test/results', {
      params: { question_id: questionId, skip, limit },
    });
    return response.data;
  },
  getLatestTestResults: async () => {
    const response = await api.get('/competency/test/results/latest');
    return response.data;
  },
  getTestProgress: async () => {
    const response = await api.get('/competency/test/progress');
    return response.data;
  },
  getGlobalThreshold: async () => {
    const response = await api.get('/competency/threshold/global');
    return response.data;
  },
  setGlobalThreshold: async (threshold: number) => {
    const response = await api.put('/competency/threshold/global', null, {
      params: { threshold: threshold.toString() },
    });
    return response.data;
  },
  deleteQuestion: async (questionId: string) => {
    const response = await api.delete(`/competency/questions/${questionId}`);
    return response.data;
  },
  deleteAllQuestions: async () => {
    const response = await api.delete('/competency/questions/all');
    return response.data;
  },
  loadQuestionsFromJson: async (clearExisting: boolean = false) => {
    const response = await api.post('/competency/questions/load-from-json', null, {
      params: { clear_existing: clearExisting },
    });
    return response.data;
  },
};
