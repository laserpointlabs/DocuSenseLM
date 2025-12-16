import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, MessageSquare, LayoutDashboard, Settings, Check, CheckCircle, AlertCircle, X, Search, Eye, RefreshCw, Archive, Trash2, File, Download, Database, ChevronDown, ChevronRight, Edit, FolderOpen } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Modal, ConfirmModal, AlertModal } from './components/Modal';

const API_PORT = 14242;

interface Config {
  document_types: Record<string, any>;
  dashboard: any;
}

interface DocumentData {
  filename: string;
  doc_type: string;
  upload_date: string;
  status: string;
  workflow_status?: string;
  archived?: boolean;
  show_on_dashboard?: boolean;
  competency_answers: Record<string, any>;
}

import { LoadingScreen } from './components/LoadingScreen';

declare global {
  interface Window {
    electronAPI?: {
      handleStartupStatus: (callback: (status: string) => void) => void;
      handlePythonReady: (callback: () => void) => void;
      handlePythonError: (callback: (error: string) => void) => void;
      getUserDataPath?: () => Promise<string>;
      openUserDataFolder?: () => Promise<{ success: boolean; path: string; error: string | null }>;
    };
  }
}

const APP_TITLE = import.meta.env.VITE_APP_TITLE || "DocuSenseLM";
const APP_VERSION = "1.0.14";

function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'documents' | 'chat' | 'templates' | 'settings'>('dashboard');
  const [config, setConfig] = useState<Config | null>(null);
  const [documents, setDocuments] = useState<Record<string, DocumentData>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [docToOpen, setDocToOpen] = useState<string | null>(null);

  useEffect(() => {
    console.log('App: Setting up IPC listeners');
    console.log('App: window.electronAPI available:', !!window.electronAPI);

    // Listen for python-ready IPC message
    let pythonReadyReceived = false;
    if (window.electronAPI?.handlePythonReady) {
      console.log('App: Setting up python-ready handler');
      window.electronAPI.handlePythonReady(() => {
        console.log('App: Received python-ready signal, initializing app...');
        pythonReadyReceived = true;
        fetchConfig();
        fetchDocuments();
        setIsLoading(false);
      });
    } else {
      console.log('App: electronAPI.handlePythonReady not available');
    }

    // Set up error listener
    if (window.electronAPI?.handlePythonError) {
      console.log('App: Setting up python error handler');
        window.electronAPI.handlePythonError((error: string) => {
            console.error('App: Received python error:', error);
            // Can't use setShowAlert here as it's outside component scope
            // Will be handled by the error display in the component
        });
    } else {
      console.log('App: electronAPI.handlePythonError not available');
    }

    // Fallback to manual health checking if IPC is not available OR if signal doesn't come within 10 seconds
    const initApp = async () => {
      // Wait up to 10 seconds for IPC signal if available
      if (window.electronAPI?.handlePythonReady) {
        await new Promise(resolve => setTimeout(resolve, 10000));
        if (pythonReadyReceived) {
          console.log('App: IPC signal received, skipping health check fallback');
          return;
        }
        console.log('App: IPC signal timeout, falling back to health check');
      }
      
      console.log('App: Starting manual health checking');
      let retries = 0;
      while (retries < 30) {
        try {
          const res = await fetch(`http://localhost:${API_PORT}/health`);
          if (res.ok) {
            console.log('App: Health check passed, initializing app');
            fetchConfig();
            fetchDocuments();
            setIsLoading(false);
            return;
          }
        } catch (e) {
          // Ignore error, retry
        }
        await new Promise(resolve => setTimeout(resolve, 2000));
        retries++;
      }
      console.error('App: Failed to connect to backend after all retries');
      setIsLoading(false); // Show the app anyway, let user see the error
    };
    initApp();

    document.title = APP_TITLE;

    const interval = setInterval(() => {
      if (!isLoading) fetchDocuments();
    }, 5000); 
    return () => clearInterval(interval);
  }, [isLoading]);

  const fetchConfig = () => {
    fetch(`http://localhost:${API_PORT}/config`)
      .then(res => {
        if (!res.ok) {
          throw new Error(`Failed to fetch config: ${res.status} ${res.statusText}`);
        }
        return res.json();
      })
      .then(data => {
        // Ensure document_types exists
        if (!data.document_types) {
          console.warn('[App] Config missing document_types, initializing empty object');
          data.document_types = {};
        }
        setConfig(data);
      })
      .catch(err => {
        console.error('[App] Error fetching config:', err);
        // Set a minimal config so dashboard can still render with error message
        setConfig({ document_types: {}, dashboard: {} });
      });
  };

  const fetchDocuments = () => {
    fetch(`http://localhost:${API_PORT}/documents`)
      .then(res => res.json())
      .then(setDocuments)
      .catch(console.error);
  };

  // Refresh config when switching to dashboard tab to pick up any config changes
  useEffect(() => {
    if (activeTab === 'dashboard') {
      fetchConfig();
    }
  }, [activeTab]);

  if (isLoading) {
    return <LoadingScreen />;
  }

  return (
    <div className="flex h-screen w-full bg-gray-50 text-gray-900 font-sans">
      {/* Sidebar */}
      <div className="w-64 bg-slate-900 text-white flex flex-col p-4">
        <div className="mb-8">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <FileText className="text-blue-400" /> {APP_TITLE}
          </h1>
          <p className="text-xs text-slate-400 mt-1">Version {APP_VERSION}</p>
        </div>
        
        <nav className="flex-1 space-y-2">
          <NavItem 
            icon={<LayoutDashboard />} 
            label="Dashboard" 
            active={activeTab === 'dashboard'} 
            onClick={() => setActiveTab('dashboard')} 
          />
          <NavItem 
            icon={<FileText />} 
            label="Documents" 
            active={activeTab === 'documents'} 
            onClick={() => setActiveTab('documents')} 
          />
          <NavItem 
            icon={<MessageSquare />} 
            label="Chat & Ask" 
            active={activeTab === 'chat'} 
            onClick={() => setActiveTab('chat')} 
          />
          <NavItem 
            icon={<File />} 
            label="Templates" 
            active={activeTab === 'templates'} 
            onClick={() => setActiveTab('templates')} 
          />
          <NavItem 
            icon={<Database />} 
            label="Settings & Data" 
            active={activeTab === 'settings'} 
            onClick={() => setActiveTab('settings')} 
          />
        </nav>
        
        <div className="mt-auto pt-4 border-t border-slate-700">
           <div className="flex items-center gap-2 text-slate-400 text-sm">
             <div className="w-2 h-2 rounded-full bg-green-500"></div>
             System Ready
           </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto p-8 relative">
        {activeTab === 'dashboard' && (
            <DashboardView 
                config={config} 
                documents={documents} 
                onOpenDocument={(filename) => {
                    setDocToOpen(filename);
                    setActiveTab('documents');
                }}
                onRefreshConfig={() => {
                  console.log('[App] Refreshing config for dashboard');
                  fetchConfig();
                }}
            />
        )}
        {activeTab === 'documents' && (
            <DocumentsView 
                config={config} 
                documents={documents} 
                refresh={fetchDocuments} 
                initialPreview={docToOpen}
                onClearPreview={() => setDocToOpen(null)}
            />
        )}
        {activeTab === 'chat' && (
            <ChatView 
                config={config} 
                documents={documents} 
                onOpenDocument={(filename) => {
                    setDocToOpen(filename);
                    setActiveTab('documents');
                }} 
            />
        )}
        {activeTab === 'templates' && <TemplatesView />}
        {activeTab === 'settings' && <SettingsView />}
      </div>
    </div>
  );
}

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode, label: string, active: boolean, onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg transition-colors ${
        active ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function DashboardView({ config, documents, onOpenDocument, onRefreshConfig }: { config: Config | null, documents: Record<string, DocumentData>, onOpenDocument: (filename: string) => void, onRefreshConfig?: () => void }) {
  const [report, setReport] = useState<string | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);


  if (!config) return <div>Loading configuration...</div>;
  
  // Ensure document_types exists and is an object
  if (!config.document_types || typeof config.document_types !== 'object') {
    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-yellow-800">Configuration is missing document types. Please check your config.yaml file.</p>
        </div>
      </div>
    );
  }
  
  // Debug: Log config to see what we're working with
  console.log('[Dashboard] Config loaded:', JSON.stringify(config.document_types, null, 2));
  
  const handleGenerateReport = async () => {
      setGeneratingReport(true);
      try {
          const res = await fetch(`http://localhost:${API_PORT}/report`, { method: "POST" });
          const data = await res.json();
          setReport(data.report);
        } catch (e) {
            console.error("Failed to generate report:", e);
            // Error is logged, user can retry
        } finally {
          setGeneratingReport(false);
      }
  };
  
  // Filter documents based on their document type's show_on_dashboard setting from config
  const docList = Object.values(documents).filter(d => {
    const docTypeConfig = config.document_types[d.doc_type];
    if (!docTypeConfig) {
      console.log(`[Dashboard] No config for doc_type: ${d.doc_type}, hiding document ${d.filename}`);
      return false; // Hide if document type not in config
    }
    // Handle both boolean false and string "false" - default to true if not specified
    const showOnDashboard = docTypeConfig.show_on_dashboard;
    // Explicitly check for false values (boolean false, string "false")
    // null/undefined should default to true (show)
    const shouldShow = showOnDashboard !== false && 
                       showOnDashboard !== "false" && 
                       showOnDashboard !== "False";
    if (!shouldShow) {
      console.log(`[Dashboard] Hiding document ${d.filename} - doc_type: ${d.doc_type}, show_on_dashboard:`, showOnDashboard, `(type: ${typeof showOnDashboard})`);
    }
    return shouldShow;
  });

  const getExpiringCount = (type: string, days: number) => {
    return docList.filter(d => {
        if (d.doc_type !== type) return false;
        const exp = d.competency_answers?.expiration_date;
        if (!exp) return false;
        const date = new Date(exp);
        if (isNaN(date.getTime())) return false;
        const now = new Date();
        const diffTime = date.getTime() - now.getTime();
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays > 0 && diffDays <= days;
    }).length;
  };

  const getExpiringDocs = (type: string, days: number) => {
    return docList.filter(d => {
        if (d.doc_type !== type) return false;
        const exp = d.competency_answers?.expiration_date;
        if (!exp) return false;
        const date = new Date(exp);
        if (isNaN(date.getTime())) return false;
        const now = new Date();
        const diffTime = date.getTime() - now.getTime();
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays > 0 && diffDays <= days;
    }).sort((a, b) => {
        const dateA = new Date(a.competency_answers.expiration_date).getTime();
        const dateB = new Date(b.competency_answers.expiration_date).getTime();
        return dateA - dateB;
    }).slice(0, 3);
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <div className="flex gap-2">
          {onRefreshConfig && (
            <button 
                onClick={() => {
                  console.log('[Dashboard] Manual config refresh triggered');
                  onRefreshConfig();
                }}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium"
                title="Refresh config from server"
            >
                <RefreshCw size={16} />
                Refresh Config
            </button>
          )}
          <button 
              onClick={handleGenerateReport}
              disabled={generatingReport}
              className="bg-gray-800 hover:bg-gray-900 text-white px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium disabled:opacity-50"
          >
              {generatingReport ? <RefreshCw className="animate-spin" size={16} /> : <FileText size={16} />}
              Generate Status Report
          </button>
        </div>
      </div>

      <Modal
        isOpen={!!report}
        onClose={() => setReport(null)}
        title="Email Status Report"
      >
          <div className="flex flex-col gap-4">
              <div className="bg-gray-50 p-4 rounded-lg text-sm font-mono whitespace-pre-wrap border border-gray-200 select-all max-h-[60vh] overflow-y-auto prose prose-sm max-w-none">
                  <ReactMarkdown 
                      remarkPlugins={[remarkGfm]}
                      components={{
                          // Reduce vertical spacing in lists and paragraphs
                          p: ({node, ...props}) => <p className="mb-2" {...props} />,
                          ul: ({node, ...props}) => <ul className="list-disc pl-4 mb-2" {...props} />,
                          ol: ({node, ...props}) => <ol className="list-decimal pl-4 mb-2" {...props} />,
                          li: ({node, ...props}) => <li className="mb-0.5" {...props} />,
                      }}
                  >
                      {report}
                  </ReactMarkdown>
              </div>
              <div className="flex justify-end">
                  <button 
                    onClick={() => {
                        if (report) navigator.clipboard.writeText(report);
                    }}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2"
                  >
                      <Check size={16} /> Copy to Clipboard
                  </button>
              </div>
          </div>
      </Modal>
      
      {Object.keys(config.document_types).length === 0 ? (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <p className="text-yellow-800 font-medium">No document types configured.</p>
          <p className="text-yellow-700 text-sm mt-2">Please configure document types in your config.yaml file to see dashboard cards.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Object.entries(config.document_types)
            .filter(([key, type]: [string, any]) => {
            // Handle both boolean false and string "false" - default to true if not specified
            const showOnDashboard = type.show_on_dashboard;
            // Explicitly check for false values (boolean false, string "false")
            // null/undefined should default to true (show)
            const shouldShow = showOnDashboard !== false && 
                               showOnDashboard !== "false" && 
                               showOnDashboard !== "False";
            if (!shouldShow) {
              console.log(`[Dashboard] Hiding document type card: ${key}, show_on_dashboard:`, showOnDashboard, `(type: ${typeof showOnDashboard})`);
            }
            return shouldShow;
          })
          .map(([key, type]: [string, any]) => {
          const count = docList.filter(d => d.doc_type === key).length;
          const expiring = getExpiringCount(key, 90);
          const expiringDocs = getExpiringDocs(key, 90);
          const reviewCount = docList.filter(d => d.doc_type === key && (d.workflow_status === 'in_review' || !d.workflow_status)).length;
          
          return (
          <div key={key} className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col">
            <h3 className="text-lg font-semibold text-gray-700">{type.name}s</h3>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-4xl font-bold text-blue-600">{count}</span>
              <span className="text-gray-500">total</span>
            </div>
             <div className="mt-2 text-sm space-y-1 mb-4">
                <div className="text-red-500 font-medium">{expiring} expiring in 90 days</div>
                <div className="text-blue-500">{reviewCount} in review</div>
             </div>
             
             {expiringDocs.length > 0 && (
                 <div className="mt-auto border-t border-gray-100 pt-3">
                     <p className="text-xs text-gray-500 font-semibold mb-2">Expiring Soon:</p>
                     <ul className="space-y-2">
                         {expiringDocs.map(doc => (
                             <li key={doc.filename}>
                                 <button 
                                    onClick={() => onOpenDocument(doc.filename)}
                                    className="text-xs text-left text-red-600 hover:underline truncate w-full block"
                                    title={doc.filename}
                                 >
                                     {doc.filename}
                                 </button>
                                 <span className="text-[10px] text-gray-400 block">
                                     Expires: {doc.competency_answers.expiration_date}
                                 </span>
                             </li>
                         ))}
                     </ul>
                 </div>
             )}
          </div>
        )})}
        </div>
      )}
    </div>
  );
}

function DocumentsView({ config, documents, refresh, initialPreview, onClearPreview }: { config: Config | null, documents: Record<string, DocumentData>, refresh: () => void, initialPreview: string | null, onClearPreview?: () => void }) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [previewDoc, setPreviewDoc] = useState<string | null>(initialPreview);
    const [reprocessingFilename, setReprocessingFilename] = useState<string | null>(null);
    const [searchTerm, setSearchTerm] = useState(initialPreview || ""); // Default search to preview doc if set
    const [showArchived, setShowArchived] = useState(false);
    const [editingType, setEditingType] = useState<string | null>(null);
    const [filterDocType, setFilterDocType] = useState<string>(""); // Filter by document type
    
    // Upload modal state
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [pendingFiles, setPendingFiles] = useState<File[]>([]);
    const [selectedType, setSelectedType] = useState<string>("");
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState<Record<string, 'uploading' | 'uploaded' | 'processing' | 'completed' | 'error'>>({});
    const [monitoringProcessing, setMonitoringProcessing] = useState(false);
    const isUploadingRef = useRef(false);
    const [showCancelUploadConfirm, setShowCancelUploadConfirm] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState<{filename: string, type: 'document' | 'template'} | null>(null);
    const [showReprocessConfirm, setShowReprocessConfirm] = useState<string | null>(null);
    const [showAlert, setShowAlert] = useState<{title: string, message: string} | null>(null);
    const [showEditMetadataModal, setShowEditMetadataModal] = useState(false);
    const [editingMetadataFilename, setEditingMetadataFilename] = useState<string | null>(null);
    const [editingMetadata, setEditingMetadata] = useState<Record<string, any> | null>(null);
    const [originalMetadata, setOriginalMetadata] = useState<Record<string, any> | null>(null);
    const [savingMetadata, setSavingMetadata] = useState(false);
    const [toast, setToast] = useState<{message: string, type: 'success' | 'error'} | null>(null);

    useEffect(() => {
        if (initialPreview) {
            setPreviewDoc(initialPreview);
            setSearchTerm(initialPreview); // Filter list to this doc
        }
    }, [initialPreview]);

    const handleClosePreview = () => {
        setPreviewDoc(null);
        setSearchTerm(""); // Clear search when closing
        if (onClearPreview) onClearPreview();
    };

    // Handle file selection - show modal instead of uploading immediately
    const handleFileSelection = (files: File[]) => {
        // Filter to only PDF and DOCX files
        const validFiles = files.filter(file => 
            file.name.toLowerCase().endsWith('.pdf') || file.name.toLowerCase().endsWith('.docx')
        );
        
        if (validFiles.length === 0) {
            setShowAlert({ title: "Invalid File Type", message: "Please select PDF or DOCX files only." });
            return;
        }
        
        // Set default type to first available type if config is loaded
        if (config && Object.keys(config.document_types).length > 0) {
            setSelectedType(Object.keys(config.document_types)[0]);
        }
        
        setPendingFiles(validFiles);
        setShowUploadModal(true);
    };

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        handleFileSelection(Array.from(e.target.files));
        // Reset input so same file can be selected again
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    // Actually perform the upload after type is selected
    const performUpload = async () => {
        if (!selectedType || pendingFiles.length === 0 || isUploadingRef.current) {
            if (!selectedType || pendingFiles.length === 0) {
                setShowAlert({ title: "Missing Information", message: "Please select a document type." });
            }
            return;
        }

        isUploadingRef.current = true;
        setUploading(true);
        const progress: Record<string, 'uploading' | 'uploaded' | 'processing' | 'completed' | 'error'> = {};
        const filesToUpload = [...pendingFiles]; // Store copy in case state changes
        filesToUpload.forEach(file => {
            progress[file.name] = 'uploading';
        });
        setUploadProgress(progress);
        
        try {
            // Upload files sequentially to show progress
            for (let i = 0; i < filesToUpload.length; i++) {
                const file = filesToUpload[i];
                const formData = new FormData();
                formData.append("file", file);
                
                try {
                    const response = await fetch(`http://localhost:${API_PORT}/upload?doc_type=${selectedType}`, {
                        method: "POST",
                        body: formData
                    });
                    
                    if (response.ok) {
                        setUploadProgress(prev => ({ ...prev, [file.name]: 'uploaded' }));
                        // Small delay to show uploaded status before moving to processing
                        await new Promise(resolve => setTimeout(resolve, 300));
                        setUploadProgress(prev => ({ ...prev, [file.name]: 'processing' }));
                    } else {
                        setUploadProgress(prev => ({ ...prev, [file.name]: 'error' }));
                    }
                } catch (err) {
                    console.error(`Error uploading ${file.name}:`, err);
                    setUploadProgress(prev => ({ ...prev, [file.name]: 'error' }));
                }
            }
            
            // Refresh to get updated document list
            refresh();
            
            // Set uploading to false so modal can be closed manually, but keep it open to monitor processing
            setUploading(false);
            setMonitoringProcessing(true);
            
            // Poll for processing completion - don't close modal until all files are actually processed
            const pollProcessingStatus = async () => {
                const maxAttempts = 180; // 3 minutes max
                let attempts = 0;
                
                const checkStatus = async () => {
                    attempts++;
                    try {
                        const response = await fetch(`http://localhost:${API_PORT}/documents`);
                        const docs = await response.json();
                        
                        // Check status of all uploaded files
                        let allProcessed = true;
                        const statuses: Record<string, string> = {};
                        
                        filesToUpload.forEach(file => {
                            const doc = docs[file.name];
                            if (!doc) {
                                // Document not found yet, still processing
                                allProcessed = false;
                                statuses[file.name] = 'not_found';
                            } else {
                                statuses[file.name] = doc.status;
                                
                                if (doc.status === 'processed') {
                                    // This one is done - mark as completed
                                    setUploadProgress(prev => {
                                        if (prev[file.name] !== 'error' && prev[file.name] !== 'completed') {
                                            return { ...prev, [file.name]: 'completed' };
                                        }
                                        return prev;
                                    });
                                    // allProcessed stays true if this is processed (it starts as true)
                                } else if (doc.status === 'error' || doc.status === 'failed') {
                                    // Error state - counts as "done" for closing purposes
                                    setUploadProgress(prev => ({ ...prev, [file.name]: 'error' }));
                                    // Error counts as processed for closing modal (allProcessed stays true)
                                } else {
                                    // Still processing (pending, processing, reprocessing)
                                    console.log(`[Upload Poll] ${file.name}: still processing (${doc.status})`);
                                    allProcessed = false;
                                }
                            }
                        });
                        
                        // If all are processed, close modal immediately
                        if (allProcessed) {
                            // IMPORTANT: Keep monitoringProcessing true while closing modal
                            // This ensures the processing view stays visible until modal closes
                            // Modal component checks isOpen immediately, so modal will close
                            // but React might render once more with monitoringProcessing still true
                            setShowUploadModal(false);
                            refresh(); // Final refresh
                            // Clear state after modal has fully closed
                            // Modal.tsx has "if (!isOpen) return null" so it closes immediately
                            // But we keep monitoringProcessing true to prevent showing initial screen
                            setTimeout(() => {
                                setMonitoringProcessing(false);
                                setUploadProgress({});
                                setSelectedType("");
                                setPendingFiles([]);
                                setUploading(false);
                                isUploadingRef.current = false;
                            }, 100); // Very short delay - just enough for React to process the close
                            return;
                        }
                        
                        if (attempts >= maxAttempts) {
                            setMonitoringProcessing(false);
                            refresh(); // Final refresh
                            cleanupUpload();
                            setShowAlert({ 
                                title: "Processing Timeout", 
                                message: "Some documents are still processing. They will continue in the background. Check their status in the documents list." 
                            });
                            return;
                        }
                        
                        // Check again in 2 seconds
                        setTimeout(checkStatus, 2000);
                    } catch (err) {
                        console.error("[Upload] Error checking processing status:", err);
                        // On error, wait a bit and try again
                        if (attempts < maxAttempts) {
                            setTimeout(checkStatus, 2000);
                        } else {
                            setMonitoringProcessing(false);
                            cleanupUpload();
                        }
                    }
                };
                
                // Start checking after a brief delay to let backend update status
                setTimeout(checkStatus, 2000);
            };
            
            // Start polling for processing completion
            pollProcessingStatus();
        } catch (err) {
            console.error('Upload error:', err);
            setUploading(false);
            setMonitoringProcessing(false);
            cleanupUpload();
        }
    };

    const cleanupUpload = () => {
        // Close modal first to avoid showing initial state
        setShowUploadModal(false);
        // Clear state after modal closes (in next render cycle)
        setTimeout(() => {
            setUploadProgress({});
            setSelectedType("");
            setPendingFiles([]);
            setUploading(false);
            setMonitoringProcessing(false);
            isUploadingRef.current = false;
            refresh(); // Final refresh
        }, 100);
    };

    const cancelUpload = () => {
        if (uploading) {
            setShowCancelUploadConfirm(true);
            return;
        }
        // Allow cancel even during upload (user can force close)
        cleanupUpload();
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const handleCancelUploadConfirm = () => {
        setShowCancelUploadConfirm(false);
        cleanupUpload();
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const handleReprocess = async (filename: string) => {
        setShowReprocessConfirm(filename);
    };

    const confirmReprocess = async () => {
        const filename = showReprocessConfirm;
        if (!filename) return;
        setShowReprocessConfirm(null);
        setReprocessingFilename(filename);
        
        try {
            // URL encode the filename to handle spaces and special characters
            const encodedFilename = encodeURIComponent(filename);
            const url = `http://localhost:${API_PORT}/reprocess/${encodedFilename}`;
            console.log(`[Reprocess] Calling API: ${url}`);
            
            const response = await fetch(url, {
                method: "POST"
            });
            
            console.log(`[Reprocess] Response status: ${response.status}`);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`[Reprocess] Error response: ${errorText}`);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const result = await response.json();
            console.log(`[Reprocess] Success:`, result);
            
            // Poll for status updates until processing completes
            const pollStatus = async () => {
                let attempts = 0;
                const maxAttempts = 120; // 2 minutes max (120 * 1 second)
                
                const checkStatus = async () => {
                    attempts++;
                    try {
                        // Fetch documents directly to get latest status
                        const response = await fetch(`http://localhost:${API_PORT}/documents`);
                        const docs = await response.json();
                        const currentDoc = docs[filename];
                        
                        // Also update the local state
                        refresh();
                        
                        // Check if processing is complete
                        if (currentDoc && currentDoc.status === 'processed') {
                            setReprocessingFilename(null);
                            refresh(); // Final refresh to update UI
                            return; // Done
                        }
                        
                        // If document doesn't exist, stop polling
                        if (!currentDoc) {
                            console.warn(`Document ${filename} not found in API response`);
                            setReprocessingFilename(null);
                            return;
                        }
                        
                        // If still processing and haven't exceeded max attempts, check again
                        if (attempts < maxAttempts && (currentDoc.status === 'processing' || currentDoc.status === 'reprocessing')) {
                            setTimeout(checkStatus, 1000); // Check again in 1 second
                        } else {
                            // Timeout or unknown status
                            setReprocessingFilename(null);
                            refresh(); // Final refresh
                            if (attempts >= maxAttempts) {
                                setShowAlert({ title: "Timeout", message: `Reprocessing ${filename} is taking longer than expected (${maxAttempts} seconds). It may still be processing in the background. Check the status again in a moment.` });
                            } else {
                                // Unknown status - might be an error
                                setShowAlert({ title: "Status Unknown", message: `Reprocessing ${filename} completed with status: ${currentDoc.status}. Check the document status.` });
                            }
                        }
                    } catch (err) {
                        console.error("[Reprocess] Error checking status:", err);
                        setReprocessingFilename(null);
                    }
                };
                
                // Start checking after a brief delay to let backend update status
                console.log(`[Reprocess] Starting status polling for ${filename}`);
                setTimeout(checkStatus, 500);
            };
            
            pollStatus();
        } catch (err) {
            console.error("[Reprocess] Failed to start reprocessing:", err);
            setShowAlert({ title: "Error", message: `Failed to start reprocessing: ${err instanceof Error ? err.message : String(err)}` });
            setReprocessingFilename(null);
        }
    };

    const updateStatus = async (filename: string, status: string) => {
        try {
            await fetch(`http://localhost:${API_PORT}/status/${filename}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status })
            });
            refresh();
        } catch (err) {
            console.error(err);
        }
    };

    const updateDocType = async (filename: string, docType: string) => {
        try {
            await fetch(`http://localhost:${API_PORT}/type/${filename}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ doc_type: docType })
            });
            // Automatically reprocess to extract new competency answers for the new type
            await handleReprocess(filename);
            refresh();
        } catch (err) {
            console.error(err);
        }
    };

    const handleArchive = async (filename: string) => {
        try {
            await fetch(`http://localhost:${API_PORT}/archive/${filename}`, { method: "POST" });
            refresh();
        } catch (err) {
            console.error(err);
        }
    };

    const handleDelete = async (filename: string) => {
        setShowDeleteConfirm({ filename, type: 'document' });
    };

    const confirmDelete = async () => {
        const confirmData = showDeleteConfirm;
        if (!confirmData) return;
        setShowDeleteConfirm(null);
        try {
            await fetch(`http://localhost:${API_PORT}/documents/${confirmData.filename}`, { method: "DELETE" });
            refresh();
            if (previewDoc === confirmData.filename) setPreviewDoc(null);
        } catch (err) {
            console.error(err);
            setShowAlert({ title: "Error", message: "Failed to delete document" });
        }
    };

    const handleSaveMetadata = async () => {
        if (!editingMetadataFilename || !editingMetadata) return;
        
        setSavingMetadata(true);
        try {
            const encodedFilename = encodeURIComponent(editingMetadataFilename);
            const response = await fetch(`http://localhost:${API_PORT}/metadata/${encodedFilename}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ competency_answers: editingMetadata })
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            // Success
            setToast({ message: "Metadata updated successfully", type: "success" });
            setTimeout(() => setToast(null), 3000);
            setShowEditMetadataModal(false);
            setEditingMetadataFilename(null);
            setEditingMetadata(null);
            setOriginalMetadata(null);
            refresh();
        } catch (err) {
            console.error("[Save Metadata] Error:", err);
            const errorMessage = err instanceof Error ? err.message : "Failed to save metadata";
            setToast({ message: errorMessage, type: "error" });
            setTimeout(() => setToast(null), 5000);
            setShowAlert({ title: "Error", message: errorMessage });
        } finally {
            setSavingMetadata(false);
        }
    };

    // Utility function to parse various date formats and convert to YYYY-MM-DD
    const parseDateForInput = (dateStr: string): string => {
        if (!dateStr || typeof dateStr !== 'string') return "";
        
        const trimmed = dateStr.trim();
        if (!trimmed) return "";
        
        // Already in YYYY-MM-DD format
        if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
            return trimmed;
        }
        
        const monthNames: Record<string, number> = {
            'jan': 0, 'january': 0, 'feb': 1, 'february': 1, 'mar': 2, 'march': 2,
            'apr': 3, 'april': 3, 'may': 4, 'jun': 5, 'june': 5,
            'jul': 6, 'july': 6, 'aug': 7, 'august': 7, 'sep': 8, 'september': 8,
            'oct': 9, 'october': 9, 'nov': 10, 'november': 10, 'dec': 11, 'december': 11
        };
        
        // Try parsing various formats
        // DD-MMM-YYYY (e.g., "31-Oct-2025")
        let match = trimmed.match(/^(\d{1,2})-([A-Za-z]{3})-(\d{4})$/);
        if (match) {
            const day = parseInt(match[1], 10);
            const month = monthNames[match[2].toLowerCase()];
            const year = parseInt(match[3], 10);
            if (month !== undefined && day >= 1 && day <= 31 && year >= 1000 && year <= 9999) {
                const date = new Date(year, month, day);
                if (!isNaN(date.getTime()) && date.getDate() === day) {
                    return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                }
            }
        }
        
        // MMM DD, YYYY (e.g., "Oct 31, 2025")
        match = trimmed.match(/^([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})$/);
        if (match) {
            const month = monthNames[match[1].toLowerCase()];
            const day = parseInt(match[2], 10);
            const year = parseInt(match[3], 10);
            if (month !== undefined && day >= 1 && day <= 31 && year >= 1000 && year <= 9999) {
                const date = new Date(year, month, day);
                if (!isNaN(date.getTime()) && date.getDate() === day) {
                    return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                }
            }
        }
        
        // MMMM DD, YYYY (e.g., "October 31, 2025")
        match = trimmed.match(/^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$/);
        if (match) {
            const month = monthNames[match[1].toLowerCase()];
            const day = parseInt(match[2], 10);
            const year = parseInt(match[3], 10);
            if (month !== undefined && day >= 1 && day <= 31 && year >= 1000 && year <= 9999) {
                const date = new Date(year, month, day);
                if (!isNaN(date.getTime()) && date.getDate() === day) {
                    return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                }
            }
        }
        
        // DD MMM YYYY (e.g., "31 Oct 2025")
        match = trimmed.match(/^(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})$/);
        if (match) {
            const day = parseInt(match[1], 10);
            const month = monthNames[match[2].toLowerCase()];
            const year = parseInt(match[3], 10);
            if (month !== undefined && day >= 1 && day <= 31 && year >= 1000 && year <= 9999) {
                const date = new Date(year, month, day);
                if (!isNaN(date.getTime()) && date.getDate() === day) {
                    return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                }
            }
        }
        
        // DD/MM/YYYY or MM/DD/YYYY
        match = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
        if (match) {
            const first = parseInt(match[1], 10);
            const second = parseInt(match[2], 10);
            const third = parseInt(match[3], 10);
            
            // Heuristic: if first > 12, it's DD/MM/YYYY, else MM/DD/YYYY
            let day: number, month: number, year: number;
            if (first > 12) {
                day = first;
                month = second - 1;
                year = third;
            } else {
                month = first - 1;
                day = second;
                year = third;
            }
            
            if (month >= 0 && month <= 11 && day >= 1 && day <= 31 && year >= 1000 && year <= 9999) {
                const date = new Date(year, month, day);
                if (!isNaN(date.getTime()) && date.getDate() === day && date.getMonth() === month) {
                    return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                }
            }
        }
        
        // YYYY/MM/DD
        match = trimmed.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
        if (match) {
            const year = parseInt(match[1], 10);
            const month = parseInt(match[2], 10) - 1;
            const day = parseInt(match[3], 10);
            if (month >= 0 && month <= 11 && day >= 1 && day <= 31 && year >= 1000 && year <= 9999) {
                const date = new Date(year, month, day);
                if (!isNaN(date.getTime()) && date.getDate() === day && date.getMonth() === month) {
                    return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                }
            }
        }
        
        // Try native Date parsing as fallback
        const parsed = new Date(trimmed);
        if (!isNaN(parsed.getTime())) {
            const year = parsed.getFullYear();
            const month = parsed.getMonth();
            const day = parsed.getDate();
            // Validate the parsed date makes sense (not too far in past/future)
            if (year >= 1000 && year <= 9999 && month >= 0 && month <= 11 && day >= 1 && day <= 31) {
                return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            }
        }
        
        // If all parsing fails, return empty string
        return "";
    };

    const handleOpenEditMetadata = (filename: string) => {
        const doc = documents[filename];
        if (!doc) return;
        
        setEditingMetadataFilename(filename);
        // Get all fields from config for this document type
        const docType = doc.doc_type;
        const docConfig = config?.document_types[docType];
        const fields = docConfig?.competency_questions || [];
        
        // Initialize with existing values or empty strings
        const initialMetadata: Record<string, any> = {};
        fields.forEach((field: any) => {
            const rawValue = doc.competency_answers?.[field.id] || "";
            // For date fields, parse and convert to YYYY-MM-DD format
            if (field.type === "date" && rawValue) {
                initialMetadata[field.id] = parseDateForInput(String(rawValue));
            } else {
                initialMetadata[field.id] = rawValue;
            }
        });
        
        // Store original for change detection
        setOriginalMetadata(JSON.parse(JSON.stringify(initialMetadata)));
        setEditingMetadata(initialMetadata);
        setShowEditMetadataModal(true);
    };

    const hasMetadataChanges = (): boolean => {
        if (!editingMetadata || !originalMetadata) return false;
        return JSON.stringify(editingMetadata) !== JSON.stringify(originalMetadata);
    };

    const filteredDocs = Object.values(documents || {}).filter(doc => {
        if (!doc) return false;
        // Search matches filename OR document type name
        const searchLower = searchTerm.toLowerCase();
        const matchesSearch = !searchTerm || 
            (doc.filename?.toLowerCase().includes(searchLower) ?? false) ||
            (config?.document_types[doc.doc_type]?.name?.toLowerCase().includes(searchLower) ?? false);
        const matchesArchive = showArchived ? doc.archived : !doc.archived;
        const matchesType = !filterDocType || doc.doc_type === filterDocType;
        return matchesSearch && matchesArchive && matchesType;
    });

    const [isDragging, setIsDragging] = useState(false);

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileSelection(Array.from(e.dataTransfer.files));
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    };

    return (
        <div className="space-y-4 h-full flex flex-col">
            <div className="flex justify-between items-center gap-4">
                <h2 className="text-xl font-bold">Documents</h2>
                <div className="flex gap-1.5 items-center flex-wrap">
                    <div className="relative">
                        <Search className="absolute left-2 top-1.5 text-gray-400" size={14} />
                        <input 
                            type="text" 
                            placeholder="Search..." 
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="pl-7 pr-2 py-1.5 w-40 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                    </div>
                    <select
                        value={filterDocType}
                        onChange={(e) => setFilterDocType(e.target.value)}
                        className="border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white min-w-[120px]"
                    >
                        <option value="">All Types</option>
                        {config && Object.keys(config.document_types).map(key => (
                            <option key={key} value={key}>
                                {config.document_types[key].name}
                            </option>
                        ))}
                    </select>
                    <button 
                        onClick={() => setShowArchived(!showArchived)}
                        className={`px-2.5 py-1.5 rounded text-xs font-medium border whitespace-nowrap ${
                            showArchived ? 'bg-gray-800 text-white border-gray-800' : 'bg-white text-gray-600 border-gray-300'
                        }`}
                    >
                        {showArchived ? 'Active' : 'Archived'}
                    </button>
                    <button 
                        onClick={() => fileInputRef.current?.click()}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1.5 rounded flex items-center gap-1.5 text-xs font-medium whitespace-nowrap"
                    >
                        <Upload size={14} /> Upload
                    </button>
                    <input 
                        type="file" 
                        ref={fileInputRef} 
                        className="hidden" 
                        accept=".pdf,.docx" 
                        multiple
                        onChange={handleUpload}
                    />
                </div>
            </div>

            <div className="flex-1 flex gap-6 min-h-0">
                {/* Document List */}
                <div 
                    className={`bg-white rounded-xl shadow-sm border overflow-auto flex-1 ${previewDoc ? 'w-1/2' : 'w-full'} ${isDragging ? 'border-blue-500 bg-blue-50 border-2 border-dashed' : 'border-gray-100'}`}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                >
                    {isDragging && (
                        <div className="h-full flex items-center justify-center text-blue-500 font-medium text-lg">
                            Drop files here to upload
                        </div>
                    )}
                    {!isDragging && (
                        <div key="document-list">
                            <div 
                                className={`p-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between transition-all ${(filterDocType || searchTerm) ? 'opacity-100' : 'opacity-0 h-0 p-0 overflow-hidden border-0'}`}
                            >
                                <div className="text-sm text-gray-600">
                                    Showing <span className="font-semibold text-gray-900">{filteredDocs.length}</span> of <span className="font-semibold text-gray-900">{Object.values(documents || {}).length}</span> document{Object.values(documents || {}).length !== 1 ? 's' : ''}
                                    <span className="ml-2">
                                        {filterDocType && <span className="text-blue-600">• Type: {config?.document_types[filterDocType]?.name || filterDocType}</span>}
                                        {searchTerm && <span className="text-blue-600">• Search: "{searchTerm}"</span>}
                                    </span>
                                </div>
                                <button
                                    onClick={() => {
                                        setFilterDocType("");
                                        setSearchTerm("");
                                    }}
                                    className="text-xs text-blue-600 hover:text-blue-700 underline"
                                >
                                    Clear filters
                                </button>
                            </div>
                            <table className="w-full text-left">
                            <thead className="bg-gray-50 border-b border-gray-100 sticky top-0">
                                <tr>
                                    <th className="p-4 font-semibold text-gray-600">Document Name</th>
                                    <th className="p-4 font-semibold text-gray-600">Type</th>
                                <th className="p-4 font-semibold text-gray-600">Status</th>
                                <th className="p-4 font-semibold text-gray-600">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {filteredDocs.map(doc => (
                                <tr key={doc.filename} className="hover:bg-gray-50 cursor-pointer" onClick={() => setPreviewDoc(doc.filename)}>
                                    <td className="p-4 font-medium">{doc.filename}</td>
                                    <td className="p-4 text-sm" onClick={(e) => { e.stopPropagation(); setEditingType(doc.filename); }}>
                                        {editingType === doc.filename ? (
                                            <select
                                                value={doc.doc_type}
                                                onChange={(e) => {
                                                    updateDocType(doc.filename, e.target.value);
                                                    setEditingType(null);
                                                }}
                                                onBlur={() => setEditingType(null)}
                                                onClick={(e) => e.stopPropagation()}
                                                autoFocus
                                                className="border border-gray-300 rounded px-2 py-1 text-sm w-full"
                                            >
                                                {config && Object.keys(config.document_types).map(key => (
                                                    <option key={key} value={key}>{config.document_types[key].name}</option>
                                                ))}
                                            </select>
                                        ) : (
                                            <span className="capitalize cursor-pointer hover:bg-gray-100 px-2 py-1 rounded">
                                                {doc.doc_type.replace('_', ' ')}
                                            </span>
                                        )}
                                    </td>
                                    <td className="p-4">
                                        <div className="flex flex-col gap-1">
                                            <span className={`px-2 py-1 rounded-full text-xs w-fit ${
                                                doc.status === 'processed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                                            }`}>
                                                System: {doc.status}
                                            </span>
                                            <span className={`px-2 py-1 rounded-full text-xs w-fit border ${
                                                doc.workflow_status === 'active' ? 'bg-green-50 border-green-200 text-green-700' : 
                                                doc.workflow_status === 'pending_signature' ? 'bg-orange-50 border-orange-200 text-orange-700' :
                                                'bg-gray-50 border-gray-200 text-gray-600'
                                            }`}>
                                                {doc.workflow_status ? doc.workflow_status.replace('_', ' ') : 'in review'}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="p-4 flex gap-2">
                                        <button 
                                            className="p-1 hover:bg-gray-200 rounded text-blue-600"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setPreviewDoc(doc.filename);
                                            }}
                                            title="View"
                                        >
                                            <Eye size={18} />
                                        </button>
                                        <button 
                                            className="p-1 hover:bg-gray-200 rounded text-gray-600 hover:text-blue-600"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleReprocess(doc.filename);
                                            }}
                                            disabled={reprocessingFilename === doc.filename}
                                            title="Reprocess & Re-index"
                                        >
                                            <RefreshCw size={18} className={reprocessingFilename === doc.filename ? "animate-spin" : ""} />
                                        </button>
                                        <button 
                                            className="p-1 hover:bg-gray-200 rounded text-gray-600 hover:text-orange-600"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleArchive(doc.filename);
                                            }}
                                            title={doc.archived ? "Restore" : "Archive"}
                                        >
                                            <Archive size={18} />
                                        </button>
                                        <button 
                                            className="p-1 hover:bg-gray-200 rounded text-gray-600 hover:text-red-600"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDelete(doc.filename);
                                            }}
                                            title="Delete"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                        </div>
                    )}
                </div>

                {/* PDF Preview Pane */}
                {previewDoc && (
                    <div className="w-1/2 bg-white rounded-xl shadow-sm border border-gray-100 flex flex-col overflow-hidden">
                        <div className="p-3 border-b border-gray-100 flex justify-between items-center bg-gray-50">
                            <h3 className="font-semibold truncate" title={previewDoc}>{previewDoc}</h3>
                            <button onClick={handleClosePreview} className="text-gray-500 hover:text-red-500">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="flex-1 bg-gray-200 relative">
                             <iframe 
                                src={`http://localhost:${API_PORT}/files/${previewDoc}`} 
                                className="w-full h-full border-none" 
                                title="Document Preview"
                             />
                        </div>
                        <div className="p-4 border-t border-gray-100 bg-gray-50 text-sm overflow-auto max-h-48">
                            <div className="flex justify-between items-center mb-2">
                                <h4 className="font-bold text-gray-700">Extracted Data</h4>
                                {documents[previewDoc] && (
                                    <button
                                        onClick={() => handleOpenEditMetadata(previewDoc)}
                                        className="text-blue-600 hover:text-blue-700 flex items-center gap-1 text-xs font-medium"
                                        title="Edit metadata"
                                    >
                                        <Edit size={14} />
                                        Edit
                                    </button>
                                )}
                            </div>
                            {documents[previewDoc]?.competency_answers ? (
                                <ul className="space-y-1">
                                    {Object.entries(documents[previewDoc].competency_answers).map(([k, v]) => (
                                        <li key={k}>
                                            <span className="font-medium text-gray-800">{k}:</span> <span className="text-gray-600">{String(v)}</span>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-gray-500 italic">No data extracted yet.</p>
                            )}

                            <div className="mt-6 pt-4 border-t border-gray-200">
                                <h4 className="font-bold text-gray-700 mb-2">Workflow Status</h4>
                                <div className="flex flex-wrap gap-2">
                                    {['in_review', 'pending_signature', 'active', 'expired'].map(status => (
                                        <button
                                            key={status}
                                            onClick={() => updateStatus(previewDoc, status)}
                                            className={`px-3 py-1 rounded text-xs border transition-colors ${
                                                documents[previewDoc]?.workflow_status === status 
                                                ? 'bg-blue-600 text-white border-blue-600' 
                                                : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                                            }`}
                                        >
                                            {status.replace('_', ' ')}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Upload Modal */}
            <Modal
                isOpen={showUploadModal}
                onClose={uploading ? () => {
                    setShowCancelUploadConfirm(true);
                } : cancelUpload}
                title={uploading ? "Uploading Documents" : monitoringProcessing ? "Processing Documents" : "Select Document Type"}
                hideCloseButton={false}
            >
                <div className="space-y-6">
                    {!uploading && !monitoringProcessing ? (
                        <>
                            <div>
                                <p className="text-sm text-gray-600 mb-4">
                                    {pendingFiles.length} file{pendingFiles.length !== 1 ? 's' : ''} selected for upload:
                                </p>
                                <div className="bg-gray-50 rounded-lg p-4 max-h-48 overflow-y-auto border border-gray-200">
                                    <ul className="space-y-1 text-sm">
                                        {pendingFiles.map((file, index) => (
                                            <li key={index} className="text-gray-700 flex items-center gap-2">
                                                <File size={14} className="text-gray-400" />
                                                <span className="truncate">{file.name}</span>
                                                <span className="text-gray-400 text-xs">({(file.size / 1024).toFixed(1)} KB)</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Document Type <span className="text-red-500">*</span>
                                </label>
                                {config && Object.keys(config.document_types).length > 0 ? (
                                    <select
                                        value={selectedType}
                                        onChange={(e) => setSelectedType(e.target.value)}
                                        className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        autoFocus
                                    >
                                        <option value="">-- Select a document type --</option>
                                        {Object.keys(config.document_types).map(key => (
                                            <option key={key} value={key}>
                                                {config.document_types[key].name}
                                            </option>
                                        ))}
                                    </select>
                                ) : (
                                    <p className="text-sm text-gray-500">Loading document types...</p>
                                )}
                                <p className="text-xs text-gray-500 mt-2">
                                    Note: All selected files will be uploaded with the same document type.
                                </p>
                            </div>

                            <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                                <button
                                    onClick={cancelUpload}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={performUpload}
                                    disabled={!selectedType}
                                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                >
                                    <Upload size={16} />
                                    Upload {pendingFiles.length} File{pendingFiles.length !== 1 ? 's' : ''}
                                </button>
                            </div>
                        </>
                    ) : (
                        <>
                            <div>
                                <div className="flex items-center gap-3 mb-4">
                                    <RefreshCw className={`animate-spin ${uploading ? 'text-blue-600' : 'text-orange-600'}`} size={20} />
                                    <p className="text-sm font-medium text-gray-700">
                                        {uploading ? 'Uploading documents...' : monitoringProcessing ? 'Processing documents (extracting data, indexing, analyzing...)' : 'Upload complete'}
                                    </p>
                                </div>
                                <div className="bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto border border-gray-200 space-y-3">
                                    {pendingFiles.map((file, index) => {
                                        const status = uploadProgress[file.name] || 'uploading';
                                        return (
                                            <div key={index} className="flex items-center gap-3 p-2 bg-white rounded border border-gray-200">
                                                <div className="flex-shrink-0">
                                                    {status === 'uploading' && (
                                                        <RefreshCw className="animate-spin text-blue-600" size={16} />
                                                    )}
                                                    {status === 'uploaded' && (
                                                        <Check className="text-green-600" size={16} />
                                                    )}
                                                    {status === 'processing' && (
                                                        <RefreshCw className="animate-spin text-orange-600" size={16} />
                                                    )}
                                                    {status === 'error' && (
                                                        <AlertCircle className="text-red-600" size={16} />
                                                    )}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="text-sm font-medium text-gray-700 truncate">
                                                        {file.name}
                                                    </div>
                                                    <div className="text-xs text-gray-500">
                                                        {status === 'uploading' && 'Uploading file...'}
                                                        {status === 'uploaded' && 'File uploaded successfully'}
                                                        {status === 'processing' && 'Processing document (extracting data, indexing...)'}
                                                        {status === 'completed' && 'Processing complete!'}
                                                        {status === 'error' && 'Upload failed'}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                                <p className="text-xs text-blue-800">
                                    <strong>Note:</strong> Documents are being processed in the background. 
                                    This includes text extraction, RAG indexing, and competency question analysis. 
                                    You can close this dialog and continue working - processing will continue.
                                </p>
                            </div>
                            <div className="flex justify-end pt-2">
                                <button
                                    onClick={() => {
                                        // Only allow closing if not actively uploading
                                        if (!uploading && !monitoringProcessing) {
                                            cleanupUpload();
                                        } else if (uploading) {
                                            setShowCancelUploadConfirm(true);
                                        } else {
                                            // During processing monitoring, allow closing but warn
                                            cleanupUpload();
                                        }
                                    }}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                    disabled={uploading}
                                >
                                    {uploading ? 'Uploading...' : monitoringProcessing ? 'Processing... (Click to close)' : 'Close Dialog'}
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </Modal>

            <ConfirmModal
                isOpen={showCancelUploadConfirm}
                onConfirm={handleCancelUploadConfirm}
                onCancel={() => setShowCancelUploadConfirm(false)}
                title="Cancel Upload?"
                message="Upload is in progress. Are you sure you want to cancel? Files already uploaded will remain."
                confirmText="Yes, Cancel"
                cancelText="Continue Upload"
                confirmButtonClass="bg-red-600 hover:bg-red-700 text-white"
            />

            <ConfirmModal
                isOpen={!!showReprocessConfirm}
                onConfirm={confirmReprocess}
                onCancel={() => setShowReprocessConfirm(null)}
                title="Reprocess Document?"
                message={`Are you sure you want to re-process ${showReprocessConfirm}? This will re-index it and run competency questions again.`}
                confirmText="Reprocess"
                cancelText="Cancel"
            />

            <ConfirmModal
                isOpen={!!showDeleteConfirm && showDeleteConfirm.type === 'document'}
                onConfirm={confirmDelete}
                onCancel={() => setShowDeleteConfirm(null)}
                title="Delete Document?"
                message={`Are you sure you want to permanently delete ${showDeleteConfirm?.filename}?`}
                confirmText="Delete"
                cancelText="Cancel"
                confirmButtonClass="bg-red-600 hover:bg-red-700 text-white"
            />

            {/* Edit Metadata Modal */}
            {showEditMetadataModal && editingMetadataFilename && editingMetadata && (
                <Modal
                    isOpen={showEditMetadataModal}
                    onClose={() => {
                        // Check if there are unsaved changes
                        if (hasMetadataChanges() && !savingMetadata) {
                            if (confirm("You have unsaved changes. Are you sure you want to close?")) {
                                setShowEditMetadataModal(false);
                                setEditingMetadataFilename(null);
                                setEditingMetadata(null);
                                setOriginalMetadata(null);
                            }
                        } else {
                            setShowEditMetadataModal(false);
                            setEditingMetadataFilename(null);
                            setEditingMetadata(null);
                            setOriginalMetadata(null);
                        }
                    }}
                    title={`Edit Metadata - ${editingMetadataFilename}`}
                >
                    <div className="space-y-4">
                        {(() => {
                            const doc = documents[editingMetadataFilename];
                            if (!doc || !config) return null;
                            
                            const docType = doc.doc_type;
                            const docConfig = config.document_types[docType];
                            const fields = docConfig?.competency_questions || [];
                            
                            if (fields.length === 0) {
                                return <p className="text-gray-500">No fields configured for this document type.</p>;
                            }
                            
                            return (
                                <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
                                    {fields.map((field: any) => {
                                        const fieldId = field.id;
                                        const fieldValue = editingMetadata[fieldId] || "";
                                        const originalValue = originalMetadata?.[fieldId] || "";
                                        const hasChanged = String(fieldValue) !== String(originalValue);
                                        
                                        return (
                                            <div key={fieldId} className={`${hasChanged ? 'bg-blue-50 border-blue-200' : 'bg-white border-gray-200'} border rounded-lg p-3`}>
                                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                                    {field.question}
                                                </label>
                                                {field.type === "date" ? (
                                                    <input
                                                        type="date"
                                                        value={fieldValue ? String(fieldValue).substring(0, 10) : ""}
                                                        onChange={(e) => {
                                                            setEditingMetadata({
                                                                ...editingMetadata,
                                                                [fieldId]: e.target.value
                                                            });
                                                        }}
                                                        className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    />
                                                ) : (
                                                    <textarea
                                                        value={String(fieldValue)}
                                                        onChange={(e) => {
                                                            setEditingMetadata({
                                                                ...editingMetadata,
                                                                [fieldId]: e.target.value
                                                            });
                                                        }}
                                                        rows={fieldValue && fieldValue.length > 50 ? 3 : 1}
                                                        className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
                                                        placeholder={`Enter ${field.question.toLowerCase()}`}
                                                    />
                                                )}
                                                {hasChanged && (
                                                    <p className="text-xs text-blue-600 mt-1">Modified</p>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            );
                        })()}
                        
                        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                            <button
                                onClick={() => {
                                    if (hasMetadataChanges() && !savingMetadata) {
                                        if (confirm("You have unsaved changes. Are you sure you want to close?")) {
                                            setShowEditMetadataModal(false);
                                            setEditingMetadataFilename(null);
                                            setEditingMetadata(null);
                                            setOriginalMetadata(null);
                                        }
                                    } else {
                                        setShowEditMetadataModal(false);
                                        setEditingMetadataFilename(null);
                                        setEditingMetadata(null);
                                        setOriginalMetadata(null);
                                    }
                                }}
                                disabled={savingMetadata}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSaveMetadata}
                                disabled={savingMetadata || !hasMetadataChanges()}
                                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                                {savingMetadata ? (
                                    <>
                                        <RefreshCw className="animate-spin" size={16} />
                                        Saving...
                                    </>
                                ) : (
                                    "Save"
                                )}
                            </button>
                        </div>
                    </div>
                </Modal>
            )}

            {/* Toast Notification */}
            {toast && (
                <div className={`fixed top-4 right-4 z-[100] px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 ${
                    toast.type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
                } animate-in fade-in slide-in-from-top-2 duration-300`}>
                    {toast.type === 'success' ? (
                        <CheckCircle size={20} />
                    ) : (
                        <AlertCircle size={20} />
                    )}
                    <span className="font-medium">{toast.message}</span>
                </div>
            )}

            <AlertModal
                isOpen={!!showAlert}
                onClose={() => setShowAlert(null)}
                title={showAlert?.title || ""}
                message={showAlert?.message || ""}
            />
        </div>
    )
}

function ChatView({ onOpenDocument }: { config: Config | null, documents: Record<string, DocumentData>, onOpenDocument: (filename: string) => void }) {
    const [messages, setMessages] = useState<{role: 'user'|'ai', content: string, sources?: string[]}[]>(() => {
        const saved = localStorage.getItem('nda_chat_history');
        return saved ? JSON.parse(saved) : [
            {role: 'ai', content: 'Hello! I can help you analyze your documents. I have access to all uploaded files.'}
        ];
    });
    // Keep a ref to the latest messages so event handlers can't accidentally use stale history
    // (e.g. user clears chat and immediately sends a message before React flushes state updates).
    const messagesRef = useRef(messages);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [inputKey, setInputKey] = useState(0); // Key to force remount of input
    const [showClearConfirm, setShowClearConfirm] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(scrollToBottom, [messages]);

    useEffect(() => {
        messagesRef.current = messages;
        localStorage.setItem('nda_chat_history', JSON.stringify(messages));
    }, [messages]);

    // Focus input after it's remounted (when inputKey changes)
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.focus();
        }
    }, [inputKey]);

    const confirmClear = () => setShowClearConfirm(true);

    const handleClear = () => {
        const cleared = [{role: 'ai' as const, content: 'Hello! I can help you analyze your documents. I have access to all uploaded files.'}];
        // Hard reset: wipe persisted history immediately and reset in-memory state.
        // This ensures the next request cannot accidentally include legacy context.
        try {
            localStorage.removeItem('nda_chat_history');
        } catch {
            // ignore storage failures (e.g. disabled storage)
        }
        messagesRef.current = cleared;
        setMessages(cleared);
        setInput(''); // Clear input state
        setLoading(false);
        setInputKey(prev => prev + 1); // Force remount of input to prevent lockup
        setShowClearConfirm(false);
    };

    const handleCancelClear = () => setShowClearConfirm(false);

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMsg = input;
        
        // Build conversation history for the API (exclude sources, map 'ai' to 'assistant')
        // Only include the last 10 message pairs to avoid token limits
        const historyForApi = messagesRef.current
            .filter(m => m.role === 'user' || m.role === 'ai')
            .slice(-20)  // Last 20 messages (10 pairs)
            .map(m => ({
                role: m.role === 'ai' ? 'assistant' : 'user',
                content: m.content
            }));
        
        setMessages(prev => [...prev, {role: 'user', content: userMsg}]);
        setInput('');
        setLoading(true);

        try {
            const res = await fetch(`http://localhost:${API_PORT}/chat`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    question: userMsg,
                    history: historyForApi  // Send conversation history
                })
            });
            const data = await res.json();
            setMessages(prev => [...prev, {
                role: 'ai',
                content: data.answer || "Sorry, I couldn't get an answer.",
                sources: data.sources
            }]);
        } catch (err) {
            setMessages(prev => [...prev, {role: 'ai', content: "Error communicating with server."}]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="h-[calc(100vh-4rem)] flex gap-6">
            <div className="flex-1 flex flex-col">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-2xl font-bold">Chat with Documents</h2>
                    <button 
                        onClick={confirmClear} 
                        className="text-gray-500 hover:text-red-600 p-2 rounded hover:bg-gray-100"
                        title="Clear Chat"
                    >
                        <Trash2 size={20} />
                    </button>
                </div>
                
                <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-100 mb-4 p-4 overflow-auto flex flex-col gap-4">
                    {messages.map((m, i) => (
                        <div key={i} className={`flex flex-col gap-1 ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                            <div className={`flex gap-3 max-w-[80%] ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                                    m.role === 'ai' ? 'bg-blue-100 text-blue-600' : 'bg-gray-200 text-gray-600'
                                }`}>
                                    {m.role === 'ai' ? 'AI' : 'Me'}
                                </div>
                                <div className={`rounded-lg p-3 text-sm overflow-hidden ${
                                    m.role === 'ai' ? 'bg-gray-100 prose prose-sm max-w-none' : 'bg-blue-600 text-white'
                                }`}>
                                    {m.role === 'ai' ? (
                                        <ReactMarkdown 
                                            remarkPlugins={[remarkGfm]}
                                            components={{
                                                table: ({node, ...props}) => <table className="border-collapse table-auto w-full my-2" {...props} />,
                                                th: ({node, ...props}) => <th className="border border-gray-300 px-2 py-1 bg-gray-200 font-semibold" {...props} />,
                                                td: ({node, ...props}) => <td className="border border-gray-300 px-2 py-1" {...props} />,
                                                ul: ({node, ...props}) => <ul className="list-disc pl-4 my-1" {...props} />,
                                                ol: ({node, ...props}) => <ol className="list-decimal pl-4 my-1" {...props} />,
                                                a: ({node, ...props}) => <a className="text-blue-600 hover:underline" {...props} />,
                                            }}
                                        >
                                            {m.content}
                                        </ReactMarkdown>
                                    ) : (
                                        <div className="whitespace-pre-wrap">{m.content}</div>
                                    )}
                                </div>
                            </div>
                            {m.sources && m.sources.length > 0 && (
                                <div className="text-xs text-gray-400 ml-11 flex gap-2 items-center flex-wrap">
                                    <span>Sources:</span>
                                    {m.sources.map(source => (
                                        <button 
                                            key={source}
                                            onClick={() => onOpenDocument(source)}
                                            className="text-blue-500 hover:underline bg-blue-50 px-2 py-0.5 rounded cursor-pointer"
                                        >
                                            {source}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                    {loading && <div className="text-sm text-gray-500 italic ml-11">AI is thinking...</div>}
                    <div ref={messagesEndRef} />
                </div>

                <div className="flex gap-2">
                    <input 
                        key={inputKey}
                        ref={inputRef}
                        type="text" 
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleSend()}
                        placeholder="Ask a question across all documents..." 
                        className="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button 
                        onClick={handleSend}
                        disabled={loading}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-6 rounded-lg font-medium disabled:opacity-50"
                    >
                        Send
                    </button>
                </div>

                {showClearConfirm && (
                    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50">
                        <div className="bg-white rounded-lg shadow-xl w-[360px] max-w-full p-5 border border-gray-200">
                            <h3 className="text-lg font-semibold text-gray-800 mb-2">Clear chat history?</h3>
                            <p className="text-sm text-gray-600 mb-4">This will remove all messages in this conversation.</p>
                            <div className="flex justify-end gap-3">
                                <button
                                    onClick={handleCancelClear}
                                    className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleClear}
                                    className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium"
                                >
                                    Clear
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

function TemplatesView() {
    const [templates, setTemplates] = useState<string[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState<{filename: string, type: 'document' | 'template'} | null>(null);

    useEffect(() => {
        fetchTemplates();
    }, []);

    const fetchTemplates = () => {
        fetch(`http://localhost:${API_PORT}/templates`)
            .then(res => res.json())
            .then(setTemplates)
            .catch(console.error);
    };

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        const file = e.target.files[0];
        const formData = new FormData();
        formData.append("file", file);
        
        try {
            await fetch(`http://localhost:${API_PORT}/upload_template`, {
                method: "POST",
                body: formData
            });
            fetchTemplates();
        } catch (err) {
            console.error(err);
        }
    };

    const handleDelete = async (filename: string) => {
        setShowDeleteConfirm({ filename, type: 'template' });
    };

    const confirmDeleteTemplate = async () => {
        const confirmData = showDeleteConfirm;
        if (!confirmData || confirmData.type !== 'template') return;
        setShowDeleteConfirm(null);
        try {
            await fetch(`http://localhost:${API_PORT}/templates/${confirmData.filename}`, { method: "DELETE" });
            fetchTemplates();
        } catch (err) {
            console.error(err);
        }
    };

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold flex justify-between items-center">
                <span>Templates</span>
                <button 
                    onClick={() => fileInputRef.current?.click()}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
                >
                    <Upload size={18} /> Upload Template
                </button>
                <input 
                    type="file" 
                    ref={fileInputRef} 
                    className="hidden" 
                    accept=".docx,.doc" 
                    onChange={handleUpload}
                />
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {templates.map(name => (
                    <div key={name} className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
                                <FileText size={24} />
                            </div>
                            <a 
                                href={`http://localhost:${API_PORT}/templates/${name}`} 
                                className="font-medium hover:text-blue-600 truncate max-w-[200px]"
                                target="_blank"
                                rel="noreferrer"
                            >
                                {name}
                            </a>
                        </div>
                        <button 
                            onClick={() => handleDelete(name)}
                            className="text-gray-400 hover:text-red-500"
                        >
                            <Trash2 size={18} />
                        </button>
                    </div>
                ))}
                {templates.length === 0 && (
                    <div className="col-span-full text-center py-12 text-gray-500 bg-white rounded-xl border border-dashed border-gray-300">
                        No templates found. Upload one to get started.
                    </div>
                )}
            </div>

            <ConfirmModal
                isOpen={!!showDeleteConfirm && showDeleteConfirm.type === 'template'}
                onConfirm={confirmDeleteTemplate}
                onCancel={() => setShowDeleteConfirm(null)}
                title="Delete Template?"
                message={`Are you sure you want to delete template ${showDeleteConfirm?.filename}?`}
                confirmText="Delete"
                cancelText="Cancel"
                confirmButtonClass="bg-red-600 hover:bg-red-700 text-white"
            />
        </div>
    );
}

function SettingsView() {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const pendingApiKeyRef = useRef<string>("");
    const [selectedFile, setSelectedFile] = useState("config.yaml");
    const [isSaving, setIsSaving] = useState(false);
    const [isEditorOpen, setIsEditorOpen] = useState(false);
    const [apiKey, setApiKey] = useState("");
    const [apiKeySet, setApiKeySet] = useState(false);
    const [apiKeyMasked, setApiKeyMasked] = useState("");
    const [savingApiKey, setSavingApiKey] = useState(false);
    const [showApiKey, setShowApiKey] = useState(false);
    const [showApiKeyOverwriteConfirm, setShowApiKeyOverwriteConfirm] = useState(false);
    const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);
    const [showAlert, setShowAlert] = useState<{title: string, message: string} | null>(null);
    const [fileContent, setFileContent] = useState("");
    const [storagePath, setStoragePath] = useState<string>("");
    const [openingStorage, setOpeningStorage] = useState(false);

    // Fetch API key status and storage path on component mount
    useEffect(() => {
        fetchApiKeyStatus();
        fetchStoragePath();
    }, []); // Run once on mount
    
    const fetchStoragePath = async () => {
        try {
            if (window.electronAPI?.getUserDataPath) {
                const p = await window.electronAPI.getUserDataPath();
                setStoragePath(p || "");
            } else {
                // Not running in Electron (e.g. browser dev mode)
                setStoragePath("");
            }
        } catch (err) {
            console.error("Failed to fetch storage path:", err);
            setStoragePath("");
        }
    };
    
    const handleOpenStorage = async () => {
        setOpeningStorage(true);
        try {
            if (!window.electronAPI?.openUserDataFolder) {
                setShowAlert({ title: "Not Available", message: "Opening the storage folder is only available in the desktop app." });
                return;
            }
            const result = await window.electronAPI.openUserDataFolder();
            if (result?.success) {
                setShowAlert({ title: "Opened", message: `Opened storage folder:\n${result.path}` });
            } else {
                setShowAlert({ title: "Error", message: result?.error || "Failed to open storage folder." });
            }
        } catch (err) {
            console.error("Failed to open storage:", err);
            setShowAlert({ title: "Error", message: "Failed to open storage directory. Please try again." });
        } finally {
            setOpeningStorage(false);
        }
    };
    
    const fetchApiKeyStatus = async () => {
        try {
            const res = await fetch(`http://localhost:${API_PORT}/config`);
            const data = await res.json();
            if (data.api) {
                setApiKeySet(data.api.openai_api_key_set || false);
                setApiKeyMasked(data.api.openai_api_key_masked || "");
            } else {
                // No api section in config
                setApiKeySet(false);
                setApiKeyMasked("");
            }
        } catch (err) {
            console.error("Failed to fetch API key status:", err);
            setApiKeySet(false);
            setApiKeyMasked("");
        }
    };

    useEffect(() => {
        if (isEditorOpen) {
            fetchFileContent(selectedFile);
        }
    }, [isEditorOpen, selectedFile]);

    const fetchFileContent = async (filename: string) => {
        try {
            const res = await fetch(`http://localhost:${API_PORT}/settings/file/${filename}`);
            const data = await res.json();
            setFileContent(data.content);
        } catch (err) {
            console.error(err);
            setFileContent("");
        }
    };

    const handleSaveFile = async () => {
        setIsSaving(true);
        const content = fileContent;
        
        try {
            const res = await fetch(`http://localhost:${API_PORT}/settings/file/${selectedFile}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content })
            });
            if (!res.ok) throw new Error();
            setShowAlert({ title: "Success", message: "File saved successfully!" });
            // Refresh API key status if config.yaml was saved
            if (selectedFile === "config.yaml") {
                fetchApiKeyStatus();
            }
        } catch (err) {
            console.error("Failed to save:", err);
            setShowAlert({ title: "Error", message: "Failed to save file. Please try again." });
        } finally {
            setIsSaving(false);
        }
    };

    const handleResetFile = async () => {
        try {
            const res = await fetch(`http://localhost:${API_PORT}/settings/reset/${selectedFile}`, {
                method: "POST"
            });
            const data = await res.json();
            setFileContent(data.content);
            setShowAlert({ title: "Success", message: "File reset to default values." });
        } catch (err) {
            console.error("Failed to reset:", err);
            setShowAlert({ title: "Error", message: "Failed to reset file. Please try again." });
        }
    };

    const handleRestoreLastGood = async () => {
        try {
            const res = await fetch(`http://localhost:${API_PORT}/settings/restore_last_good/${selectedFile}`, {
                method: "POST"
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            setFileContent(data.content);
            setShowAlert({ title: "Success", message: "File restored from last saved backup." });
        } catch (err) {
            console.error("No backup found:", err);
            setShowAlert({ title: "Error", message: "No backup found to restore." });
        }
    };

    const handleBackup = () => {
        window.open(`http://localhost:${API_PORT}/backup`, '_blank');
    };

    const handleSaveApiKey = async () => {
        if (!apiKey.trim()) {
            setShowAlert({ title: "Missing API Key", message: "Please enter an API key" });
            return;
        }
        
        // Warn if overwriting existing key
        if (apiKeySet) {
            pendingApiKeyRef.current = apiKey.trim();
            setShowApiKeyOverwriteConfirm(true);
            return;
        }
        
        await performSaveApiKey(apiKey.trim());
    };

    const performSaveApiKey = async (keyToSave: string) => {
        setSavingApiKey(true);
        try {
            // Get current config
            const res = await fetch(`http://localhost:${API_PORT}/settings/file/config.yaml`);
            const data = await res.json();
            let content = data.content;
            
            // Update API key in YAML content
            const lines = content.split('\n');
            let updated = false;
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].trim().startsWith('openai_api_key:')) {
                    lines[i] = `  openai_api_key: "${keyToSave}"`;
                    updated = true;
                    break;
                }
            }
            
            // If api section doesn't exist, add it at the top
            if (!updated) {
                const apiSection = `# API Configuration\napi:\n  openai_api_key: "${keyToSave}"\n\n`;
                content = apiSection + content;
            } else {
                content = lines.join('\n');
            }
            
            // Save updated config
            const saveRes = await fetch(`http://localhost:${API_PORT}/settings/file/config.yaml`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content })
            });
            
            if (!saveRes.ok) throw new Error("Failed to save");
            
            setShowAlert({ title: "Success", message: "API key saved successfully! The application will now use this key for OpenAI features." });
            setApiKey("");
            setShowApiKey(false);
            fetchApiKeyStatus();
        } catch (err) {
            console.error("Failed to save API key:", err);
            setShowAlert({ title: "Error", message: "Failed to save API key. Please try again." });
        } finally {
            setSavingApiKey(false);
        }
    };

    const confirmApiKeyOverwrite = () => {
        setShowApiKeyOverwriteConfirm(false);
        const keyToSave = pendingApiKeyRef.current;
        pendingApiKeyRef.current = "";
        if (keyToSave) {
            performSaveApiKey(keyToSave);
        }
    };
    
    const handleRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        setShowRestoreConfirm(true);
        // Store file reference for later use
        (handleRestore as any).pendingFile = e.target.files[0];
    };

    const confirmRestore = async () => {
        setShowRestoreConfirm(false);
        const file = (handleRestore as any).pendingFile;
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch(`http://localhost:${API_PORT}/restore`, {
                method: "POST",
                body: formData
            });
            const data = await res.json();
            setShowAlert({ title: "Restore Complete", message: data.message });
            setTimeout(() => {
                window.location.reload(); // Reload to refresh data
            }, 2000);
        } catch (err) {
            console.error(err);
            setShowAlert({ title: "Error", message: "Failed to restore backup." });
        }
    };

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold">Settings & Data Management</h2>
            
            {/* Storage Location Section */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                    <FolderOpen className="text-blue-600" /> Storage Location
                </h3>
                <div className="space-y-3">
                    <p className="text-sm text-gray-600">
                        All your documents, configuration files, and application data are stored in the following directory:
                    </p>
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                        <code className="text-sm text-gray-800 break-all">{storagePath || "Loading..."}</code>
                    </div>
                    <button
                        onClick={handleOpenStorage}
                        disabled={openingStorage || !storagePath}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <FolderOpen size={16} />
                        {openingStorage ? "Opening..." : "Open Storage Folder"}
                    </button>
                    <p className="text-xs text-gray-500">
                        Click the button above to open the storage directory in your system's file explorer.
                    </p>
                </div>
            </div>
            
            {/* API Key Section */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                    <Settings className="text-blue-600" /> OpenAI API Key
                </h3>
                
                {apiKeySet ? (
                    <>
                        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
                            <div className="flex items-start gap-3">
                                <Check className="text-green-600 mt-0.5" size={20} />
                                <div className="flex-1">
                                    <p className="text-green-800 font-medium mb-1">
                                        API key is configured and active
                                    </p>
                                    <p className="text-green-700 text-sm">
                                        Current key: <code className="bg-green-100 px-2 py-0.5 rounded">{apiKeyMasked}</code>
                                    </p>
                                    <p className="text-green-600 text-xs mt-2">
                                        Your API key is stored securely in your local config file. All OpenAI features are enabled.
                                    </p>
                                </div>
                            </div>
                        </div>
                        
                        <details className="mb-4">
                            <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900 select-none">
                                Change or update API key
                            </summary>
                            <div className="mt-3 space-y-3 pl-4 border-l-2 border-gray-200">
                                <p className="text-sm text-gray-600">
                                    Enter a new API key below to replace the current one.
                                </p>
                                <div className="flex gap-3">
                                    <input
                                        type={showApiKey ? "text" : "password"}
                                        value={apiKey}
                                        onChange={(e) => setApiKey(e.target.value)}
                                        placeholder="Enter new API key (sk-...)"
                                        className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <button
                                        onClick={() => setShowApiKey(!showApiKey)}
                                        className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                                        title={showApiKey ? "Hide API key" : "Show API key"}
                                    >
                                        <Eye size={18} />
                                    </button>
                                    <button
                                        onClick={handleSaveApiKey}
                                        disabled={savingApiKey || !apiKey.trim()}
                                        className="bg-orange-600 hover:bg-orange-700 text-white px-6 py-2 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {savingApiKey ? "Updating..." : "Update Key"}
                                    </button>
                                </div>
                            </div>
                        </details>
                    </>
                ) : (
                    <>
                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
                            <div className="flex items-start gap-3">
                                <AlertCircle className="text-yellow-600 mt-0.5" size={20} />
                                <div>
                                    <p className="text-yellow-800 font-medium mb-1">
                                        No API key configured
                                    </p>
                                    <p className="text-yellow-700 text-sm">
                                        Add your OpenAI API key to enable document processing and chat features.
                                    </p>
                                </div>
                            </div>
                        </div>
                        
                        <p className="text-gray-600 mb-4 text-sm">
                            Enter your OpenAI API key below. It will be stored securely in your local configuration file.
                        </p>
                        
                        <div className="space-y-3">
                            <div className="flex gap-3">
                                <input
                                    type={showApiKey ? "text" : "password"}
                                    value={apiKey}
                                    onChange={(e) => setApiKey(e.target.value)}
                                    placeholder="sk-..."
                                    className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                                <button
                                    onClick={() => setShowApiKey(!showApiKey)}
                                    className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                                    title={showApiKey ? "Hide API key" : "Show API key"}
                                >
                                    <Eye size={18} />
                                </button>
                                <button
                                    onClick={handleSaveApiKey}
                                    disabled={savingApiKey || !apiKey.trim()}
                                    className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {savingApiKey ? "Saving..." : "Save API Key"}
                                </button>
                            </div>
                            <p className="text-xs text-gray-500">
                                Get your API key from <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">OpenAI Platform</a>. 
                                Your key is stored securely in your local configuration file.
                            </p>
                        </div>
                    </>
                )}
            </div>
            
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 mb-6 overflow-hidden">
                <button 
                    onClick={() => setIsEditorOpen(!isEditorOpen)}
                    className="w-full p-6 flex items-center justify-between hover:bg-gray-50 transition-colors"
                >
                    <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                        <Settings className="text-gray-600" /> Configuration Editor
                    </h3>
                    {isEditorOpen ? <ChevronDown size={20} className="text-gray-400" /> : <ChevronRight size={20} className="text-gray-400" />}
                </button>
                
                {isEditorOpen && (
                    <div className="p-6 pt-0 border-t border-gray-100">
                        <div className="flex gap-4 mb-4 mt-4">
                            <select 
                                value={selectedFile}
                                onChange={(e) => setSelectedFile(e.target.value)}
                                className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
                            >
                                <option value="config.yaml">config.yaml (App Settings)</option>
                                <option value="prompts.yaml">prompts.yaml (AI Prompts)</option>
                            </select>
                            <button 
                                onClick={handleSaveFile}
                                disabled={isSaving}
                                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 min-w-[120px]"
                            >
                                {isSaving ? "Saving..." : "Save Changes"}
                            </button>
                            <button 
                                onClick={handleRestoreLastGood}
                                className="text-orange-600 hover:bg-orange-50 px-4 py-2 rounded-lg text-sm font-medium"
                                title="Undo recent changes"
                            >
                                Undo / Restore Last Saved
                            </button>
                            <button 
                                onClick={handleResetFile}
                                className="text-red-600 hover:bg-red-50 px-4 py-2 rounded-lg text-sm font-medium ml-auto"
                            >
                                Reset to Default
                            </button>
                        </div>
                        <textarea
                            ref={textareaRef}
                            value={fileContent}
                            onChange={(e) => setFileContent(e.target.value)}
                            className="w-full h-96 font-mono text-sm p-4 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white caret-black resize-y"
                            spellCheck={false}
                        />
                    </div>
                )}
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                    <Database className="text-blue-600" /> Data Backup
                </h3>
                <p className="text-gray-600 mb-6">
                    Export your entire system state (documents, database, metadata) to a ZIP file. 
                    You can use this file to migrate to another computer or restore your data later.
                </p>
                
                <div className="flex gap-4">
                    <button 
                        onClick={handleBackup}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium flex items-center gap-2"
                    >
                        <Download size={18} /> Download Backup
                    </button>
                    
                    <button 
                        onClick={() => fileInputRef.current?.click()}
                        className="bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 px-6 py-3 rounded-lg font-medium flex items-center gap-2"
                    >
                        <Upload size={18} /> Restore from Backup
                    </button>
                    <input 
                        type="file" 
                        ref={fileInputRef} 
                        className="hidden" 
                        accept=".zip" 
                        onChange={handleRestore}
                    />
                </div>
            </div>

            <div className="bg-yellow-50 p-6 rounded-xl border border-yellow-200">
                <h3 className="text-sm font-bold text-yellow-800 mb-2 flex items-center gap-2">
                    <AlertCircle size={16} /> Important Note
                </h3>
                <p className="text-sm text-yellow-700">
                    Restoring a backup will <strong>permanently delete</strong> all current documents and settings. 
                    Please ensure you have backed up your current data before restoring.
                </p>
            </div>

            <ConfirmModal
                isOpen={showApiKeyOverwriteConfirm}
                onConfirm={confirmApiKeyOverwrite}
                onCancel={() => {
                    setShowApiKeyOverwriteConfirm(false);
                    pendingApiKeyRef.current = "";
                }}
                title="Replace API Key?"
                message={`You already have an API key configured (${apiKeyMasked}).\n\nDo you want to replace it with the new key?`}
                confirmText="Replace"
                cancelText="Keep Existing"
                confirmButtonClass="bg-orange-600 hover:bg-orange-700 text-white"
            />

            <ConfirmModal
                isOpen={showRestoreConfirm}
                onConfirm={confirmRestore}
                onCancel={() => setShowRestoreConfirm(false)}
                title="Restore Backup?"
                message="WARNING: This will overwrite all current data with the backup. Continue?"
                confirmText="Yes, Restore"
                cancelText="Cancel"
                confirmButtonClass="bg-red-600 hover:bg-red-700 text-white"
            />

            <AlertModal
                isOpen={!!showAlert}
                onClose={() => setShowAlert(null)}
                title={showAlert?.title || ""}
                message={showAlert?.message || ""}
            />
        </div>
    );
}

export default App;
