import { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  Bell,
  BookOpen,
  Calendar,
  CheckSquare,
  LayoutDashboard,
  LogOut,
  RefreshCw,
} from "lucide-react";
import { User } from "../types";

interface LayoutProps {
  user: User;
  onLogout: () => void;
  children: ReactNode;
}

const navItems = [
  { to: "/", label: "Hoje", icon: LayoutDashboard },
  { to: "/tasks", label: "Tarefas", icon: CheckSquare },
  { to: "/calendar", label: "Calendário", icon: Calendar },
  { to: "/subjects", label: "Disciplinas", icon: BookOpen },
  { to: "/notifications", label: "Avisos", icon: Bell },
  { to: "/integrations", label: "Automação", icon: RefreshCw },
];

export function Layout({ user, onLogout, children }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-paper text-ink">
      {/* Navegação lateral desktop */}
      <aside className="hidden md:flex md:flex-col w-60 border-r border-line bg-surface px-5 py-7 justify-between shrink-0">
        <div>
          <div className="pb-6 mb-6 border-b border-line">
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
              Personal Academic
            </p>
            <h1 className="font-editorial text-2xl font-semibold tracking-tight text-ink mt-1">
              UniFlow
            </h1>
          </div>

          <nav className="space-y-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 text-sm rounded transition-colors ${
                    isActive
                      ? "bg-accent-soft text-accent font-medium"
                      : "text-muted hover:text-ink hover:bg-paper"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="pt-5 border-t border-line">
          <p className="text-xs font-medium text-ink truncate">{user.display_name}</p>
          <p className="text-xs text-muted truncate mb-3">{user.email}</p>
          <button
            onClick={onLogout}
            className="flex items-center gap-2 text-xs text-muted hover:text-danger transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            Encerrar sessão
          </button>
        </div>
      </aside>

      {/* Conteúdo principal */}
      <main className="flex-1 pb-20 md:pb-10 px-4 sm:px-8 lg:px-12 py-6 md:py-10 max-w-5xl w-full mx-auto">
        {children}
      </main>

      {/* Navegação inferior mobile */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 bg-surface border-t border-line flex justify-around py-2 px-1 z-30">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 px-2 py-1 text-[11px] ${
                isActive ? "text-accent font-medium" : "text-muted"
              }`
            }
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
