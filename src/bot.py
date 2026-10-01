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

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="c+", intents=intents)
bot.help_command = None

HORA_INICIO = None
FUSO_BRT = timezone(timedelta(hours=-3))

# ---------- Variáveis ----------

TOKEN = os.getenv("TOKEN")
SERVIDOR_DEVS = int(os.getenv("SERVIDOR_DOS_DEVS", 0))
CARGO_DEVS = int(os.getenv("CARGO_DOS_DEVS", 0))
SEU_GUILD_ID = int(os.getenv("SERVIDOR"))

CODIGO_ANTECIPADO = int(os.getenv("CODIGO_ANTECIPADO", 0))
CODIGO_PUBLICO = int(os.getenv("CODIGO_PUBLICO", 0))
CODIGO_LEMBRETE = int(os.getenv("CODIGO_LEMBRETE", 0))
CANAL_BANCO = int(os.getenv("CANAL_BANCO", 0))
CANAL_COMANDOS = [int(x.strip()) for x in os.getenv("CANAL_COMANDOS", "0").split(",") if x.strip().isdigit()]
CANAL_ANUNCIO_LIVES = int(os.getenv("CANAL_ANUNCIO_LIVES", 0))
CANAL_ANUNCIO_VIDEOS = int(os.getenv("CANAL_ANUNCIO_VIDEOS", 0))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CANAL_ID = os.getenv("YOUTUBE_CANAL_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("CLIENT_SECRET_YT")
MEMBRO_YT = int(os.getenv("MEMBRO_YT", 0))
MODERADOR_YT = int(os.getenv("MODERADOR_YT", 0))

CALL_LIVE = int(os.getenv("Call_Live"))
CALL_RECONECTAR = int(os.getenv("Call_Reconectar"))

WEBHOOK_ANTECIPADO = os.getenv("CODIGO_SALAS_ANTECIPADO")

ADMINISTRADOR = int(os.getenv("Administrador"))
VIP = int(os.getenv("Vip"))
AMIGOS_ROLE = int(os.getenv("Amigos"))

PING_LEMBRETE = os.getenv("PING_LEMBRETE", "")
PING_LIVE_PROGRAMADA = os.getenv("PING_LIVE_PROGRAMADA", "")
PING_LIVE_AO_VIVO = os.getenv("PING_LIVE_AO_VIVO", "")
PING_VIDEO_NOVO = os.getenv("PING_VIDEO_NOVO", "")
PING_SHORTS_NOVO = os.getenv("PING_SHORTS_NOVO", "")
ROLE_PING_LEMBRETE = f"<@&{PING_LEMBRETE}>" if PING_LEMBRETE else ""

BOT_BANCO_ID = int(os.getenv("BOT_BANCO_ID", 0))
DONO_BOT = int(os.getenv("DONO_BOT", 0))
CHIP = int(os.getenv("CHIP", 0))

ARQUIVO_VIPS = os.getenv("ARQUIVO_VIPS")
ARQUIVO_AMIGOS = os.getenv("ARQUIVO_AMIGOS")
ARQUIVO_WARNS = os.getenv("ARQUIVO_WARNS")
ARQUIVO_TIMERS = os.getenv("ARQUIVO_TIMERS")
ARQUIVO_BANCO_AV = os.getenv("ARQUIVO_AV_BANCO")
ARQUIVO_SALAS = os.getenv("ARQUIVO_SALAS")
if not ARQUIVO_SALAS and ARQUIVO_VIPS:
    import os as _os
    ARQUIVO_SALAS = _os.path.join(_os.path.dirname(ARQUIVO_VIPS), "Salas.json")

SALAS_PONTE = int(os.getenv("SALAS_PONTE", 0))
ANTECIPADO_PONTE = int(os.getenv("ANTECIPADO_PONTE", 0))
CANAL_SALAS_PUBLICO = CODIGO_PUBLICO
CANAL_SALAS_ANTECIPADO = CODIGO_ANTECIPADO
ARQUIVO_MODERACAO = os.getenv("ARQUIVO_MODERACAO")
ARQUIVO_YOUTUBE = os.getenv("ARQUIVO_YOUTUBE")

PASTA_BACKUP = os.getenv("PASTA_BACKUP")
PASTA_SRC = os.getenv("PASTA_SRC")
PASTA_MEMORIAS = os.getenv("PASTA_MEMORIAS")
PASTA_BOT_RAIZ = "/home/rpyt51/Documentos/Bots/Bot Chip"

LOGS_GERAIS = os.getenv("LOGS_GERAIS")
LOGS_CODIGOS = os.getenv("LOGS_CODIGOS")
LOGS_PAINEL = os.getenv("LOGS_PAINEL")
LOGS_JOIN = os.getenv("LOGS_JOIN")
LOGS_WARNS = os.getenv("LOGS_WARNS")
LOGS_VIP = os.getenv("LOGS_VIP")
LOGS_AMIGOS = os.getenv("LOGS_AMIGOS")
LOGS_PUNICOES = os.getenv("LOGS_PUNICOES")
LOGS_MODERACAO = os.getenv("LOGS_MODERACAO")
LOGS_MEMBROS = os.getenv("LOGS_MEMBROS")
LOGS_MENSAGENS = os.getenv("LOGS_MENSAGENS")
LOGS_CALLS = os.getenv("LOGS_CALLS")
LOGS_SERVIDOR = os.getenv("LOGS_SERVIDOR")
LOGS_CANAIS = os.getenv("LOGS_CANAIS")
LOGS_CARGOS = os.getenv("LOGS_CARGOS")

# ---------- CFG ----------

CFG = {
    "bot": bot,
    "guild_id": SEU_GUILD_ID,
    "admin_role_id": ADMINISTRADOR,
    "vip_role_id": VIP,
    "amigos_role_id": AMIGOS_ROLE,
    "call_live": CALL_LIVE,
    "call_reconectar": CALL_RECONECTAR,
    "canal_comandos": CANAL_COMANDOS,
    "codigo_antecipado": CODIGO_ANTECIPADO,
    "codigo_publico": CODIGO_PUBLICO,
    "codigo_lembrete": CODIGO_LEMBRETE,
    "canal_banco": CANAL_BANCO,
    "canal_anuncio_lives": CANAL_ANUNCIO_LIVES,
    "canal_anuncio_videos": CANAL_ANUNCIO_VIDEOS,
    "youtube_api_key": YOUTUBE_API_KEY,
    "youtube_canal_id": YOUTUBE_CANAL_ID,
    "youtube_client_secret": YOUTUBE_CLIENT_SECRET,
    "cargo_membro_yt": MEMBRO_YT,
    "cargo_moderador_yt": MODERADOR_YT,
    "arquivo_vips": ARQUIVO_VIPS,
    "arquivo_amigos": ARQUIVO_AMIGOS,
    "arquivo_warns": ARQUIVO_WARNS,
    "arquivo_timers": ARQUIVO_TIMERS,
    "arquivo_banco_av": ARQUIVO_BANCO_AV,
    "arquivo_salas": ARQUIVO_SALAS,
    "salas_ponte": SALAS_PONTE,
    "antecipado_ponte": ANTECIPADO_PONTE,
    "canal_salas_publico": CANAL_SALAS_PUBLICO,
    "canal_salas_antecipado": CANAL_SALAS_ANTECIPADO,
    "arquivo_moderacao": ARQUIVO_MODERACAO,
    "arquivo_youtube": ARQUIVO_YOUTUBE,
    "pasta_backup": PASTA_BACKUP,
    "pasta_src": PASTA_SRC,
    "pasta_memorias": PASTA_MEMORIAS,
    "pasta_bot_raiz": PASTA_BOT_RAIZ,
    "servidor_devs": SERVIDOR_DEVS,
    "cargo_devs": CARGO_DEVS,
    "webhook_antecipado": WEBHOOK_ANTECIPADO,
    "role_ping_lembrete": ROLE_PING_LEMBRETE,
    "ping_live_programada": PING_LIVE_PROGRAMADA,
    "ping_live_ao_vivo": PING_LIVE_AO_VIVO,
    "ping_video_novo": PING_VIDEO_NOVO,
    "ping_shorts_novo": PING_SHORTS_NOVO,
    "discord_bot_token": TOKEN,
    "fuso_brt": FUSO_BRT,
    "hora_inicio": None,
    "logs_gerais": LOGS_GERAIS,
    "logs_codigos": LOGS_CODIGOS,
    "logs_painel": LOGS_PAINEL,
    "logs_join": LOGS_JOIN,
    "logs_warns": LOGS_WARNS,
    "logs_vip": LOGS_VIP,
    "logs_amigos": LOGS_AMIGOS,
    "logs_punicoes": LOGS_PUNICOES,
    "logs_moderacao": LOGS_MODERACAO,
    "logs_membros": LOGS_MEMBROS,
    "logs_mensagens": LOGS_MENSAGENS,
    "logs_calls": LOGS_CALLS,
    "logs_servidor": LOGS_SERVIDOR,
    "logs_canais": LOGS_CANAIS,
    "logs_cargos": LOGS_CARGOS,
}

# ---------- Imports ----------

from Modulos.webhooks import registrar_log_normal, registrar_log_codigo, registrar_log_painel, registrar_log_vip, registrar_log_amigos, registrar_log_punicoes, enviar_webhook, apagar_webhook_msg
from Modulos.vip import checar_vips_expirados
from Modulos.warns import checar_warns_expirados
from Modulos.codigos import retomar_timers_pendentes, agendar_job
from Modulos.banco import retomar_msgs_banco, processar_msg_banco
from Modulos.backup import backup_automatico, git_auto_commit
from Modulos.logs import (log_entrada_membro, log_saida_membro, log_cargo_alterado,
                           log_mensagem_apagada, log_mensagem_editada, processar_log_call,
                           log_punicao_externa, log_servidor_atualizado,
                           log_canal_criado, log_canal_deletado, log_canal_atualizado,
                           log_cargo_criado, log_cargo_deletado, log_cargo_atualizado,
                           log_apelido_alterado)
from Modulos.moderacao import processar_moderacao, processar_comando_local_errado
from Modulos.salas import processar_msg_sala, processar_edicao_sala, retomar_salas_pendentes
from Modulos.youtube import checar_youtube, monitorar_chat_live
from Modulos.comandos import registrar_comandos

registrar_comandos(bot, CFG)

# ---------- Cooldown codigos ----------
ULTIMO_CODIGO_EM = None

# ---------- Loops ----------

@tasks.loop(minutes=5)
async def loop_verificar_vips():
    expirados = await checar_vips_expirados(bot, SEU_GUILD_ID, VIP, ARQUIVO_VIPS, FUSO_BRT)
    if expirados:
        embed = discord.Embed(
            title="⌛ VIPs expirados automaticamente",
            description="\n".join(f"<@{uid}>" for uid in expirados),
            color=discord.Color.dark_grey()
        )
        await registrar_log_vip(embed, bot=bot, canal_id=LOGS_VIP)

    warns_expirados = checar_warns_expirados(ARQUIVO_WARNS, FUSO_BRT)
    if warns_expirados:
        embed_warns = discord.Embed(
            title="⌛ Warns expirados automaticamente",
            description="\n".join(f"#{w['id']} — <@{w['user_id']}>" for w in warns_expirados),
            color=discord.Color.dark_grey()
        )
        await registrar_log_punicoes(embed_warns, bot=bot, canal_id=LOGS_PUNICOES)

@tasks.loop(minutes=30)
async def loop_youtube():
    if YOUTUBE_API_KEY and YOUTUBE_CANAL_ID:
        await checar_youtube(CFG)

# ---------- on_ready ----------

@bot.event
async def on_ready():
    global HORA_INICIO
    HORA_INICIO = datetime.now(timezone.utc)
    CFG["hora_inicio"] = HORA_INICIO

    logging.info(f"Bot logado como {bot.user}")
    try:
        guild = discord.Object(id=SEU_GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        logging.info(f"Comandos slash sincronizados na guild {SEU_GUILD_ID}: {len(synced)}")
    except Exception as e:
        logging.error(f"Erro ao sincronizar comandos slash: {e}")

    await checar_vips_expirados(bot, SEU_GUILD_ID, VIP, ARQUIVO_VIPS, FUSO_BRT)

    if not loop_verificar_vips.is_running():
        loop_verificar_vips.start()
    if YOUTUBE_API_KEY and YOUTUBE_CANAL_ID and not loop_youtube.is_running():
        loop_youtube.start()

    retomar_timers_pendentes(bot, ARQUIVO_TIMERS, FUSO_BRT,
                             WEBHOOK_ANTECIPADO, CODIGO_ANTECIPADO, CODIGO_PUBLICO, CODIGO_LEMBRETE,
                             LOGS_GERAIS, LOGS_CODIGOS, ROLE_PING_LEMBRETE)
    await retomar_msgs_banco(bot, CANAL_BANCO, BOT_BANCO_ID, SEU_GUILD_ID, VIP, ARQUIVO_VIPS,
                             ARQUIVO_BANCO_AV, FUSO_BRT, CFG)
    await backup_automatico(PASTA_BACKUP, PASTA_SRC, PASTA_MEMORIAS, FUSO_BRT, None)

    if PING_LEMBRETE:
        match = re.search(r"(\d+)", PING_LEMBRETE)
        if match:
            role_id = int(match.group(1))
            guild_obj = bot.get_guild(SEU_GUILD_ID)
            if guild_obj:
                role = guild_obj.get_role(role_id)
                if role:
                    logging.info(f"🏷️ Role ping lembrete: {role.name} (ID: {role_id})")

    await git_auto_commit(PASTA_BOT_RAIZ, bot=bot, canal_id=LOGS_GERAIS)
    await preencher_info_usuarios()
    await retomar_salas_pendentes(bot, CFG)
    await registrar_log_normal(f"✅ Bot online: {bot.user}", tipo="sucesso", bot=bot, canal_id=LOGS_GERAIS)

# ---------- Auxiliares ----------

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

async def enviar_msg_canal(canal_id: int, conteudo: str = None, embed: discord.Embed = None):
    canal = bot.get_channel(canal_id)
    if canal:
        try:
            await canal.send(content=conteudo, embed=embed)
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem no canal {canal_id}: {e}")

# ---------- Eventos ----------

@bot.event
async def on_member_join(member: discord.Member):
    from Modulos.amigos import consultar_amigo, atribuir_cargo_amigo
    if member.guild.id != SEU_GUILD_ID:
        return

    dados_amigo = consultar_amigo(member.id, ARQUIVO_AMIGOS)
    if dados_amigo.get("amigo"):
        await atribuir_cargo_amigo(member.id, bot, SEU_GUILD_ID, AMIGOS_ROLE)

    # Log de entrada com estilo (inspirado no exemplo)
    await log_entrada_membro(member, CFG)

    # Mensagem de boas-vindas no canal de join
    if LOGS_JOIN:
        agora = datetime.now(FUSO_BRT)
        guild = member.guild
        member_count = guild.member_count

        embed = discord.Embed(
            description=f"➡ **{member.name}** (@{member.name})\nEntrou no servidor!\n\nAgora somos **{member_count}** membros\nId: {member.id}",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.timestamp = datetime.now(timezone.utc)

        canal_join = bot.get_channel(int(LOGS_JOIN))
        if canal_join:
            await canal_join.send(f"👋 <@{member.id}>", embed=embed)

@bot.event
async def on_member_remove(member: discord.Member):
    from Modulos.vip import carregar_vips, salvar_vips, consultar_vip
    if member.guild.id != SEU_GUILD_ID:
        return

    dados_vip = consultar_vip(member.id, ARQUIVO_VIPS)
    if dados_vip.get("vip"):
        dados = carregar_vips(ARQUIVO_VIPS)
        uid = str(member.id)
        dados["usuarios"][uid]["vip"] = False
        dados["usuarios"][uid]["expira_em"] = None
        dados["usuarios"][uid]["eterno"] = False
        salvar_vips(dados, ARQUIVO_VIPS)
        embed = discord.Embed(
            title="💎 VIP perdido (saiu do servidor)",
            description=f"{member.mention} saiu do servidor e perdeu o VIP definitivamente.",
            color=discord.Color.red()
        )
        embed.add_field(name="ID", value=str(member.id), inline=True)
        await registrar_log_vip(embed, bot=bot, canal_id=LOGS_VIP)

    await log_saida_membro(member, CFG)

    # Mensagem de saída no canal de join
    if LOGS_JOIN:
        guild = member.guild
        member_count = guild.member_count

        embed = discord.Embed(
            description=f"⬅ **{member.name}** (@{member.name})\nSaiu no servidor!\n\nAgora somos **{member_count}** membros\nId: {member.id}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.timestamp = datetime.now(timezone.utc)

        canal_join = bot.get_channel(int(LOGS_JOIN))
        if canal_join:
            await canal_join.send(embed=embed)

@bot.event
async def on_member_update(antes: discord.Member, depois: discord.Member):
    if antes.guild.id != SEU_GUILD_ID:
        return
    await log_cargo_alterado(depois, antes, CFG)
    await log_apelido_alterado(antes, depois, CFG)

@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.guild.id != SEU_GUILD_ID:
        return
    if message.author == bot.user:
        return
    # Ignora mensagens de código correto que viraram embed
    if message.channel.id in [CODIGO_ANTECIPADO, CODIGO_PUBLICO]:
        if len(message.content) == 6 and message.content.isupper() and message.content.isalpha():
            return
    await log_mensagem_apagada(message, CFG)

@bot.event
async def on_message_edit(antes: discord.Message, depois: discord.Message):
    if not antes.guild or antes.guild.id != SEU_GUILD_ID:
        return

    # Edição nos canais ponte — atualiza embed da sala
    if antes.channel.id in [SALAS_PONTE, ANTECIPADO_PONTE] and (antes.webhook_id or antes.author.bot):
        await processar_edicao_sala(depois, bot, CFG)
        return

    await log_mensagem_editada(antes, depois, CFG)

@bot.event
async def on_voice_state_update(member: discord.Member, antes: discord.VoiceState, depois: discord.VoiceState):
    if member.guild.id != SEU_GUILD_ID:
        return
    await processar_log_call(antes, depois, member, CFG)

@bot.event
async def on_guild_update(antes: discord.Guild, depois: discord.Guild):
    if depois.id != SEU_GUILD_ID:
        return
    await log_servidor_atualizado(antes, depois, CFG)

@bot.event
async def on_guild_channel_create(canal: discord.abc.GuildChannel):
    if canal.guild.id != SEU_GUILD_ID:
        return
    await log_canal_criado(canal, CFG)

@bot.event
async def on_guild_channel_delete(canal: discord.abc.GuildChannel):
    if canal.guild.id != SEU_GUILD_ID:
        return
    await log_canal_deletado(canal, CFG)

@bot.event
async def on_guild_channel_update(antes: discord.abc.GuildChannel, depois: discord.abc.GuildChannel):
    if depois.guild.id != SEU_GUILD_ID:
        return
    await log_canal_atualizado(antes, depois, CFG)

@bot.event
async def on_guild_role_create(cargo: discord.Role):
    if cargo.guild.id != SEU_GUILD_ID:
        return
    await log_cargo_criado(cargo, CFG)

@bot.event
async def on_guild_role_delete(cargo: discord.Role):
    if cargo.guild.id != SEU_GUILD_ID:
        return
    await log_cargo_deletado(cargo, CFG)

@bot.event
async def on_guild_role_update(antes: discord.Role, depois: discord.Role):
    if depois.guild.id != SEU_GUILD_ID:
        return
    await log_cargo_atualizado(antes, depois, CFG)

@bot.event
async def on_guild_audit_log_entry_create(entry: discord.AuditLogEntry):
    if entry.guild.id != SEU_GUILD_ID:
        return
    await log_punicao_externa(entry, CFG)

@bot.event
async def on_message(message: discord.Message):
    global ULTIMO_CODIGO_EM

    eh_bot_banco = (BOT_BANCO_ID != 0 and message.author.id == BOT_BANCO_ID and message.channel.id == CANAL_BANCO)
    eh_msg_sala = (message.channel.id in ([SALAS_PONTE] if SALAS_PONTE else []) + ([ANTECIPADO_PONTE] if ANTECIPADO_PONTE else []) and (message.webhook_id is not None or message.author.bot))

    if message.author.bot and message.author != bot.user and not eh_bot_banco and not eh_msg_sala:
        return

    if not message.author.bot:
        bloqueado = await processar_comando_local_errado(message, CFG)
        if bloqueado:
            return
        bloqueado = await processar_moderacao(message, CFG)
        if bloqueado:
            return

    # Canais ponte — salas (webhook externa)
    if SALAS_PONTE != 0 and message.channel.id == SALAS_PONTE and (message.webhook_id or message.author.bot):
        await processar_msg_sala(message, bot, CFG, tipo="publico")
        return

    if ANTECIPADO_PONTE != 0 and message.channel.id == ANTECIPADO_PONTE and (message.webhook_id or message.author.bot):
        await processar_msg_sala(message, bot, CFG, tipo="antecipado")
        return

    # Canal antecipado — manda pelo proprio canal (sem webhook)
    if message.channel.id == CODIGO_ANTECIPADO and message.author != bot.user:
        if ULTIMO_CODIGO_EM is not None:
            decorrido = (datetime.now(timezone.utc) - ULTIMO_CODIGO_EM).total_seconds()
            if decorrido < 3:
                try:
                    await message.delete()
                except Exception:
                    pass
                return

        if len(message.content) == 6 and " " not in message.content and message.content.isupper() and message.content.isalpha():
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
                canal_antecipado = bot.get_channel(CODIGO_ANTECIPADO)
                antecipado_msg = await canal_antecipado.send(embed=embed)
                antecipado_id = antecipado_msg.id
                ULTIMO_CODIGO_EM = datetime.now(timezone.utc)
                await registrar_log_codigo(f"Código reenviado no antecipado: {conteudo}", tipo="info", bot=bot, canal_id=LOGS_CODIGOS)
            except Exception as e:
                await registrar_log_normal(f"Erro ao reenviar código antecipado: {e}", tipo="erro", bot=bot, canal_id=LOGS_GERAIS)
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
                agendar_job(chave, job, bot, ARQUIVO_TIMERS, FUSO_BRT,
                            WEBHOOK_ANTECIPADO, CODIGO_ANTECIPADO, CODIGO_PUBLICO, CODIGO_LEMBRETE,
                            LOGS_GERAIS, LOGS_CODIGOS, ROLE_PING_LEMBRETE)
        else:
            try:
                await message.delete()
                await registrar_log_codigo(f"Mensagem inválida apagada no antecipado: {message.content}", tipo="aviso", bot=bot, canal_id=LOGS_CODIGOS)
            except Exception as e:
                await registrar_log_normal(f"Erro ao apagar mensagem inválida: {e}", tipo="erro", bot=bot, canal_id=LOGS_GERAIS)

    # Canal público — manda pelo proprio canal (sem webhook)
    elif message.channel.id == CODIGO_PUBLICO and message.author != bot.user:
        if len(message.content) == 6 and " " not in message.content and message.content.isupper() and message.content.isalpha():
            if ULTIMO_CODIGO_EM is not None:
                decorrido = (datetime.now(timezone.utc) - ULTIMO_CODIGO_EM).total_seconds()
                if decorrido < 3:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    return

            conteudo = message.content
            autor_nome = f"{message.author.display_name} - {message.author.name}"
            autor_avatar = message.author.avatar.url if message.author.avatar else None

            embed = discord.Embed(title=f"Sala do {message.author.display_name}", description=conteudo, color=discord.Color.blue())
            embed.set_author(name=autor_nome, icon_url=autor_avatar)
            embed.timestamp = datetime.now(timezone.utc)
            embed.set_footer(text="Dica Mobile: Segure no código para copiar")

            try:
                await message.delete()
                canal_publico = bot.get_channel(CODIGO_PUBLICO)
                publico_msg = await canal_publico.send(embed=embed)
                ULTIMO_CODIGO_EM = datetime.now(timezone.utc)
                await registrar_log_codigo(f"Código enviado direto ao público: {conteudo}", tipo="sucesso", bot=bot, canal_id=LOGS_CODIGOS)
            except Exception as e:
                await registrar_log_normal(f"Erro ao reenviar código público: {e}", tipo="erro", bot=bot, canal_id=LOGS_GERAIS)
                return

            agora = datetime.now(FUSO_BRT)
            for chave, job in [
                (f"publico_expira:{publico_msg.id}", {"tipo": "publico_expira", "publico_id": publico_msg.id, "conteudo": conteudo, "disparar_em": (agora + timedelta(seconds=600)).isoformat()}),
                (f"lembrete:{publico_msg.id}", {"tipo": "lembrete", "conteudo": conteudo, "disparar_em": (agora + timedelta(seconds=15)).isoformat()})
            ]:
                agendar_job(chave, job, bot, ARQUIVO_TIMERS, FUSO_BRT,
                            WEBHOOK_ANTECIPADO, CODIGO_ANTECIPADO, CODIGO_PUBLICO, CODIGO_LEMBRETE,
                            LOGS_GERAIS, LOGS_CODIGOS, ROLE_PING_LEMBRETE)
        else:
            try:
                await message.delete()
                await registrar_log_codigo(f"Mensagem inválida apagada no público: {message.content}", tipo="aviso", bot=bot, canal_id=LOGS_CODIGOS)
            except Exception as e:
                await registrar_log_normal(f"Erro ao apagar mensagem inválida: {e}", tipo="erro", bot=bot, canal_id=LOGS_GERAIS)

    elif message.channel.id == CANAL_BANCO and BOT_BANCO_ID != 0 and message.author.id == BOT_BANCO_ID:
        await processar_msg_banco(message, bot, SEU_GUILD_ID, VIP, ARQUIVO_VIPS, ARQUIVO_BANCO_AV,
                                  FUSO_BRT, CFG)

    await bot.process_commands(message)

bot.run(TOKEN)
