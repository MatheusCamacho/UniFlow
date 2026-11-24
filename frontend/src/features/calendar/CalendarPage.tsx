import { FormEvent, useEffect, useState } from "react";
import { Lock, Plus, Trash2 } from "lucide-react";
import { apiFetch, formatDateTime } from "../../lib/api";
import { CalendarEvent } from "../../types";

export function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [title, setTitle] = useState("");
  const [eventType, setEventType] = useState<CalendarEvent["event_type"]>("exam");
  const [startAt, setStartAt] = useState("");
  const [endAt, setEndAt] = useState("");
  const [location, setLocation] = useState("");
  const [syncGoogle, setSyncGoogle] = useState(true);

  async function load() {
    setEvents(await apiFetch<CalendarEvent[]>("/events"));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!title.trim() || !startAt || !endAt) return;
    await apiFetch("/events", {
      method: "POST",
      body: JSON.stringify({
        title: title.trim(),
        event_type: eventType,
        all_day: false,
        start_at: new Date(startAt).toISOString(),
        end_at: new Date(endAt).toISOString(),
        location: location || null,
        sync_to_google: syncGoogle,
      }),
    });
    setTitle("");
    setLocation("");
    await load();
  }

  async function handleDelete(id: string) {
    await apiFetch(`/events/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <div className="space-y-8">
      <header className="pb-5 border-b border-line">
        <p className="text-xs uppercase tracking-[0.16em] text-muted">Compromissos</p>
        <h1 className="font-editorial text-3xl font-semibold mt-1">Calendário acadêmico</h1>
      </header>

      <form onSubmit={handleCreate} className="bg-surface border border-line p-5 space-y-4">
        <p className="text-xs uppercase tracking-wider text-muted">Novo evento local</p>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <input
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Título (ex.: Prova de Redes)"
            className="md:col-span-4 px-3 py-2 bg-paper border border-line text-sm"
          />
          <select
            value={eventType}
            onChange={(e) => setEventType(e.target.value as CalendarEvent["event_type"])}
            className="md:col-span-2 px-3 py-2 bg-paper border border-line text-sm"
          >
            <option value="class">Aula</option>
            <option value="exam">Prova</option>
            <option value="assignment">Trabalho</option>
            <option value="academic">Acadêmico</option>
            <option value="personal">Pessoal</option>
          </select>
          <input
            type="datetime-local"
            required
            value={startAt}
            onChange={(e) => setStartAt(e.target.value)}
            className="md:col-span-3 px-3 py-2 bg-paper border border-line text-sm"
          />
          <input
            type="datetime-local"
            required
            value={endAt}
            onChange={(e) => setEndAt(e.target.value)}
            className="md:col-span-3 px-3 py-2 bg-paper border border-line text-sm"
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-4">
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Local (opcional)"
              className="px-3 py-1.5 bg-paper border border-line text-xs"
            />
            <label className="inline-flex items-center gap-2 text-xs text-muted cursor-pointer">
              <input
                type="checkbox"
                checked={syncGoogle}
                onChange={(e) => setSyncGoogle(e.target.checked)}
                className="accent-accent"
              />
              Enviar para Google Calendar
            </label>
          </div>
          <button
            type="submit"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-surface text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            Agendar evento
          </button>
        </div>
      </form>

      <div className="divide-y divide-line border-t border-b border-line bg-surface">
        {events.length === 0 ? (
          <p className="p-6 text-sm text-muted">Nenhum evento cadastrado.</p>
        ) : (
          events.map((ev) => (
            <div key={ev.id} className="p-4 flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-medium text-ink">{ev.title}</p>
                  <span className="text-[11px] uppercase tracking-wider px-2 py-0.5 bg-paper border border-line text-muted">
                    {ev.event_type}
                  </span>
                  <span className="text-[11px] uppercase tracking-wider px-2 py-0.5 bg-accent-soft text-accent">
                    {ev.origin}
                  </span>
                  {ev.is_read_only && (
                    <span className="inline-flex items-center gap-1 text-[11px] text-muted">
                      <Lock className="w-3 h-3" /> Somente leitura
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted mt-1">
                  {ev.all_day
                    ? `Dia inteiro (${ev.start_date})`
                    : `${formatDateTime(ev.start_at)} — ${formatDateTime(ev.end_at)}`}
                  {ev.location ? ` · ${ev.location}` : ""}
                </p>
              </div>
              {!ev.is_read_only && (
                <button
                  onClick={() => handleDelete(ev.id)}
                  className="text-muted hover:text-danger p-1"
                  title="Excluir evento"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
