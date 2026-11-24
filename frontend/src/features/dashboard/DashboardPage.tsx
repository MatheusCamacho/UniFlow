import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Calendar, CheckCircle2, Clock, RefreshCw } from "lucide-react";
import { apiFetch, formatDateTime } from "../../lib/api";
import { DashboardData, User } from "../../types";

export function DashboardPage({ user }: { user: User }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    const res = await apiFetch<DashboardData>("/dashboard");
    setData(res);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleQuickSync() {
    setSyncing(true);
    setNotice(null);
    try {
      await apiFetch("/integrations/google/sync", { method: "POST" });
      await apiFetch("/integrations/deadlines/check", { method: "POST" });
      await load();
      setNotice("Sincronização e verificação de prazos concluídas.");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Erro ao sincronizar.");
    } finally {
      setSyncing(false);
    }
  }

  const todayLabel = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());

  return (
    <div className="space-y-8">
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-6 border-b border-line">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted capitalize">
            {todayLabel}
          </p>
          <h1 className="font-editorial text-3xl sm:text-4xl font-semibold text-ink mt-1">
            O que preciso fazer hoje, {user.display_name.split(" ")[0]}?
          </h1>
        </div>
        <button
          onClick={handleQuickSync}
          disabled={syncing}
          className="inline-flex items-center gap-2 px-4 py-2 border border-line bg-surface text-sm text-ink hover:border-accent transition-colors self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "Sincronizando..." : "Sincronizar agora"}
        </button>
      </header>

      {notice && (
        <div className="px-4 py-3 border border-accent/30 bg-accent-soft text-accent text-sm">
          {notice}
        </div>
      )}

      {!data ? (
        <p className="text-sm text-muted">Carregando resumo acadêmico...</p>
      ) : (
        <>
          {/* Indicadores semanais */}
          <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-surface border border-line p-4">
              <p className="text-xs uppercase tracking-wider text-muted">Pendentes</p>
              <p className="font-editorial text-3xl mt-1">{data.weekly_pending}</p>
            </div>
            <div className="bg-surface border border-line p-4">
              <p className="text-xs uppercase tracking-wider text-muted">Atrasadas</p>
              <p className={`font-editorial text-3xl mt-1 ${data.overdue_count > 0 ? "text-danger" : ""}`}>
                {data.overdue_count}
              </p>
            </div>
            <div className="bg-surface border border-line p-4">
              <p className="text-xs uppercase tracking-wider text-muted">Concluídas (7d)</p>
              <p className="font-editorial text-3xl mt-1 text-success">{data.weekly_completed}</p>
            </div>
            <div className="bg-surface border border-line p-4">
              <p className="text-xs uppercase tracking-wider text-muted">Google Calendar</p>
              <p className="text-sm font-medium mt-2 capitalize">
                {data.google_status.connection_status === "connected" ? (
                  <span className="text-success">Conectado</span>
                ) : (
                  <Link to="/integrations" className="text-accent underline">
                    {data.google_status.connection_status}
                  </Link>
                )}
              </p>
            </div>
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Coluna esquerda: Atrasadas e próximas tarefas */}
            <div className="lg:col-span-7 space-y-6">
              {data.overdue_tasks.length > 0 && (
                <section>
                  <h2 className="font-editorial text-xl font-semibold text-danger flex items-center gap-2 mb-3">
                    <AlertCircle className="w-5 h-5" />
                    Tarefas atrasadas
                  </h2>
                  <div className="divide-y divide-line border-t border-b border-line bg-surface">
                    {data.overdue_tasks.map((t) => (
                      <div key={t.id} className="p-4 flex justify-between items-start gap-4">
                        <div>
                          <p className="text-sm font-medium text-ink">{t.title}</p>
                          <p className="text-xs text-muted mt-0.5">
                            {t.subject?.name || "Sem disciplina"} · {t.priority}
                          </p>
                        </div>
                        <span className="text-xs text-danger whitespace-nowrap">
                          {formatDateTime(t.due_at)}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              <section>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-editorial text-xl font-semibold">Próximos prazos</h2>
                  <Link to="/tasks" className="text-xs text-accent hover:underline">
                    Ver todas
                  </Link>
                </div>
                {data.upcoming_tasks.length === 0 ? (
                  <div className="p-6 border border-line bg-surface text-sm text-muted flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-success" />
                    Nenhuma tarefa pendente no momento.
                  </div>
                ) : (
                  <div className="divide-y divide-line border-t border-b border-line bg-surface">
                    {data.upcoming_tasks.map((t) => (
                      <div key={t.id} className="p-4 flex justify-between items-start gap-4">
                        <div>
                          <p className="text-sm font-medium text-ink">{t.title}</p>
                          <p className="text-xs text-muted mt-0.5">
                            {t.subject?.name || "Geral"} · prioridade {t.priority}
                            {t.sync_due_to_google ? " · Google Sync" : ""}
                          </p>
                        </div>
                        <span className="text-xs text-muted whitespace-nowrap flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          {formatDateTime(t.due_at)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>

            {/* Coluna direita: Agenda de hoje */}
            <div className="lg:col-span-5">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-editorial text-xl font-semibold flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-accent" />
                  Agenda de hoje
                </h2>
                <Link to="/calendar" className="text-xs text-accent hover:underline">
                  Abrir calendário
                </Link>
              </div>
              {data.today_events.length === 0 ? (
                <div className="p-6 border border-line bg-surface text-sm text-muted">
                  Nenhum compromisso agendado para hoje.
                </div>
              ) : (
                <div className="divide-y divide-line border-t border-b border-line bg-surface">
                  {data.today_events.map((ev) => (
                    <div key={ev.id} className="p-4">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium">{ev.title}</p>
                        <span className="text-[11px] uppercase tracking-wider px-2 py-0.5 bg-paper border border-line text-muted">
                          {ev.origin}
                        </span>
                      </div>
                      <p className="text-xs text-muted mt-1">
                        {ev.all_day ? "Dia inteiro" : formatDateTime(ev.start_at)}
                        {ev.location ? ` · ${ev.location}` : ""}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
