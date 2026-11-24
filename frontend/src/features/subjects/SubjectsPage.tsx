import { FormEvent, useEffect, useState } from "react";
import { Archive, Plus } from "lucide-react";
import { apiFetch } from "../../lib/api";
import { Subject } from "../../types";

const PALETTE = ["#365D73", "#52745D", "#8A6B42", "#7C4D59", "#4F5D6B", "#6A5B7B"];

export function SubjectsPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [name, setName] = useState("");
  const [professor, setProfessor] = useState("");
  const [term, setTerm] = useState("2026/2");
  const [color, setColor] = useState(PALETTE[0]);

  async function load() {
    setSubjects(await apiFetch<Subject[]>("/subjects"));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await apiFetch("/subjects", {
      method: "POST",
      body: JSON.stringify({ name: name.trim(), professor: professor || null, term: term || null, color }),
    });
    setName("");
    setProfessor("");
    await load();
  }

  async function handleArchive(id: string) {
    await apiFetch(`/subjects/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <div className="space-y-8">
      <header className="pb-5 border-b border-line">
        <p className="text-xs uppercase tracking-[0.16em] text-muted">Estrutura letiva</p>
        <h1 className="font-editorial text-3xl font-semibold mt-1">Disciplinas</h1>
      </header>

      <form onSubmit={handleCreate} className="bg-surface border border-line p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Nome da disciplina"
            className="md:col-span-5 px-3 py-2 bg-paper border border-line text-sm"
          />
          <input
            type="text"
            value={professor}
            onChange={(e) => setProfessor(e.target.value)}
            placeholder="Professor(a)"
            className="md:col-span-4 px-3 py-2 bg-paper border border-line text-sm"
          />
          <input
            type="text"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="Semestre (ex: 2026/2)"
            className="md:col-span-3 px-3 py-2 bg-paper border border-line text-sm"
          />
        </div>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">Cor:</span>
            {PALETTE.map((hex) => (
              <button
                key={hex}
                type="button"
                onClick={() => setColor(hex)}
                style={{ backgroundColor: hex }}
                className={`w-5 h-5 rounded-full ${
                  color === hex ? "ring-2 ring-offset-2 ring-ink" : ""
                }`}
              />
            ))}
          </div>
          <button
            type="submit"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-surface text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            Criar disciplina
          </button>
        </div>
      </form>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {subjects.map((s) => (
          <div key={s.id} className="bg-surface border border-line p-5 flex justify-between items-start gap-4">
            <div className="flex gap-3">
              <span
                className="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0"
                style={{ backgroundColor: s.color }}
              />
              <div>
                <h2 className="font-editorial text-lg font-semibold leading-snug">{s.name}</h2>
                <p className="text-xs text-muted mt-1">
                  {s.professor || "Docente não informado"} {s.term ? `· ${s.term}` : ""}
                </p>
              </div>
            </div>
            <button
              onClick={() => handleArchive(s.id)}
              title="Arquivar disciplina"
              className="text-muted hover:text-danger p-1"
            >
              <Archive className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
