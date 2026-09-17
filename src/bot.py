import discord
from discord.ext import commands, tasks
import logging
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta, timezone
import re

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)

logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)
logging.getLogger("discord.client").setLevel(logging.WARNING)
logging.getLogger("discord.voice").setLevel(logging.CRITICAL)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="c+", intents=intents)
bot.help_command = None

HORA_INICIO = None
ULTIMO_CODIGO_EM = None

TOKEN = os.getenv("TOKEN")
CODIGO_ANTECIPADO = int(os.getenv("CODIGO_ANTECIPADO", 0))
CODIGO_PUBLICO = int(os.getenv("CODIGO_PUBLICO", 0))
SEU_GUILD_ID = int(os.getenv("ID_SERVER"))
ADMINISTRADOR = int(os.getenv("Administrador"))
VIP = int(os.getenv("Vip"))
AMIGOS = int(os.getenv("Amigos"))
CALL_LIVE = int(os.getenv("Call_Live"))
CALL_RECONECTAR = int(os.getenv("Call_Reconectar"))

WEBHOOK_CODIGOS = os.getenv("CODIGO_SALAS")
WEBHOOK_LOGS = os.getenv("LOGS_GERAIS")
WEBHOOK_ANTECIPADO = os.getenv("CODIGO_SALAS_ANTECIPADO")
WEBHOOK_LOGS_CODIGOS = os.getenv("LOGS_CODIGOS")
WEBHOOK_LEMBRETE_CHAT = os.getenv("LEMBRETE_CHAT")
WEBHOOK_LOGS_PAINEL = os.getenv("LOGS_PAINEL")
WEBHOOK_ENTRADA = os.getenv("ENTRADA")

CANAL_BANCO = int(os.getenv("CANAL_BANCO", 0))
BOT_BANCO_ID = int(os.getenv("BOT_BANCO_ID", 0))
WEBHOOK_BANCO = os.getenv("BANCO")

ARQUIVO_VIPS = os.getenv("ARQUIVO_VIPS")
ARQUIVO_AMIGOS = os.getenv("ARQUIVO_AMIGOS")
ARQUIVO_WARNS = os.getenv("ARQUIVO_WARNS")
ARQUIVO_TIMERS = os.getenv("ARQUIVO_TIMERS")

ARQUIVO_BANCO_AV = os.getenv("ARQUIVO_AV_BANCO")

PASTA_BACKUP = os.getenv("PASTA_BACKUP")
if not PASTA_BACKUP and ARQUIVO_VIPS:
    PASTA_BACKUP = os.path.join(os.path.dirname(ARQUIVO_VIPS), "Backups")

PASTA_COD = os.getenv("PASTA_COD")
PASTA_MEMORIAS = os.getenv("PASTA_MEMORIAS")

SERVIDOR_DEVS = int(os.getenv("SERVIDOR_DOS_DEVS", 0))
CARGO_DEVS = int(os.getenv("CARGO_DOS_DEVS", 0))
FUSO_BRT = timezone(timedelta(hours=-3))
ROLE_PING_LEMBRETE = "<@&1541614789808361593>"


# ---------- Webhooks ----------

_webhook_nome_cache: dict[str, str] = {}

async def obter_nome_webhook(url: str) -> str:
    if url in _webhook_nome_cache:
        return _webhook_nome_cache[url]
    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(url, session=session)
            info = await webhook.fetch()
            nome = info.name or "Sala do Chip"
            _webhook_nome_cache[url] = nome
            return nome
    except Exception:
        return "Sala do Chip"

async def enviar_webhook(url: str, conteudo: str = "", embed: discord.Embed = None,
                         username: str = None, avatar_url: str = None, wait: bool = False):
    if username is None:
        username = await obter_nome_webhook(url)
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(url, session=session)
        return await webhook.send(
            content=conteudo,
            embed=embed,
            username=username,
            avatar_url=avatar_url,
            wait=wait
        )

async def apagar_webhook_msg(url: str, msg_id: int):
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(url, session=session)
        try:
            await webhook.delete_message(msg_id)
            return True
        except discord.NotFound:
            return False
        except Exception as e:
            logging.error(f"Erro ao apagar mensagem webhook: {e}")
            return False

CORES_LOG = {
    "sucesso": discord.Color.green(),
    "info": discord.Color.blurple(),
    "aviso": discord.Color.orange(),
    "erro": discord.Color.red(),
    "neutro": discord.Color.greyple()
}

EMOJIS_LOG = {
    "sucesso": "✅",
    "info": "ℹ️",
    "aviso": "⚠️",
    "erro": "❌",
    "neutro": "🕒"
}

def montar_embed_log(texto: str, tipo: str) -> discord.Embed:
    embed = discord.Embed(
        description=f"{EMOJIS_LOG.get(tipo, 'ℹ️')} {texto}",
        color=CORES_LOG.get(tipo, discord.Color.blurple())
    )
    embed.timestamp = datetime.now(timezone.utc)
    return embed

async def registrar_log_normal(texto: str, tipo: str = "info"):
    logging.info(texto)
    if WEBHOOK_LOGS:
        try:
            await enviar_webhook(WEBHOOK_LOGS, embed=montar_embed_log(texto, tipo))
        except Exception as e:
            logging.error(f"Erro ao enviar log geral via webhook: {e}")

async def registrar_log_codigo(texto: str, tipo: str = "info"):
    logging.info(texto)
    if WEBHOOK_LOGS_CODIGOS:
        try:
            await enviar_webhook(WEBHOOK_LOGS_CODIGOS, embed=montar_embed_log(texto, tipo))
        except Exception as e:
            logging.error(f"Erro ao enviar log de código via webhook: {e}")

async def registrar_log_painel(embed: discord.Embed):
    if WEBHOOK_LOGS_PAINEL:
        try:
            await enviar_webhook(WEBHOOK_LOGS_PAINEL, embed=embed)
        except Exception as e:
            logging.error(f"Erro ao enviar log do painel via webhook: {e}")

async def enviar_ou_editar(destino, embed: discord.Embed, view: discord.ui.View):
    if isinstance(destino, discord.Interaction):
        try:
            await destino.response.edit_message(embed=embed, view=view)
        except discord.NotFound:
            logging.warning("Interação expirou antes de editar a mensagem.")
    else:
        await destino.send(embed=embed, view=view)


# ---------- VIP: persistência ----------

def carregar_vips():
    if not os.path.exists(ARQUIVO_VIPS):
        return {"usuarios": {}}
    try:
        with open(ARQUIVO_VIPS, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"usuarios": {}}

def salvar_vips(dados):
    with open(ARQUIVO_VIPS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def consultar_vip(user_id: int):
    dados = carregar_vips()
    return dados.get("usuarios", {}).get(str(user_id), {"vip": False})

def atualizar_info_usuario(dados: dict, user_id: int, membro: discord.Member = None):
    """Atualiza apelido e nome do usuário no JSON se necessário (máximo 1x por hora)"""
    user_id_str = str(user_id)
    if user_id_str not in dados["usuarios"]:
        dados["usuarios"][user_id_str] = {}
    
    usuario = dados["usuarios"][user_id_str]
    agora = datetime.now(timezone.utc).isoformat()
    
    # Verifica se precisa atualizar (máximo a cada 1 hora)
    ultima_atualizacao = usuario.get("ultima_atualizacao_info", "1970-01-01T00:00:00")
    tempo_desde_update = (datetime.now(timezone.utc) - datetime.fromisoformat(ultima_atualizacao)).total_seconds()
    
    if tempo_desde_update >= 3600 or "apelido" not in usuario:  # 3600 = 1 hora
        if membro:
            usuario["apelido"] = membro.display_name
            usuario["nome_usuario"] = membro.name
        usuario["ultima_atualizacao_info"] = agora
    
    return dados

async def atribuir_cargo_vip(user_id: int):
    guild = bot.get_guild(SEU_GUILD_ID)
    if guild is None:
        await registrar_log_normal(f"Guild não encontrada ao tentar dar cargo VIP a {user_id}.", tipo="erro")
        return
    cargo = guild.get_role(VIP)
    membro = guild.get_member(user_id)
    if membro is None:
        try:
            membro = await guild.fetch_member(user_id)
        except discord.NotFound:
            membro = None
    if cargo and membro:
        try:
            await membro.add_roles(cargo, reason="VIP ativado")
        except Exception as e:
            await registrar_log_normal(f"Erro ao dar cargo VIP a {user_id}: {e}", tipo="erro")

async def remover_cargo_vip(user_id: int):
    guild = bot.get_guild(SEU_GUILD_ID)
    if guild is None:
        await registrar_log_normal(f"Guild não encontrada ao tentar tirar cargo VIP de {user_id}.", tipo="erro")
        return
    cargo = guild.get_role(VIP)
    membro = guild.get_member(user_id)
    if membro is None:
        try:
            membro = await guild.fetch_member(user_id)
        except discord.NotFound:
            membro = None
    if cargo and membro:
        try:
            await membro.remove_roles(cargo, reason="VIP desativado")
        except Exception as e:
            await registrar_log_normal(f"Erro ao tirar cargo VIP de {user_id}: {e}", tipo="erro")

async def adicionar_vip(user_id: int, dias: int = None):
    dados = carregar_vips()
    usuarios = dados.get("usuarios", {})
    agora = datetime.now(FUSO_BRT)
    info = usuarios.get(str(user_id), {})
    ja_tinha_vip = info.get("vip", False)
    ja_eterno = ja_tinha_vip and info.get("expira_em") is None
    ativo_em = info.get("ativo_em") if ja_tinha_vip else agora.isoformat()

    if dias is None:
        usuarios[str(user_id)] = {
            "vip": True,
            "ativo_em": ativo_em,
            "expira_em": None,
            "eterno": True
        }
    elif ja_eterno:
        pass
    else:
        base = agora
        if ja_tinha_vip and info.get("expira_em"):
            expira_atual = datetime.fromisoformat(info["expira_em"])
            if expira_atual > agora:
                base = expira_atual
        usuarios[str(user_id)] = {
            "vip": True,
            "ativo_em": ativo_em,
            "expira_em": (base + timedelta(days=dias)).isoformat(),
            "eterno": False
        }


    dados["usuarios"] = usuarios
    
    # Atualizar apelido e nome do usuário
    guild = bot.get_guild(SEU_GUILD_ID)
    if guild:
        membro = guild.get_member(user_id)
        if membro is None:
            try:
                membro = await guild.fetch_member(user_id)
            except discord.NotFound:
                membro = None
        dados = atualizar_info_usuario(dados, user_id, membro)
    
    salvar_vips(dados)
    if not ja_tinha_vip:
        await atribuir_cargo_vip(user_id)

async def remover_vip(user_id: int):
    dados = carregar_vips()
    usuarios = dados.get("usuarios", {})
    if str(user_id) in usuarios:
        usuarios[str(user_id)]["vip"] = False
        usuarios[str(user_id)]["expira_em"] = None
        usuarios[str(user_id)]["eterno"] = False
    dados["usuarios"] = usuarios
    salvar_vips(dados)
    await remover_cargo_vip(user_id)

async def setar_tempo_vip(user_id: int, dias: int):
    dados = carregar_vips()
    usuarios = dados.get("usuarios", {})
    info = usuarios.get(str(user_id), {})
    ja_tinha_vip = info.get("vip", False)
    agora = datetime.now(FUSO_BRT)
    ativo_em = info.get("ativo_em") if ja_tinha_vip else agora.isoformat()

    usuarios[str(user_id)] = {
        "vip": True,
        "ativo_em": ativo_em,
        "expira_em": (agora + timedelta(days=dias)).isoformat(),
        "eterno": False
    }

    dados["usuarios"] = usuarios
    salvar_vips(dados)
    if not ja_tinha_vip:
        await atribuir_cargo_vip(user_id)

async def remover_tempo_vip(user_id: int, dias: int):
    dados = carregar_vips()
    usuarios = dados.get("usuarios", {})
    info = usuarios.get(str(user_id))

    if not info or not info.get("vip"):
        return "sem_vip"
    if info.get("expira_em") is None:
        return "eterno"

    expira = datetime.fromisoformat(info["expira_em"])
    nova_expira = expira - timedelta(days=dias)
    agora = datetime.now(FUSO_BRT)

    if nova_expira <= agora:
        info["vip"] = False
        info["expira_em"] = None
        info["eterno"] = False
        resultado = "desativado"
    else:
        info["expira_em"] = nova_expira.isoformat()
        resultado = "reduzido"

    usuarios[str(user_id)] = info
    dados["usuarios"] = usuarios
    salvar_vips(dados)

    if resultado == "desativado":
        await remover_cargo_vip(user_id)
    return resultado

async def checar_vips_expirados():
    dados = carregar_vips()
    usuarios = dados.get("usuarios", {})
    agora = datetime.now(FUSO_BRT)
    expirados = []

    for user_id, info in usuarios.items():
        if info.get("vip") and info.get("expira_em"):
            if datetime.fromisoformat(info["expira_em"]) <= agora:
                info["vip"] = False
                info["expira_em"] = None
                info["eterno"] = False
                expirados.append(user_id)

    if expirados:
        dados["usuarios"] = usuarios
        salvar_vips(dados)
        for user_id in expirados:
            await remover_cargo_vip(int(user_id))

    return expirados

@tasks.loop(minutes=5)
async def loop_verificar_vips():
    expirados = await checar_vips_expirados()
    if expirados:
        await registrar_log_normal("Um ou mais VIPs expiraram e foram desativados automaticamente.", tipo="neutro")
        embed_log = discord.Embed(
            title="⌛ VIPs expirados automaticamente",
            description="\n".join(f"<@{uid}>" for uid in expirados),
            color=discord.Color.dark_grey()
        )
        await registrar_log_painel(embed_log)

    warns_expirados = checar_warns_expirados()
    if warns_expirados:
        embed_log_warns = discord.Embed(
            title="⌛ Warns expirados automaticamente",
            description="\n".join(f"#{w['id']} — <@{w['user_id']}>" for w in warns_expirados),
            color=discord.Color.dark_grey()
        )
        await registrar_log_painel(embed_log_warns)


# ---------- Amigos: persistência ----------

def carregar_amigos():
    if not os.path.exists(ARQUIVO_AMIGOS):
        return {"usuarios": {}}
    try:
        with open(ARQUIVO_AMIGOS, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"usuarios": {}}

def salvar_amigos(dados):
    with open(ARQUIVO_AMIGOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def consultar_amigo(user_id: int):
    dados = carregar_amigos()
    return dados.get("usuarios", {}).get(str(user_id), {"amigo": False})

async def atribuir_cargo_amigo(user_id: int):
    guild = bot.get_guild(SEU_GUILD_ID)
    if guild is None:
        await registrar_log_normal(f"Guild não encontrada ao tentar dar cargo de Amigo a {user_id}.", tipo="erro")
        return
    cargo = guild.get_role(AMIGOS)
    membro = guild.get_member(user_id)
    if membro is None:
        try:
            membro = await guild.fetch_member(user_id)
        except discord.NotFound:
            membro = None
    if cargo and membro:
        try:
            await membro.add_roles(cargo, reason="Amigo adicionado")
        except Exception as e:
            await registrar_log_normal(f"Erro ao dar cargo de Amigo a {user_id}: {e}", tipo="erro")

async def remover_cargo_amigo(user_id: int):
    guild = bot.get_guild(SEU_GUILD_ID)
    if guild is None:
        await registrar_log_normal(f"Guild não encontrada ao tentar tirar cargo de Amigo de {user_id}.", tipo="erro")
        return
    cargo = guild.get_role(AMIGOS)
    membro = guild.get_member(user_id)
    if membro is None:
        try:
            membro = await guild.fetch_member(user_id)
        except discord.NotFound:
            membro = None
    if cargo and membro:
        try:
            await membro.remove_roles(cargo, reason="Amigo removido")
        except Exception as e:
            await registrar_log_normal(f"Erro ao tirar cargo de Amigo de {user_id}: {e}", tipo="erro")

async def adicionar_amigo(user_id: int):
    dados = carregar_amigos()
    usuarios = dados.get("usuarios", {})
    usuarios[str(user_id)] = {"amigo": True}
    dados["usuarios"] = usuarios
    salvar_amigos(dados)
    await atribuir_cargo_amigo(user_id)

async def remover_amigo(user_id: int):
    dados = carregar_amigos()
    usuarios = dados.get("usuarios", {})
    if str(user_id) in usuarios:
        usuarios[str(user_id)]["amigo"] = False
    dados["usuarios"] = usuarios
    salvar_amigos(dados)
    await remover_cargo_amigo(user_id)


# ---------- Warns: persistência ----------

DIAS_EXPIRACAO_WARN = 60

TEMPOS_TIMEOUT = {
    1: timedelta(minutes=30),
    2: timedelta(hours=1),
    3: timedelta(days=1)
}

def carregar_warns():
    if not ARQUIVO_WARNS or not os.path.exists(ARQUIVO_WARNS):
        return {"proximo_id": 1, "warns": {}}
    try:
        with open(ARQUIVO_WARNS, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("proximo_id", 1)
            dados.setdefault("warns", {})
            return dados
    except json.JSONDecodeError:
        return {"proximo_id": 1, "warns": {}}

def salvar_warns(dados):
    with open(ARQUIVO_WARNS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def warns_ativos_do_usuario(user_id: int):
    dados = carregar_warns()
    return [
        w for w in dados["warns"].values()
        if str(w.get("user_id")) == str(user_id) and w.get("status") == "ativo"
    ]

def criar_warn(user_id: int, autor_id: int, motivo: str, eterno: bool):
    dados = carregar_warns()
    novo_id = dados["proximo_id"]
    agora = datetime.now(FUSO_BRT)

    warn = {
        "id": novo_id,
        "user_id": user_id,
        "autor_id": autor_id,
        "motivo": motivo,
        "eterno": eterno,
        "criado_em": agora.isoformat(),
        "expira_em": None if eterno else (agora + timedelta(days=DIAS_EXPIRACAO_WARN)).isoformat(),
        "status": "ativo"
    }

    dados["warns"][str(novo_id)] = warn
    dados["proximo_id"] = novo_id + 1
    salvar_warns(dados)
    return warn

def remover_warn(warn_id: int):
    dados = carregar_warns()
    warn = dados["warns"].get(str(warn_id))
    if not warn or warn.get("status") != "ativo":
        return None
    warn["status"] = "removido"
    warn["removido_em"] = datetime.now(FUSO_BRT).isoformat()
    dados["warns"][str(warn_id)] = warn
    salvar_warns(dados)
    return warn

def checar_warns_expirados():
    dados = carregar_warns()
    agora = datetime.now(FUSO_BRT)
    expirados = []

    for warn in dados["warns"].values():
        if warn.get("status") == "ativo" and warn.get("expira_em"):
            if datetime.fromisoformat(warn["expira_em"]) <= agora:
                warn["status"] = "expirado"
                expirados.append(warn)

    if expirados:
        salvar_warns(dados)

    return expirados

async def aplicar_punicao_progressao(guild: discord.Guild, user_id: int, quantidade_ativos: int):
    membro = guild.get_member(user_id)
    if membro is None:
        try:
            membro = await guild.fetch_member(user_id)
        except discord.NotFound:
            membro = None

    if membro is None:
        return f"Membro {user_id} não encontrado no servidor para aplicar punição."

    try:
        if quantidade_ativos in TEMPOS_TIMEOUT:
            await membro.timeout(TEMPOS_TIMEOUT[quantidade_ativos], reason=f"Warn #{quantidade_ativos}")
            return f"Timeout de {TEMPOS_TIMEOUT[quantidade_ativos]} aplicado a {membro.mention}."

        elif quantidade_ativos == 4:
            await remover_vip(user_id)
            await remover_amigo(user_id)
            await membro.kick(reason="4º warn - remoção de cargos e kick automático")
            return f"{membro.mention} perdeu VIP, Amigos e foi expulso do servidor (4º warn)."

        elif quantidade_ativos >= 5:
            await guild.ban(membro, reason="5º warn - ban automático")
            return f"{membro.mention} foi banido permanentemente (5º warn)."

    except Exception as e:
        return f"Erro ao aplicar punição a {user_id}: {e}"

    return None


# ---------- Backup com data e contador ----------

def criar_backup_manual() -> str:
    """Cria backup manual com Codigo e Memoria em pasta com data"""
    if not PASTA_BACKUP or not PASTA_COD or not PASTA_MEMORIAS:
        return None
    
    if not os.path.exists(PASTA_COD) or not os.path.exists(PASTA_MEMORIAS):
        return None
    
    os.makedirs(PASTA_BACKUP, exist_ok=True)
    
    # Gera nome da pasta: 2026-09-11_1, 2026-09-11_2, etc
    hoje = datetime.now(FUSO_BRT).strftime("%Y-%m-%d")
    contador = 1
    
    while True:
        nome_pasta = f"{hoje}_{contador}"
        caminho_novo_backup = os.path.join(PASTA_BACKUP, nome_pasta)
        if not os.path.exists(caminho_novo_backup):
            break
        
        # Verifica se conteúdo é idêntico
        if backup_identico(caminho_novo_backup):
            return None  # Ignora se já existe igual
        
        contador += 1
    
    try:
        import shutil
        os.makedirs(caminho_novo_backup, exist_ok=True)
        
        # Copia Codigo
        shutil.copytree(PASTA_COD, os.path.join(caminho_novo_backup, "Codigo"))
        
        # Copia Memoria
        shutil.copytree(PASTA_MEMORIAS, os.path.join(caminho_novo_backup, "Memoria"))
        
        return nome_pasta
    except Exception as e:
        logging.error(f"Erro ao criar backup: {e}")
        return None

def backup_identico(pasta_backup: str) -> bool:
    """Verifica se a pasta de backup tem exatamente o mesmo conteúdo que Codigo+Memoria"""
    if not os.path.exists(pasta_backup):
        return False
    
    try:
        # Compara Codigo
        pasta_cod_backup = os.path.join(pasta_backup, "Codigo")
        if not pastas_identicas(PASTA_COD, pasta_cod_backup):
            return False
        
        # Compara Memoria
        pasta_mem_backup = os.path.join(pasta_backup, "Memoria")
        if not pastas_identicas(PASTA_MEMORIAS, pasta_mem_backup):
            return False
        
        return True
    except Exception:
        return False

def pastas_identicas(pasta1: str, pasta2: str) -> bool:
    """Verifica se duas pastas têm exatamente o mesmo conteúdo"""
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

async def backup_automatico():
    """Chamado no on_ready pra fazer backup automático"""
    if not PASTA_BACKUP or not PASTA_COD or not PASTA_MEMORIAS:
        return
    
    if not os.path.exists(PASTA_COD) or not os.path.exists(PASTA_MEMORIAS):
        return
    
    hoje = datetime.now(FUSO_BRT).strftime("%Y-%m-%d")
    
    # Verifica se já existe backup de hoje
    if os.path.exists(PASTA_BACKUP):
        for item in os.listdir(PASTA_BACKUP):
            if item.startswith(hoje):
                # Verifica se conteúdo é idêntico
                if backup_identico(os.path.join(PASTA_BACKUP, item)):
                    return  # Ignora se já existe igual
    
    # Cria novo backup automático
    resultado = criar_backup_manual()
    if resultado:
        await registrar_log_normal(f"💾 Backup automático criado: {resultado}", tipo="sucesso")


# ---------- Estado do banco (última mensagem processada) ----------

def carregar_banco_state():
    if not ARQUIVO_BANCO_AV or not os.path.exists(ARQUIVO_BANCO_AV):
        return {"ultima_msg_id": None}
    try:
        with open(ARQUIVO_BANCO_AV, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"ultima_msg_id": None}

def salvar_banco_state(msg_id: int):
    if not ARQUIVO_BANCO_AV:
        return
    with open(ARQUIVO_BANCO_AV, "w", encoding="utf-8") as f:
        json.dump({"ultima_msg_id": msg_id}, f)

async def processar_msg_banco(message: discord.Message):
    if not message.embeds:
        return

    embed = message.embeds[0]
    descricao = embed.description or ""

    if "You have used 1 💎 VIP" not in descricao:
        return

    descricao_upper = descricao.upper()
    if "ETERNO" in descricao_upper:
        dias = None
    elif "VIP 30" in descricao_upper:
        dias = 30
    elif "VIP 7" in descricao_upper:
        dias = 7
    elif "VIP 1" in descricao_upper:
        dias = 1
    else:
        dias = None

    user_id = None
    if embed.author and embed.author.icon_url:
        match = re.search(r"/avatars/(\d+)/", embed.author.icon_url)
        if match:
            user_id = int(match.group(1))

    if user_id:
        await adicionar_vip(user_id, dias)

        label_tempo = "Eterno" if dias is None else f"{dias} dia(s)"

        embed_confirmacao = discord.Embed(
            title="💎 VIP ativado com sucesso!",
            description=f"<@{user_id}>, seu VIP de **{label_tempo}** foi ativado automaticamente.",
            color=discord.Color.green()
        )
        if WEBHOOK_BANCO:
            await enviar_webhook(WEBHOOK_BANCO, conteudo=f"<@{user_id}>", embed=embed_confirmacao)
        else:
            canal = bot.get_channel(CANAL_BANCO)
            if canal:
                await canal.send(content=f"<@{user_id}>", embed=embed_confirmacao)

        embed_log = discord.Embed(
            title="💎 VIP adicionado automaticamente",
            description=f"VIP de <@{user_id}> adicionado automaticamente após compra no banco.",
            color=discord.Color.green()
        )
        embed_log.add_field(name="Tempo", value=label_tempo, inline=True)
        embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
        await registrar_log_painel(embed_log)
    else:
        await registrar_log_normal(
            "⚠️ VIP vendido no banco mas não foi possível identificar o comprador pelo embed.",
            tipo="aviso"
        )

    salvar_banco_state(message.id)

async def retomar_msgs_banco():
    if not CANAL_BANCO or not BOT_BANCO_ID:
        return

    canal = bot.get_channel(CANAL_BANCO)
    if canal is None:
        return

    state = carregar_banco_state()
    ultima_id = state.get("ultima_msg_id")

    kwargs = {"limit": 50}
    if ultima_id:
        kwargs["after"] = discord.Object(id=ultima_id)

    try:
        msgs = [m async for m in canal.history(**kwargs)]
        msgs.sort(key=lambda m: m.id)

        pendentes = [
            m for m in msgs
            if m.author.id == BOT_BANCO_ID
            and m.embeds
            and "You have used 1 💎 VIP" in (m.embeds[0].description or "")
        ]

        for m in pendentes:
            await processar_msg_banco(m)

        if pendentes:
            await registrar_log_normal(
                f"🏦 {len(pendentes)} compra(s) de VIP processada(s) retroativamente ao ligar.",
                tipo="sucesso"
            )
    except Exception as e:
        await registrar_log_normal(f"Erro ao retomar mensagens do banco: {e}", tipo="erro")


# ---------- Timers persistentes dos códigos ----------

def carregar_timers():
    if not ARQUIVO_TIMERS or not os.path.exists(ARQUIVO_TIMERS):
        return {"codigos": {}}
    try:
        with open(ARQUIVO_TIMERS, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"codigos": {}}

def salvar_timers(dados):
    with open(ARQUIVO_TIMERS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def salvar_timer_codigo(chave: str, job: dict):
    dados = carregar_timers()
    dados.setdefault("codigos", {})[chave] = job
    salvar_timers(dados)

def remover_timer_codigo(chave: str):
    dados = carregar_timers()
    codigos = dados.setdefault("codigos", {})
    if chave in codigos:
        del codigos[chave]
        salvar_timers(dados)

def montar_embed_codigo(job: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"Sala do {job.get('autor_apelido', job['autor_nome'])}",
        description=job["conteudo"],
        color=discord.Color.blue()
    )
    embed.set_author(name=job["autor_nome"], icon_url=job.get("autor_avatar"))
    embed.timestamp = datetime.fromisoformat(job["criado_em"])
    embed.set_footer(text="Dica Mobile: Segure no código para copiar")
    return embed

async def aguardar_ate(timestamp_iso: str):
    alvo = datetime.fromisoformat(timestamp_iso)
    agora = datetime.now(FUSO_BRT)
    restante = (alvo - agora).total_seconds()
    if restante > 0:
        await asyncio.sleep(restante)

def agendar_job(chave: str, job: dict):
    salvar_timer_codigo(chave, job)
    bot.loop.create_task(aguardar_e_processar(chave, job))

async def aguardar_e_processar(chave: str, job: dict):
    await aguardar_ate(job["disparar_em"])

    # Relê o job do arquivo: pode ter sido removido/alterado enquanto esperava
    dados = carregar_timers()
    job_atual = dados.get("codigos", {}).get(chave)
    if job_atual is None:
        return

    await processar_job(chave, job_atual)

async def processar_job(chave: str, job: dict):
    tipo = job.get("tipo")

    try:
        if tipo == "antecipado_expira":
            if await apagar_webhook_msg(WEBHOOK_ANTECIPADO, job["antecipado_id"]):
                await registrar_log_codigo(f"Mensagem antecipada expirada (apagada): {job['conteudo']}", tipo="neutro")
            else:
                await registrar_log_codigo("Mensagem antecipada já apagada antes do timer.", tipo="aviso")

        elif tipo == "publicar":
            ainda_existe = True
            try:
                async with aiohttp.ClientSession() as session:
                    webhook = discord.Webhook.from_url(WEBHOOK_ANTECIPADO, session=session)
                    await webhook.fetch_message(job["antecipado_id"])
            except discord.NotFound:
                ainda_existe = False

            if not ainda_existe:
                await registrar_log_codigo("Mensagem antecipada já apagada, cancelando envio ao público.", tipo="aviso")
            else:
                embed = montar_embed_codigo(job)
                publico_msg = await enviar_webhook(
                    WEBHOOK_CODIGOS, embed=embed, username=f"Sala do {job.get('autor_apelido', job['autor_nome'])}", wait=True
                )
                await registrar_log_codigo(f"Mensagem enviada ao público: {job['conteudo']}", tipo="sucesso")

                agora = datetime.now(FUSO_BRT)
                agendar_job(f"publico_expira:{publico_msg.id}", {
                    "tipo": "publico_expira",
                    "publico_id": publico_msg.id,
                    "conteudo": job["conteudo"],
                    "disparar_em": (agora + timedelta(seconds=600)).isoformat()
                })
                agendar_job(f"lembrete:{publico_msg.id}", {
                    "tipo": "lembrete",
                    "conteudo": job["conteudo"],
                    "disparar_em": (agora + timedelta(seconds=15)).isoformat()
                })

        elif tipo == "publico_expira":
            if await apagar_webhook_msg(WEBHOOK_CODIGOS, job["publico_id"]):
                await registrar_log_codigo(f"Mensagem pública expirada (apagada): {job['conteudo']}", tipo="neutro")
            else:
                await registrar_log_codigo("Mensagem pública já apagada antes do timer.", tipo="aviso")

        elif tipo == "lembrete":
            lembrete_embed = discord.Embed(
                title="Lembrete enviar código chat live",
                description=job["conteudo"],
                color=discord.Color.red()
            )
            lembrete_msg = await enviar_webhook(
                WEBHOOK_LEMBRETE_CHAT,
                conteudo=ROLE_PING_LEMBRETE,
                embed=lembrete_embed,
                wait=True
            )
            await registrar_log_codigo(f"Lembrete enviado com ping para o código: {job['conteudo']}", tipo="sucesso")

            agora = datetime.now(FUSO_BRT)
            agendar_job(f"lembrete_apagar:{lembrete_msg.id}", {
                "tipo": "lembrete_apagar",
                "lembrete_id": lembrete_msg.id,
                "conteudo": job["conteudo"],
                "disparar_em": (agora + timedelta(seconds=180)).isoformat()
            })

        elif tipo == "lembrete_apagar":
            if await apagar_webhook_msg(WEBHOOK_LEMBRETE_CHAT, job["lembrete_id"]):
                await registrar_log_codigo(f"Lembrete expirado (apagado): {job['conteudo']}", tipo="neutro")
            else:
                await registrar_log_codigo("Lembrete já apagado antes do timer.", tipo="aviso")

    except Exception as e:
        await registrar_log_normal(f"Erro ao processar timer '{tipo}': {e}", tipo="erro")

    remover_timer_codigo(chave)

def retomar_timers_pendentes():
    dados = carregar_timers()
    for chave, job in dados.get("codigos", {}).items():
        bot.loop.create_task(aguardar_e_processar(chave, job))


@bot.event
async def on_ready():
    global HORA_INICIO
    HORA_INICIO = datetime.now(timezone.utc)
    await registrar_log_normal(f"Bot logado como {bot.user}", tipo="sucesso")
    try:
        guild = discord.Object(id=SEU_GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        logging.info(f"Comandos slash sincronizados na guild {SEU_GUILD_ID}: {len(synced)}")
    except Exception as e:
        logging.error(f"Erro ao sincronizar comandos slash: {e}")

    await checar_vips_expirados()
    if not loop_verificar_vips.is_running():
        loop_verificar_vips.start()

    retomar_timers_pendentes()
    await retomar_msgs_banco()
    await backup_automatico()

@bot.event
async def on_member_remove(member: discord.Member):
    if member.guild.id != SEU_GUILD_ID:
        return

    dados_vip = consultar_vip(member.id)
    if dados_vip.get("vip"):
        dados = carregar_vips()
        usuarios = dados.get("usuarios", {})
        usuarios[str(member.id)]["vip"] = False
        usuarios[str(member.id)]["expira_em"] = None
        usuarios[str(member.id)]["eterno"] = False
        dados["usuarios"] = usuarios
        salvar_vips(dados)

        embed_log = discord.Embed(
            title="💎 VIP perdido (saiu do servidor)",
            description=f"{member.mention} saiu do servidor e perdeu o VIP definitivamente.",
            color=discord.Color.red()
        )
        embed_log.add_field(name="ID do usuário", value=str(member.id), inline=True)
        await registrar_log_painel(embed_log)

@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != SEU_GUILD_ID:
        return

    dados_amigo = consultar_amigo(member.id)
    if dados_amigo.get("amigo"):
        await atribuir_cargo_amigo(member.id)

        embed_log = discord.Embed(
            title="👥 Cargo de Amigo restaurado",
            description=f"{member.mention} voltou ao servidor e o cargo de Amigo foi restaurado automaticamente.",
            color=discord.Color.teal()
        )
        embed_log.add_field(name="ID do usuário", value=str(member.id), inline=True)
        await registrar_log_painel(embed_log)
    if WEBHOOK_ENTRADA:
        try:
            msg_entrada = await enviar_webhook(
                WEBHOOK_ENTRADA,
                conteudo=f"Clique aqui {member.display_name} 👋 {member.mention}",
                wait=True
            )
            await asyncio.sleep(10)
            await apagar_webhook_msg(WEBHOOK_ENTRADA, msg_entrada.id)
        except Exception as e:
            await registrar_log_normal(f"Erro ao enviar ping de entrada para {member.id}: {e}", tipo="erro")


@bot.event
async def on_message(message: discord.Message):
    global ULTIMO_CODIGO_EM

    eh_bot_banco = (
        BOT_BANCO_ID != 0
        and message.author.id == BOT_BANCO_ID
        and message.channel.id == CANAL_BANCO
    )

    if message.author.bot and message.author != bot.user and not eh_bot_banco:
        return

    if message.channel.id == CODIGO_ANTECIPADO:
        if ULTIMO_CODIGO_EM is not None:
            decorrido = (datetime.now(timezone.utc) - ULTIMO_CODIGO_EM).total_seconds()
            if decorrido < 3:
                try:
                    await message.delete()
                except Exception:
                    pass
                return

        if len(message.content) == 6 and " " not in message.content and message.content.isupper():
            conteudo = message.content
            autor_nome = f"{message.author.display_name} - {message.author.name}"
            autor_avatar = message.author.avatar.url if message.author.avatar else None
            criado_em = datetime.now(timezone.utc).isoformat()

            embed = discord.Embed(
                title=f"Sala do {message.author.display_name}",
                description=conteudo,
                color=discord.Color.blue()
            )
            embed.set_author(name=autor_nome, icon_url=autor_avatar)
            embed.timestamp = datetime.now(timezone.utc)
            embed.set_footer(text="Dica Mobile: Segure no código para copiar")

            try:
                await message.delete()
                antecipado_msg = await enviar_webhook(
                    WEBHOOK_ANTECIPADO, embed=embed, username=f"Sala do {message.author.display_name}", wait=True
                )
                antecipado_id = antecipado_msg.id
                ULTIMO_CODIGO_EM = datetime.now(timezone.utc)
                await registrar_log_codigo(f"Mensagem reenviada no antecipado: {conteudo}", tipo="info")
            except Exception as e:
                await registrar_log_normal(f"Erro ao reenviar mensagem antecipada: {e}", tipo="erro")
                return

            agora = datetime.now(FUSO_BRT)
            info_base = {
                "conteudo": conteudo,
                "autor_nome": autor_nome,
                "autor_apelido": message.author.display_name,
                "autor_avatar": autor_avatar,
                "criado_em": criado_em,
                "antecipado_id": antecipado_id
            }

            agendar_job(f"publicar:{antecipado_id}", {
                **info_base,
                "tipo": "publicar",
                "disparar_em": (agora + timedelta(seconds=30)).isoformat()
            })
            agendar_job(f"antecipado_expira:{antecipado_id}", {
                **info_base,
                "tipo": "antecipado_expira",
                "disparar_em": (agora + timedelta(seconds=600)).isoformat()
            })

        else:
            try:
                await message.delete()
                await registrar_log_codigo(f"Mensagem inválida apagada no antecipado: {message.content}", tipo="aviso")
            except Exception as e:
                await registrar_log_normal(f"Erro ao apagar mensagem inválida: {e}", tipo="erro")

    elif message.channel.id == CODIGO_PUBLICO:
        if len(message.content) == 6 and " " not in message.content and message.content.isupper():
            conteudo = message.content
            autor_nome = f"{message.author.display_name} - {message.author.name}"
            autor_avatar = message.author.avatar.url if message.author.avatar else None
            criado_em = datetime.now(timezone.utc).isoformat()

            embed = discord.Embed(
                title=f"Sala do {message.author.display_name}",
                description=conteudo,
                color=discord.Color.blue()
            )
            embed.set_author(name=autor_nome, icon_url=autor_avatar)
            embed.timestamp = datetime.now(timezone.utc)
            embed.set_footer(text="Dica Mobile: Segure no código para copiar")

            try:
                await message.delete()
                publico_msg = await enviar_webhook(
                    WEBHOOK_CODIGOS, embed=embed, username=f"Sala do {message.author.display_name}", wait=True
                )
                await registrar_log_codigo(f"Mensagem enviada direto ao público: {conteudo}", tipo="sucesso")
            except Exception as e:
                await registrar_log_normal(f"Erro ao reenviar mensagem direta no público: {e}", tipo="erro")
                return

            agora = datetime.now(FUSO_BRT)
            agendar_job(f"publico_expira:{publico_msg.id}", {
                "tipo": "publico_expira",
                "publico_id": publico_msg.id,
                "conteudo": conteudo,
                "disparar_em": (agora + timedelta(seconds=600)).isoformat()
            })
            agendar_job(f"lembrete:{publico_msg.id}", {
                "tipo": "lembrete",
                "conteudo": conteudo,
                "disparar_em": (agora + timedelta(seconds=15)).isoformat()
            })

        else:
            try:
                await message.delete()
                await registrar_log_codigo(f"Mensagem inválida apagada no público: {message.content}", tipo="aviso")
            except Exception as e:
                await registrar_log_normal(f"Erro ao apagar mensagem inválida: {e}", tipo="erro")

    elif (
        message.channel.id == CANAL_BANCO
        and BOT_BANCO_ID != 0
        and message.author.id == BOT_BANCO_ID
    ):
        await processar_msg_banco(message)

    await bot.process_commands(message)


# ---------- Painel ----------

def gerar_painel_inicial():
    embed = discord.Embed(
        title="🎲 Painel de Controle",
        description="Escolha uma das opções abaixo para gerenciar o servidor.",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="💎 VIP",
        value="Adicione, remova ou acompanhe o VIP de um usuário.",
        inline=False
    )
    embed.add_field(
        name="👥 Amigos",
        value="Dê ou tire o cargo de Amigo próximo de um usuário.",
        inline=False
    )
    embed.add_field(
        name="🎙️ Call",
        value="Controle entrada, fala e quem está na call live.",
        inline=False
    )
    return embed

class PainelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PainelSelectInicial())

def montar_view_selecionar_alvo(tipo: str) -> discord.ui.View:
    view = discord.ui.View()

    select = discord.ui.UserSelect(placeholder="Escolha um membro do servidor...")

    async def select_callback(interaction: discord.Interaction):
        membro = select.values[0]
        await abrir_gerenciamento_por_tipo(interaction, tipo, membro.id, membro)

    select.callback = select_callback
    view.add_item(select)

    botao_manual = discord.ui.Button(label="Digitar ID manualmente", style=discord.ButtonStyle.secondary)

    async def manual_callback(interaction: discord.Interaction):
        if tipo == "vip":
            await interaction.response.send_modal(VIPModal())
        elif tipo == "amigo":
            await interaction.response.send_modal(AmigoModal())
        elif tipo == "warn":
            await interaction.response.send_modal(WarnModal())

    botao_manual.callback = manual_callback
    view.add_item(botao_manual)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        embed_voltar = gerar_painel_inicial()
        await interaction_voltar.response.edit_message(embed=embed_voltar, view=PainelView())
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    return view

async def abrir_gerenciamento_por_tipo(interaction: discord.Interaction, tipo: str, user_id: int, user: discord.User = None):
    if tipo == "vip":
        if user and user.bot:
            await interaction.response.send_message(
                f"🚫 O usuário {user.mention} é um bot e não pode ter VIP.",
                ephemeral=True
            )
            return
        dados_vip = consultar_vip(user_id)
        await mostrar_gerenciar_vip(interaction, user_id, dados_vip.get("vip", False), user=user)
    elif tipo == "amigo":
        if user and user.bot:
            await interaction.response.send_message(
                f"🚫 O usuário {user.mention} é um bot e não pode ter o cargo de Amigo.",
                ephemeral=True
            )
            return
        await mostrar_gerenciar_amigo(interaction, user_id, user=user)
    elif tipo == "warn":
        await mostrar_gerenciar_warns(interaction, user_id)

class PainelSelectInicial(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="💎 VIP", description="Gerenciar VIP de um usuário"),
            discord.SelectOption(label="👥 Amigos", description="Gerenciar cargo de Amigo próximo"),
            discord.SelectOption(label="🎙️ Call", description="Gerenciar a call live"),
            discord.SelectOption(label="⚠️ Warns", description="Gerenciar warns de um usuário")
        ]
        super().__init__(placeholder="Escolha uma seção...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "💎 VIP":
            embed = discord.Embed(
                title="💎 Escolher usuário",
                description="Selecione um membro do servidor, ou digite o ID manualmente se a pessoa já saiu.",
                color=discord.Color.gold()
            )
            await interaction.response.edit_message(embed=embed, view=montar_view_selecionar_alvo("vip"))
        elif self.values[0] == "👥 Amigos":
            embed = discord.Embed(
                title="👥 Escolher usuário",
                description="Selecione um membro do servidor, ou digite o ID manualmente se a pessoa já saiu.",
                color=discord.Color.teal()
            )
            await interaction.response.edit_message(embed=embed, view=montar_view_selecionar_alvo("amigo"))
        elif self.values[0] == "🎙️ Call":
            await mostrar_gerenciar_call(interaction)
        elif self.values[0] == "⚠️ Warns":
            embed = discord.Embed(
                title="⚠️ Escolher usuário",
                description="Selecione um membro do servidor, ou digite o ID manualmente.",
                color=discord.Color.orange()
            )
            await interaction.response.edit_message(embed=embed, view=montar_view_selecionar_alvo("warn"))

class WarnModal(discord.ui.Modal, title="⚠️ Gerenciar Warns"):
    usuario_id = discord.ui.TextInput(
        label="ID do usuário",
        placeholder="Digite o ID do usuário",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.usuario_id.value)
        except ValueError:
            await interaction.response.send_message("🚫 ID inválido.", ephemeral=True)
            return

        await mostrar_gerenciar_warns(interaction, user_id)

async def mostrar_gerenciar_warns(interaction: discord.Interaction, user_id: int):
    checar_warns_expirados()
    ativos = sorted(warns_ativos_do_usuario(user_id), key=lambda w: w["id"])

    embed = discord.Embed(
        title="⚠️ Gerenciar Warns",
        description=f"👤 <@{user_id}>",
        color=discord.Color.orange() if ativos else discord.Color.greyple()
    )

    if ativos:
        linhas = [f"{'♾️' if w.get('eterno') else '⏳'} **#{w['id']}** — {w['motivo']}" for w in ativos]
        embed.add_field(name=f"Warns ativos ({len(ativos)})", value="\n".join(linhas)[:1024], inline=False)
    else:
        embed.add_field(name="Warns ativos", value="Nenhum.", inline=False)

    view = discord.ui.View()

    botao_warn = discord.ui.Button(label="Dar Warn", style=discord.ButtonStyle.red)
    botao_ewarn = discord.ui.Button(label="Dar Warn Eterno", style=discord.ButtonStyle.danger)

    async def warn_callback(interaction_btn: discord.Interaction):
        await interaction_btn.response.send_modal(WarnMotivoModal(user_id, eterno=False))

    async def ewarn_callback(interaction_btn: discord.Interaction):
        await interaction_btn.response.send_modal(WarnMotivoModal(user_id, eterno=True))

    botao_warn.callback = warn_callback
    botao_ewarn.callback = ewarn_callback
    view.add_item(botao_warn)
    view.add_item(botao_ewarn)

    if ativos:
        botao_remover_ultimo = discord.ui.Button(label="Remover Último Warn", style=discord.ButtonStyle.secondary)

        async def remover_ultimo_callback(interaction_btn: discord.Interaction):
            ultimo = max(ativos, key=lambda w: w["id"])
            warn_removido = remover_warn(ultimo["id"])
            if warn_removido:
                embed_log = discord.Embed(
                    title="🗑️ Warn removido",
                    description=f"{interaction_btn.user.mention} removeu o warn #{ultimo['id']} de <@{user_id}> pelo painel.",
                    color=discord.Color.red()
                )
                await registrar_log_painel(embed_log)
            await mostrar_gerenciar_warns(interaction_btn, user_id)

        botao_remover_ultimo.callback = remover_ultimo_callback
        view.add_item(botao_remover_ultimo)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        embed_voltar = gerar_painel_inicial()
        await interaction_voltar.response.edit_message(embed=embed_voltar, view=PainelView())
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await enviar_ou_editar(interaction, embed, view)

class WarnMotivoModal(discord.ui.Modal, title="⚠️ Motivo do Warn"):
    motivo = discord.ui.TextInput(
        label="Motivo",
        placeholder="Descreva o motivo do warn",
        required=True,
        style=discord.TextStyle.paragraph
    )

    def __init__(self, user_id: int, eterno: bool):
        super().__init__()
        self.user_id = user_id
        self.eterno = eterno

    async def on_submit(self, interaction: discord.Interaction):
        warn_criado = criar_warn(self.user_id, interaction.user.id, self.motivo.value, self.eterno)
        quantidade_ativos = len(warns_ativos_do_usuario(self.user_id))

        resultado_punicao = await aplicar_punicao_progressao(interaction.guild, self.user_id, quantidade_ativos)

        embed_log = discord.Embed(
            title="⚠️ Warn aplicado" if not self.eterno else "♾️ Warn eterno aplicado",
            description=f"{interaction.user.mention} aplicou um warn em <@{self.user_id}> (#{warn_criado['id']}) pelo painel.",
            color=discord.Color.orange()
        )
        embed_log.add_field(name="Motivo", value=self.motivo.value, inline=False)
        embed_log.add_field(name="Warns ativos", value=str(quantidade_ativos), inline=True)
        if resultado_punicao:
            embed_log.add_field(name="Punição automática", value=resultado_punicao, inline=False)
        await registrar_log_painel(embed_log)

        await mostrar_gerenciar_warns(interaction, self.user_id)

class VIPModal(discord.ui.Modal, title="💎 Gerenciar VIP"):
    usuario_id = discord.ui.TextInput(
        label="ID do usuário",
        placeholder="Digite o ID do usuário",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = int(self.usuario_id.value)

        user = await interaction.client.fetch_user(user_id)

        if user.bot:
            await interaction.response.send_message(
                f"🚫 O usuário {user.mention} é um bot e não pode ter VIP.",
                ephemeral=True
            )
            return

        dados_vip = consultar_vip(user_id)
        tem_vip = dados_vip.get("vip", False)
        await mostrar_gerenciar_vip(interaction, user_id, tem_vip, user=user)

class AmigoModal(discord.ui.Modal, title="👥 Gerenciar Amigo"):
    usuario_id = discord.ui.TextInput(
        label="ID do usuário",
        placeholder="Digite o ID do usuário",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = int(self.usuario_id.value)

        user = await interaction.client.fetch_user(user_id)

        if user.bot:
            await interaction.response.send_message(
                f"🚫 O usuário {user.mention} é um bot e não pode ter o cargo de Amigo.",
                ephemeral=True
            )
            return

        await mostrar_gerenciar_amigo(interaction, user_id, user=user)

async def mostrar_gerenciar_amigo(interaction: discord.Interaction, user_id: int, user: discord.User = None):
    dados_amigo = consultar_amigo(user_id)
    tem_amigo = dados_amigo.get("amigo", False)

    embed = discord.Embed(
        title="👥 Gerenciar Amigo",
        description=f"👤 <@{user_id}>",
        color=discord.Color.teal() if tem_amigo else discord.Color.greyple()
    )
    embed.add_field(name="Cargo de Amigo", value="Ativo" if tem_amigo else "Inativo", inline=False)

    if user is None:
        user = await bot.fetch_user(user_id)
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

    view = discord.ui.View()

    if tem_amigo:
        botao_remover = discord.ui.Button(label="Remover Amigo", style=discord.ButtonStyle.red)

        async def remover_callback(interaction_btn: discord.Interaction):
            await remover_amigo(user_id)
            embed_log = discord.Embed(
                title="👥 Amigo removido",
                description=f"{interaction_btn.user.mention} removeu o cargo de Amigo de <@{user_id}>.",
                color=discord.Color.red()
            )
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_amigo(interaction_btn, user_id)

        botao_remover.callback = remover_callback
        view.add_item(botao_remover)
    else:
        botao_add = discord.ui.Button(label="Adicionar Amigo", style=discord.ButtonStyle.green)

        async def adicionar_callback(interaction_btn: discord.Interaction):
            await adicionar_amigo(user_id)
            embed_log = discord.Embed(
                title="👥 Amigo adicionado",
                description=f"{interaction_btn.user.mention} adicionou o cargo de Amigo para <@{user_id}>.",
                color=discord.Color.teal()
            )
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_amigo(interaction_btn, user_id)

        botao_add.callback = adicionar_callback
        view.add_item(botao_add)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        embed_voltar = gerar_painel_inicial()
        await interaction_voltar.response.edit_message(embed=embed_voltar, view=PainelView())
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await enviar_ou_editar(interaction, embed, view)

async def mostrar_gerenciar_call(interaction: discord.Interaction):
    guild = bot.get_guild(SEU_GUILD_ID)
    canal = guild.get_channel(CALL_LIVE) if guild else None

    if canal is None:
        if isinstance(interaction, discord.Interaction):
            try:
                await interaction.response.send_message("🚫 Canal da call live não encontrado.", ephemeral=True)
            except discord.NotFound:
                pass
        else:
            await interaction.send("🚫 Canal da call live não encontrado.")
        return

    everyone = guild.default_role
    overwrite = canal.overwrites_for(everyone)
    entrada_bloqueada = overwrite.connect is False
    fala_bloqueada = overwrite.speak is False
    membros_na_call = canal.members
    todos_mutados = len(membros_na_call) > 0 and all(m.voice and m.voice.mute for m in membros_na_call)

    admin_role = guild.get_role(ADMINISTRADOR)
    canal_reconectar = guild.get_channel(CALL_RECONECTAR)

    def eh_admin(membro):
        return admin_role is not None and any(role.position >= admin_role.position for role in membro.roles)

    membros_nao_admin = [m for m in membros_na_call if not eh_admin(m)]

    embed = discord.Embed(
        title="🎙️ Gerenciar Call Live",
        description=f"Canal: {canal.mention}",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Entrada", value="🔒 Bloqueada" if entrada_bloqueada else "🔓 Liberada", inline=True)
    embed.add_field(name="Fala", value="🔇 Bloqueada" if fala_bloqueada else "🔊 Liberada", inline=True)
    embed.add_field(name="Admins na call", value=str(len(membros_na_call) - len(membros_nao_admin)), inline=True)
    embed.add_field(name="Membros na call", value=str(len(membros_nao_admin)), inline=True)
    embed.add_field(name="Pessoas na call", value=str(len(membros_na_call)), inline=True)

    view = discord.ui.View()

    botao_entrada = discord.ui.Button(
        label="Liberar Entrada" if entrada_bloqueada else "Bloquear Entrada",
        style=discord.ButtonStyle.green if entrada_bloqueada else discord.ButtonStyle.red
    )

    async def entrada_callback(interaction_btn: discord.Interaction):
        novo_overwrite = canal.overwrites_for(everyone)
        novo_overwrite.connect = None if entrada_bloqueada else False
        await canal.set_permissions(everyone, overwrite=novo_overwrite)

        embed_log = discord.Embed(
            title="🔓 Entrada da call liberada" if entrada_bloqueada else "🔒 Entrada da call bloqueada",
            description=f"{interaction_btn.user.mention} {'liberou' if entrada_bloqueada else 'bloqueou'} a entrada em {canal.mention}.",
            color=discord.Color.green() if entrada_bloqueada else discord.Color.red()
        )
        await registrar_log_painel(embed_log)
        await mostrar_gerenciar_call(interaction_btn)

    botao_entrada.callback = entrada_callback
    view.add_item(botao_entrada)

    if not entrada_bloqueada:
        botao_fala = discord.ui.Button(
            label="Liberar Fala" if fala_bloqueada else "Bloquear Fala",
            style=discord.ButtonStyle.green if fala_bloqueada else discord.ButtonStyle.red
        )

        async def fala_callback(interaction_btn: discord.Interaction):
            novo_overwrite = canal.overwrites_for(everyone)
            novo_overwrite.speak = None if fala_bloqueada else False
            await canal.set_permissions(everyone, overwrite=novo_overwrite)

            embed_log = discord.Embed(
                title="🔊 Fala da call liberada" if fala_bloqueada else "🔇 Fala da call bloqueada",
                description=f"{interaction_btn.user.mention} {'liberou' if fala_bloqueada else 'bloqueou'} a fala em {canal.mention}.",
                color=discord.Color.green() if fala_bloqueada else discord.Color.red()
            )
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_call(interaction_btn)

        botao_fala.callback = fala_callback
        view.add_item(botao_fala)

    if not entrada_bloqueada:
        botao_mute = discord.ui.Button(
            label="Desmutar Todos" if todos_mutados else "Mutar Todos",
            style=discord.ButtonStyle.green if todos_mutados else discord.ButtonStyle.red
        )

        async def mute_callback(interaction_btn: discord.Interaction):
            membros = list(canal.members)
            afetados = []
            for membro in membros:
                try:
                    await membro.edit(mute=not todos_mutados, reason="Mute geral - painel")
                    afetados.append(membro)
                except Exception as e:
                    await registrar_log_normal(f"Erro ao mutar/desmutar {membro.id} na call: {e}", tipo="erro")

            embed_log = discord.Embed(
                title="🔊 Todos desmutados" if todos_mutados else "🔇 Todos mutados",
                description=f"{interaction_btn.user.mention} {'desmutou' if todos_mutados else 'mutou'} {len(afetados)} pessoa(s) em {canal.mention}.",
                color=discord.Color.green() if todos_mutados else discord.Color.red()
            )
            if afetados:
                embed_log.add_field(
                    name="Desmutados" if todos_mutados else "Mutados",
                    value="\n".join(m.mention for m in afetados),
                    inline=False
                )
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_call(interaction_btn)

        botao_mute.callback = mute_callback
        view.add_item(botao_mute)

    if len(membros_na_call) > 0:
        botao_desconectar = discord.ui.Button(label="Desconectar Todos", style=discord.ButtonStyle.secondary)

        async def desconectar_callback(interaction_btn: discord.Interaction):
            membros = list(canal.members)
            afetados = []
            for membro in membros:
                try:
                    await membro.move_to(None, reason="Desconectar todos - painel")
                    afetados.append(membro)
                except Exception as e:
                    await registrar_log_normal(f"Erro ao desconectar {membro.id} da call: {e}", tipo="erro")

            embed_log = discord.Embed(
                title="👢 Todos desconectados da call",
                description=f"{interaction_btn.user.mention} desconectou {len(afetados)} pessoa(s) de {canal.mention}.",
                color=discord.Color.orange()
            )
            if afetados:
                embed_log.add_field(
                    name="Desconectados",
                    value="\n".join(m.mention for m in afetados),
                    inline=False
                )
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_call(interaction_btn)

        botao_desconectar.callback = desconectar_callback
        view.add_item(botao_desconectar)

    if membros_nao_admin and canal_reconectar is not None:
        botao_reconectar = discord.ui.Button(label="Reconectar Todos", style=discord.ButtonStyle.secondary)

        async def reconectar_callback(interaction_btn: discord.Interaction):
            candidatos = list(membros_nao_admin)
            afetados = []
            for membro in candidatos:
                try:
                    await membro.move_to(canal_reconectar, reason="Reconectar - painel")
                    await membro.move_to(canal, reason="Reconectar - painel")
                    afetados.append(membro)
                except Exception as e:
                    await registrar_log_normal(f"Erro ao reconectar {membro.id} na call: {e}", tipo="erro")

            embed_log = discord.Embed(
                title="🔄 Reconexão forçada na call",
                description=f"{interaction_btn.user.mention} reconectou {len(afetados)} pessoa(s) em {canal.mention}.",
                color=discord.Color.blurple()
            )
            if afetados:
                embed_log.add_field(
                    name="Reconectados",
                    value="\n".join(m.mention for m in afetados),
                    inline=False
                )
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_call(interaction_btn)

        botao_reconectar.callback = reconectar_callback
        view.add_item(botao_reconectar)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        embed_voltar = gerar_painel_inicial()
        await interaction_voltar.response.edit_message(embed=embed_voltar, view=PainelView())
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await enviar_ou_editar(interaction, embed, view)


async def mostrar_setar_tempo_vip(interaction: discord.Interaction, user_id: int, tem_vip: bool):
    embed = discord.Embed(
        title="🕒 Setar Tempo VIP",
        description=f"Escolha o tempo exato de VIP para <@{user_id}> (substitui o tempo atual, inclusive se for eterno).",
        color=discord.Color.gold()
    )
    view = discord.ui.View()

    for label, dias in [("1 Dia", 1), ("3 Dias", 3), ("7 Dias", 7), ("30 Dias", 30)]:
        botao = discord.ui.Button(label=label, style=discord.ButtonStyle.blurple)

        async def callback(interaction_btn: discord.Interaction, dias=dias):
            await setar_tempo_vip(user_id, dias)
            embed_log = discord.Embed(
                title="🕒 Tempo de VIP setado",
                description=f"{interaction_btn.user.mention} setou o VIP de <@{user_id}> para {dias} dia(s), substituindo o tempo anterior.",
                color=discord.Color.gold()
            )
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_vip(interaction_btn, user_id, True)

        botao.callback = callback
        view.add_item(botao)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await mostrar_gerenciar_vip(interaction_voltar, user_id, tem_vip)
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    try:
        await interaction.response.edit_message(embed=embed, view=view)
    except discord.NotFound:
        logging.warning(f"Interação expirou antes de editar a tela de setar tempo VIP para {user_id}.")

async def mostrar_adicionar_vip(interaction: discord.Interaction, user_id: int, tem_vip: bool):
    embed = discord.Embed(
        title="➕ Adicionar VIP",
        description=f"Quanto tempo deseja adicionar a <@{user_id}>?",
        color=discord.Color.green()
    )
    view = discord.ui.View()

    for label, dias in [("1 Dia", 1), ("3 Dias", 3), ("7 Dias", 7), ("30 Dias", 30), ("Eterno", None)]:
        botao = discord.ui.Button(label=label, style=discord.ButtonStyle.green)

        async def callback(interaction_btn: discord.Interaction, dias=dias):
            await adicionar_vip(user_id, dias)
            label_tempo = "Eterno" if dias is None else f"{dias} dia(s)"
            embed_log = discord.Embed(
                title="💎 VIP adicionado",
                description=f"{interaction_btn.user.mention} adicionou VIP para <@{user_id}>.",
                color=discord.Color.green()
            )
            embed_log.add_field(name="Tempo", value=label_tempo, inline=True)
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_vip(interaction_btn, user_id, True)

        botao.callback = callback
        view.add_item(botao)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await mostrar_gerenciar_vip(interaction_voltar, user_id, tem_vip)
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await interaction.response.edit_message(embed=embed, view=view)

async def mostrar_remover_tempo_vip(interaction: discord.Interaction, user_id: int, tem_vip: bool):
    embed = discord.Embed(
        title="➖ Remover tempo de VIP",
        description=f"Quanto tempo deseja remover de <@{user_id}>?",
        color=discord.Color.orange()
    )
    view = discord.ui.View()

    for label, dias in [("1 Dia", 1), ("3 Dias", 3), ("7 Dias", 7), ("30 Dias", 30)]:
        botao = discord.ui.Button(label=label, style=discord.ButtonStyle.blurple)

        async def callback(interaction_btn: discord.Interaction, dias=dias):
            resultado = await remover_tempo_vip(user_id, dias)

            if resultado == "eterno":
                descricao_log = f"{interaction_btn.user.mention} tentou remover {dias} dia(s) de <@{user_id}>, mas o VIP é eterno (nada foi alterado)."
                cor = discord.Color.greyple()
            elif resultado == "desativado":
                descricao_log = f"{interaction_btn.user.mention} removeu {dias} dia(s) de <@{user_id}> e o VIP foi desativado."
                cor = discord.Color.red()
            else:
                descricao_log = f"{interaction_btn.user.mention} removeu {dias} dia(s) de VIP de <@{user_id}>."
                cor = discord.Color.orange()

            embed_log = discord.Embed(title="➖ Tempo de VIP removido", description=descricao_log, color=cor)
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_vip(interaction_btn, user_id, True)

        botao.callback = callback
        view.add_item(botao)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await mostrar_gerenciar_vip(interaction_voltar, user_id, tem_vip)
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await interaction.response.edit_message(embed=embed, view=view)

async def mostrar_gerenciar_vip(interaction: discord.Interaction, user_id: int, tem_vip: bool = None, user: discord.User = None):
    dados_vip = consultar_vip(user_id)
    tem_vip = dados_vip.get("vip", False)

    embed = discord.Embed(
        title="💎 Gerenciar VIP",
        description=f"👤 <@{user_id}>",
        color=discord.Color.gold() if tem_vip else discord.Color.greyple()
    )

    if tem_vip:
        ativo_em = dados_vip.get("ativo_em", "-")
        expira_em = dados_vip.get("expira_em", None)

        ativo_em_fmt = datetime.fromisoformat(ativo_em).strftime("%d/%m/%Y %H:%M") if ativo_em else "-"
        expira_em_fmt = datetime.fromisoformat(expira_em).strftime("%d/%m/%Y %H:%M") if expira_em else "Eterno"

        embed.add_field(name="Vip", value="Ativo", inline=False)
        embed.add_field(name="Ativo em", value=ativo_em_fmt, inline=True)
        embed.add_field(name="Expira em", value=expira_em_fmt, inline=True)
    else:
        embed.add_field(name="Vip", value="Inativo", inline=False)
        embed.add_field(name="Ativo em", value="-", inline=True)
        embed.add_field(name="Expira em", value="-", inline=True)

    if user is None:
        user = await bot.fetch_user(user_id)
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

    view = discord.ui.View()

    if tem_vip:
        eterno = dados_vip.get("expira_em") is None
        botao_remover = discord.ui.Button(label="Remover VIP", style=discord.ButtonStyle.red)
        botao_setar_tempo = discord.ui.Button(label="Setar Tempo VIP", style=discord.ButtonStyle.gray)

        async def setar_tempo_callback(interaction_btn: discord.Interaction):
            await mostrar_setar_tempo_vip(interaction_btn, user_id, tem_vip)

        async def remover_callback(interaction_btn: discord.Interaction):
            await remover_vip(user_id)
            embed_log = discord.Embed(
                title="🗑️ VIP removido",
                description=f"{interaction_btn.user.mention} removeu o VIP de <@{user_id}>.",
                color=discord.Color.red()
            )
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log)
            await mostrar_gerenciar_vip(interaction_btn, user_id, False)

        botao_setar_tempo.callback = setar_tempo_callback
        botao_remover.callback = remover_callback

        if not eterno:
            botao_add_tempo = discord.ui.Button(label="Adicionar tempo VIP", style=discord.ButtonStyle.green)
            botao_remover_tempo = discord.ui.Button(label="Remover tempo VIP", style=discord.ButtonStyle.blurple)

            async def adicionar_tempo_callback(interaction_btn: discord.Interaction):
                await mostrar_adicionar_vip(interaction_btn, user_id, tem_vip)

            async def remover_tempo_callback(interaction_btn: discord.Interaction):
                await mostrar_remover_tempo_vip(interaction_btn, user_id, tem_vip)

            botao_add_tempo.callback = adicionar_tempo_callback
            botao_remover_tempo.callback = remover_tempo_callback

            view.add_item(botao_add_tempo)
            view.add_item(botao_remover_tempo)

        view.add_item(botao_setar_tempo)
        view.add_item(botao_remover)
    else:
        botao_add = discord.ui.Button(label="Adicionar VIP", style=discord.ButtonStyle.green)

        async def adicionar_callback(interaction_btn: discord.Interaction):
            await mostrar_adicionar_vip(interaction_btn, user_id, tem_vip)

        botao_add.callback = adicionar_callback
        view.add_item(botao_add)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        embed_voltar = gerar_painel_inicial()
        await interaction_voltar.response.edit_message(embed=embed_voltar, view=PainelView())
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await enviar_ou_editar(interaction, embed, view)


# ---------- Comandos de prefixo básicos ----------

@bot.command(name="cod")
async def cod_cmd(ctx: commands.Context, codigo: str = None):
    if codigo is None:
        await ctx.send("🚫 Uso: `c+cod <código>`")
        return

    conteudo = codigo.strip().upper()
    if len(conteudo) != 6 or not conteudo.isalpha():
        await ctx.send("🚫 Código inválido. Use 6 letras, sem espaços.")
        return

    autor_nome = f"{ctx.author.display_name} - {ctx.author.name}"
    autor_avatar = ctx.author.avatar.url if ctx.author.avatar else None

    embed = discord.Embed(
        title=f"Sala do {ctx.author.display_name}",
        description=conteudo,
        color=discord.Color.blue()
    )
    embed.set_author(name=autor_nome, icon_url=autor_avatar)
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text="Dica Mobile: Segure no código para copiar")

    try:
        await ctx.message.delete()
    except Exception:
        pass

    await ctx.send(embed=embed)
    await registrar_log_codigo(f"Código enviado via c+cod por {ctx.author} no canal #{ctx.channel}: {conteudo}", tipo="info")

@bot.command(name="backup")
async def backup(ctx: commands.Context):
    # Verifica se tem cargo de dev
    if SERVIDOR_DEVS == 0 or CARGO_DEVS == 0:
        await ctx.send("🚫 Sistema de dev não configurado.")
        return
    
    servidor_devs = bot.get_guild(SERVIDOR_DEVS)
    if servidor_devs is None:
        await ctx.send("🚫 Servidor dos devs não encontrado.")
        return
    
    membro_devs = servidor_devs.get_member(ctx.author.id)
    if membro_devs is None:
        try:
            membro_devs = await servidor_devs.fetch_member(ctx.author.id)
        except discord.NotFound:
            membro_devs = None
    
    if membro_devs is None or not any(role.id == CARGO_DEVS for role in membro_devs.roles):
        await ctx.send("🚫 Você não tem permissão (cargo de dev necessário).")
        return

    if not PASTA_BACKUP:
        await ctx.send("🚫 Pasta de backup não configurada no `.env`.")
        return

    versao = criar_backup_manual()
    if versao:
        embed = discord.Embed(
            title="💾 Backup criado com sucesso!",
            description=f"Pasta: **{versao}**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

        embed_log = discord.Embed(
            title="💾 Backup da pasta criado",
            description=f"{ctx.author.mention} criou um backup manualmente ({versao}).",
            color=discord.Color.green()
        )
        await registrar_log_painel(embed_log)
    elif versao is None:
        await ctx.send("⚠️ Backup já existe com conteúdo idêntico, ignorando.")
    else:
        await ctx.send("❌ Erro ao criar backup.")

@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latencia_ms = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência: {latencia_ms}ms",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)

@bot.command(name="uptime")
async def uptime(ctx: commands.Context):
    if HORA_INICIO is None:
        await ctx.send("⚠️ Não foi possível calcular o uptime.")
        return

    agora = datetime.now(timezone.utc)
    delta = agora - HORA_INICIO
    dias, resto = divmod(int(delta.total_seconds()), 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segundos = divmod(resto, 60)

    partes = []
    if dias:
        partes.append(f"{dias}d")
    if horas:
        partes.append(f"{horas}h")
    if minutos:
        partes.append(f"{minutos}m")
    partes.append(f"{segundos}s")

    embed = discord.Embed(
        title="🕒 Uptime",
        description=f"Online há {' '.join(partes)}",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)


# ---------- Comandos de prefixo: Warns ----------

def eh_admin_membro(membro: discord.Member) -> bool:
    guild = membro.guild
    admin_role = guild.get_role(ADMINISTRADOR)
    if admin_role is None:
        return False
    return any(role.position >= admin_role.position for role in membro.roles)

async def extrair_user_id(ctx: commands.Context, alvo: str):
    alvo = alvo.strip().lstrip("<@!").rstrip(">")
    try:
        return int(alvo)
    except ValueError:
        await ctx.send("🚫 ID ou menção inválida.")
        return None

async def processar_novo_warn(ctx: commands.Context, alvo: str, motivo: str, eterno: bool):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    if not motivo:
        await ctx.send("🚫 Você precisa informar um motivo. Uso: `c+warn @user motivo` ou `c+ewarn @user motivo`.")
        return

    user_id = await extrair_user_id(ctx, alvo)
    if user_id is None:
        return

    warn = criar_warn(user_id, ctx.author.id, motivo, eterno)
    quantidade_ativos = len(warns_ativos_do_usuario(user_id))

    embed = discord.Embed(
        title="⚠️ Warn aplicado" if not eterno else "♾️ Warn eterno aplicado",
        description=f"<@{user_id}> recebeu um warn (#{warn['id']}).",
        color=discord.Color.orange()
    )
    embed.add_field(name="Motivo", value=motivo, inline=False)
    embed.add_field(name="Warns ativos", value=str(quantidade_ativos), inline=True)
    await ctx.send(embed=embed)

    resultado_punicao = await aplicar_punicao_progressao(ctx.guild, user_id, quantidade_ativos)

    embed_log = discord.Embed(
        title="⚠️ Warn aplicado" if not eterno else "♾️ Warn eterno aplicado",
        description=f"{ctx.author.mention} aplicou um warn em <@{user_id}> (#{warn['id']}).",
        color=discord.Color.orange()
    )
    embed_log.add_field(name="Motivo", value=motivo, inline=False)
    embed_log.add_field(name="Warns ativos", value=str(quantidade_ativos), inline=True)
    if resultado_punicao:
        embed_log.add_field(name="Punição automática", value=resultado_punicao, inline=False)
    await registrar_log_painel(embed_log)

@bot.command(name="warn")
async def warn(ctx: commands.Context, alvo: str = None, *, motivo: str = None):
    if alvo is None:
        await ctx.send("🚫 Uso: `c+warn @user motivo`")
        return
    await processar_novo_warn(ctx, alvo, motivo, eterno=False)

@bot.command(name="ewarn")
async def ewarn(ctx: commands.Context, alvo: str = None, *, motivo: str = None):
    if alvo is None:
        await ctx.send("🚫 Uso: `c+ewarn @user motivo`")
        return
    await processar_novo_warn(ctx, alvo, motivo, eterno=True)


# ---------- Atalhos de prefixo: espelham o /painel ----------

@bot.command(name="vip")
async def vip_cmd(ctx: commands.Context, alvo: str = None):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return
    if alvo is None:
        await ctx.send("🚫 Uso: `c+vip @user/id`")
        return
    user_id = await extrair_user_id(ctx, alvo)
    if user_id is None:
        return
    dados_vip = consultar_vip(user_id)
    await mostrar_gerenciar_vip(ctx, user_id, dados_vip.get("vip", False))

@bot.command(name="vips")
async def vips_cmd(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    dados = carregar_vips()
    ativos = [uid for uid, info in dados.get("usuarios", {}).items() if info.get("vip")]

    if not ativos:
        await ctx.send("💎 Nenhum usuário com VIP ativo no momento.")
        return

    texto = "\n".join(f"<@{uid}>" for uid in ativos)
    embed = discord.Embed(title="💎 Usuários com VIP", description=texto[:4000], color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command(name="amigo")
async def amigo_cmd(ctx: commands.Context, alvo: str = None):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return
    if alvo is None:
        await ctx.send("🚫 Uso: `c+amigo @user/id`")
        return
    user_id = await extrair_user_id(ctx, alvo)
    if user_id is None:
        return
    await mostrar_gerenciar_amigo(ctx, user_id)

@bot.command(name="amigos")
async def amigos_cmd(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    dados = carregar_amigos()
    ativos = [uid for uid, info in dados.get("usuarios", {}).items() if info.get("amigo")]

    if not ativos:
        await ctx.send("👥 Nenhum usuário com cargo de Amigo no momento.")
        return

    texto = "\n".join(f"<@{uid}>" for uid in ativos)
    embed = discord.Embed(title="👥 Usuários com Amigo", description=texto[:4000], color=discord.Color.teal())
    await ctx.send(embed=embed)

@bot.command(name="call")
async def call_cmd(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return
    await mostrar_gerenciar_call(ctx)

async def resolver_canal_call():
    guild = bot.get_guild(SEU_GUILD_ID)
    if guild is None:
        return None, None
    canal = guild.get_channel(CALL_LIVE)
    return guild, canal

@bot.command(name="call_lock")
async def call_lock_cmd(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    guild, canal = await resolver_canal_call()
    if canal is None:
        await ctx.send("🚫 Canal da call live não encontrado.")
        return

    everyone = guild.default_role
    overwrite = canal.overwrites_for(everyone)
    overwrite.connect = False
    await canal.set_permissions(everyone, overwrite=overwrite)
    await ctx.send(f"🔒 Entrada da call {canal.mention} bloqueada.")

    embed_log = discord.Embed(
        title="🔒 Entrada da call bloqueada",
        description=f"{ctx.author.mention} bloqueou a entrada em {canal.mention} via comando.",
        color=discord.Color.red()
    )
    await registrar_log_painel(embed_log)

@bot.command(name="call_mute")
async def call_mute_cmd(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    guild, canal = await resolver_canal_call()
    if canal is None:
        await ctx.send("🚫 Canal da call live não encontrado.")
        return

    everyone = guild.default_role
    overwrite = canal.overwrites_for(everyone)
    overwrite.speak = False
    await canal.set_permissions(everyone, overwrite=overwrite)
    await ctx.send(f"🔇 Fala da call {canal.mention} bloqueada.")

    embed_log = discord.Embed(
        title="🔇 Fala da call bloqueada",
        description=f"{ctx.author.mention} bloqueou a fala em {canal.mention} via comando.",
        color=discord.Color.red()
    )
    await registrar_log_painel(embed_log)

@bot.command(name="call_allmute")
async def call_allmute_cmd(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    guild, canal = await resolver_canal_call()
    if canal is None:
        await ctx.send("🚫 Canal da call live não encontrado.")
        return

    membros = list(canal.members)
    afetados = []
    for membro in membros:
        try:
            await membro.edit(mute=True, reason="Mute geral - comando")
            afetados.append(membro)
        except Exception as e:
            await registrar_log_normal(f"Erro ao mutar {membro.id} na call: {e}", tipo="erro")

    await ctx.send(f"🔇 {len(afetados)} pessoa(s) mutada(s) em {canal.mention}.")

    embed_log = discord.Embed(
        title="🔇 Todos mutados",
        description=f"{ctx.author.mention} mutou {len(afetados)} pessoa(s) em {canal.mention} via comando.",
        color=discord.Color.red()
    )
    if afetados:
        embed_log.add_field(name="Mutados", value="\n".join(m.mention for m in afetados), inline=False)
    await registrar_log_painel(embed_log)

@bot.command(name="call_allkick")
async def call_allkick_cmd(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    guild, canal = await resolver_canal_call()
    if canal is None:
        await ctx.send("🚫 Canal da call live não encontrado.")
        return

    membros = list(canal.members)
    afetados = []
    for membro in membros:
        try:
            await membro.move_to(None, reason="Desconectar todos - comando")
            afetados.append(membro)
        except Exception as e:
            await registrar_log_normal(f"Erro ao desconectar {membro.id} da call: {e}", tipo="erro")

    await ctx.send(f"👢 {len(afetados)} pessoa(s) desconectada(s) de {canal.mention}.")

    embed_log = discord.Embed(
        title="👢 Todos desconectados da call",
        description=f"{ctx.author.mention} desconectou {len(afetados)} pessoa(s) de {canal.mention} via comando.",
        color=discord.Color.orange()
    )
    if afetados:
        embed_log.add_field(name="Desconectados", value="\n".join(m.mention for m in afetados), inline=False)
    await registrar_log_painel(embed_log)

@bot.command(name="call_reconnect", aliases=["cr"])
async def call_reconnect_cmd(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    guild, canal = await resolver_canal_call()
    if canal is None:
        await ctx.send("🚫 Canal da call live não encontrado.")
        return

    canal_reconectar = guild.get_channel(CALL_RECONECTAR)
    if canal_reconectar is None:
        await ctx.send("🚫 Canal de reconexão não encontrado.")
        return

    admin_role = guild.get_role(ADMINISTRADOR)

    def eh_admin(membro):
        return admin_role is not None and any(role.position >= admin_role.position for role in membro.roles)

    candidatos = [m for m in canal.members if not eh_admin(m)]
    afetados = []
    for membro in candidatos:
        try:
            await membro.move_to(canal_reconectar, reason="Reconectar - comando")
            await membro.move_to(canal, reason="Reconectar - comando")
            afetados.append(membro)
        except Exception as e:
            await registrar_log_normal(f"Erro ao reconectar {membro.id} na call: {e}", tipo="erro")

    await ctx.send(f"🔄 {len(afetados)} pessoa(s) reconectada(s) em {canal.mention}.")

    embed_log = discord.Embed(
        title="🔄 Reconexão forçada na call",
        description=f"{ctx.author.mention} reconectou {len(afetados)} pessoa(s) em {canal.mention} via comando.",
        color=discord.Color.blurple()
    )
    if afetados:
        embed_log.add_field(name="Reconectados", value="\n".join(m.mention for m in afetados), inline=False)
    await registrar_log_painel(embed_log)

@bot.command(name="warns")
async def warns(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    checar_warns_expirados()
    dados = carregar_warns()
    ativos = [w for w in dados["warns"].values() if w.get("status") == "ativo"]

    if not ativos:
        await ctx.send("✅ Nenhum warn ativo no momento.")
        return

    ativos.sort(key=lambda w: w["id"])
    linhas = []
    for w in ativos:
        marca = "♾️" if w.get("eterno") else "⏳"
        linhas.append(f"{marca} **#{w['id']}** — <@{w['user_id']}>: {w['motivo']}")

    texto = "\n".join(linhas)
    if len(texto) > 3900:
        texto = texto[:3900] + "\n... (lista truncada)"

    embed = discord.Embed(
        title="⚠️ Warns ativos",
        description=texto,
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name="warn_remove")
async def warn_remove(ctx: commands.Context, warn_id: int = None):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    if warn_id is None:
        await ctx.send("🚫 Uso: `c+warn_remove <id>`")
        return

    warn_removido = remover_warn(warn_id)
    if warn_removido is None:
        await ctx.send(f"🚫 Warn #{warn_id} não encontrado ou já não está ativo.")
        return

    await ctx.send(f"✅ Warn #{warn_id} removido.")

    embed_log = discord.Embed(
        title="🗑️ Warn removido",
        description=f"{ctx.author.mention} removeu o warn #{warn_id} de <@{warn_removido['user_id']}>.",
        color=discord.Color.red()
    )
    embed_log.add_field(name="Motivo original", value=warn_removido["motivo"], inline=False)
    await registrar_log_painel(embed_log)

@bot.command(name="warn_info")
async def warn_info(ctx: commands.Context, warn_id: int = None):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    if warn_id is None:
        await ctx.send("🚫 Uso: `c+warn_info <id>`")
        return

    dados = carregar_warns()
    w = dados["warns"].get(str(warn_id))
    if w is None:
        await ctx.send(f"🚫 Warn #{warn_id} não encontrado.")
        return

    criado_em_fmt = datetime.fromisoformat(w["criado_em"]).strftime("%d/%m/%Y %H:%M")
    expira_em_fmt = "Nunca (eterno)" if w.get("eterno") else (
        datetime.fromisoformat(w["expira_em"]).strftime("%d/%m/%Y %H:%M") if w.get("expira_em") else "-"
    )

    embed = discord.Embed(
        title=f"📄 Warn #{w['id']}",
        description=f"Usuário: <@{w['user_id']}>",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Motivo", value=w["motivo"], inline=False)
    embed.add_field(name="Aplicado por", value=f"<@{w['autor_id']}>", inline=True)
    embed.add_field(name="Status", value=w["status"].capitalize(), inline=True)
    embed.add_field(name="Eterno", value="Sim" if w.get("eterno") else "Não", inline=True)
    embed.add_field(name="Criado em", value=criado_em_fmt, inline=True)
    embed.add_field(name="Expira em", value=expira_em_fmt, inline=True)
    await ctx.send(embed=embed)

@bot.command(name="warns_deleted")
async def warns_deleted(ctx: commands.Context):
    if not eh_admin_membro(ctx.author):
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    checar_warns_expirados()
    dados = carregar_warns()
    expirados = [w for w in dados["warns"].values() if w.get("status") == "expirado"]
    removidos = [w for w in dados["warns"].values() if w.get("status") == "removido"]

    expirados.sort(key=lambda w: w["id"])
    removidos.sort(key=lambda w: w["id"])

    texto_expirados = "\n".join(f"**#{w['id']}** — <@{w['user_id']}>: {w['motivo']}" for w in expirados) or "Nenhum."
    texto_removidos = "\n".join(f"**#{w['id']}** — <@{w['user_id']}>: {w['motivo']}" for w in removidos) or "Nenhum."

    embed = discord.Embed(title="🗂️ Warns expirados e removidos", color=discord.Color.greyple())
    embed.add_field(name="⏳ Expirados naturalmente", value=texto_expirados[:1024], inline=False)
    embed.add_field(name="🗑️ Removidos manualmente", value=texto_removidos[:1024], inline=False)
    await ctx.send(embed=embed)

@bot.tree.command(
    name="painel",
    description="Abrir painel de controle do bot",
    guild=discord.Object(id=SEU_GUILD_ID)
)
async def painel(interaction: discord.Interaction):
    admin_role = interaction.guild.get_role(ADMINISTRADOR)

    if admin_role is None or not any(role.position >= admin_role.position for role in interaction.user.roles):
        await interaction.response.send_message(
            "🚫 Você não tem permissão para usar este comando.",
            ephemeral=True
        )

        embed_log = discord.Embed(
            title="🚨 Tentativa de acesso bloqueada",
            description=f"Usuário {interaction.user.mention} tentou abrir o painel sem permissão.",
            color=discord.Color.red()
        )
        embed_log.add_field(name="ID do usuário", value=str(interaction.user.id), inline=True)
        embed_log.add_field(name="Cargo mais alto", value=interaction.user.top_role.name, inline=True)
        embed_log.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        await registrar_log_painel(embed_log)

        return

    embed = gerar_painel_inicial()
    await interaction.response.send_message(
        embed=embed,
        view=PainelView(),
        ephemeral=True
    )

    embed_log = discord.Embed(
        title="📋 Painel aberto",
        description=f"{interaction.user.mention} abriu o painel de controle.",
        color=discord.Color.blurple()
    )
    embed_log.add_field(name="ID do usuário", value=str(interaction.user.id), inline=True)
    await registrar_log_painel(embed_log)


COMANDOS_INFO = {
    "ping": {"uso": "c+ping", "descricao": "Mostra a latência do bot."},
    "uptime": {"uso": "c+uptime", "descricao": "Mostra há quanto tempo o bot está online desde o último restart."},
    "cod": {"uso": "c+cod <código>", "descricao": "Envia um código formatado direto no canal onde o comando foi usado. Qualquer pessoa pode usar."},
    "backup": {"uso": "c+backup", "descricao": "Cria um backup do bot.py atual com versionamento automático (3.0.0, 3.0.1, etc). Só admin."},
    "vip": {"uso": "c+vip @user/id", "descricao": "Abre a tela de gerenciamento de VIP de um usuário."},
    "vips": {"uso": "c+vips", "descricao": "Lista todos os usuários com VIP ativo."},
    "amigo": {"uso": "c+amigo @user/id", "descricao": "Abre a tela de gerenciamento do cargo de Amigo de um usuário."},
    "amigos": {"uso": "c+amigos", "descricao": "Lista todos os usuários com o cargo de Amigo."},
    "call": {"uso": "c+call", "descricao": "Abre a tela de gerenciamento da call live (mesma do /painel)."},
    "call_lock": {"uso": "c+call_lock", "descricao": "Bloqueia a entrada na call live."},
    "call_mute": {"uso": "c+call_mute", "descricao": "Bloqueia a fala na call live."},
    "call_allmute": {"uso": "c+call_allmute", "descricao": "Muta todos que estão na call live agora."},
    "call_allkick": {"uso": "c+call_allkick", "descricao": "Desconecta todos que estão na call live agora."},
    "call_reconnect": {"uso": "c+call_reconnect (ou c+cr)", "descricao": "Reconecta os não-admins da call, forçando a atualização de permissões (ex: após bloquear fala)."},
    "warn": {"uso": "c+warn @user motivo", "descricao": "Aplica um warn normal, que expira sozinho em 60 dias sem nova infração."},
    "ewarn": {"uso": "c+ewarn @user motivo", "descricao": "Aplica um warn eterno, que nunca expira sozinho."},
    "warns": {"uso": "c+warns", "descricao": "Lista todos os warns ativos de todos os usuários do servidor."},
    "warn_remove": {"uso": "c+warn_remove <id>", "descricao": "Remove um warn específico pelo ID (fica registrado como removido)."},
    "warn_info": {"uso": "c+warn_info <id>", "descricao": "Mostra detalhes completos de um warn específico."},
    "warns_deleted": {"uso": "c+warns_deleted", "descricao": "Lista os warns expirados e removidos, separadamente."},
}

ALIASES_HELP = {"cr": "call_reconnect"}

CATEGORIAS_HELP = {
    "💎 VIP": ["vip", "vips"],
    "👥 Amigos": ["amigo", "amigos"],
    "🎙️ Call": ["call", "call_lock", "call_mute", "call_allmute", "call_allkick", "call_reconnect"],
    "⚠️ Warns": ["warn", "ewarn", "warns", "warn_remove", "warn_info", "warns_deleted"],
    "🔧 Utilidades": ["ping", "uptime", "cod", "backup"]
}

def montar_embed_help_geral() -> discord.Embed:
    embed = discord.Embed(
        title="❓ Central de Ajuda",
        description="Escolha uma categoria abaixo para ver os comandos disponíveis, ou use `c+help <comando>` para detalhes de um comando específico.",
        color=discord.Color.blurple()
    )
    for categoria, comandos in CATEGORIAS_HELP.items():
        embed.add_field(name=categoria, value=f"{len(comandos)} comando(s)", inline=True)
    return embed

def montar_embed_categoria_help(categoria: str) -> discord.Embed:
    embed = discord.Embed(title=f"{categoria} — Comandos", color=discord.Color.blurple())
    for nome_cmd in CATEGORIAS_HELP[categoria]:
        info = COMANDOS_INFO[nome_cmd]
        embed.add_field(name=info["uso"], value=info["descricao"], inline=False)
    return embed

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=cat) for cat in CATEGORIAS_HELP.keys()]
        super().__init__(placeholder="Escolha uma categoria...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        embed = montar_embed_categoria_help(self.values[0])
        await enviar_ou_editar(interaction, embed, HelpView())

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(HelpSelect())

@bot.command(name="help")
async def help_cmd(ctx: commands.Context, comando: str = None):
    if comando:
        nome = comando[2:] if comando.startswith("c+") else comando
        nome = nome.lower()
        nome = ALIASES_HELP.get(nome, nome)
        info = COMANDOS_INFO.get(nome)

        if info is None:
            await ctx.send(f"🚫 Comando `{comando}` não encontrado. Use `c+help` para ver a lista completa.")
            return

        embed = discord.Embed(
            title=f"❓ Ajuda: {info['uso']}",
            description=info["descricao"],
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)
        return

    await ctx.send(embed=montar_embed_help_geral(), view=HelpView())

@bot.tree.command(
    name="help",
    description="Ver a lista de comandos do bot",
    guild=discord.Object(id=SEU_GUILD_ID)
)
async def help_slash(interaction: discord.Interaction):
    await interaction.response.send_message(embed=montar_embed_help_geral(), view=HelpView(), ephemeral=True)


# ---------- Tratamento de erro geral de comandos ----------

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        nome_comando = ctx.command.name if ctx.command else None
        info = COMANDOS_INFO.get(nome_comando)
        if info:
            await ctx.send(f"🚫 Por favor use `{info['uso']}`")
        else:
            await ctx.send("🚫 Uso incorreto do comando. Use `c+help` para ver a lista de comandos.")
        return

    logging.error(f"Erro não tratado no comando {ctx.command}: {error}")


bot.run(TOKEN)