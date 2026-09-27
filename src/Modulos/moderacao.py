import discord
import json
import os
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict

JANELA_AVISO_SEGUNDOS = 5400  # 1h30

_historico_msgs = defaultdict(list)
_historico_msgs_conteudo = defaultdict(list)

DOMINIOS_DIVULGACAO = [
    r"discord\.gg/",
    r"discord\.com/invite/",
    r"discordapp\.com/invite/",
    r"t\.me/",
    r"chat\.whatsapp\.com/"
]

DOMINIOS_LINKS_PERMITIDOS = [
    r"youtube\.com",
    r"youtu\.be",
    r"tenor\.com",
    r"giphy\.com",
]

def carregar_moderacao(arquivo: str) -> dict:
    if not arquivo or not os.path.exists(arquivo):
        return {"avisos": {}}
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"avisos": {}}

def salvar_moderacao(dados: dict, arquivo: str):
    if not arquivo:
        return
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def registrar_aviso(user_id: int, tipo: str, arquivo: str):
    dados = carregar_moderacao(arquivo)
    user_str = str(user_id)
    agora = datetime.now(timezone.utc).isoformat()
    if user_str not in dados["avisos"]:
        dados["avisos"][user_str] = {}
    dados["avisos"][user_str][tipo] = agora
    salvar_moderacao(dados, arquivo)

def checar_segundo_aviso(user_id: int, tipo: str, arquivo: str) -> bool:
    dados = carregar_moderacao(arquivo)
    user_str = str(user_id)
    avisos = dados.get("avisos", {}).get(user_str, {})
    if tipo not in avisos:
        return False
    ultimo = datetime.fromisoformat(avisos[tipo])
    agora = datetime.now(timezone.utc)
    return (agora - ultimo).total_seconds() <= JANELA_AVISO_SEGUNDOS

def eh_imune(membro: discord.Member, admin_role_id: int) -> bool:
    admin_role = membro.guild.get_role(admin_role_id)
    if admin_role is None:
        return False
    return any(role.position > admin_role.position for role in membro.roles)

def detectar_divulgacao(conteudo: str) -> bool:
    for padrao in DOMINIOS_DIVULGACAO:
        if re.search(padrao, conteudo, re.IGNORECASE):
            return True
    return False

def detectar_link_bloqueado(conteudo: str) -> bool:
    url_padrao = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)
    urls = url_padrao.findall(conteudo)
    for url in urls:
        permitido = any(re.search(d, url, re.IGNORECASE) for d in DOMINIOS_LINKS_PERMITIDOS)
        if not permitido:
            return True
    return False

def detectar_flood(user_id: int, conteudo: str):
    agora = datetime.now(timezone.utc)

    historico = _historico_msgs[user_id]
    historico.append(agora)
    _historico_msgs[user_id] = [t for t in historico if (agora - t).total_seconds() <= 5]

    conteudos = _historico_msgs_conteudo[user_id]
    conteudos.append(conteudo)
    if len(conteudos) > 10:
        conteudos.pop(0)
    _historico_msgs_conteudo[user_id] = conteudos

    if len(conteudos) >= 3 and len(set(conteudos[-3:])) == 1:
        return "repetidas"

    if len(_historico_msgs[user_id]) >= 5:
        return "rapidas"

    return None

async def enviar_aviso_canal(canal: discord.TextChannel, membro: discord.Member, mensagem: str):
    import asyncio
    try:
        msg = await canal.send(f"{membro.mention} {mensagem}")
        await asyncio.sleep(10)
        try:
            await msg.delete()
        except Exception:
            pass
    except Exception:
        pass

async def log_moderacao(message: discord.Message, tipo: str, cfg: dict):
    canal_id = cfg.get("logs_moderacao")
    if not canal_id:
        return
    canal = cfg["bot"].get_channel(int(canal_id))
    if not canal:
        return

    titulos = {
        "divulgacao": "🚫 Divulgação bloqueada",
        "link": "🔗 Link bloqueado",
        "repetidas": "🔁 Flood (mensagens repetidas)",
        "rapidas": "⚡ Flood (mensagens rápidas)",
        "comando_local": "⌨️ Comando em local errado"
    }

    embed = discord.Embed(title=titulos.get(tipo, "⚠️ Moderação automática"), color=discord.Color.orange())
    embed.add_field(name="Usuário", value=f"{message.author.mention} (`{message.author.name}`)", inline=True)
    embed.add_field(name="Canal", value=message.channel.mention, inline=True)
    conteudo_curto = message.content[:500] + ("..." if len(message.content) > 500 else "")
    embed.add_field(name="Conteúdo", value=f"```{conteudo_curto}```", inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=f"ID: {message.author.id}")

    await canal.send(embed=embed)

async def processar_moderacao(message: discord.Message, cfg: dict) -> bool:
    if not isinstance(message.author, discord.Member):
        return False
    if eh_imune(message.author, cfg["admin_role_id"]):
        return False
    if message.author.bot:
        return False

    conteudo = message.content
    user_id = message.author.id
    arquivo = cfg["arquivo_moderacao"]

    if detectar_divulgacao(conteudo):
        segundo = checar_segundo_aviso(user_id, "divulgacao", arquivo)
        try:
            await message.delete()
        except Exception:
            pass
        if segundo:
            from Modulos.warns import criar_warn
            await criar_warn(user_id, message.guild.me.id, "Divulgação de servidor (automático)", False,
                             cfg["bot"], cfg["guild_id"], cfg["arquivo_warns"], cfg["fuso_brt"])
            await enviar_aviso_canal(message.channel, message.author,
                                     "⚠️ Divulgação não é permitida. Warn aplicado automaticamente.")
        else:
            registrar_aviso(user_id, "divulgacao", arquivo)
            await enviar_aviso_canal(message.channel, message.author,
                                     "🚫 Divulgação de outros servidores não é permitida aqui.")
        await log_moderacao(message, "divulgacao", cfg)
        return True

    if detectar_link_bloqueado(conteudo):
        segundo = checar_segundo_aviso(user_id, "link", arquivo)
        try:
            await message.delete()
        except Exception:
            pass
        if segundo:
            from Modulos.warns import criar_warn
            await criar_warn(user_id, message.guild.me.id, "Link não permitido (automático)", False,
                             cfg["bot"], cfg["guild_id"], cfg["arquivo_warns"], cfg["fuso_brt"])
            await enviar_aviso_canal(message.channel, message.author,
                                     "⚠️ Links não são permitidos aqui. Warn aplicado automaticamente.")
        else:
            registrar_aviso(user_id, "link", arquivo)
            await enviar_aviso_canal(message.channel, message.author,
                                     "🚫 Links não são permitidos aqui. Apenas YouTube e GIFs do Discord.")
        await log_moderacao(message, "link", cfg)
        return True

    tipo_flood = detectar_flood(user_id, conteudo)
    if tipo_flood:
        segundo = checar_segundo_aviso(user_id, "flood", arquivo)
        try:
            await message.delete()
        except Exception:
            pass
        if segundo:
            from Modulos.warns import criar_warn
            await criar_warn(user_id, message.guild.me.id, "Spam/flood (automático)", False,
                             cfg["bot"], cfg["guild_id"], cfg["arquivo_warns"], cfg["fuso_brt"])
            await enviar_aviso_canal(message.channel, message.author,
                                     "⚠️ Para de spammar. Warn aplicado automaticamente.")
        else:
            registrar_aviso(user_id, "flood", arquivo)
            await enviar_aviso_canal(message.channel, message.author,
                                     "🚫 Não envie mensagens repetidas ou muito rápido.")
        await log_moderacao(message, tipo_flood, cfg)
        return True

    return False

async def processar_comando_local_errado(message: discord.Message, cfg: dict) -> bool:
    if not isinstance(message.author, discord.Member):
        return False
    if eh_imune(message.author, cfg["admin_role_id"]):
        return False
    if not message.content.startswith("c+"):
        return False

    canal_comandos = cfg.get("canal_comandos", 0)
    canal_antecipado = cfg.get("codigo_antecipado", 0)
    canal_publico = cfg.get("codigo_publico", 0)
    eh_cod = message.content.lower().startswith("c+cod")

    if message.channel.id in [canal_antecipado, canal_publico]:
        if not eh_cod:
            segundo = checar_segundo_aviso(message.author.id, "comando_local", cfg["arquivo_moderacao"])
            try:
                await message.delete()
            except Exception:
                pass
            if segundo:
                from Modulos.warns import criar_warn
                await criar_warn(message.author.id, message.guild.me.id, "Comando em local errado (automático)", False,
                                 cfg["bot"], cfg["guild_id"], cfg["arquivo_warns"], cfg["fuso_brt"])
                await enviar_aviso_canal(message.channel, message.author,
                                         "⚠️ Apenas `c+cod` é permitido aqui. Warn aplicado.")
            else:
                registrar_aviso(message.author.id, "comando_local", cfg["arquivo_moderacao"])
                await enviar_aviso_canal(message.channel, message.author,
                                         f"🚫 Apenas `c+cod` é permitido neste canal. Use <#{canal_comandos}> para outros comandos.")
            await log_moderacao(message, "comando_local", cfg)
            return True

    elif message.channel.id != canal_comandos:
        segundo = checar_segundo_aviso(message.author.id, "comando_local", cfg["arquivo_moderacao"])
        try:
            await message.delete()
        except Exception:
            pass
        if segundo:
            from Modulos.warns import criar_warn
            await criar_warn(message.author.id, message.guild.me.id, "Comando em local errado (automático)", False,
                             cfg["bot"], cfg["guild_id"], cfg["arquivo_warns"], cfg["fuso_brt"])
            await enviar_aviso_canal(message.channel, message.author,
                                     "⚠️ Comandos não são permitidos aqui. Warn aplicado.")
        else:
            registrar_aviso(message.author.id, "comando_local", cfg["arquivo_moderacao"])
            await enviar_aviso_canal(message.channel, message.author,
                                     f"🚫 Comandos só podem ser usados em <#{canal_comandos}>.")
        await log_moderacao(message, "comando_local", cfg)
        return True

    return False
