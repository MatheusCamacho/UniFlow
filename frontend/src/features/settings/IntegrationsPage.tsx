import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { AlertTriangle, Link2, RefreshCw, Trash2, Upload } from "lucide-react";
import { apiFetch, formatDateTime } from "../../lib/api";
import { CalendarSource, GoogleStatus, SyncRun } from "../../types";

export function IntegrationsPage() {
  const [google, setGoogle] = useState<GoogleStatus | null>(null);
  const [sources, setSources] = useState<CalendarSource[]>([]);
  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [icsName, setIcsName] = useState("");
  const [icsUrl, setIcsUrl] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const [g, s, r] = await Promise.all([
      apiFetch<GoogleStatus>("/integrations/google/status"),
      apiFetch<CalendarSource[]>("/integrations/ics"),
      apiFetch<SyncRun[]>("/integrations/sync-runs"),
    ]);
    setGoogle(g);
    setSources(s);
    setRuns(r);
  }

  useEffect(() => {
    load();
  }, []);

  async function connectGoogle() {
    try {
      const res = await apiFetch<{ auth_url: string }>("/integrations/google/connect");
      window.location.href = res.auth_url;
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Erro ao iniciar OAuth.");
    }
  }

  async function disconnectGoogle() {
    await apiFetch("/integrations/google/disconnect", { method: "POST" });
    await load();
  }

  async function runGoogleSync(simulateFailure = false) {
    setBusy(true);
    setFeedback(null);
    try {
      const run = await apiFetch<SyncRun>(
        `/integrations/google/sync?simulate_failure=${simulateFailure}`,
        { method: "POST" }
      );
      setFeedback(
        run.status === "failed"
          ? `Falha capturada com resiliência: ${run.error_summary}`
          : `Sync Google concluído (+${run.items_created} / ~${run.items_updated} / -${run.items_deleted}).`
      );
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function handleAddIcsUrl(e: FormEvent) {
    e.preventDefault();
    setFeedback(null);
    try {
      const run = await apiFetch<SyncRun>("/integrations/ics/url", {
        method: "POST",
        body: JSON.stringify({ name: icsName, url: icsUrl }),
      });
      setIcsName("");
      setIcsUrl("");
      setFeedback(`Feed ICS importado: +${run.items_created} eventos.`);
      await load();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Erro ao cadastrar ICS.");
    }
  }

  async function handleUploadIcs(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("name", file.name);
    form.append("file", file);
    setFeedback(null);
    try {
      const run = await apiFetch<SyncRun>("/integrations/ics/upload", {
        method: "POST",
        body: form,
      });
      setFeedback(`Arquivo .ics processado: +${run.items_created} novos, ${run.items_unchanged} inalterados.`);
      await load();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Falha no upload .ics.");
    } finally {
      e.target.value = "";
    }
  }

  async function deleteSource(id: string) {
    await apiFetch(`/integrations/ics/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <div className="space-y-8">
      <header className="pb-5 border-b border-line">
        <p className="text-xs uppercase tracking-[0.16em] text-muted">Motor de automação</p>
        <h1 className="font-editorial text-3xl font-semibold mt-1">
          Integrações e histórico de sincronização
        </h1>
      </header>

      {feedback && (
        <div className="p-4 border border-accent/30 bg-accent-soft text-accent text-sm">
          {feedback}
        </div>
      )}

      {/* Bloco Google Calendar */}
      <section className="bg-surface border border-line p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="font-editorial text-xl font-semibold">Google Calendar (Bidirecional)</h2>
            <p className="text-xs text-muted mt-1">
              Status: <strong className="text-ink">{google?.connection_status || "..."}</strong>
              {google?.last_synced_at ? ` · Última sync: ${formatDateTime(google.last_synced_at)}` : ""}
            </p>
            {google?.last_error && (
              <p className="text-xs text-danger mt-1">{google.last_error}</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {google?.connection_status === "connected" ? (
              <button
                onClick={disconnectGoogle}
                className="px-3 py-2 border border-line text-xs text-danger hover:bg-danger/5"
              >
                Desconectar
              </button>
            ) : (
              <button
                onClick={connectGoogle}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-surface text-xs font-medium"
              >
                <Link2 className="w-3.5 h-3.5" /> Conectar Google
              </button>
            )}
            <button
              onClick={() => runGoogleSync(false)}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-line text-xs hover:border-accent"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${busy ? "animate-spin" : ""}`} />
              Sincronizar agora
            </button>
            <button
              onClick={() => runGoogleSync(true)}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-danger/40 text-xs text-danger hover:bg-danger/5"
              title="Simula erro HTTP 503 para demonstrar resiliência na Live Demo"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              Simular falha (Demo)
            </button>
          </div>
        </div>
      </section>

      {/* Bloco ICS */}
      <section className="bg-surface border border-line p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-editorial text-xl font-semibold">
              Calendários acadêmicos (iCalendar .ics)
            </h2>
            <p className="text-xs text-muted mt-1">
              Importação somente leitura via URL HTTPS (anti-SSRF) ou upload de arquivo .ics.
            </p>
          </div>
          <label className="inline-flex items-center gap-2 px-4 py-2 border border-line bg-paper text-xs font-medium cursor-pointer hover:border-accent self-start">
            <Upload className="w-3.5 h-3.5" />
            Importar arquivo .ics
            <input type="file" accept=".ics,text/calendar" onChange={handleUploadIcs} className="hidden" />
          </label>
        </div>

        <form onSubmit={handleAddIcsUrl} className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <input
            type="text"
            required
            value={icsName}
            onChange={(e) => setIcsName(e.target.value)}
            placeholder="Nome da fonte (ex.: Calendário UniSenac)"
            className="md:col-span-4 px-3 py-2 bg-paper border border-line text-sm"
          />
          <input
            type="url"
            required
            value={icsUrl}
            onChange={(e) => setIcsUrl(e.target.value)}
            placeholder="https://instituicao.edu.br/calendario.ics"
            className="md:col-span-6 px-3 py-2 bg-paper border border-line text-sm"
          />
          <button
            type="submit"
            className="md:col-span-2 px-4 py-2 bg-accent text-surface text-xs font-medium"
          >
            Adicionar URL
          </button>
        </form>

        {sources.length > 0 && (
          <div className="divide-y divide-line border-t border-line">
            {sources.map((src) => (
              <div key={src.id} className="py-3 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium">{src.name}</p>
                  <p className="text-xs text-muted">
                    Tipo: {src.source_type} · Última leitura: {formatDateTime(src.last_fetched_at)}
                    {src.last_error ? ` · Erro: ${src.last_error}` : ""}
                  </p>
                </div>
                <button
                  onClick={() => deleteSource(src.id)}
                  className="text-muted hover:text-danger p-1"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Histórico Sync Runs */}
      <section className="space-y-3">
        <h2 className="font-editorial text-xl font-semibold">Histórico de execuções (sync_runs)</h2>
        <div className="overflow-x-auto bg-surface border border-line">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-muted uppercase tracking-wider">
              <tr>
                <th className="py-3 px-4">Provedor</th>
                <th className="py-3 px-4">Gatilho</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Alterações</th>
                <th className="py-3 px-4">Início</th>
                <th className="py-3 px-4">Detalhe</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-5 px-4 text-muted">
                    Nenhuma execução registrada ainda.
                  </td>
                </tr>
              ) : (
                runs.map((r) => (
                  <tr key={r.id}>
                    <td className="py-3 px-4 font-medium uppercase">{r.provider}</td>
                    <td className="py-3 px-4 text-muted">{r.trigger}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`font-medium ${
                          r.status === "completed"
                            ? "text-success"
                            : r.status === "failed"
                            ? "text-danger"
                            : "text-accent"
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-muted">
                      +{r.items_created} / ~{r.items_updated} / -{r.items_deleted}
                    </td>
                    <td className="py-3 px-4 text-muted">{formatDateTime(r.started_at)}</td>
                    <td className="py-3 px-4 text-muted max-w-xs truncate">
                      {r.error_summary || "OK"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
