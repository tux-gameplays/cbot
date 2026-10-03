import asyncio
import logging
import time
import discord
from datetime import datetime, timezone
from Modulos.webhooks import registrar_log_punicoes

SEGUNDOS_APAGAR_MENSAGENS = 3600
TENTATIVAS_DESBAN = 3
ESPERA_DESBAN = 2
JANELA_REPETICAO = 30

_ultimo_softban = {}

def eh_isento(membro: discord.Member, cfg: dict) -> bool:
    if membro.bot or membro.id == membro.guild.owner_id:
        return True
    gerente = membro.guild.get_role(cfg.get("gerente_role_id", 0))
    if gerente is None:
        logging.warning("Honeypot: cargo GERENTE não encontrado, ninguém será punido.")
        return True
    return any(role.position >= gerente.position for role in membro.roles)

async def resetar_status(membro_id: int, cfg: dict):
    return None

def montar_embed_dm(guild: discord.Guild, canal, convite: str) -> discord.Embed:
    descricao = (
        f"Você mandou uma mensagem em #{canal.name}, um canal armadilha usado para pegar contas invadidas e bots.\n\n"
        "Por segurança, você foi removido do servidor e suas mensagens da última hora foram apagadas.\n\n"
        "Se foi um engano ou se sua conta já está segura (troque a senha e ative a verificação em duas etapas), "
        "você pode voltar quando quiser."
    )
    embed = discord.Embed(title=f"Você foi removido de {guild.name}", description=descricao, color=discord.Color.orange())
    if convite:
        embed.add_field(name="Convite para voltar", value=convite, inline=False)
    return embed

async def enviar_dm_aviso(membro: discord.Member, canal, cfg: dict) -> bool:
    try:
        await membro.send(embed=montar_embed_dm(membro.guild, canal, cfg.get("convite", "")))
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False

async def aplicar_softban(membro: discord.Member, cfg: dict):
    guild = membro.guild
    try:
        await guild.ban(membro, reason="Honeypot: mensagem no canal armadilha",
                        delete_message_seconds=SEGUNDOS_APAGAR_MENSAGENS)
    except discord.HTTPException as e:
        return "falha_ban", str(e)

    erro = ""
    for _ in range(TENTATIVAS_DESBAN):
        try:
            await guild.unban(membro, reason="Honeypot: softban (desban automático)")
            return "ok", None
        except discord.NotFound:
            return "ok", None
        except discord.HTTPException as e:
            erro = str(e)
            await asyncio.sleep(ESPERA_DESBAN)
    return "preso_no_ban", erro

async def registrar_log_honeypot(message: discord.Message, membro: discord.Member, dm_enviada: bool, resultado: str, erro, cfg: dict):
    titulos = {
        "ok": ("🍯 Honeypot: softban aplicado", discord.Color.orange()),
        "falha_ban": ("❌ Honeypot: falha ao banir", discord.Color.red()),
        "preso_no_ban": ("🚨 Honeypot: desban falhou, desbanir manualmente", discord.Color.red()),
    }
    titulo, cor = titulos[resultado]
    embed = discord.Embed(title=titulo, color=cor)
    embed.set_thumbnail(url=membro.avatar.url if membro.avatar else membro.default_avatar.url)
    embed.add_field(name="Usuário", value=f"{membro.mention} (`{membro.name}`)", inline=True)
    embed.add_field(name="ID", value=str(membro.id), inline=True)
    embed.add_field(name="Canal", value=message.channel.mention, inline=True)
    if message.content:
        conteudo = message.content[:500] + ("..." if len(message.content) > 500 else "")
        embed.add_field(name="Conteúdo", value=f"```{conteudo}```", inline=False)
    embed.add_field(name="DM de aviso", value="Enviada" if dm_enviada else "Não enviada (DM fechada)", inline=True)
    embed.add_field(name="Mensagens apagadas", value="Última hora" if resultado == "ok" else "-", inline=True)
    if erro:
        embed.add_field(name="Erro", value=erro[:500], inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    await registrar_log_punicoes(embed, bot=cfg["bot"], canal_id=cfg.get("logs_punicoes"))

async def processar_honeypot(message: discord.Message, cfg: dict) -> bool:
    canal_id = cfg.get("canal_honeypot")
    if not canal_id or message.channel.id != canal_id:
        return False
    if message.guild is None or message.guild.id != cfg["guild_id"]:
        return False
    membro = message.author
    if not isinstance(membro, discord.Member) or eh_isento(membro, cfg):
        return False

    try:
        await message.delete()
    except Exception:
        pass

    agora = time.monotonic()
    for uid in [u for u, t in _ultimo_softban.items() if agora - t > JANELA_REPETICAO]:
        del _ultimo_softban[uid]
    if membro.id in _ultimo_softban:
        return True
    _ultimo_softban[membro.id] = agora

    dm_enviada = await enviar_dm_aviso(membro, message.channel, cfg)
    resultado, erro = await aplicar_softban(membro, cfg)
    if resultado == "ok":
        await resetar_status(membro.id, cfg)
    await registrar_log_honeypot(message, membro, dm_enviada, resultado, erro, cfg)
    return True
