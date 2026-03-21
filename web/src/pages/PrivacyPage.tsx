import { useState, useEffect } from 'react';
import api from '../lib/api';

interface PrivacySubject {
  id: string;
  subject_type: string;
  subject_identifier: string;
  consent_given: boolean;
  erasure_requested: boolean;
  created_at: string;
}

export default function PrivacyPage() {
  const [subjects, setSubjects] = useState<PrivacySubject[]>([]);
  const [consents, setConsents] = useState<any[]>([]);
  const [exports, setExports] = useState<any[]>([]);
  const [tab, setTab] = useState<'subjects' | 'consent' | 'exports' | 'erasure'>('subjects');

  useEffect(() => {
    api.get('/api/v1/privacy/subjects').then((r: any) => setSubjects(r.data.items || [])).catch(() => {});
    api.get('/api/v1/privacy/consent').then((r: any) => setConsents(r.data.items || [])).catch(() => {});
    api.get('/api/v1/privacy/exports').then((r: any) => setExports(r.data.items || [])).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Privacy & Compliance (GDPR/CCPA)</h1>
      </div>

      <div className="flex space-x-1 bg-gray-800 rounded-lg p-1">
        {(['subjects', 'consent', 'exports', 'erasure'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === t ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'subjects' && (
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Data Subjects</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-gray-400 border-b border-gray-700">
                <th className="pb-3 text-left">Type</th>
                <th className="pb-3 text-left">Identifier</th>
                <th className="pb-3 text-left">Consent</th>
                <th className="pb-3 text-left">Erasure</th>
                <th className="pb-3 text-left">Created</th>
              </tr></thead>
              <tbody>
                {subjects.map(s => (
                  <tr key={s.id} className="border-b border-gray-700/50 text-gray-300">
                    <td className="py-3">{s.subject_type}</td>
                    <td className="py-3">{s.subject_identifier}</td>
                    <td className="py-3">
                      <span className={`px-2 py-1 rounded text-xs ${s.consent_given ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
                        {s.consent_given ? 'Given' : 'Not Given'}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className={`px-2 py-1 rounded text-xs ${s.erasure_requested ? 'bg-yellow-900 text-yellow-300' : 'bg-gray-700 text-gray-400'}`}>
                        {s.erasure_requested ? 'Requested' : 'No'}
                      </span>
                    </td>
                    <td className="py-3 text-gray-500">{new Date(s.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
                {subjects.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-gray-500">No data subjects registered</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'consent' && (
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Consent Records</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-gray-400 border-b border-gray-700">
                <th className="pb-3 text-left">Subject</th>
                <th className="pb-3 text-left">Purpose</th>
                <th className="pb-3 text-left">Legal Basis</th>
                <th className="pb-3 text-left">Status</th>
                <th className="pb-3 text-left">Date</th>
              </tr></thead>
              <tbody>
                {consents.map((c: any) => (
                  <tr key={c.id} className="border-b border-gray-700/50 text-gray-300">
                    <td className="py-3">{c.subject_id}</td>
                    <td className="py-3">{c.purpose}</td>
                    <td className="py-3">{c.legal_basis}</td>
                    <td className="py-3">
                      <span className={`px-2 py-1 rounded text-xs ${c.granted ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
                        {c.granted ? 'Granted' : 'Revoked'}
                      </span>
                    </td>
                    <td className="py-3 text-gray-500">{c.granted_at}</td>
                  </tr>
                ))}
                {consents.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-gray-500">No consent records</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'exports' && (
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Data Export Requests</h2>
          <div className="space-y-3">
            {exports.map((e: any) => (
              <div key={e.id} className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg">
                <div>
                  <p className="text-white font-medium">Export #{e.id?.slice(0, 8)}</p>
                  <p className="text-gray-400 text-sm">Format: {e.export_format} | Requested by: {e.requested_by}</p>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                  e.status === 'ready' ? 'bg-green-900 text-green-300' :
                  e.status === 'processing' ? 'bg-blue-900 text-blue-300' :
                  'bg-yellow-900 text-yellow-300'}`}>
                  {e.status}
                </span>
              </div>
            ))}
            {exports.length === 0 && <p className="text-gray-500 text-center py-8">No export requests</p>}
          </div>
        </div>
      )}

      {tab === 'erasure' && (
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Right to Erasure (RTBF)</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-gray-700/50 rounded-lg p-4">
              <p className="text-gray-400 text-sm">Total Subjects</p>
              <p className="text-2xl font-bold text-white">{subjects.length}</p>
            </div>
            <div className="bg-gray-700/50 rounded-lg p-4">
              <p className="text-gray-400 text-sm">Erasure Requested</p>
              <p className="text-2xl font-bold text-yellow-400">{subjects.filter(s => s.erasure_requested).length}</p>
            </div>
            <div className="bg-gray-700/50 rounded-lg p-4">
              <p className="text-gray-400 text-sm">Consent Given</p>
              <p className="text-2xl font-bold text-green-400">{subjects.filter(s => s.consent_given).length}</p>
            </div>
          </div>
          <p className="text-gray-400 text-sm">
            Erasure requests are processed within 30 days per GDPR Article 17 requirements.
            All personal data associated with the subject will be anonymized or deleted.
          </p>
        </div>
      )}
    </div>
  );
}
