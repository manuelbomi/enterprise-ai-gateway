// ============================================================
// src/pages/Dashboard/DashboardPage.tsx — Usage Analytics Dashboard
//
// ARCHITECT'S NOTE:
//   This page is visible to all authenticated users but shows
//   different data depending on role:
//     - Regular users: their own usage this month
//     - Admins: team-level breakdowns and cost charts
//
//   Charts use Recharts — a React-native chart library that
//   is well-maintained and SSR-friendly.
// ============================================================

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from 'recharts';
import { adminApi } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { DollarSign, MessageSquare, Zap, TrendingUp } from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin' || user?.role === 'team_admin';

  const { data: teamUsage = [] } = useQuery({
    queryKey: ['usage-by-team'],
    queryFn: () => adminApi.getUsageByTeam(30),
    enabled: isAdmin,
  });

  const { data: dailyCost = [] } = useQuery({
    queryKey: ['daily-cost'],
    queryFn: () => adminApi.getDailyCost(30),
    enabled: isAdmin,
  });

  // Totals across all teams
  const totalCost = teamUsage.reduce((s, t) => s + t.total_cost_usd, 0);
  const totalCalls = teamUsage.reduce((s, t) => s + t.total_calls, 0);
  const totalTokens = teamUsage.reduce((s, t) => s + t.total_tokens, 0);

  return (
    <div className="h-full overflow-y-auto bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Last 30 days · All times UTC</p>
        </div>

        {/* KPI Cards */}
        {isAdmin && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <KpiCard
              icon={<DollarSign className="w-5 h-5 text-green-600" />}
              label="Total Spend"
              value={`$${totalCost.toFixed(2)}`}
              color="green"
            />
            <KpiCard
              icon={<MessageSquare className="w-5 h-5 text-brand-600" />}
              label="Total API Calls"
              value={totalCalls.toLocaleString()}
              color="blue"
            />
            <KpiCard
              icon={<Zap className="w-5 h-5 text-yellow-600" />}
              label="Total Tokens"
              value={`${(totalTokens / 1_000_000).toFixed(2)}M`}
              color="yellow"
            />
          </div>
        )}

        {!isAdmin && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
            <TrendingUp className="w-10 h-10 text-brand-400 mx-auto mb-3" />
            <h2 className="font-semibold text-gray-700">Usage Analytics</h2>
            <p className="text-sm text-gray-400 mt-1">
              Admin access required to view team analytics.
              Contact your team admin.
            </p>
          </div>
        )}

        {/* Charts — admin only */}
        {isAdmin && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Cost by Team — Bar Chart */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-gray-800 mb-4">Cost by Team (USD)</h2>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={teamUsage} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="team_name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                  <Tooltip formatter={(v: number) => [`$${v.toFixed(4)}`, 'Cost']} />
                  <Bar dataKey="total_cost_usd" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Daily Cost Trend — Line Chart */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-gray-800 mb-4">Daily Spend Trend</h2>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={dailyCost} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                  <Tooltip formatter={(v: number) => [`$${v.toFixed(4)}`, 'Spend']} />
                  <Legend />
                  <Line type="monotone" dataKey="cost_usd" stroke="#3b82f6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Team Usage Table */}
            <div className="bg-white rounded-xl border border-gray-200 p-5 lg:col-span-2">
              <h2 className="font-semibold text-gray-800 mb-4">Team Breakdown</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-100">
                    <th className="pb-2 font-medium">Team</th>
                    <th className="pb-2 font-medium text-right">API Calls</th>
                    <th className="pb-2 font-medium text-right">Tokens</th>
                    <th className="pb-2 font-medium text-right">Cost (USD)</th>
                    <th className="pb-2 font-medium text-right">Top Model</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {teamUsage.map((row) => (
                    <tr key={row.team_name} className="hover:bg-gray-50">
                      <td className="py-2.5 font-medium text-gray-800">{row.team_name}</td>
                      <td className="py-2.5 text-right text-gray-600">{row.total_calls.toLocaleString()}</td>
                      <td className="py-2.5 text-right text-gray-600">{row.total_tokens.toLocaleString()}</td>
                      <td className="py-2.5 text-right font-medium text-gray-800">
                        ${row.total_cost_usd.toFixed(4)}
                      </td>
                      <td className="py-2.5 text-right">
                        <span className="px-2 py-0.5 bg-brand-100 text-brand-700 rounded text-xs font-medium">
                          {row.top_model ?? 'N/A'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {teamUsage.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-gray-400">
                        No usage data for this period
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ---- KPI Card ----
interface KpiCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: 'green' | 'blue' | 'yellow';
}

const colorMap = {
  green:  'bg-green-50 border-green-200',
  blue:   'bg-blue-50 border-blue-200',
  yellow: 'bg-yellow-50 border-yellow-200',
};

const KpiCard: React.FC<KpiCardProps> = ({ icon, label, value, color }) => (
  <div className={`rounded-xl border p-5 ${colorMap[color]}`}>
    <div className="flex items-center gap-3 mb-2">
      {icon}
      <span className="text-sm font-medium text-gray-600">{label}</span>
    </div>
    <p className="text-2xl font-bold text-gray-900">{value}</p>
  </div>
);
