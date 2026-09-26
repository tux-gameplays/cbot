import discord
from discord.ext import commands, tasks
import logging
import os
import asyncio
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
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
FUSO_BRT = timezone(timedelta(hours=-3))

# ---------- Variáveis ----------

# Dev
TOKEN = os.getenv("TOKEN")
SERVIDOR_DEVS = int(os.getenv("SERVIDOR_DOS_DEVS", 0))
CARGO_DEVS = int(os.getenv("CARGO_DOS_DEVS", 0))
SEU_GUILD_ID = int(os.getenv("SERVIDOR"))

# Canais
CODIGO_ANTECIPADO = int(os.getenv("CODIGO_ANTECIPADO", 0))
CODIGO_PUBLICO = int(os.getenv("CODIGO_PUBLICO", 0))
CANAL_BANCO = int(os.getenv("CANAL_BANCO", 0))

# Calls
CALL_LIVE = int(os.getenv("Call_Live"))
CALL_RECONECTAR = int(os.getenv("Call_Reconectar"))

# Webhooks
WEBHOOK_CODIGOS = os.getenv("CODIGO_SALAS")
WEBHOOK_LOGS = os.getenv("LOGS_GERAIS")
WEBHOOK_ANTECIPADO = os.getenv("CODIGO_SALAS_ANTECIPADO")
WEBHOOK_LOGS_CODIGOS = os.getenv("LOGS_CODIGOS")
WEBHOOK_LEMBRETE_CHAT = os.getenv("LEMBRETE_CHAT")
WEBHOOK_LOGS_PAINEL = os.getenv("LOGS_PAINEL")
WEBHOOK_ENTRADA = os.getenv("ENTRADA")
WEBHOOK_BANCO = os.getenv("BANCO")

# Cargos
ADMINISTRADOR = int(os.getenv("Administrador"))
VIP = int(os.getenv("Vip"))
AMIGOS = int(os.getenv("Amigos"))
ROLE_PING_LEMBRETE = os.getenv("PING_LEMBRETE", "")

# Pessoas
BOT_BANCO_ID = int(os.getenv("BOT_BANCO_ID", 0))
DONO_BOT = int(os.getenv("DONO_BOT", 0))
CHIP = int(os.getenv("CHIP", 0))

# Memória
ARQUIVO_VIPS = os.getenv("ARQUIVO_VIPS")
ARQUIVO_AMIGOS = os.getenv("ARQUIVO_AMIGOS")
ARQUIVO_WARNS = os.getenv("ARQUIVO_WARNS")
ARQUIVO_TIMERS = os.getenv("ARQUIVO_TIMERS")
ARQUIVO_BANCO_AV = os.getenv("ARQUIVO_AV_BANCO")

# Pastas
PASTA_BACKUP = os.getenv("PASTA_BACKUP")
if not PASTA_BACKUP and ARQUIVO_VIPS:
    PASTA_BACKUP = os.path.join(os.path.dirname(ARQUIVO_VIPS), "Backups")

PASTA_SRC = os.getenv("PASTA_SRC")
PASTA_MEMORIAS = os.getenv("PASTA_MEMORIAS")
PASTA_BOT_RAIZ = "/home/rpyt51/Documentos/Bots/Bot Chip"

# ---------- Config compartilhada entre módulos ----------

CFG = {
    "bot": bot,
    "guild_id": SEU_GUILD_ID,
    "admin_role_id": ADMINISTRADOR,
    "vip_role_id": VIP,
    "amigos_role_id": AMIGOS,
    "call_live": CALL_LIVE,
    "call_reconectar": CALL_RECONECTAR,
    "arquivo_vips": ARQUIVO_VIPS,
    "arquivo_amigos": ARQUIVO_AMIGOS,
    "arquivo_warns": ARQUIVO_WARNS,
    "arquivo_timers": ARQUIVO_TIMERS,
    "arquivo_banco_av": ARQUIVO_BANCO_AV,
    "pasta_backup": PASTA_BACKUP,
    "pasta_src": PASTA_SRC,
    "pasta_memorias": PASTA_MEMORIAS,
    "pasta_bot_raiz": PASTA_BOT_RAIZ,
    "servidor_devs": SERVIDOR_DEVS,
    "cargo_devs": CARGO_DEVS,
    "webhook_codigos": WEBHOOK_CODIGOS,
    "webhook_logs": WEBHOOK_LOGS,
    "webhook_antecipado": WEBHOOK_ANTECIPADO,
    "webhook_logs_codigos": WEBHOOK_LOGS_CODIGOS,
    "webhook_lembrete_chat": WEBHOOK_LEMBRETE_CHAT,
    "webhook_logs_painel": WEBHOOK_LOGS_PAINEL,
    "webhook_entrada": WEBHOOK_ENTRADA,
    "webhook_banco": WEBHOOK_BANCO,
    "role_ping_lembrete": ROLE_PING_LEMBRETE,
    "fuso_brt": FUSO_BRT,
    "hora_inicio": None,
}

# ---------- Importa módulos ----------

from Modulos.webhooks import registrar_log_normal, registrar_log_codigo, registrar_log_painel, enviar_webhook, apagar_webhook_msg
from Modulos.vip import checar_vips_expirados
from Modulos.warns import checar_warns_expirados
from Modulos.codigos import retomar_timers_pendentes, agendar_job
from Modulos.banco import retomar_msgs_banco, processar_msg_banco
from Modulos.backup import backup_automatico, git_auto_commit
from Modulos.comandos import registrar_comandos

registrar_comandos(bot, CFG)

# ---------- Loop de verificação ----------

@tasks.loop(minutes=5)
async def loop_verificar_vips():
    expirados = await checar_vips_expirados(bot, SEU_GUILD_ID, VIP, ARQUIVO_VIPS, FUSO_BRT, WEBHOOK_LOGS)
    if expirados:
        await registrar_log_normal("Um ou mais VIPs expiraram e foram desativados automaticamente.", tipo="neutro", webhook_logs=WEBHOOK_LOGS)
        embed_log = discord.Embed(
            title="⌛ VIPs expirados automaticamente",
            description="\n".join(f"<@{uid}>" for uid in expirados),
            color=discord.Color.dark_grey()
        )
        await registrar_log_painel(embed_log, webhook_logs_painel=WEBHOOK_LOGS_PAINEL)

    warns_expirados = checar_warns_expirados(ARQUIVO_WARNS, FUSO_BRT)
    if warns_expirados:
        embed_log_warns = discord.Embed(
            title="⌛ Warns expirados automaticamente",
            description="\n".join(f"#{w['id']} — <@{w['user_id']}>" for w in warns_expirados),
            color=discord.Color.dark_grey()
        )
        await registrar_log_painel(embed_log_warns, webhook_logs_painel=WEBHOOK_LOGS_PAINEL)

# ---------- Eventos ----------

@bot.event
async def on_ready():
    global HORA_INICIO
    HORA_INICIO = datetime.now(timezone.utc)
    CFG["hora_inicio"] = HORA_INICIO

    await registrar_log_normal(f"Bot logado como {bot.user}", tipo="sucesso", webhook_logs=WEBHOOK_LOGS)
    try:
        guild = discord.Object(id=SEU_GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        logging.info(f"Comandos slash sincronizados na guild {SEU_GUILD_ID}: {len(synced)}")
    except Exception as e:
        logging.error(f"Erro ao sincronizar comandos slash: {e}")

    await checar_vips_expirados(bot, SEU_GUILD_ID, VIP, ARQUIVO_VIPS, FUSO_BRT, WEBHOOK_LOGS)
    if not loop_verificar_vips.is_running():
        loop_verificar_vips.start()

    retomar_timers_pendentes(bot, ARQUIVO_TIMERS, FUSO_BRT, WEBHOOK_ANTECIPADO, WEBHOOK_CODIGOS,
                             WEBHOOK_LEMBRETE_CHAT, WEBHOOK_LOGS, WEBHOOK_LOGS_CODIGOS, ROLE_PING_LEMBRETE)
    await retomar_msgs_banco(bot, CANAL_BANCO, BOT_BANCO_ID, SEU_GUILD_ID, VIP, ARQUIVO_VIPS,
                             ARQUIVO_BANCO_AV, FUSO_BRT, WEBHOOK_BANCO, WEBHOOK_LOGS, WEBHOOK_LOGS_PAINEL)
    await backup_automatico(PASTA_BACKUP, PASTA_SRC, PASTA_MEMORIAS, FUSO_BRT, WEBHOOK_LOGS)

    if ROLE_PING_LEMBRETE and ROLE_PING_LEMBRETE.startswith("<@&"):
        match = re.search(r"<@&(\d+)>", ROLE_PING_LEMBRETE)
        if match:
            role_id = int(match.group(1))
            guild_obj = bot.get_guild(SEU_GUILD_ID)
            if guild_obj:
                role = guild_obj.get_role(role_id)
                if role:
                    logging.info(f"🏷️ Role ping lembrete: {role.name} (ID: {role_id})")

    await git_auto_commit(PASTA_BOT_RAIZ, WEBHOOK_LOGS)
    await preencher_info_usuarios()

async def preencher_info_usuarios():
    from Modulos.vip import carregar_vips, salvar_vips, atualizar_info_usuario
    from Modulos.amigos import carregar_amigos, salvar_amigos
    from Modulos.warns import carregar_warns, salvar_warns

    guild = bot.get_guild(SEU_GUILD_ID)
    if not guild:
        return

    agora = datetime.now(timezone.utc).isoformat()
    atualizados = 0

    dados_vip = carregar_vips(ARQUIVO_VIPS)
    for user_id_str, info in dados_vip["usuarios"].items():
        if "apelido" not in info or "nome_usuario" not in info:
            try:
                membro = guild.get_member(int(user_id_str)) or await guild.fetch_member(int(user_id_str))
                info["apelido"] = membro.display_name
                info["nome_usuario"] = membro.name
                info["ultima_atualizacao_info"] = agora
                atualizados += 1
            except Exception:
                pass
    salvar_vips(dados_vip, ARQUIVO_VIPS)

    dados_amigos = carregar_amigos(ARQUIVO_AMIGOS)
    for user_id_str, info in dados_amigos["usuarios"].items():
        if "apelido" not in info or "nome_usuario" not in info:
            try:
                membro = guild.get_member(int(user_id_str)) or await guild.fetch_member(int(user_id_str))
                info["apelido"] = membro.display_name
                info["nome_usuario"] = membro.name
                info["ultima_atualizacao_info"] = agora
                atualizados += 1
            except Exception:
                pass
    salvar_amigos(dados_amigos, ARQUIVO_AMIGOS)

    dados_warns = carregar_warns(ARQUIVO_WARNS)
    usuarios_warns = set(str(w["user_id"]) for w in dados_warns["warns"].values())
    for user_id_str in usuarios_warns:
        warn_info = dados_warns.get("info_usuarios", {}).get(user_id_str, {})
        if "apelido" not in warn_info or "nome_usuario" not in warn_info:
            try:
                membro = guild.get_member(int(user_id_str)) or await guild.fetch_member(int(user_id_str))
                if "info_usuarios" not in dados_warns:
                    dados_warns["info_usuarios"] = {}
                dados_warns["info_usuarios"][user_id_str] = {
                    "apelido": membro.display_name,
                    "nome_usuario": membro.name,
                    "ultima_atualizacao_info": agora
                }
                atualizados += 1
            except Exception:
                pass
    salvar_warns(dados_warns, ARQUIVO_WARNS)

    if atualizados > 0:
        logging.info(f"👤 Info de {atualizados} usuário(s) preenchida(s) nos JSONs")

@bot.event
async def on_member_remove(member: discord.Member):
    from Modulos.vip import carregar_vips, salvar_vips, consultar_vip
    if member.guild.id != SEU_GUILD_ID:
        return
    dados_vip = consultar_vip(member.id, ARQUIVO_VIPS)
    if dados_vip.get("vip"):
        dados = carregar_vips(ARQUIVO_VIPS)
        usuarios = dados.get("usuarios", {})
        usuarios[str(member.id)]["vip"] = False
        usuarios[str(member.id)]["expira_em"] = None
        usuarios[str(member.id)]["eterno"] = False
        dados["usuarios"] = usuarios
        salvar_vips(dados, ARQUIVO_VIPS)
        embed_log = discord.Embed(title="💎 VIP perdido (saiu do servidor)", description=f"{member.mention} saiu do servidor e perdeu o VIP definitivamente.", color=discord.Color.red())
        embed_log.add_field(name="ID do usuário", value=str(member.id), inline=True)
        await registrar_log_painel(embed_log, webhook_logs_painel=WEBHOOK_LOGS_PAINEL)

@bot.event
async def on_member_join(member: discord.Member):
    from Modulos.amigos import consultar_amigo, atribuir_cargo_amigo
    if member.guild.id != SEU_GUILD_ID:
        return
    dados_amigo = consultar_amigo(member.id, ARQUIVO_AMIGOS)
    if dados_amigo.get("amigo"):
        await atribuir_cargo_amigo(member.id, bot, SEU_GUILD_ID, AMIGOS, WEBHOOK_LOGS)
        embed_log = discord.Embed(title="👥 Cargo de Amigo restaurado", description=f"{member.mention} voltou ao servidor e o cargo de Amigo foi restaurado automaticamente.", color=discord.Color.teal())
        embed_log.add_field(name="ID do usuário", value=str(member.id), inline=True)
        await registrar_log_painel(embed_log, webhook_logs_painel=WEBHOOK_LOGS_PAINEL)
    if WEBHOOK_ENTRADA:
        try:
            msg_entrada = await enviar_webhook(WEBHOOK_ENTRADA, conteudo=f"Clique aqui {member.display_name} 👋 {member.mention}", wait=True)
            await asyncio.sleep(10)
            await apagar_webhook_msg(WEBHOOK_ENTRADA, msg_entrada.id)
        except Exception as e:
            await registrar_log_normal(f"Erro ao enviar ping de entrada para {member.id}: {e}", tipo="erro", webhook_logs=WEBHOOK_LOGS)

@bot.event
async def on_message(message: discord.Message):
    global ULTIMO_CODIGO_EM

    eh_bot_banco = (BOT_BANCO_ID != 0 and message.author.id == BOT_BANCO_ID and message.channel.id == CANAL_BANCO)

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

            embed = discord.Embed(title=f"Sala do {message.author.display_name}", description=conteudo, color=discord.Color.blue())
            embed.set_author(name=autor_nome, icon_url=autor_avatar)
            embed.timestamp = datetime.now(timezone.utc)
            embed.set_footer(text="Dica Mobile: Segure no código para copiar")

            try:
                await message.delete()
                antecipado_msg = await enviar_webhook(WEBHOOK_ANTECIPADO, embed=embed, username=f"Sala do {message.author.display_name}", wait=True)
                antecipado_id = antecipado_msg.id
                ULTIMO_CODIGO_EM = datetime.now(timezone.utc)
                await registrar_log_codigo(f"Mensagem reenviada no antecipado: {conteudo}", tipo="info", webhook_logs_codigos=WEBHOOK_LOGS_CODIGOS)
            except Exception as e:
                await registrar_log_normal(f"Erro ao reenviar mensagem antecipada: {e}", tipo="erro", webhook_logs=WEBHOOK_LOGS)
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

            for chave, job in [
                (f"publicar:{antecipado_id}", {**info_base, "tipo": "publicar", "disparar_em": (agora + timedelta(seconds=30)).isoformat()}),
                (f"antecipado_expira:{antecipado_id}", {**info_base, "tipo": "antecipado_expira", "disparar_em": (agora + timedelta(seconds=600)).isoformat()})
            ]:
                agendar_job(chave, job, bot, ARQUIVO_TIMERS, FUSO_BRT, WEBHOOK_ANTECIPADO, WEBHOOK_CODIGOS,
                            WEBHOOK_LEMBRETE_CHAT, WEBHOOK_LOGS, WEBHOOK_LOGS_CODIGOS, ROLE_PING_LEMBRETE)
        else:
            try:
                await message.delete()
                await registrar_log_codigo(f"Mensagem inválida apagada no antecipado: {message.content}", tipo="aviso", webhook_logs_codigos=WEBHOOK_LOGS_CODIGOS)
            except Exception as e:
                await registrar_log_normal(f"Erro ao apagar mensagem inválida: {e}", tipo="erro", webhook_logs=WEBHOOK_LOGS)

    elif message.channel.id == CODIGO_PUBLICO:
        if len(message.content) == 6 and " " not in message.content and message.content.isupper():
            conteudo = message.content
            autor_nome = f"{message.author.display_name} - {message.author.name}"
            autor_avatar = message.author.avatar.url if message.author.avatar else None

            embed = discord.Embed(title=f"Sala do {message.author.display_name}", description=conteudo, color=discord.Color.blue())
            embed.set_author(name=autor_nome, icon_url=autor_avatar)
            embed.timestamp = datetime.now(timezone.utc)
            embed.set_footer(text="Dica Mobile: Segure no código para copiar")

            try:
                await message.delete()
                publico_msg = await enviar_webhook(WEBHOOK_CODIGOS, embed=embed, username=f"Sala do {message.author.display_name}", wait=True)
                await registrar_log_codigo(f"Mensagem enviada direto ao público: {conteudo}", tipo="sucesso", webhook_logs_codigos=WEBHOOK_LOGS_CODIGOS)
            except Exception as e:
                await registrar_log_normal(f"Erro ao reenviar mensagem direta no público: {e}", tipo="erro", webhook_logs=WEBHOOK_LOGS)
                return

            agora = datetime.now(FUSO_BRT)
            for chave, job in [
                (f"publico_expira:{publico_msg.id}", {"tipo": "publico_expira", "publico_id": publico_msg.id, "conteudo": conteudo, "disparar_em": (agora + timedelta(seconds=600)).isoformat()}),
                (f"lembrete:{publico_msg.id}", {"tipo": "lembrete", "conteudo": conteudo, "disparar_em": (agora + timedelta(seconds=15)).isoformat()})
            ]:
                agendar_job(chave, job, bot, ARQUIVO_TIMERS, FUSO_BRT, WEBHOOK_ANTECIPADO, WEBHOOK_CODIGOS,
                            WEBHOOK_LEMBRETE_CHAT, WEBHOOK_LOGS, WEBHOOK_LOGS_CODIGOS, ROLE_PING_LEMBRETE)
        else:
            try:
                await message.delete()
                await registrar_log_codigo(f"Mensagem inválida apagada no público: {message.content}", tipo="aviso", webhook_logs_codigos=WEBHOOK_LOGS_CODIGOS)
            except Exception as e:
                await registrar_log_normal(f"Erro ao apagar mensagem inválida: {e}", tipo="erro", webhook_logs=WEBHOOK_LOGS)

    elif message.channel.id == CANAL_BANCO and BOT_BANCO_ID != 0 and message.author.id == BOT_BANCO_ID:
        await processar_msg_banco(message, bot, SEU_GUILD_ID, VIP, ARQUIVO_VIPS, ARQUIVO_BANCO_AV,
                                  FUSO_BRT, WEBHOOK_BANCO, CANAL_BANCO, WEBHOOK_LOGS, WEBHOOK_LOGS_PAINEL)

    await bot.process_commands(message)

bot.run(TOKEN)
