# UniFlow — Especificação Executável do MVP (v1.1)

Este documento consolida o recorte executável da Especificação Técnica v1.0, otimizado para manter o sistema **100% compreensível linha por linha**, robusto em produção e diretamente alinhado aos 6 requisitos técnicos da disciplina de Automação e Programabilidade em Redes.

## Decisões de Engenharia do MVP

1. **Modelo de dados enxuto (10 tabelas):** `users`, `user_sessions`, `subjects`, `tasks`, `calendar_events`, `calendar_connections`, `calendar_sources`, `external_event_mappings`, `sync_runs` e `notifications`. Todas as entidades de domínio carregam `user_id` para suportar múltiplas contas no futuro.
2. **Worker separado da API:** o processo `app.automation.worker` roda `APScheduler` em container isolado e utiliza PostgreSQL Advisory Locks (`pg_try_advisory_lock`) para garantir execução única.
3. **Sincronização Google Calendar resiliente:**
   - Autenticação OAuth 2.0 server-side com `refresh_token` cifrado em repouso (Fernet).
   - Sincronização incremental via `syncToken` com recuperação automática de `HTTP 410 Gone`.
   - Retentativas com backoff exponencial em timeouts, `HTTP 429` e `HTTP 5xx`.
   - Prevenção de duplicação via tabela `external_event_mappings` + hash de conteúdo (`SHA-256`).
4. **Importação iCalendar (`.ics`) segura:**
   - Suporte a URL HTTPS e upload de arquivo `.ics`.
   - Cache condicional (`ETag` / `If-Modified-Since`).
   - Proteção contra SSRF bloqueando loopback, redes privadas e link-local.
   - Eventos marcados como `is_read_only = True`.
5. **Alertas confiáveis com deduplicação:**
   - Regras condicionais para 24h antes, 2h antes e tarefas atrasadas.
   - Chave única `deduplication_key` no banco impedindo spam.
   - Canal interno na interface + disparo opcional para Webhook (Discord/Telegram).
6. **Modo de simulação de falha para Live Demo:**
   - Endpoint dedicado permite simular erro transitório de rede/API (`503 Service Unavailable`) durante a apresentação, comprovando captura via `try/except`, backoff e registro no histórico `sync_runs`.
