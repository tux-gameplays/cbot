import os
import logging
import subprocess
from datetime import datetime
from Modulos.webhooks import registrar_log_normal

def criar_backup_manual(pasta_backup: str, pasta_src: str, pasta_memorias: str, fuso_brt) -> str:
    if not pasta_backup or not pasta_src or not pasta_memorias:
        return None
    if not os.path.exists(pasta_src) or not os.path.exists(pasta_memorias):
        return None

    os.makedirs(pasta_backup, exist_ok=True)
    hoje = datetime.now(fuso_brt).strftime("%Y-%m-%d")
    contador = 1

    while True:
        nome_pasta = f"{hoje}_{contador}"
        caminho_novo_backup = os.path.join(pasta_backup, nome_pasta)
        if not os.path.exists(caminho_novo_backup):
            break
        if backup_identico(caminho_novo_backup, pasta_src, pasta_memorias):
            return None
        contador += 1

    try:
        import shutil
        os.makedirs(caminho_novo_backup, exist_ok=True)
        shutil.copytree(pasta_src, os.path.join(caminho_novo_backup, "Codigo"))
        shutil.copytree(pasta_memorias, os.path.join(caminho_novo_backup, "Memoria"))
        return nome_pasta
    except Exception as e:
        logging.error(f"Erro ao criar backup: {e}")
        return None

def backup_identico(pasta_backup: str, pasta_src: str, pasta_memorias: str) -> bool:
    if not os.path.exists(pasta_backup):
        return False
    try:
        if not pastas_identicas(pasta_src, os.path.join(pasta_backup, "Codigo")):
            return False
        if not pastas_identicas(pasta_memorias, os.path.join(pasta_backup, "Memoria")):
            return False
        return True
    except Exception:
        return False

def pastas_identicas(pasta1: str, pasta2: str) -> bool:
    if not os.path.exists(pasta2):
        return False
    try:
        for root, dirs, files in os.walk(pasta1):
            rel_path = os.path.relpath(root, pasta1)
            pasta2_equiv = os.path.join(pasta2, rel_path) if rel_path != "." else pasta2
            if not os.path.exists(pasta2_equiv):
                return False
            for arquivo in files:
                caminho1 = os.path.join(root, arquivo)
                caminho2 = os.path.join(pasta2_equiv, arquivo)
                if not os.path.exists(caminho2):
                    return False
                with open(caminho1, "rb") as f1, open(caminho2, "rb") as f2:
                    if f1.read() != f2.read():
                        return False
        return True
    except Exception:
        return False

async def backup_automatico(pasta_backup: str, pasta_src: str, pasta_memorias: str, fuso_brt, webhook_logs: str):
    if not pasta_backup or not pasta_src or not pasta_memorias:
        return
    if not os.path.exists(pasta_src) or not os.path.exists(pasta_memorias):
        return

    hoje = datetime.now(fuso_brt).strftime("%Y-%m-%d")

    if os.path.exists(pasta_backup):
        for item in os.listdir(pasta_backup):
            if item.startswith(hoje):
                if backup_identico(os.path.join(pasta_backup, item), pasta_src, pasta_memorias):
                    return

    resultado = criar_backup_manual(pasta_backup, pasta_src, pasta_memorias, fuso_brt)
    if resultado:
        await registrar_log_normal(f"💾 Backup automático criado: {resultado}", tipo="sucesso", webhook_logs=webhook_logs)

def fazer_git_commit(pasta_raiz: str, mensagem: str = "Atualiza projeto") -> bool:
    try:
        logging.info(f"📦 Git: tentando commit em {pasta_raiz}")
        os.chdir(pasta_raiz)
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        logging.info(f"📦 Git: output status = '{result.stdout.strip()}'")

        if not result.stdout.strip():
            logging.info("📦 Git: nenhuma alteração encontrada")
            return False

        logging.info("📦 Git: fazendo add...")
        subprocess.run(["git", "add", "."], capture_output=True)
        logging.info("📦 Git: fazendo commit...")
        subprocess.run(["git", "commit", "-m", mensagem], capture_output=True)
        logging.info("📦 Git: fazendo push...")
        push_result = subprocess.run(["git", "push"], capture_output=True, text=True)
        logging.info(f"📦 Git: push result = {push_result.returncode}")

        return push_result.returncode == 0
    except Exception as e:
        logging.error(f"❌ Erro ao fazer commit Git: {e}")
        return False

async def git_auto_commit(pasta_raiz: str, webhook_logs: str):
    resultado = fazer_git_commit(pasta_raiz)
    if resultado:
        logging.info("📦 Git: alterações enviadas automaticamente")
        await registrar_log_normal("📦 Git: alterações enviadas automaticamente", tipo="sucesso", webhook_logs=webhook_logs)
    elif resultado is False:
        logging.info("📦 Git: nenhuma alteração encontrada")
