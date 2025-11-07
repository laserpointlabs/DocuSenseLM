/**
 * API client for NDA Dashboard with verbose debugging helpers.
 */
import axios, { AxiosInstance } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEBUG_ENABLED =
  process.env.NEXT_PUBLIC_DEBUG_API === 'true' ||
  process.env.NODE_ENV !== 'production';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

export const adminAPI = {
  getStats: async () => {
    const response = await api.get('/admin/stats');
    return response.data;
  },
  reindex: async (documentId?: string) => {
    if (documentId) {
      return api.post(`/admin/reindex/${documentId}`);
    }
    return api.post('/admin/reindex/all');
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
  listQuestions: async (categoryId?: string, skip = 0, limit = 100) => {
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
  deleteQuestion: async (questionId: string) => {
    const response = await api.delete(`/competency/questions/${questionId}`);
    return response.data;
  },
};
