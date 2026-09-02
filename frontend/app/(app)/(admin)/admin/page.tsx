"use client";

import { useEffect, useState } from "react";
import { Loader2, DollarSign, Clock, AlertTriangle } from "lucide-react";
import { getLatencyStats, getWallLatencyStats, getFailureStats, getCostStats, getDailyActivity } from "@/lib/api";
import type { LatencyStat, WallLatencyStat, FailureStat, CostStat, ActivityStat } from "@/lib/types";

export default function AdminDashboard() {
  const [latency, setLatency] = useState<LatencyStat[]>([]);
  const [wallLatency, setWallLatency] = useState<WallLatencyStat[]>([]);
  const [failures, setFailures] = useState<FailureStat[]>([]);
  const [costs, setCosts] = useState<CostStat[]>([]);
  const [activity, setActivity] = useState<ActivityStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [hours, setHours] = useState(24);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getLatencyStats(hours),
      getWallLatencyStats(hours),
      getFailureStats(hours),
      getCostStats(hours),
      getDailyActivity(14),
    ])
      .then(([l, w, f, c, a]) => {
        setLatency(l);
        setWallLatency(w);
        setFailures(f);
        setCosts(c);
        setActivity(a);
      })
      .finally(() => setLoading(false));
  }, [hours]);

  const totalCost = costs.reduce((sum, c) => sum + c.estimated_cost_usd, 0);
  const totalCalls = costs.reduce((sum, c) => sum + c.successful_calls, 0);
  const worstFailure = failures[0];
  const slowestWall = wallLatency[0];

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted">
        <Loader2 size={18} className="animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-mono text-lg text-text-primary">Dashboard</h1>
        <select
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
          className="rounded border border-hairline bg-surface px-3 py-1.5 text-sm text-text-primary outline-none"
        >
          <option value={24}>Last 24 hours</option>
          <option value={168}>Last 7 days</option>
          <option value={720}>Last 30 days</option>
        </select>
      </div>

      {/* summary cards */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <div className="mb-1 flex items-center gap-2 text-text-muted">
            <DollarSign size={14} />
            <span className="text-xs uppercase tracking-wide">Estimated cost</span>
          </div>
          <p className="font-mono text-2xl text-text-primary">${totalCost.toFixed(4)}</p>
          <p className="mt-1 text-xs text-text-muted">{totalCalls} successful LLM calls</p>
        </div>
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <div className="mb-1 flex items-center gap-2 text-text-muted">
            <Clock size={14} />
            <span className="text-xs uppercase tracking-wide">Slowest node (wall, p95)</span>
          </div>
          <p className="font-mono text-2xl text-text-primary">
            {slowestWall ? `${(slowestWall.p95 / 1000).toFixed(1)}s` : "—"}
          </p>
          <p className="mt-1 text-xs text-text-muted">{slowestWall?.node_name || "no data"}</p>
        </div>
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <div className="mb-1 flex items-center gap-2 text-text-muted">
            <AlertTriangle size={14} />
            <span className="text-xs uppercase tracking-wide">Highest failure rate</span>
          </div>
          <p className="font-mono text-2xl text-text-primary">
            {worstFailure ? `${worstFailure.failure_pct}%` : "0%"}
          </p>
          <p className="mt-1 text-xs text-text-muted">{worstFailure?.node_name || "no failures"}</p>
        </div>
      </div>

      {/* wall latency table — what users actually experienced, including retries/backoff */}
      <div className="mb-6 rounded-lg border border-hairline bg-surface">
        <div className="border-b border-hairline px-4 py-2.5">
          <h2 className="font-mono text-xs uppercase tracking-wide text-text-muted">
            Node latency — total (includes retries &amp; fallback attempts)
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-text-muted">
              <th className="px-4 py-2 font-normal">Node</th>
              <th className="px-4 py-2 font-normal">Calls</th>
              <th className="px-4 py-2 font-normal">P50</th>
              <th className="px-4 py-2 font-normal">P95</th>
              <th className="px-4 py-2 font-normal">Avg</th>
              <th className="px-4 py-2 font-normal">Max</th>
            </tr>
          </thead>
          <tbody>
            {wallLatency.map((row) => (
              <tr key={row.node_name} className="border-t border-hairline text-text-primary">
                <td className="px-4 py-2 font-mono">{row.node_name}</td>
                <td className="px-4 py-2">{row.call_count}</td>
                <td className="px-4 py-2">{(row.p50 / 1000).toFixed(2)}s</td>
                <td className="px-4 py-2 text-accent">{(row.p95 / 1000).toFixed(2)}s</td>
                <td className="px-4 py-2">{(row.avg_ms / 1000).toFixed(2)}s</td>
                <td className="px-4 py-2 text-text-muted">{(row.max_ms / 1000).toFixed(2)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* clean LLM call latency — successful attempts only, for comparing raw model speed */}
      <div className="mb-6 rounded-lg border border-hairline bg-surface">
        <div className="border-b border-hairline px-4 py-2.5">
          <h2 className="font-mono text-xs uppercase tracking-wide text-text-muted">
            LLM call latency — successful attempts only
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-text-muted">
              <th className="px-4 py-2 font-normal">Node</th>
              <th className="px-4 py-2 font-normal">Calls</th>
              <th className="px-4 py-2 font-normal">P50</th>
              <th className="px-4 py-2 font-normal">P95</th>
              <th className="px-4 py-2 font-normal">Avg</th>
            </tr>
          </thead>
          <tbody>
            {latency.map((row) => (
              <tr key={row.node_name} className="border-t border-hairline text-text-primary">
                <td className="px-4 py-2 font-mono">{row.node_name}</td>
                <td className="px-4 py-2">{row.call_count}</td>
                <td className="px-4 py-2">{(row.p50 / 1000).toFixed(2)}s</td>
                <td className="px-4 py-2">{(row.p95 / 1000).toFixed(2)}s</td>
                <td className="px-4 py-2">{(row.avg_ms / 1000).toFixed(2)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* failures table */}
      <div className="mb-6 rounded-lg border border-hairline bg-surface">
        <div className="border-b border-hairline px-4 py-2.5">
          <h2 className="font-mono text-xs uppercase tracking-wide text-text-muted">Failure rate by node</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-text-muted">
              <th className="px-4 py-2 font-normal">Node</th>
              <th className="px-4 py-2 font-normal">Failures</th>
              <th className="px-4 py-2 font-normal">Total attempts</th>
              <th className="px-4 py-2 font-normal">Failure %</th>
            </tr>
          </thead>
          <tbody>
            {failures.map((row) => (
              <tr key={row.node_name} className="border-t border-hairline text-text-primary">
                <td className="px-4 py-2 font-mono">{row.node_name}</td>
                <td className="px-4 py-2 text-red-400">{row.failures}</td>
                <td className="px-4 py-2">{row.total_attempts}</td>
                <td className="px-4 py-2">{row.failure_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* cost by model */}
      <div className="rounded-lg border border-hairline bg-surface">
        <div className="border-b border-hairline px-4 py-2.5">
          <h2 className="font-mono text-xs uppercase tracking-wide text-text-muted">Cost by model</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-text-muted">
              <th className="px-4 py-2 font-normal">Model</th>
              <th className="px-4 py-2 font-normal">Input tokens</th>
              <th className="px-4 py-2 font-normal">Output tokens</th>
              <th className="px-4 py-2 font-normal">Calls</th>
              <th className="px-4 py-2 font-normal">Est. cost</th>
            </tr>
          </thead>
          <tbody>
            {costs.map((row) => (
              <tr key={row.model} className="border-t border-hairline text-text-primary">
                <td className="px-4 py-2 font-mono">{row.model}</td>
                <td className="px-4 py-2">{row.total_input_tokens.toLocaleString()}</td>
                <td className="px-4 py-2">{row.total_output_tokens.toLocaleString()}</td>
                <td className="px-4 py-2">{row.successful_calls}</td>
                <td className="px-4 py-2 text-accent">${row.estimated_cost_usd.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}