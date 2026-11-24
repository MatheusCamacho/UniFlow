import { FormEvent, useState } from "react";
import { apiFetch, setCsrfToken } from "../../lib/api";
import { User } from "../../types";

interface Props {
  onSuccess: (user: User) => void;
}

export function LoginPage({ onSuccess }: Props) {
  const [email, setEmail] = useState("estudante@uniflow.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await apiFetch<{ user: User; csrf_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setCsrfToken(res.csrf_token);
      onSuccess(res.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-paper">
      <div className="w-full max-w-md bg-surface border border-line p-8">
        <p className="text-[11px] uppercase tracking-[0.2em] text-muted">
          Personal Academic Management
        </p>
        <h1 className="font-editorial text-3xl font-semibold mt-1 text-ink">UniFlow</h1>
        <p className="text-sm text-muted mt-2 mb-6">
          Acesse sua central acadêmica pessoal.
        </p>

        {error && (
          <div className="mb-4 p-3 border border-danger/40 bg-danger/5 text-danger text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted mb-1">
              E-mail
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 bg-paper border border-line text-sm focus:outline-none focus:border-accent"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider text-muted mb-1">
              Senha
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2 bg-paper border border-line text-sm focus:outline-none focus:border-accent"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-accent text-surface text-sm font-medium hover:opacity-95 disabled:opacity-60 transition-opacity"
          >
            {loading ? "Entrando..." : "Entrar no UniFlow"}
          </button>
        </form>
      </div>
    </div>
  );
}
