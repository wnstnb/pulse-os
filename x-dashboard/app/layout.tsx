import "./globals.css";

import { Sidebar } from "@/components/sidebar";
import { TopNav } from "@/components/top-nav";

export const metadata = {
  title: "Pulse OS - X Agent Dashboard",
  description: "Daily brief, skills, and publishing for X Agent OS"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen bg-slate-950">
          <Sidebar />
          <div className="flex flex-1 flex-col">
            <TopNav />
            <main className="flex-1 px-6 py-6">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
