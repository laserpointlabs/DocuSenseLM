'use client';

import { useState, useEffect } from 'react';
import { documentAPI } from '@/lib/api';
import Link from 'next/link';

interface Document {
  id: string;
  filename: string;
  status: string;
  upload_date: string;
  metadata_json?: any;
}

interface DocumentWithMetadata extends Document {
  effective_date?: string;
  expiration_date?: string;
  governing_law?: string;
  is_mutual?: boolean;
  term_months?: number;
  survival_months?: number;
  parties?: Array<{ name: string; type: string }>;
  days_until_expiration?: number;
  expiration_status?: 'active' | 'expiring_soon' | 'expiring_very_soon' | 'expired';
}

export default function DashboardPage() {
  const [documents, setDocuments] = useState<DocumentWithMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'active' | 'expiring_soon' | 'expired'>('all');
  const [sortBy, setSortBy] = useState<'expiration' | 'company' | 'effective_date'>('expiration');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const response = await documentAPI.list(0, 1000);
      // The API now returns full metadata in the list endpoint, so we can use it directly
      // But we still need to calculate expiration dates
      const docsWithMetadata = await enrichDocumentsWithMetadata(response.documents || []);
      setDocuments(docsWithMetadata);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const enrichDocumentsWithMetadata = async (docs: Document[]): Promise<DocumentWithMetadata[]> => {
    // The API now returns full metadata in the list endpoint, so we can use it directly
    // No need to call get() for each document - just calculate expiration dates
    const enriched = docs.map((doc) => {
        try {
          // Extract metadata from the document (already includes DocumentMetadata fields)
          const metadata = (doc as any).metadata || (doc as any).metadata_json || {};
          const effectiveDate = metadata.effective_date;
          const termMonths = metadata.term_months;

          // Calculate expiration date
          let expirationDate: string | undefined;
          let daysUntilExpiration: number | undefined;
          let expirationStatus: 'active' | 'expiring_soon' | 'expiring_very_soon' | 'expired' = 'active';

          if (effectiveDate && termMonths) {
            const effective = new Date(effectiveDate);
            const expiration = new Date(effective);
            expiration.setMonth(expiration.getMonth() + termMonths);
            expirationDate = expiration.toISOString().split('T')[0];

            const today = new Date();
            today.setHours(0, 0, 0, 0);
            const expDate = new Date(expiration);
            expDate.setHours(0, 0, 0, 0);

            daysUntilExpiration = Math.ceil((expDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

            if (daysUntilExpiration < 0) {
              expirationStatus = 'expired';
            } else if (daysUntilExpiration <= 30) {
              expirationStatus = 'expiring_very_soon';
            } else if (daysUntilExpiration <= 90) {
              expirationStatus = 'expiring_soon';
            }
          }

          // Extract company name from filename
          const companyName = extractCompanyName(doc.filename);

          return {
            ...doc,
            effective_date: effectiveDate,
            expiration_date: expirationDate,
            governing_law: metadata.governing_law,
            is_mutual: metadata.is_mutual,
            term_months: termMonths,
            survival_months: metadata.survival_months,
            parties: metadata.parties || [],
            days_until_expiration: daysUntilExpiration,
            expiration_status: expirationStatus,
            company_name: companyName,
          } as DocumentWithMetadata & { company_name: string };
        } catch (error) {
          console.error(`Failed to enrich document ${doc.id}:`, error);
          return {
            ...doc,
            company_name: extractCompanyName(doc.filename),
          } as DocumentWithMetadata & { company_name: string };
        }
    });

    return enriched;
  };

  const extractCompanyName = (filename: string): string => {
    // Extract company name from filename (e.g., "Norris Cylinder Company_Signed NDA_expires Sept. 2028.pdf")
    const parts = filename.split('_');
    if (parts.length > 0) {
      return parts[0].trim();
    }
    return filename.replace('.pdf', '').replace('.docx', '');
  };

  const parseExpirationDate = (dateStr: string): Date | null => {
    // Parse dates like "Sept. 2028" or "September 2028"
    const monthNames: { [key: string]: number } = {
      'jan': 0, 'january': 0,
      'feb': 1, 'february': 1,
      'mar': 2, 'march': 2,
      'apr': 3, 'april': 3,
      'may': 4,
      'jun': 5, 'june': 5,
      'jul': 6, 'july': 6,
      'aug': 7, 'august': 7,
      'sep': 8, 'sept': 8, 'september': 8,
      'oct': 9, 'october': 9,
      'nov': 10, 'november': 10,
      'dec': 11, 'december': 11,
    };

    try {
      const parts = dateStr.trim().toLowerCase().replace(/\./g, '').split(/\s+/);
      if (parts.length >= 2) {
        const monthName = parts[0];
        const year = parseInt(parts[1]);
        const month = monthNames[monthName];
        if (month !== undefined && !isNaN(year)) {
          return new Date(year, month, 1);
        }
      }
    } catch (e) {
      // Ignore parsing errors
    }
    return null;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'expired':
        return 'bg-red-100 text-red-800';
      case 'expiring_very_soon':
        return 'bg-red-200 text-red-900';
      case 'expiring_soon':
        return 'bg-yellow-100 text-yellow-800';
      case 'active':
        return 'bg-green-100 text-green-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'expired':
        return 'Expired';
      case 'expiring_very_soon':
        return 'Expiring Very Soon';
      case 'expiring_soon':
        return 'Expiring Soon';
      case 'active':
        return 'Active';
      default:
        return 'Unknown';
    }
  };

  const filteredDocuments = documents.filter((doc) => {
    if (filter === 'all') return true;
    if (filter === 'expired') return doc.expiration_status === 'expired';
    if (filter === 'expiring_soon') return doc.expiration_status === 'expiring_soon' || doc.expiration_status === 'expiring_very_soon';
    if (filter === 'active') return doc.expiration_status === 'active' && doc.days_until_expiration !== undefined && doc.days_until_expiration > 90;
    return true;
  });

  const sortedDocuments = [...filteredDocuments].sort((a, b) => {
    let comparison = 0;

    if (sortBy === 'expiration') {
      const aDays = a.days_until_expiration ?? Infinity;
      const bDays = b.days_until_expiration ?? Infinity;
      comparison = aDays - bDays;
    } else if (sortBy === 'company') {
      const aName = (a as any).company_name || a.filename;
      const bName = (b as any).company_name || b.filename;
      comparison = aName.localeCompare(bName);
    } else if (sortBy === 'effective_date') {
      const aDate = a.effective_date ? new Date(a.effective_date).getTime() : 0;
      const bDate = b.effective_date ? new Date(b.effective_date).getTime() : 0;
      comparison = aDate - bDate;
    }

    return sortOrder === 'asc' ? comparison : -comparison;
  });

  // Calculate statistics
  const stats = {
    total: documents.length,
    active: documents.filter(d => d.expiration_status === 'active').length,
    expiring_soon: documents.filter(d => d.expiration_status === 'expiring_soon' || d.expiration_status === 'expiring_very_soon').length,
    expired: documents.filter(d => d.expiration_status === 'expired').length,
    mutual: documents.filter(d => d.is_mutual === true).length,
    unilateral: documents.filter(d => d.is_mutual === false).length,
  };

  const handleSort = (column: typeof sortBy) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">NDA Dashboard</h1>
        <p className="mt-2 text-sm text-gray-600">
          Monitor active NDAs, expiration dates, and key metrics
        </p>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total NDAs</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">{stats.total}</p>
            </div>
            <div className="bg-blue-100 rounded-full p-3">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Active</p>
              <p className="text-3xl font-bold text-green-600 mt-2">{stats.active}</p>
            </div>
            <div className="bg-green-100 rounded-full p-3">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Expiring Soon</p>
              <p className="text-3xl font-bold text-yellow-600 mt-2">{stats.expiring_soon}</p>
              <p className="text-xs text-gray-500 mt-1">Within 90 days</p>
            </div>
            <div className="bg-yellow-100 rounded-full p-3">
              <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Expired</p>
              <p className="text-3xl font-bold text-red-600 mt-2">{stats.expired}</p>
            </div>
            <div className="bg-red-100 rounded-full p-3">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Additional Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <p className="text-sm font-medium text-gray-600">Mutual NDAs</p>
          <p className="text-2xl font-bold text-gray-900 mt-2">{stats.mutual}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <p className="text-sm font-medium text-gray-600">Unilateral NDAs</p>
          <p className="text-2xl font-bold text-gray-900 mt-2">{stats.unilateral}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <p className="text-sm font-medium text-gray-600">Processing</p>
          <p className="text-2xl font-bold text-gray-900 mt-2">
            {documents.filter(d => d.status === 'processing').length}
          </p>
        </div>
      </div>

      {/* Filters and Controls */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Filter</label>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as any)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            >
              <option value="all">All NDAs</option>
              <option value="active">Active</option>
              <option value="expiring_soon">Expiring Soon</option>
              <option value="expired">Expired</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Sort By</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            >
              <option value="expiration">Expiration Date</option>
              <option value="company">Company Name</option>
              <option value="effective_date">Effective Date</option>
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              {sortOrder === 'asc' ? '↑ Ascending' : '↓ Descending'}
            </button>
          </div>
          <div className="ml-auto">
            <button
              onClick={loadDocuments}
              className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            <p className="mt-2 text-sm text-gray-600">Loading documents...</p>
          </div>
        ) : sortedDocuments.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-sm text-gray-600">No documents found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('company')}>
                    Company
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('effective_date')}>
                    Effective Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('expiration')}>
                    Expiration
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Term
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Governing Law
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {sortedDocuments.map((doc) => (
                  <tr key={doc.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {(doc as any).company_name || doc.filename}
                      </div>
                      <div className="text-xs text-gray-500">
                        {doc.parties && doc.parties.length > 0 && (
                          <span>{doc.parties.map(p => p.name).join(', ')}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(doc.expiration_status || 'unknown')}`}>
                        {getStatusLabel(doc.expiration_status || 'unknown')}
                      </span>
                      {doc.days_until_expiration !== undefined && (
                        <div className="text-xs text-gray-500 mt-1">
                          {doc.days_until_expiration < 0
                            ? `${Math.abs(doc.days_until_expiration)} days ago`
                            : `${doc.days_until_expiration} days remaining`}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {doc.effective_date
                        ? new Date(doc.effective_date).toLocaleDateString()
                        : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">
                        {doc.expiration_date
                          ? new Date(doc.expiration_date).toLocaleDateString()
                          : '-'}
                      </div>
                      {doc.days_until_expiration !== undefined && doc.days_until_expiration >= 0 && (
                        <div className="text-xs text-gray-500">
                          {doc.days_until_expiration <= 30 && (
                            <span className="text-red-600 font-medium">⚠️ Critical</span>
                          )}
                          {doc.days_until_expiration > 30 && doc.days_until_expiration <= 90 && (
                            <span className="text-yellow-600 font-medium">⚠️ Warning</span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {doc.term_months ? `${doc.term_months} months` : '-'}
                      {doc.survival_months && (
                        <div className="text-xs text-gray-400">
                          +{doc.survival_months}mo survival
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                        doc.is_mutual ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                      }`}>
                        {doc.is_mutual ? 'Mutual' : 'Unilateral'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {doc.governing_law || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <Link
                        href={`/documents/${doc.id}`}
                        className="text-primary-600 hover:text-primary-700"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
