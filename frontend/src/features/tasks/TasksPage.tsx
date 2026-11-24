import { FormEvent, useEffect, useState } from "react";
import { Check, Plus, Trash2 } from "lucide-react";
import { apiFetch, formatDateTime } from "../../lib/api";
import { Subject, Task } from "../../types";

export function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [title, setTitle] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [priority, setPriority] = useState<Task["priority"]>("normal");
  const [dueAt, setDueAt] = useState("");
  const [syncGoogle, setSyncGoogle] = useState(true);
  const [filterStatus, setFilterStatus] = useState("");

  async function load() {
    const query = filterStatus ? `?status_filter=${filterStatus}` : "";
    const [t, s] = await Promise.all([
      apiFetch<Task[]>(`/tasks${query}`),
      apiFetch<Subject[]>("/subjects"),
    ]);
    setTasks(t);
    setSubjects(s);
  }

  useEffect(() => {
    load();
  }, [filterStatus]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    await apiFetch("/tasks", {
      method: "POST",
      body: JSON.stringify({
        title: title.trim(),
        subject_id: subjectId || null,
        priority,
        due_at: dueAt ? new Date(dueAt).toISOString() : null,
        sync_due_to_google: syncGoogle,
      }),
    });
    setTitle("");
    setDueAt("");
    await load();
  }

  async function toggleDone(task: Task) {
    const nextStatus = task.status === "completed" ? "pending" : "completed";
    await apiFetch(`/tasks/${task.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: nextStatus }),
    });
    await load();
  }

  async function handleDelete(id: string) {
    await apiFetch(`/tasks/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <div className="space-y-8">
      <header className="pb-5 border-b border-line flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted">Organização</p>
          <h1 className="font-editorial text-3xl font-semibold mt-1">Tarefas e trabalhos</h1>
        </div>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 bg-surface border border-line text-sm"
        >
          <option value="">Todos os estados</option>
          <option value="pending">Pendentes</option>
          <option value="in_progress">Em andamento</option>
          <option value="completed">Concluídas</option>
        </select>
      </header>

      <form onSubmit={handleCreate} className="bg-surface border border-line p-5 space-y-4">
        <p className="text-xs uppercase tracking-wider text-muted">Nova entrega ou atividade</p>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <input
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex.: Entregar documentação da API REST"
            className="md:col-span-5 px-3 py-2 bg-paper border border-line text-sm"
          />
          <select
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            className="md:col-span-3 px-3 py-2 bg-paper border border-line text-sm"
          >
            <option value="">Disciplina (opcional)</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as Task["priority"])}
            className="md:col-span-2 px-3 py-2 bg-paper border border-line text-sm"
          >
            <option value="low">Baixa</option>
            <option value="normal">Normal</option>
            <option value="high">Alta</option>
            <option value="urgent">Urgente</option>
          </select>
          <input
            type="datetime-local"
            value={dueAt}
            onChange={(e) => setDueAt(e.target.value)}
            className="md:col-span-2 px-3 py-2 bg-paper border border-line text-sm"
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="inline-flex items-center gap-2 text-xs text-muted cursor-pointer">
            <input
              type="checkbox"
              checked={syncGoogle}
              onChange={(e) => setSyncGoogle(e.target.checked)}
              className="accent-accent"
            />
            Criar evento no calendário e sincronizar prazo com Google Calendar
          </label>
          <button
            type="submit"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-surface text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            Adicionar tarefa
          </button>
        </div>
      </form>

      <div className="divide-y divide-line border-t border-b border-line bg-surface">
        {tasks.length === 0 ? (
          <p className="p-6 text-sm text-muted">Nenhuma tarefa encontrada.</p>
        ) : (
          tasks.map((task) => (
            <div key={task.id} className="p-4 flex items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <button
                  onClick={() => toggleDone(task)}
                  aria-label="Alternar conclusão"
                  className={`mt-0.5 w-5 h-5 border flex items-center justify-center shrink-0 ${
                    task.status === "completed"
                      ? "bg-success border-success text-surface"
                      : "border-muted/50 hover:border-accent"
                  }`}
                >
                  {task.status === "completed" && <Check className="w-3.5 h-3.5" />}
                </button>
                <div>
                  <p
                    className={`text-sm font-medium ${
                      task.status === "completed" ? "line-through text-muted" : "text-ink"
                    }`}
                  >
                    {task.title}
                  </p>
                  <p className="text-xs text-muted mt-0.5">
                    {task.subject?.name || "Geral"} · {task.priority} · {formatDateTime(task.due_at)}
                    {task.sync_due_to_google ? " · Sync Google" : ""}
                  </p>
                </div>
              </div>
              <button
                onClick={() => handleDelete(task.id)}
                className="text-muted hover:text-danger p-1"
                title="Excluir tarefa"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
