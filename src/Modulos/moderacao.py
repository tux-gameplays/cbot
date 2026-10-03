import discord
import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict

JANELA_AVISO_SEGUNDOS = 5400  # 1h30

_historico_msgs = defaultdict(list)
_historico_msgs_conteudo = defaultdict(list)

DOMINIOS_DIVULGACAO = [
    r"discord\.gg/\S+",
    r"discord\.com/invite/\S+",
    r"discordapp\.com/invite/\S+",
    r"t\.me/\S+",
    r"chat\.whatsapp\.com/\S+",
]

DOMINIOS_LINKS_PERMITIDOS = [
    r"youtube\.com",
    r"youtu\.be",
    r"tenor\.com",
    r"giphy\.com",
]

def como_lista(valor) -> list[int]:
    if isinstance(valor, (list, tuple, set)):
        return [int(x) for x in valor if x]
    return [int(valor)] if valor else []

def canal_com_links_liberados(message: discord.Message, cfg: dict) -> bool:
    liberados = como_lista(cfg.get("canais_links_whitelist"))
    ids = {message.channel.id, getattr(message.channel, "parent_id", None)}
    return any(i in liberados for i in ids if i)

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
    ultimo_str = avisos[tipo]
    ultimo = datetime.fromisoformat(ultimo_str)
    if ultimo.tzinfo is None:
        ultimo = ultimo.replace(tzinfo=timezone.utc)
    agora = datetime.now(timezone.utc)
    return (agora - ultimo).total_seconds() <= JANELA_AVISO_SEGUNDOS

def eh_imune(membro: discord.Member, admin_role_id: int) -> bool:
    # Imune apenas se ACIMA de administrador (não inclui o próprio cargo)
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
    url_padrao = re.compile(r"https?://[^\s<>]+|www\.[^\s<>]+", re.IGNORECASE)
    urls = url_padrao.findall(conteudo)
    for url in urls:
        # Ignora URLs de divulgação — já tratadas antes
        if detectar_divulgacao(url):
            continue
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
    if conteudo_curto:
        embed.add_field(name="Conteúdo", value=f"```{conteudo_curto}```", inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=f"ID: {message.author.id}")

    await canal.send(embed=embed)

async def _aplicar_ou_avisar(message: discord.Message, tipo: str, aviso_texto: str, warn_texto: str, cfg: dict):
    arquivo = cfg["arquivo_moderacao"]
    user_id = message.author.id
    segundo = checar_segundo_aviso(user_id, tipo, arquivo)

    try:
        await message.delete()
    except Exception:
        pass

    if segundo:
        from Modulos.warns import criar_warn
        await criar_warn(user_id, message.guild.me.id, warn_texto, False,
                         cfg["bot"], cfg["guild_id"], cfg["arquivo_warns"], cfg["fuso_brt"])
        await enviar_aviso_canal(message.channel, message.author,
                                 f"⚠️ {warn_texto}. Warn aplicado automaticamente.")
    else:
        registrar_aviso(user_id, tipo, arquivo)
        await enviar_aviso_canal(message.channel, message.author, f"🚫 {aviso_texto}")

    await log_moderacao(message, tipo, cfg)

async def processar_moderacao(message: discord.Message, cfg: dict) -> bool:
    if not isinstance(message.author, discord.Member):
        return False
    if message.guild.id != cfg["guild_id"]:
        return False
    if eh_imune(message.author, cfg["admin_role_id"]):
        return False
    if message.author.bot:
        return False

    conteudo = message.content

    if detectar_divulgacao(conteudo):
        await _aplicar_ou_avisar(message, "divulgacao",
                                  "Divulgação de outros servidores não é permitida aqui.",
                                  "Divulgação de servidor", cfg)
        return True

    if not canal_com_links_liberados(message, cfg) and detectar_link_bloqueado(conteudo):
        await _aplicar_ou_avisar(message, "link",
                                  "Links não são permitidos aqui. Apenas YouTube e GIFs do Discord.",
                                  "Link não permitido", cfg)
        return True

    tipo_flood = detectar_flood(message.author.id, conteudo)
    if tipo_flood:
        await _aplicar_ou_avisar(message, "flood",
                                  "Não envie mensagens repetidas ou muito rápido.",
                                  "Spam/flood", cfg)
        return True

    return False

async def processar_comando_local_errado(message: discord.Message, cfg: dict) -> bool:
    if not isinstance(message.author, discord.Member):
        return False
    if message.guild.id != cfg["guild_id"]:
        return False
    if eh_imune(message.author, cfg["admin_role_id"]):
        return False
    if not message.content.startswith("c+"):
        return False

    canais_comandos = como_lista(cfg.get("canal_comandos"))
    mencoes_comandos = ", ".join(f"<#{c}>" for c in canais_comandos)
    canal_antecipado = cfg.get("codigo_antecipado", 0)
    canal_publico = cfg.get("codigo_publico", 0)
    eh_cod = message.content.lower().startswith("c+cod")

    if message.channel.id in [canal_antecipado, canal_publico]:
        if not eh_cod:
            await _aplicar_ou_avisar(message, "comando_local",
                                      f"Apenas `c+cod` é permitido neste canal. Use {mencoes_comandos} para outros comandos.",
                                      "Comando em local errado", cfg)
            return True

    elif canais_comandos and message.channel.id not in canais_comandos:
        await _aplicar_ou_avisar(message, "comando_local",
                                  f"Comandos só podem ser usados em {mencoes_comandos}.",
                                  "Comando em local errado", cfg)
        return True

    return False
