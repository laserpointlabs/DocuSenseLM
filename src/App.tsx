import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, MessageSquare, LayoutDashboard, Settings, Check, AlertCircle, X, Search, Eye, RefreshCw, Archive, Trash2, File } from 'lucide-react';

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

function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'documents' | 'chat' | 'templates'>('dashboard');
  const [config, setConfig] = useState<Config | null>(null);
  const [documents, setDocuments] = useState<Record<string, DocumentData>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [docToOpen, setDocToOpen] = useState<string | null>(null);

  useEffect(() => {
    const initApp = async () => {
      let retries = 0;
      while (retries < 20) {
        try {
          const res = await fetch(`http://localhost:${API_PORT}/health`);
          if (res.ok) {
            fetchConfig();
            fetchDocuments();
            setIsLoading(false);
            return;
          }
        } catch (e) {
          // Ignore error, retry
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
        retries++;
      }
      alert("Failed to connect to backend service. Please restart the application.");
    };

    initApp();

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
        <h1 className="text-xl font-bold mb-8 flex items-center gap-2">
          <FileText className="text-blue-400" /> NDA Tool Lite
        </h1>
        
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
        {activeTab === 'dashboard' && <DashboardView config={config} documents={documents} />}
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

function DashboardView({ config, documents }: { config: Config | null, documents: Record<string, DocumentData> }) {
  if (!config) return <div>Loading configuration...</div>;
  
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

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Dashboard</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {Object.entries(config.document_types).map(([key, type]: [string, any]) => {
          const count = docList.filter(d => d.doc_type === key).length;
          const expiring = getExpiringCount(key, 90);
          const reviewCount = docList.filter(d => d.doc_type === key && (d.workflow_status === 'in_review' || !d.workflow_status)).length;
          
          return (
          <div key={key} className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h3 className="text-lg font-semibold text-gray-700">{type.name}s</h3>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-4xl font-bold text-blue-600">{count}</span>
              <span className="text-gray-500">total</span>
            </div>
             <div className="mt-2 text-sm space-y-1">
                <div className="text-red-500 font-medium">{expiring} expiring in 90 days</div>
                <div className="text-blue-500">{reviewCount} in review</div>
             </div>
          </div>
        )})}
      </div>
    </div>
  );
}

function DocumentsView({ config, documents, refresh, initialPreview, onClearPreview }: { config: Config | null, documents: Record<string, DocumentData>, refresh: () => void, initialPreview: string | null, onClearPreview?: () => void }) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedType, setSelectedType] = useState("nda");
    const [previewDoc, setPreviewDoc] = useState<string | null>(initialPreview);
    const [reprocessing, setReprocessing] = useState(false);
    const [searchTerm, setSearchTerm] = useState(initialPreview || ""); // Default search to preview doc if set
    const [showArchived, setShowArchived] = useState(false);

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

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        const file = e.target.files[0];
        const formData = new FormData();
        formData.append("file", file);
        
        try {
            await fetch(`http://localhost:${API_PORT}/upload?doc_type=${selectedType}`, {
                method: "POST",
                body: formData
            });
            refresh();
        } catch (err) {
            console.error(err);
        }
    };

    const handleReprocess = async (filename: string) => {
        if (!confirm(`Are you sure you want to re-process ${filename}? This will re-index it and run competency questions again.`)) return;
        
        setReprocessing(true);
        try {
            await fetch(`http://localhost:${API_PORT}/reprocess/${filename}`, {
                method: "POST"
            });
            refresh();
        } catch (err) {
            console.error(err);
            alert("Failed to start reprocessing");
        } finally {
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

    const filteredDocs = Object.values(documents).filter(doc => {
        const matchesSearch = doc.filename.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesArchive = showArchived ? doc.archived : !doc.archived;
        return matchesSearch && matchesArchive;
    });

    return (
        <div className="space-y-6 h-full flex flex-col">
            <h2 className="text-2xl font-bold flex justify-between items-center">
                <span>Documents</span>
                <div className="flex gap-2">
                    <div className="relative">
                        <Search className="absolute left-3 top-2.5 text-gray-400" size={16} />
                        <input 
                            type="text" 
                            placeholder="Search..." 
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>
                    <button 
                        onClick={() => setShowArchived(!showArchived)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium border ${
                            showArchived ? 'bg-gray-800 text-white border-gray-800' : 'bg-white text-gray-600 border-gray-300'
                        }`}
                    >
                        {showArchived ? 'Show Active' : 'Show Archived'}
                    </button>
                    <select 
                        value={selectedType} 
                        onChange={e => setSelectedType(e.target.value)}
                        className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    >
                        {config && Object.keys(config.document_types).map(key => (
                            <option key={key} value={key}>{config.document_types[key].name}</option>
                        ))}
                    </select>
                    <button 
                        onClick={() => fileInputRef.current?.click()}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
                    >
                        <Upload size={18} /> Upload New
                    </button>
                    <input 
                        type="file" 
                        ref={fileInputRef} 
                        className="hidden" 
                        accept=".pdf,.docx" 
                        onChange={handleUpload}
                    />
                </div>
            </h2>

            <div className="flex-1 flex gap-6 min-h-0">
                {/* Document List */}
                <div className={`bg-white rounded-xl shadow-sm border border-gray-100 overflow-auto flex-1 ${previewDoc ? 'w-1/2' : 'w-full'}`}>
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
                                    <td className="p-4 capitalize text-sm">{doc.doc_type.replace('_', ' ')}</td>
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
        </div>
    )
}

function ChatView({ config, documents, onOpenDocument }: { config: Config | null, documents: Record<string, DocumentData>, onOpenDocument: (filename: string) => void }) {
    const [messages, setMessages] = useState<{role: 'user'|'ai', content: string, sources?: string[]}[]>([
        {role: 'ai', content: 'Hello! I can help you analyze your documents. I have access to all uploaded files.'}
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(scrollToBottom, [messages]);

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
                <h2 className="text-2xl font-bold mb-4">Chat with Documents</h2>
                
                <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-100 mb-4 p-4 overflow-auto flex flex-col gap-4">
                    {messages.map((m, i) => (
                        <div key={i} className={`flex flex-col gap-1 ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                            <div className={`flex gap-3 max-w-[80%] ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                                    m.role === 'ai' ? 'bg-blue-100 text-blue-600' : 'bg-gray-200 text-gray-600'
                                }`}>
                                    {m.role === 'ai' ? 'AI' : 'Me'}
                                </div>
                                <div className={`rounded-lg p-3 text-sm whitespace-pre-wrap ${
                                    m.role === 'ai' ? 'bg-gray-100' : 'bg-blue-600 text-white'
                                }`}>
                                    {m.content}
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

export default App;
