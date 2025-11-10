'use client';

import { useState } from 'react';

interface Feature {
  id: string;
  title: string;
  description: string;
  category: 'automation' | 'ai' | 'integration' | 'access' | 'process';
  priority: 'high' | 'medium' | 'low';
  icon: string;
}

const features: Feature[] = [
  {
    id: 'customer-template-link',
    title: 'Customer NDA Template Portal',
    description: 'External link for potential customers to fetch and download the standard NDA template. Includes version control and automatic updates when templates change.',
    category: 'access',
    priority: 'high',
    icon: '🔗',
  },
  {
    id: 'bpmn-workflow',
    title: 'Automated BPMN Workflow Processing',
    description: 'Automated business process workflow to process new NDAs when customers submit them. Includes automated routing, validation, and status tracking through the approval pipeline.',
    category: 'automation',
    priority: 'high',
    icon: '⚙️',
  },
  {
    id: 'notification-workflows',
    title: 'Email & Slack Notification Workflows',
    description: 'Automated email and Slack integrations for signature requests, expiration warnings, renewal reminders, and status updates. Configurable notification schedules and escalation chains.',
    category: 'automation',
    priority: 'high',
    icon: '📧',
  },
  {
    id: 'multi-nda-analysis',
    title: 'Advanced Multi-NDA AI Analysis',
    description: 'AI-powered analysis across the entire NDA pool to identify patterns, inconsistencies, risk factors, and optimization opportunities. Includes comparative analysis, trend identification, and compliance scoring.',
    category: 'ai',
    priority: 'high',
    icon: '🤖',
  },
  {
    id: 'engineering-api',
    title: 'Engineering API Access',
    description: 'General API access for engineering teams to verify NDA existence and active status programmatically. Includes RESTful endpoints for integration with internal systems and automated checks.',
    category: 'access',
    priority: 'high',
    icon: '🔌',
  },
  {
    id: 'compliance-checking',
    title: 'Automated Compliance Checking',
    description: 'AI-powered compliance verification against company policies and legal standards. Automatically flags non-standard clauses, missing required terms, and policy violations.',
    category: 'ai',
    priority: 'medium',
    icon: '✅',
  },
  {
    id: 'contract-comparison',
    title: 'Contract Comparison Tool',
    description: 'Side-by-side comparison of multiple NDAs to identify differences, similarities, and variations. Highlights key terms, clause differences, and negotiation points.',
    category: 'ai',
    priority: 'medium',
    icon: '📊',
  },
  {
    id: 'risk-assessment',
    title: 'Automated Risk Assessment Scoring',
    description: 'AI-driven risk scoring for each NDA based on terms, expiration status, compliance factors, and historical data. Provides actionable insights and prioritization recommendations.',
    category: 'ai',
    priority: 'medium',
    icon: '⚠️',
  },
  {
    id: 'crm-integration',
    title: 'CRM System Integration',
    description: 'Integration with CRM platforms (Salesforce, HubSpot, etc.) to automatically sync NDA status, expiration dates, and customer information. Bidirectional data flow for seamless workflow.',
    category: 'integration',
    priority: 'medium',
    icon: '🔗',
  },
  {
    id: 'jd-edwards-integration',
    title: 'JD Edwards ERP Integration',
    description: 'Integration with JD Edwards ERP system to synchronize NDA data, customer information, and contract status. Automatically update vendor/customer records, track NDA compliance in procurement workflows, and ensure data consistency across systems.',
    category: 'integration',
    priority: 'high',
    icon: '🏢',
  },
  {
    id: 'bulk-operations',
    title: 'Bulk Operations & Batch Processing',
    description: 'Perform bulk operations across multiple NDAs: bulk renewal reminders, bulk analysis reports, bulk status updates, and batch metadata corrections.',
    category: 'process',
    priority: 'medium',
    icon: '📦',
  },
  {
    id: 'version-control',
    title: 'Version Control & Change Tracking',
    description: 'Track document versions, amendments, and modifications over time. Maintain audit trail of changes, approvals, and document history with full version comparison.',
    category: 'process',
    priority: 'medium',
    icon: '📝',
  },
  {
    id: 'clause-extraction',
    title: 'Automated Clause Extraction & Standardization',
    description: 'AI-powered extraction and standardization of clauses across NDAs. Identifies common patterns, creates clause libraries, and suggests standardization opportunities.',
    category: 'ai',
    priority: 'low',
    icon: '📋',
  },
  {
    id: 'custom-reporting',
    title: 'Custom Reporting & Analytics Dashboard',
    description: 'Advanced reporting capabilities with custom metrics, visualizations, and scheduled reports. Export to PDF, Excel, or CSV. Track KPIs, trends, and business insights.',
    category: 'process',
    priority: 'medium',
    icon: '📈',
  },
  {
    id: 'template-library',
    title: 'Document Templates Library',
    description: 'Centralized library of NDA templates by use case, industry, or region. Version management, approval workflows, and template usage tracking.',
    category: 'process',
    priority: 'low',
    icon: '📚',
  },
  {
    id: 'esignature-integration',
    title: 'E-Signature Integration',
    description: 'Integration with e-signature platforms (DocuSign, HelloSign, etc.) for seamless signature collection, tracking, and document completion workflows.',
    category: 'integration',
    priority: 'medium',
    icon: '✍️',
  },
  {
    id: 'redlining-support',
    title: 'Automated Redlining & Negotiation Support',
    description: 'AI-assisted redlining tool that compares submitted NDAs against standard templates, highlights differences, and suggests negotiation points with explanations.',
    category: 'ai',
    priority: 'low',
    icon: '🖊️',
  },
];

const categoryLabels = {
  automation: 'Automation',
  ai: 'AI Features',
  integration: 'Integrations',
  access: 'Access & APIs',
  process: 'Process Improvement',
};

const priorityColors = {
  high: 'bg-red-100 text-red-800 border-red-300',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  low: 'bg-blue-100 text-blue-800 border-blue-300',
};

const priorityLabels = {
  high: 'High Priority',
  medium: 'Medium Priority',
  low: 'Low Priority',
};

export default function RoadmapPage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedPriority, setSelectedPriority] = useState<string | null>(null);

  const filteredFeatures = features.filter((feature) => {
    if (selectedCategory && feature.category !== selectedCategory) return false;
    if (selectedPriority && feature.priority !== selectedPriority) return false;
    return true;
  });

  const categoryCounts = {
    automation: features.filter(f => f.category === 'automation').length,
    ai: features.filter(f => f.category === 'ai').length,
    integration: features.filter(f => f.category === 'integration').length,
    access: features.filter(f => f.category === 'access').length,
    process: features.filter(f => f.category === 'process').length,
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Future Enhancements & Roadmap</h1>
        <p className="mt-2 text-sm text-gray-600">
          Planned features and improvements to enhance the NDA management platform
        </p>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
        {Object.entries(categoryLabels).map(([key, label]) => (
          <div key={key} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="text-sm font-medium text-gray-600">{label}</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{categoryCounts[key as keyof typeof categoryCounts]}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Category</label>
            <select
              value={selectedCategory || ''}
              onChange={(e) => setSelectedCategory(e.target.value || null)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            >
              <option value="">All Categories</option>
              {Object.entries(categoryLabels).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Priority</label>
            <select
              value={selectedPriority || ''}
              onChange={(e) => setSelectedPriority(e.target.value || null)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            >
              <option value="">All Priorities</option>
              {Object.entries(priorityLabels).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={() => {
                setSelectedCategory(null);
                setSelectedPriority(null);
              }}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredFeatures.map((feature) => (
          <div
            key={feature.id}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="text-3xl">{feature.icon}</div>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${priorityColors[feature.priority]}`}>
                {priorityLabels[feature.priority]}
              </span>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">{feature.title}</h3>
            <p className="text-sm text-gray-600 mb-4">{feature.description}</p>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800">
                {categoryLabels[feature.category]}
              </span>
            </div>
          </div>
        ))}
      </div>

      {filteredFeatures.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow-sm border border-gray-200">
          <p className="text-sm text-gray-600">No features match the selected filters.</p>
        </div>
      )}

      {/* Multi-NDA Analysis Details */}
      <div className="mt-12 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200 p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">🤖 Multi-NDA Analysis Capabilities</h2>
        <p className="text-gray-700 mb-6">
          The Advanced Multi-NDA AI Analysis feature will provide comprehensive insights for business teams:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg p-4 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">📊 Pattern Recognition</h3>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• Identify common clause patterns across NDAs</li>
              <li>• Detect unusual or outlier terms</li>
              <li>• Find inconsistencies in similar agreements</li>
            </ul>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">⚠️ Risk Analysis</h3>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• Aggregate risk scoring across portfolio</li>
              <li>• Identify high-risk agreements</li>
              <li>• Track risk trends over time</li>
            </ul>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">📈 Business Intelligence</h3>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• Expiration forecasting and renewal planning</li>
              <li>• Contract term optimization insights</li>
              <li>• Negotiation leverage analysis</li>
            </ul>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-2">🔍 Compliance Insights</h3>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• Compliance gap analysis across agreements</li>
              <li>• Standardization opportunities</li>
              <li>• Policy adherence reporting</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

