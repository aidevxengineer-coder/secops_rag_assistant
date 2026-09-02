"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LayoutDashboard, Users, ArrowLeft, ShieldHalf } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.push("/login");
      return;
    }
    if (user.role !== "admin") {
      router.push("/chat"); // logged in but not admin — bounce to normal app, not login
    }
  }, [loading, user, router]);

  if (loading || !user || user.role !== "admin") {
    return <div className="flex min-h-screen items-center justify-center bg-base text-text-muted">Loading...</div>;
  }

  const navItem = (href: string, label: string, Icon: typeof LayoutDashboard) => (
    <Link
      href={href}
      className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm ${
        pathname === href ? "bg-accent/10 text-accent" : "text-text-muted hover:bg-elevated hover:text-text-primary"
      }`}
    >
      <Icon size={15} />
      {label}
    </Link>
  );

  return (
    <div className="flex h-screen bg-base">
      <aside className="flex w-56 shrink-0 flex-col border-r border-hairline bg-surface">
        <div className="flex items-center gap-2 border-b border-hairline px-4 py-3.5">
          <ShieldHalf size={18} className="text-accent" strokeWidth={2} />
          <span className="font-mono text-sm font-semibold text-text-primary">Admin</span>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {navItem("/admin", "Dashboard", LayoutDashboard)}
          {navItem("/admin/users", "Users", Users)}
        </nav>
        <div className="mt-auto border-t border-hairline p-3">
          <Link href="/chat" className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text-muted hover:bg-elevated hover:text-text-primary">
            <ArrowLeft size={14} />
            Back to app
          </Link>
        </div>
      </aside>
      <div className="flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}