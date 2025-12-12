import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, MessageSquare, LayoutDashboard, Settings, Check, AlertCircle, X, Search, Eye, RefreshCw, Archive, Trash2, File, Download, Database, ChevronDown, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Modal } from './components/Modal';

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
  competency_answers: Record<string, any>;
}

import { LoadingScreen } from './components/LoadingScreen';

declare global {
  interface Window {
    electronAPI?: {
      handleStartupStatus: (callback: (status: string) => void) => void;
      handlePythonReady: (callback: () => void) => void;
      handlePythonError: (callback: (error: string) => void) => void;
    };
  }
}

const APP_TITLE = import.meta.env.VITE_APP_TITLE || "DocuSenseLM";
const APP_VERSION = "1.0.13";

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
        alert(`Startup failed: ${error}`);
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
      .then(res => res.json())
      .then(setConfig)
      .catch(console.error);
  };

  const fetchDocuments = () => {
    fetch(`http://localhost:${API_PORT}/documents`)
      .then(res => res.json())
      .then(setDocuments)
      .catch(console.error);
  };

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

function DashboardView({ config, documents, onOpenDocument }: { config: Config | null, documents: Record<string, DocumentData>, onOpenDocument: (filename: string) => void }) {
  const [report, setReport] = useState<string | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);

  if (!config) return <div>Loading configuration...</div>;
  
  const handleGenerateReport = async () => {
      setGeneratingReport(true);
      try {
          const res = await fetch(`http://localhost:${API_PORT}/report`, { method: "POST" });
          const data = await res.json();
          setReport(data.report);
      } catch (e) {
          console.error(e);
          alert("Failed to generate report");
      } finally {
          setGeneratingReport(false);
      }
  };
  
  const docList = Object.values(documents);

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
        <button 
            onClick={handleGenerateReport}
            disabled={generatingReport}
            className="bg-gray-800 hover:bg-gray-900 text-white px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium disabled:opacity-50"
        >
            {generatingReport ? <RefreshCw className="animate-spin" size={16} /> : <FileText size={16} />}
            Generate Status Report
        </button>
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
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {Object.entries(config.document_types).map(([key, type]: [string, any]) => {
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
    </div>
  );
}

function DocumentsView({ config, documents, refresh, initialPreview, onClearPreview }: { config: Config | null, documents: Record<string, DocumentData>, refresh: () => void, initialPreview: string | null, onClearPreview?: () => void }) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [previewDoc, setPreviewDoc] = useState<string | null>(initialPreview);
    const [reprocessing, setReprocessing] = useState(false);
    const [searchTerm, setSearchTerm] = useState(initialPreview || ""); // Default search to preview doc if set
    const [showArchived, setShowArchived] = useState(false);
    const [editingType, setEditingType] = useState<string | null>(null);
    const [filterDocType, setFilterDocType] = useState<string>(""); // Filter by document type
    
    // Upload modal state
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [pendingFiles, setPendingFiles] = useState<File[]>([]);
    const [selectedType, setSelectedType] = useState<string>("");
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState<Record<string, 'uploading' | 'uploaded' | 'processing' | 'error'>>({});
    const isUploadingRef = useRef(false);

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
            alert('Please select PDF or DOCX files only.');
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
                alert('Please select a document type.');
            }
            return;
        }

        isUploadingRef.current = true;
        setUploading(true);
        const progress: Record<string, 'uploading' | 'uploaded' | 'processing' | 'error'> = {};
        const filesToUpload = [...pendingFiles]; // Store copy in case state changes
        filesToUpload.forEach(file => {
            progress[file.name] = 'uploading';
        });
        setUploadProgress(progress);
        
        let uploadCompleted = false;
        const timeoutId = setTimeout(() => {
            if (!uploadCompleted) {
                console.warn('Upload timeout - closing modal');
                cleanupUpload();
            }
        }, 30000); // 30 second timeout
        
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
            
            uploadCompleted = true;
            clearTimeout(timeoutId);
            
            // Refresh to get updated document list
            refresh();
            
            // Wait a moment then close modal and show success
            await new Promise(resolve => setTimeout(resolve, 1500));
        } catch (err) {
            console.error('Upload error:', err);
            uploadCompleted = true;
            clearTimeout(timeoutId);
        } finally {
            cleanupUpload();
        }
    };

    const cleanupUpload = () => {
        // Clear state in a way that doesn't conflict with React's rendering
        setUploadProgress({});
        setSelectedType("");
        setPendingFiles([]);
        setUploading(false);
        isUploadingRef.current = false;
        // Close modal after state is cleared
        setShowUploadModal(false);
        // Refresh again to show final status after a brief delay
        setTimeout(() => refresh(), 500);
    };

    const cancelUpload = () => {
        if (uploading && !confirm('Upload is in progress. Are you sure you want to cancel? Files already uploaded will remain.')) {
            return;
        }
        // Allow cancel even during upload (user can force close)
        cleanupUpload();
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const handleReprocess = async (filename: string) => {
        if (!confirm(`Are you sure you want to re-process ${filename}? This will re-index it and run competency questions again.`)) return;

        setReprocessing(true);
        try {
            const response = await fetch(`http://localhost:${API_PORT}/reprocess/${filename}`, {
                method: "POST"
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            // Wait a moment to ensure the backend has started processing
            setTimeout(() => {
                refresh();
                setReprocessing(false);
            }, 1000);
        } catch (err) {
            console.error(err);
            alert("Failed to start reprocessing");
            setReprocessing(false);
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
        if (!confirm(`Are you sure you want to permanently delete ${filename}?`)) return;
        try {
            await fetch(`http://localhost:${API_PORT}/documents/${filename}`, { method: "DELETE" });
            refresh();
            if (previewDoc === filename) setPreviewDoc(null);
        } catch (err) {
            console.error(err);
        }
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
                                            disabled={reprocessing}
                                            title="Reprocess & Re-index"
                                        >
                                            <RefreshCw size={18} className={reprocessing ? "animate-spin" : ""} />
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
                            <h4 className="font-bold text-gray-700 mb-2">Extracted Data</h4>
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
                    if (confirm('Upload is in progress. Close anyway? Files already uploaded will remain.')) {
                        cleanupUpload();
                    }
                } : cancelUpload}
                title={uploading ? "Uploading Documents" : "Select Document Type"}
                hideCloseButton={false}
            >
                <div className="space-y-6">
                    {!uploading ? (
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
                                    <RefreshCw className="animate-spin text-blue-600" size={20} />
                                    <p className="text-sm font-medium text-gray-700">
                                        Uploading and processing documents...
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
                                        if (confirm('Close upload dialog? Files already uploaded will continue processing.')) {
                                            cleanupUpload();
                                        }
                                    }}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                                >
                                    Close Dialog
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </Modal>
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
        setMessages([{role: 'ai', content: 'Hello! I can help you analyze your documents. I have access to all uploaded files.'}]);
        setInput(''); // Clear input state
        setInputKey(prev => prev + 1); // Force remount of input to prevent lockup
        setShowClearConfirm(false);
    };

    const handleCancelClear = () => setShowClearConfirm(false);

    const handleSend = async () => {
        if (!input.trim()) return;
        
        const userMsg = input;
        setMessages(prev => [...prev, {role: 'user', content: userMsg}]);
        setInput('');
        setLoading(true);

        try {
            const res = await fetch(`http://localhost:${API_PORT}/chat`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    question: userMsg
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
        if (!confirm(`Delete template ${filename}?`)) return;
        try {
            await fetch(`http://localhost:${API_PORT}/templates/${filename}`, { method: "DELETE" });
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
        </div>
    );
}

function SettingsView() {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [selectedFile, setSelectedFile] = useState("config.yaml");
    const [isSaving, setIsSaving] = useState(false);
    const [isEditorOpen, setIsEditorOpen] = useState(false);
    const [apiKey, setApiKey] = useState("");
    const [apiKeySet, setApiKeySet] = useState(false);
    const [apiKeyMasked, setApiKeyMasked] = useState("");
    const [savingApiKey, setSavingApiKey] = useState(false);
    const [showApiKey, setShowApiKey] = useState(false);

    // Fetch API key status on component mount and when selectedFile changes
    useEffect(() => {
        fetchFileContent(selectedFile);
    }, [selectedFile]);
    
    useEffect(() => {
        fetchApiKeyStatus();
    }, []); // Run once on mount
    
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
        if (isEditorOpen && textareaRef.current) {
            fetchFileContent(selectedFile);
        }
    }, [isEditorOpen]);

    const fetchFileContent = async (filename: string) => {
        try {
            const res = await fetch(`http://localhost:${API_PORT}/settings/file/${filename}`);
            const data = await res.json();
            if (textareaRef.current) {
                textareaRef.current.value = data.content;
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleSaveFile = async () => {
        if (!textareaRef.current) return;
        
        setIsSaving(true);
        const content = textareaRef.current.value;
        
        try {
            const res = await fetch(`http://localhost:${API_PORT}/settings/file/${selectedFile}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content })
            });
            if (!res.ok) throw new Error();
            // Success
        } catch (err) {
            console.error("Failed to save:", err);
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
            if (textareaRef.current) {
                textareaRef.current.value = data.content;
            }
        } catch (err) {
            console.error("Failed to reset:", err);
        }
    };

    const handleRestoreLastGood = async () => {
        try {
            const res = await fetch(`http://localhost:${API_PORT}/settings/restore_last_good/${selectedFile}`, {
                method: "POST"
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            if (textareaRef.current) {
                textareaRef.current.value = data.content;
            }
        } catch (err) {
            console.error("No backup found:", err);
        }
    };

    const handleBackup = () => {
        window.open(`http://localhost:${API_PORT}/backup`, '_blank');
    };

    const handleSaveApiKey = async () => {
        if (!apiKey.trim()) {
            alert("Please enter an API key");
            return;
        }
        
        // Warn if overwriting existing key
        if (apiKeySet) {
            const confirmOverwrite = confirm(
                `You already have an API key configured (${apiKeyMasked}).\n\n` +
                "Do you want to replace it with the new key?\n\n" +
                "Click OK to replace, or Cancel to keep the existing key."
            );
            if (!confirmOverwrite) {
                setApiKey("");
                return;
            }
        }
        
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
                    lines[i] = `  openai_api_key: "${apiKey.trim()}"`;
                    updated = true;
                    break;
                }
            }
            
            // If api section doesn't exist, add it at the top
            if (!updated) {
                const apiSection = `# API Configuration\napi:\n  openai_api_key: "${apiKey.trim()}"\n\n`;
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
            
            alert("API key saved successfully! The application will now use this key for OpenAI features.");
            setApiKey("");
            setShowApiKey(false);
            fetchApiKeyStatus();
        } catch (err) {
            console.error("Failed to save API key:", err);
            alert("Failed to save API key. Please try again.");
        } finally {
            setSavingApiKey(false);
        }
    };
    
    const handleRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        if (!confirm("WARNING: This will overwrite all current data with the backup. Continue?")) return;

        const file = e.target.files[0];
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch(`http://localhost:${API_PORT}/restore`, {
                method: "POST",
                body: formData
            });
            const data = await res.json();
            alert(data.message);
            window.location.reload(); // Reload to refresh data
        } catch (err) {
            console.error(err);
            alert("Failed to restore backup.");
        }
    };

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold">Settings & Data Management</h2>
            
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
                            defaultValue=""
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
        </div>
    );
}

export default App;
