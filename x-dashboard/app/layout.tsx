import "./globals.css";

import { Sidebar } from "@/components/sidebar";

export const metadata = {
  title: "Pulse OS - X Agent Dashboard",
  description: "Daily brief, skills, and publishing for X Agent OS"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 bg-slate-950 px-6 py-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
