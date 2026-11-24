import { useEffect, useState } from "react";
import { Bell, Check, RefreshCw } from "lucide-react";
import { apiFetch, formatDateTime } from "../../lib/api";
import { NotificationItem } from "../../types";

export function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [checking, setChecking] = useState(false);

  async function load() {
    setItems(await apiFetch<NotificationItem[]>("/notifications"));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCheckNow() {
    setChecking(true);
    try {
      await apiFetch("/integrations/deadlines/check", { method: "POST" });
      await load();
    } finally {
      setChecking(false);
    }
  }

  async function markRead(id: string) {
    await apiFetch(`/notifications/${id}/read`, { method: "PATCH" });
    await load();
  }

  return (
    <div className="space-y-8">
      <header className="pb-5 border-b border-line flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted">Alertas automatizados</p>
          <h1 className="font-editorial text-3xl font-semibold mt-1">Central de notificações</h1>
        </div>
        <button
          onClick={handleCheckNow}
          disabled={checking}
          className="inline-flex items-center gap-2 px-4 py-2 border border-line bg-surface text-sm hover:border-accent"
        >
          <RefreshCw className={`w-4 h-4 ${checking ? "animate-spin" : ""}`} />
          Avaliar prazos agora
        </button>
      </header>

      <div className="divide-y divide-line border-t border-b border-line bg-surface">
        {items.length === 0 ? (
          <div className="p-6 text-sm text-muted flex items-center gap-2">
            <Bell className="w-4 h-4" />
            Nenhuma notificação gerada até o momento.
          </div>
        ) : (
          items.map((n) => (
            <div
              key={n.id}
              className={`p-4 flex items-start justify-between gap-4 ${
                n.read_at ? "opacity-65" : ""
              }`}
            >
              <div>
                <p className="text-sm font-medium text-ink">{n.title}</p>
                <p className="text-xs text-muted mt-1">{n.body}</p>
                <p className="text-[11px] text-muted mt-1.5">
                  {formatDateTime(n.created_at)}
                  {n.webhook_sent ? " · Enviado ao Webhook" : ""}
                </p>
              </div>
              {!n.read_at && (
                <button
                  onClick={() => markRead(n.id)}
                  className="inline-flex items-center gap-1 text-xs text-accent hover:underline shrink-0"
                >
                  <Check className="w-3.5 h-3.5" /> Marcar lida
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
