export function TopNav() {
  const today = new Date().toISOString().slice(0, 10);

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-800 bg-slate-950/95 px-6 py-4 backdrop-blur">
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500">Pulse OS</div>
        <div className="text-sm font-semibold text-white">Daily Execution</div>
      </div>
      <div className="text-xs text-slate-400">Today: {today}</div>
    </header>
  );
}
