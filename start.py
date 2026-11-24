"""
Inicializador automático do UniFlow (Windows, Linux e macOS — SEM Docker).
O que este script faz sozinho na primeira execução:
  1. Cria backend/.env a partir de .env.example com chaves seguras geradas na hora.
  2. Cria o ambiente virtual Python (backend/.venv) e instala requirements.txt.
  3. Inicializa o banco SQLite (backend/uniflow.db) e cria a conta inicial + dados demo.
  4. Instala as dependências do frontend (npm install) se necessário.
  5. Sobe simultaneamente API (FastAPI), Worker (APScheduler) e Frontend (Vite) e abre o navegador.
"""
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV_DIR = BACKEND / ".venv"
IS_WIN = os.name == "nt"


def venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if IS_WIN else "bin/python")


def npm_cmd() -> str:
    found = shutil.which("npm.cmd" if IS_WIN else "npm") or shutil.which("npm")
    if not found:
        print("[ERRO] Node.js/npm não encontrado no PATH.")
        print("       Instale o Node.js LTS em https://nodejs.org/ e execute novamente.")
        sys.exit(1)
    return found


def ensure_env_file() -> None:
    env_file = BACKEND / ".env"
    example = ROOT / ".env.example"
    if env_file.exists():
        return

    print("[1/4] Criando backend/.env com chaves de segurança geradas automaticamente...")
    content = example.read_text(encoding="utf-8")
    secret_key = secrets.token_urlsafe(32)
    content = content.replace("APP_SECRET_KEY=gerar_automaticamente", f"APP_SECRET_KEY={secret_key}")

    # Gera chave Fernet real usando o python da venv (ou fallback via cryptography depois)
    env_file.write_text(content, encoding="utf-8")


def fill_fernet_key_if_needed(py: Path) -> None:
    env_file = BACKEND / ".env"
    content = env_file.read_text(encoding="utf-8")
    if "TOKEN_ENCRYPTION_KEY=gerar_automaticamente" not in content:
        return
    fernet_key = subprocess.check_output(
        [str(py), "-c", "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"],
        text=True,
    ).strip()
    content = content.replace(
        "TOKEN_ENCRYPTION_KEY=gerar_automaticamente",
        f"TOKEN_ENCRYPTION_KEY={fernet_key}",
    )
    env_file.write_text(content, encoding="utf-8")


def ensure_backend() -> Path:
    py = venv_python()
    marker = VENV_DIR / ".deps_installed"

    if not py.exists():
        print("[2/4] Criando ambiente virtual Python em backend/.venv ...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

    if not marker.exists():
        print("[2/4] Instalando dependências do backend (só acontece na primeira vez)...")
        subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(BACKEND / "requirements.txt")])
        marker.write_text("ok", encoding="utf-8")

    fill_fernet_key_if_needed(py)

    print("[3/4] Preparando banco de dados local e conta inicial...")
    subprocess.check_call([str(py), str(BACKEND / "scripts" / "create_admin.py"), "--seed"], cwd=str(BACKEND))
    return py


def ensure_frontend(npm: str) -> None:
    if not (FRONTEND / "node_modules").exists():
        print("[4/4] Instalando dependências do frontend (npm install — só na primeira vez)...")
        subprocess.check_call([npm, "install"], cwd=str(FRONTEND))
    else:
        print("[4/4] Dependências do frontend já instaladas.")


def main() -> None:
    print("=" * 60)
    print("  UniFlow — Inicialização Automática (Sem Docker)")
    print("=" * 60)

    npm = npm_cmd()
    ensure_env_file()
    py = ensure_backend()
    ensure_frontend(npm)

    procs: list[subprocess.Popen] = []

    def stop_all(*_args):
        print("\nEncerrando UniFlow...")
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop_all)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_all)

    print("\nSubindo serviços...")
    api_proc = subprocess.Popen(
        [str(py), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=str(BACKEND),
    )
    procs.append(api_proc)

    worker_proc = subprocess.Popen(
        [str(py), "-m", "app.automation.worker"],
        cwd=str(BACKEND),
    )
    procs.append(worker_proc)

    front_proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=str(FRONTEND),
    )
    procs.append(front_proc)

    time.sleep(3)
    print("\n" + "=" * 60)
    print("  UniFlow pronto para uso!")
    print("  Frontend : http://localhost:5173")
    print("  API Docs : http://localhost:8000/docs")
    print("  Login    : estudante@uniflow.local")
    print("  Senha    : uniflow123")
    print("  (Pressione Ctrl+C nesta janela para encerrar tudo)")
    print("=" * 60 + "\n")

    try:
        webbrowser.open("http://localhost:5173")
    except Exception:
        pass

    try:
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"[AVISO] Um processo encerrou (código {p.returncode}). Encerrando os demais...")
                    stop_all()
            time.sleep(1)
    except KeyboardInterrupt:
        stop_all()


if __name__ == "__main__":
    main()
