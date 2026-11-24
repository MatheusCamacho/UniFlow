const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

let csrfToken = "";

export function setCsrfToken(token: string) {
  csrfToken = token;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  const isFormData = init.body instanceof FormData;

  if (!isFormData && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (csrfToken && init.method && !["GET", "HEAD"].includes(init.method.toUpperCase())) {
    headers.set("X-CSRF-Token", csrfToken);
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!res.ok) {
    let detail = `Erro HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // ignora resposta não JSON
    }
    throw new Error(detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "Sem prazo";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}
