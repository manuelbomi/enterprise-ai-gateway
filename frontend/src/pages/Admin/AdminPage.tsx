// ============================================================
// src/pages/Admin/AdminPage.tsx — Admin Panel
//
// ARCHITECT'S NOTE:
//   This page is the IT/AI Architect's control center.
//   It demonstrates the enterprise governance model:
//     1. Create teams (departments)
//     2. Assign model policies (which LLMs each team can use)
//     3. Invite users and assign them to teams
//
//   In a real deployment, team creation and user invitation
//   would integrate with the company's SSO/LDAP system.
// ============================================================

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi, authApi } from '@/services/api';
import { Users, Plus, Shield, Check } from 'lucide-react';

export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'teams' | 'users'>('teams');

  return (
    <div className="h-full overflow-y-auto bg-gray-50 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="w-6 h-6 text-brand-600" />
            Admin Panel
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            Manage teams, model policies, and user access
          </p>
        </div>

        {/* Tab Nav */}
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
          <TabButton active={activeTab === 'teams'} onClick={() => setActiveTab('teams')} label="Teams & Policies" />
          <TabButton active={activeTab === 'users'} onClick={() => setActiveTab('users')} label="Create User" />
        </div>

        {activeTab === 'teams' && <TeamsSection />}
        {activeTab === 'users' && <CreateUserSection />}
      </div>
    </div>
  );
};

// ---- Teams Section ----
const TeamsSection: React.FC = () => {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: '',
    slug: '',
    description: '',
    allowed_models: [] as string[],
    default_model: 'claude-haiku',
    spend_limit_usd: 100,
    rpm_limit: 100,
  });
  const [success, setSuccess] = useState('');

  const { data: teams = [], isLoading } = useQuery({
    queryKey: ['teams'],
    queryFn: adminApi.listTeams,
  });

  const createMutation = useMutation({
    mutationFn: adminApi.createTeam,
    onSuccess: (team) => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      setSuccess(`Team "${team.name}" created successfully`);
      setShowForm(false);
      setForm({ name: '', slug: '', description: '', allowed_models: [], default_model: 'claude-haiku', spend_limit_usd: 100, rpm_limit: 100 });
    },
  });

  const ALL_MODELS = ['claude-haiku', 'claude-sonnet', 'claude-opus', 'gpt-4o-mini', 'gpt-4o', 'gemini-pro'];

  const toggleModel = (model: string) => {
    setForm((prev) => ({
      ...prev,
      allowed_models: prev.allowed_models.includes(model)
        ? prev.allowed_models.filter((m) => m !== model)
        : [...prev.allowed_models, model],
    }));
  };

  return (
    <div className="space-y-4">
      {success && (
        <div className="flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-3 text-sm">
          <Check className="w-4 h-4" /> {success}
        </div>
      )}

      {/* Team List */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">Teams ({teams.length})</h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-1.5 text-sm bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" /> New Team
          </button>
        </div>

        {isLoading ? (
          <div className="p-6 text-center text-gray-400 text-sm">Loading teams…</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 bg-gray-50">
                <th className="px-5 py-3 font-medium">Name</th>
                <th className="px-5 py-3 font-medium">Members</th>
                <th className="px-5 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {teams.map((team) => (
                <tr key={team.id} className="hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <p className="font-medium text-gray-800">{team.name}</p>
                    <p className="text-xs text-gray-400">{team.description}</p>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-1 text-gray-600">
                      <Users className="w-3.5 h-3.5" /> {team.member_count}
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      team.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {team.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                </tr>
              ))}
              {teams.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-5 py-8 text-center text-gray-400">
                    No teams yet. Create your first team.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Create Team Form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-brand-200 p-6">
          <h3 className="font-semibold text-gray-800 mb-4">Create New Team</h3>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Team Name" required>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value, slug: e.target.value.toLowerCase().replace(/\s+/g, '-') })}
                placeholder="e.g. HR Team"
                className={inputCls}
              />
            </Field>
            <Field label="Slug">
              <input
                value={form.slug}
                onChange={(e) => setForm({ ...form, slug: e.target.value })}
                placeholder="e.g. hr-team"
                className={inputCls}
              />
            </Field>
            <Field label="Description" className="col-span-2">
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Optional description"
                className={inputCls}
              />
            </Field>
            <Field label="Monthly Budget (USD)">
              <input
                type="number"
                value={form.spend_limit_usd}
                onChange={(e) => setForm({ ...form, spend_limit_usd: Number(e.target.value) })}
                className={inputCls}
              />
            </Field>
            <Field label="Rate Limit (req/min)">
              <input
                type="number"
                value={form.rpm_limit}
                onChange={(e) => setForm({ ...form, rpm_limit: Number(e.target.value) })}
                className={inputCls}
              />
            </Field>
            <Field label="Allowed Models" className="col-span-2">
              <div className="flex flex-wrap gap-2 mt-1">
                {ALL_MODELS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => toggleModel(m)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                      form.allowed_models.includes(m)
                        ? 'bg-brand-600 text-white border-brand-600'
                        : 'border-gray-200 text-gray-600 hover:border-brand-400'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Default Model">
              <select
                value={form.default_model}
                onChange={(e) => setForm({ ...form, default_model: e.target.value })}
                className={inputCls}
              >
                {form.allowed_models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </Field>
          </div>
          <div className="flex gap-3 mt-5">
            <button
              onClick={() => createMutation.mutate(form)}
              disabled={!form.name || form.allowed_models.length === 0 || createMutation.isPending}
              className="bg-brand-600 hover:bg-brand-700 disabled:bg-gray-200 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
            >
              {createMutation.isPending ? 'Creating…' : 'Create Team'}
            </button>
            <button onClick={() => setShowForm(false)} className="text-sm text-gray-500 hover:text-gray-700">
              Cancel
            </button>
          </div>
          {createMutation.error && (
            <p className="text-red-600 text-sm mt-2">Error: {String(createMutation.error)}</p>
          )}
        </div>
      )}
    </div>
  );
};

// ---- Create User Section ----
const CreateUserSection: React.FC = () => {
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'member' });
  const [success, setSuccess] = useState('');

  const mutation = useMutation({
    mutationFn: authApi.register,
    onSuccess: (user) => {
      setSuccess(`User ${user.email} created. Assign them to a team via the Teams section.`);
      setForm({ email: '', full_name: '', password: '', role: 'member' });
    },
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 max-w-lg">
      <h2 className="font-semibold text-gray-800 mb-4">Create New User</h2>
      {success && (
        <div className="flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-3 text-sm mb-4">
          <Check className="w-4 h-4" /> {success}
        </div>
      )}
      <div className="space-y-4">
        <Field label="Full Name" required>
          <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className={inputCls} placeholder="Jane Smith" />
        </Field>
        <Field label="Work Email" required>
          <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputCls} placeholder="jane@company.com" />
        </Field>
        <Field label="Temporary Password" required>
          <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={inputCls} placeholder="Min. 8 characters" />
        </Field>
        <Field label="Role">
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className={inputCls}>
            <option value="member">Member</option>
            <option value="team_admin">Team Admin</option>
            <option value="super_admin">Super Admin</option>
          </select>
        </Field>
        <button
          onClick={() => mutation.mutate(form)}
          disabled={!form.email || !form.full_name || !form.password || mutation.isPending}
          className="w-full bg-brand-600 hover:bg-brand-700 disabled:bg-gray-200 text-white text-sm font-semibold py-2.5 rounded-lg transition-colors"
        >
          {mutation.isPending ? 'Creating…' : 'Create User'}
        </button>
        {mutation.error && <p className="text-red-600 text-sm">{String(mutation.error)}</p>}
      </div>
    </div>
  );
};

// ---- Helpers ----
const inputCls = 'w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500';

const Field: React.FC<{ label: string; required?: boolean; children: React.ReactNode; className?: string }> = ({
  label, required, children, className = '',
}) => (
  <div className={className}>
    <label className="block text-xs font-medium text-gray-600 mb-1">
      {label} {required && <span className="text-red-500">*</span>}
    </label>
    {children}
  </div>
);

const TabButton: React.FC<{ active: boolean; onClick: () => void; label: string }> = ({ active, onClick, label }) => (
  <button
    onClick={onClick}
    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
      active ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'
    }`}
  >
    {label}
  </button>
);
