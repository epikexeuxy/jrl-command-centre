/**
 * Platform shell (Phase 1 scaffold).
 * The full WealthLens UI — auth flow, dashboard, portfolio analytics, CSV upload —
 * ships in the next build increment on top of this verified toolchain.
 */
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Activity, BarChart3, Briefcase, ShieldCheck } from "lucide-react";
import { api, type HealthResponse } from "./lib/api";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.get<HealthResponse>("/health").then((r) => setHealth(r.data)).catch(() => setError(true));
  }, []);

  return (
    <div className="min-h-full bg-gradient-to-br from-navy-950 via-navy-900 to-navy-800 flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-2xl rounded-2xl bg-white/95 shadow-2xl backdrop-blur p-10"
      >
        <div className="flex items-baseline justify-between border-b-2 border-navy-900 pb-4">
          <h1 className="text-2xl font-semibold text-navy-900 tracking-tight">
            J.R. Laddha Financial Services
          </h1>
          <span className="text-sm font-bold uppercase tracking-wider text-gold-500">
            Command Centre
          </span>
        </div>

        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Module icon={<BarChart3 className="h-5 w-5" />} title="WealthLens"
            desc="HNI portfolio analytics — live NAVs, XIRR/TWR, risk & allocation." ready />
          <Module icon={<Briefcase className="h-5 w-5" />} title="DealDesk"
            desc="IB pipeline CRM with AI India Entry Briefs." ready={false} />
        </div>

        <div className="mt-8 flex items-center gap-2 rounded-lg bg-slate-100 px-4 py-3 text-sm">
          {error ? (
            <>
              <Activity className="h-4 w-4 text-red-600" />
              <span className="text-red-700">API unreachable — start the backend on :8000</span>
            </>
          ) : health ? (
            <>
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              <span className="text-slate-700">
                API <b>{health.status}</b> · {health.app} v{health.version} · database {health.database}
              </span>
            </>
          ) : (
            <span className="text-slate-500">Checking API…</span>
          )}
        </div>
      </motion.div>
    </div>
  );
}

function Module({ icon, title, desc, ready }: {
  icon: React.ReactNode; title: string; desc: string; ready: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-200 p-5 hover:border-gold-400 transition-colors">
      <div className="flex items-center gap-2 text-navy-900">
        {icon}
        <h2 className="font-semibold">{title}</h2>
        <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
          ready ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
        }`}>
          {ready ? "API live" : "Phase 3"}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-600">{desc}</p>
    </div>
  );
}
