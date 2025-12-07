import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, MessageSquare, LayoutDashboard, Settings, Check, AlertCircle, X, Search } from 'lucide-react';

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
  competency_answers: Record<string, any>;
}

function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'documents' | 'chat'>('dashboard');
  const [config, setConfig] = useState<Config | null>(null);
  const [documents, setDocuments] = useState<Record<string, DocumentData>>({});

  useEffect(() => {
    fetchConfig();
    fetchDocuments();
    const interval = setInterval(fetchDocuments, 5000); // Poll for updates
    return () => clearInterval(interval);
  }, []);

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
        </nav>
        
        <div className="mt-auto pt-4 border-t border-slate-700">
           <div className="flex items-center gap-2 text-slate-400 text-sm">
             <div className="w-2 h-2 rounded-full bg-green-500"></div>
             System Ready
           </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto p-8">
        {activeTab === 'dashboard' && <DashboardView config={config} documents={documents} />}
        {activeTab === 'documents' && <DocumentsView config={config} documents={documents} refresh={fetchDocuments} />}
        {activeTab === 'chat' && <ChatView config={config} documents={documents} />}
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
    // Basic logic: parse expiration date from competency answers and compare
    // This is naive and depends on LLM format "YYYY-MM-DD"
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
          
          return (
          <div key={key} className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h3 className="text-lg font-semibold text-gray-700">{type.name}s</h3>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-4xl font-bold text-blue-600">{count}</span>
              <span className="text-gray-500">total</span>
            </div>
             <div className="mt-2 text-sm text-red-500">{expiring} expiring in 90 days</div>
          </div>
        )})}
      </div>
      
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <h3 className="text-lg font-semibold mb-4">Recent Documents</h3>
        <ul className="divide-y divide-gray-100">
            {docList.slice(0, 5).map(doc => (
                <li key={doc.filename} className="py-3 flex justify-between">
                    <span>{doc.filename}</span>
                    <span className="text-gray-500 text-sm">{doc.status}</span>
                </li>
            ))}
            {docList.length === 0 && <li className="text-gray-500 italic">No documents yet.</li>}
        </ul>
      </div>
    </div>
  );
}

function DocumentsView({ config, documents, refresh }: { config: Config | null, documents: Record<string, DocumentData>, refresh: () => void }) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedType, setSelectedType] = useState("nda");

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

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold flex justify-between items-center">
                <span>Documents</span>
                <div className="flex gap-2">
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

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-gray-50 border-b border-gray-100">
                        <tr>
                            <th className="p-4 font-semibold text-gray-600">Document Name</th>
                            <th className="p-4 font-semibold text-gray-600">Type</th>
                            <th className="p-4 font-semibold text-gray-600">Status</th>
                            <th className="p-4 font-semibold text-gray-600">Key Info (Competency)</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {Object.values(documents).map(doc => (
                            <tr key={doc.filename} className="hover:bg-gray-50">
                                <td className="p-4">{doc.filename}</td>
                                <td className="p-4 capitalize">{doc.doc_type.replace('_', ' ')}</td>
                                <td className="p-4">
                                    <span className={`px-2 py-1 rounded-full text-xs ${
                                        doc.status === 'processed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                                    }`}>
                                        {doc.status}
                                    </span>
                                </td>
                                <td className="p-4 text-sm text-gray-600">
                                    {doc.status === 'processed' ? (
                                        <ul className="list-disc pl-4 space-y-1">
                                            {Object.entries(doc.competency_answers || {}).slice(0, 3).map(([k, v]) => (
                                                <li key={k} title={String(v)} className="truncate max-w-xs">
                                                    <span className="font-medium">{k}:</span> {String(v)}
                                                </li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <span className="italic">Analyzing...</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                        {Object.keys(documents).length === 0 && (
                            <tr>
                                <td className="p-8 text-center text-gray-500" colSpan={4}>
                                    No documents found.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

function ChatView({ config, documents }: { config: Config | null, documents: Record<string, DocumentData> }) {
    const [messages, setMessages] = useState<{role: 'user'|'ai', content: string}[]>([
        {role: 'ai', content: 'Hello! I can help you analyze your documents. Select documents below to include them in context.'}
    ]);
    const [input, setInput] = useState('');
    const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
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
                    question: userMsg,
                    context_files: selectedDocs
                })
            });
            const data = await res.json();
            setMessages(prev => [...prev, {role: 'ai', content: data.answer || "Sorry, I couldn't get an answer."}]);
        } catch (err) {
            setMessages(prev => [...prev, {role: 'ai', content: "Error communicating with server."}]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="h-[calc(100vh-4rem)] flex gap-6">
            <div className="flex-1 flex flex-col">
                <h2 className="text-2xl font-bold mb-4">Chat</h2>
                
                <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-100 mb-4 p-4 overflow-auto flex flex-col gap-4">
                    {messages.map((m, i) => (
                        <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                                m.role === 'ai' ? 'bg-blue-100 text-blue-600' : 'bg-gray-200 text-gray-600'
                            }`}>
                                {m.role === 'ai' ? 'AI' : 'Me'}
                            </div>
                            <div className={`rounded-lg p-3 max-w-[80%] text-sm whitespace-pre-wrap ${
                                m.role === 'ai' ? 'bg-gray-100' : 'bg-blue-600 text-white'
                            }`}>
                                {m.content}
                            </div>
                        </div>
                    ))}
                    {loading && <div className="text-sm text-gray-500 italic">AI is thinking...</div>}
                    <div ref={messagesEndRef} />
                </div>

                <div className="flex gap-2">
                    <input 
                        type="text" 
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleSend()}
                        placeholder="Ask a question..." 
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

            {/* Document Context Selector */}
            <div className="w-72 bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex flex-col">
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                    <Search size={16} /> Context
                </h3>
                <div className="flex-1 overflow-auto space-y-2">
                    {Object.values(documents).map(doc => (
                        <label key={doc.filename} className="flex items-start gap-2 text-sm p-2 hover:bg-gray-50 rounded cursor-pointer">
                            <input 
                                type="checkbox" 
                                checked={selectedDocs.includes(doc.filename)}
                                onChange={e => {
                                    if (e.target.checked) setSelectedDocs(prev => [...prev, doc.filename]);
                                    else setSelectedDocs(prev => prev.filter(f => f !== doc.filename));
                                }}
                                className="mt-1"
                            />
                            <div className="break-all">
                                <div className="font-medium">{doc.filename}</div>
                                <div className="text-xs text-gray-500">{doc.doc_type}</div>
                            </div>
                        </label>
                    ))}
                    {Object.keys(documents).length === 0 && <div className="text-gray-500 text-sm italic">No documents available.</div>}
                </div>
            </div>
        </div>
    )
}

export default App;
