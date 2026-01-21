import Link from "next/link";

const navItems = [
  { href: "/today", label: "Today" },
  { href: "/creators", label: "Creators" },
  { href: "/skills", label: "Skills" },
  { href: "/sessions", label: "Sessions" },
  { href: "/explorer", label: "Explorer" },
  { href: "/analytics", label: "Analytics" },
  { href: "/publishing", label: "Publishing" }
];

export function Sidebar() {
  return (
    <aside className="min-h-screen w-60 border-r border-slate-800 bg-slate-950 px-4 py-6">
      <div className="mb-8">
        <div className="text-sm uppercase text-slate-400">X Agent OS</div>
        <div className="text-lg font-semibold text-white">Pulse Dashboard</div>
      </div>
      <nav className="space-y-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="block rounded-md px-3 py-2 text-sm text-slate-200 hover:bg-slate-900"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
