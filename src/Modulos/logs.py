import discord
from datetime import datetime, timezone, timedelta

def get_canal(bot, canal_id):
    if not canal_id:
        return None
    try:
        return bot.get_channel(int(canal_id))
    except Exception:
        return None

async def enviar_log(bot, canal_id, embed: discord.Embed):
    canal = get_canal(bot, canal_id)
    if canal:
        try:
            await canal.send(embed=embed)
        except Exception:
            pass

# ---------- Logs de Membros ----------

async def log_entrada_membro(member: discord.Member, cfg: dict):
    agora = datetime.now(timezone.utc)
    criado_em = member.created_at
    delta = agora - criado_em
    conta_nova = delta.total_seconds() < 86400

    embed = discord.Embed(
        title="📥 Membro entrou",
        color=discord.Color.green() if not conta_nova else discord.Color.red()
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Usuário", value=f"{member.mention} (`{member.name}`)", inline=True)
    embed.add_field(name="ID", value=str(member.id), inline=True)
    embed.add_field(name="Conta criada em", value=criado_em.strftime("%d/%m/%Y %H:%M"), inline=True)
    if conta_nova:
        embed.add_field(name="⚠️ Conta nova", value="Conta criada no mesmo dia da entrada!", inline=False)
    embed.timestamp = agora

    await enviar_log(cfg["bot"], cfg.get("logs_membros"), embed)

async def log_saida_membro(member: discord.Member, cfg: dict):
    tempo_no_server = datetime.now(timezone.utc) - member.joined_at if member.joined_at else None
    cargos = [r.name for r in member.roles if r.name != "@everyone"]

    embed = discord.Embed(title="📤 Membro saiu", color=discord.Color.orange())
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Usuário", value=f"{member.mention} (`{member.name}`)", inline=True)
    embed.add_field(name="ID", value=str(member.id), inline=True)
    if tempo_no_server:
        dias = tempo_no_server.days
        embed.add_field(name="Tempo no servidor", value=f"{dias} dia(s)", inline=True)
    if cargos:
        embed.add_field(name="Cargos que tinha", value=", ".join(cargos[:10]), inline=False)
    embed.timestamp = datetime.now(timezone.utc)

    await enviar_log(cfg["bot"], cfg.get("logs_membros"), embed)

async def log_cargo_alterado(member: discord.Member, antes: discord.Member, cfg: dict):
    cargos_antes = set(antes.roles)
    cargos_depois = set(member.roles)

    adicionados = cargos_depois - cargos_antes
    removidos = cargos_antes - cargos_depois

    if not adicionados and not removidos:
        return

    embed = discord.Embed(title="🏷️ Cargo alterado", color=discord.Color.blurple())
    embed.add_field(name="Usuário", value=f"{member.mention} (`{member.name}`)", inline=True)
    embed.add_field(name="ID", value=str(member.id), inline=True)

    if adicionados:
        embed.add_field(name="➕ Adicionados", value=", ".join(r.name for r in adicionados), inline=False)
    if removidos:
        embed.add_field(name="➖ Removidos", value=", ".join(r.name for r in removidos), inline=False)

    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_membros"), embed)

# ---------- Logs de Mensagens ----------

async def log_mensagem_apagada(message: discord.Message, cfg: dict):
    if message.author.bot:
        return
    if not message.content and not message.attachments:
        return

    embed = discord.Embed(title="🗑️ Mensagem apagada", color=discord.Color.red())
    embed.add_field(name="Autor", value=f"{message.author.mention} (`{message.author.name}`)", inline=True)
    embed.add_field(name="Canal", value=message.channel.mention, inline=True)

    if message.content:
        conteudo = message.content[:1000] + ("..." if len(message.content) > 1000 else "")
        embed.add_field(name="Conteúdo", value=f"```{conteudo}```", inline=False)

    if message.attachments:
        embed.add_field(name="Anexos", value="\n".join(a.filename for a in message.attachments), inline=False)

    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=f"ID do autor: {message.author.id}")

    await enviar_log(cfg["bot"], cfg.get("logs_mensagens"), embed)

async def log_mensagem_editada(antes: discord.Message, depois: discord.Message, cfg: dict):
    if antes.author.bot:
        return
    if antes.content == depois.content:
        return

    embed = discord.Embed(title="✏️ Mensagem editada", color=discord.Color.yellow())
    embed.add_field(name="Autor", value=f"{antes.author.mention} (`{antes.author.name}`)", inline=True)
    embed.add_field(name="Canal", value=antes.channel.mention, inline=True)

    antes_curto = antes.content[:500] + ("..." if len(antes.content) > 500 else "")
    depois_curto = depois.content[:500] + ("..." if len(depois.content) > 500 else "")

    embed.add_field(name="Antes", value=f"```{antes_curto}```", inline=False)
    embed.add_field(name="Depois", value=f"```{depois_curto}```", inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=f"ID: {antes.id}")

    await enviar_log(cfg["bot"], cfg.get("logs_mensagens"), embed)

# ---------- Logs de Calls ----------

async def log_call(membro: discord.Member, tipo: str, canal_antes=None, canal_depois=None, cfg: dict = None):
    titulos = {
        "entrou": ("📞 Entrou na call", discord.Color.green()),
        "saiu": ("📴 Saiu da call", discord.Color.red()),
        "movido": ("↔️ Movido de call", discord.Color.blurple()),
        "expulso": ("👢 Expulso da call", discord.Color.orange()),
        "mute_admin": ("🔇 Mutado por admin", discord.Color.dark_red()),
        "surdo_admin": ("🔕 Ensurdecido por admin", discord.Color.dark_red()),
    }

    titulo, cor = titulos.get(tipo, ("🎙️ Evento de call", discord.Color.greyple()))
    embed = discord.Embed(title=titulo, color=cor)
    embed.add_field(name="Usuário", value=f"{membro.mention} (`{membro.name}`)", inline=True)
    embed.add_field(name="ID", value=str(membro.id), inline=True)

    if tipo == "movido" and canal_antes and canal_depois:
        embed.add_field(name="De", value=canal_antes.mention, inline=True)
        embed.add_field(name="Para", value=canal_depois.mention, inline=True)
    elif canal_depois:
        embed.add_field(name="Canal", value=canal_depois.mention, inline=True)
    elif canal_antes:
        embed.add_field(name="Canal", value=canal_antes.mention, inline=True)

    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_calls"), embed)

async def processar_log_call(antes: discord.VoiceState, depois: discord.VoiceState, membro: discord.Member, cfg: dict):
    canal_live = cfg.get("call_live", 0)

    canal_antes = antes.channel
    canal_depois = depois.channel

    relevante_antes = canal_antes and canal_antes.id == canal_live
    relevante_depois = canal_depois and canal_depois.id == canal_live

    if not relevante_antes and not relevante_depois:
        return

    if not antes.mute and depois.mute and canal_depois:
        if depois.channel == canal_depois:
            await log_call(membro, "mute_admin", canal_depois=canal_depois, cfg=cfg)
            return

    if not antes.deaf and depois.deaf and canal_depois:
        await log_call(membro, "surdo_admin", canal_depois=canal_depois, cfg=cfg)
        return

    if canal_antes == canal_depois:
        return

    if not canal_antes and canal_depois:
        await log_call(membro, "entrou", canal_depois=canal_depois, cfg=cfg)
    elif canal_antes and not canal_depois:
        await log_call(membro, "saiu", canal_antes=canal_antes, cfg=cfg)
    elif canal_antes and canal_depois:
        await log_call(membro, "movido", canal_antes=canal_antes, canal_depois=canal_depois, cfg=cfg)

# ---------- Logs de Punições ----------

async def log_punicao_externa(entry: discord.AuditLogEntry, cfg: dict):
    acoes = {
        discord.AuditLogAction.ban: ("🔨 Ban aplicado", discord.Color.dark_red()),
        discord.AuditLogAction.unban: ("🔓 Unban aplicado", discord.Color.green()),
        discord.AuditLogAction.kick: ("👢 Kick aplicado", discord.Color.orange()),
        discord.AuditLogAction.member_update: ("⏱️ Timeout aplicado", discord.Color.red()),
    }

    if entry.action not in acoes:
        return

    titulo, cor = acoes[entry.action]
    embed = discord.Embed(title=titulo, color=cor)

    if entry.target:
        embed.add_field(name="Usuário", value=f"<@{entry.target.id}> (`{entry.target}`)", inline=True)
        embed.add_field(name="ID", value=str(entry.target.id), inline=True)

    if entry.user:
        embed.add_field(name="Executado por", value=f"{entry.user.mention} (`{entry.user.name}`)", inline=True)

    if entry.reason:
        embed.add_field(name="Motivo", value=entry.reason, inline=False)

    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_punicoes"), embed)

# ---------- Logs de Servidor ----------

async def log_servidor_atualizado(antes: discord.Guild, depois: discord.Guild, cfg: dict):
    mudancas = []
    if antes.name != depois.name:
        mudancas.append(f"**Nome:** `{antes.name}` → `{depois.name}`")
    if antes.icon != depois.icon:
        mudancas.append("**Ícone:** alterado")
    if antes.description != depois.description:
        mudancas.append(f"**Descrição:** alterada")

    if not mudancas:
        return

    embed = discord.Embed(title="🏠 Servidor atualizado", color=discord.Color.blurple())
    embed.add_field(name="Mudanças", value="\n".join(mudancas), inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_servidor"), embed)

# ---------- Logs de Canais ----------

async def log_canal_criado(canal: discord.abc.GuildChannel, cfg: dict):
    embed = discord.Embed(title="➕ Canal criado", color=discord.Color.green())
    embed.add_field(name="Nome", value=canal.name, inline=True)
    embed.add_field(name="Tipo", value=str(canal.type).split(".")[-1], inline=True)
    embed.add_field(name="Categoria", value=canal.category.name if canal.category else "Nenhuma", inline=True)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_canais"), embed)

async def log_canal_deletado(canal: discord.abc.GuildChannel, cfg: dict):
    embed = discord.Embed(title="➖ Canal deletado", color=discord.Color.red())
    embed.add_field(name="Nome", value=canal.name, inline=True)
    embed.add_field(name="Tipo", value=str(canal.type).split(".")[-1], inline=True)
    embed.add_field(name="Categoria", value=canal.category.name if canal.category else "Nenhuma", inline=True)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_canais"), embed)

async def log_canal_atualizado(antes: discord.abc.GuildChannel, depois: discord.abc.GuildChannel, cfg: dict):
    mudancas = []
    if antes.name != depois.name:
        mudancas.append(f"**Nome:** `{antes.name}` → `{depois.name}`")

    if hasattr(antes, "topic") and hasattr(depois, "topic"):
        if antes.topic != depois.topic:
            mudancas.append(f"**Tópico:** alterado")

    if hasattr(antes, "overwrites") and hasattr(depois, "overwrites"):
        if antes.overwrites != depois.overwrites:
            mudancas.append("**Permissões:** alteradas")

    if not mudancas:
        return

    embed = discord.Embed(title="✏️ Canal atualizado", color=discord.Color.yellow())
    embed.add_field(name="Canal", value=depois.mention if hasattr(depois, "mention") else depois.name, inline=True)
    embed.add_field(name="Mudanças", value="\n".join(mudancas), inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_canais"), embed)

# ---------- Logs de Cargos ----------

async def log_cargo_criado(cargo: discord.Role, cfg: dict):
    embed = discord.Embed(title="➕ Cargo criado", color=cargo.color if cargo.color != discord.Color.default() else discord.Color.green())
    embed.add_field(name="Nome", value=cargo.name, inline=True)
    embed.add_field(name="ID", value=str(cargo.id), inline=True)
    embed.add_field(name="Cor", value=str(cargo.color), inline=True)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_cargos"), embed)

async def log_cargo_deletado(cargo: discord.Role, cfg: dict):
    embed = discord.Embed(title="➖ Cargo deletado", color=discord.Color.red())
    embed.add_field(name="Nome", value=cargo.name, inline=True)
    embed.add_field(name="ID", value=str(cargo.id), inline=True)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_cargos"), embed)

async def log_cargo_atualizado(antes: discord.Role, depois: discord.Role, cfg: dict):
    mudancas = []
    if antes.name != depois.name:
        mudancas.append(f"**Nome:** `{antes.name}` → `{depois.name}`")
    if antes.color != depois.color:
        mudancas.append(f"**Cor:** `{antes.color}` → `{depois.color}`")
    if antes.permissions != depois.permissions:
        mudancas.append("**Permissões:** alteradas")

    if not mudancas:
        return

    embed = discord.Embed(title="✏️ Cargo atualizado", color=discord.Color.yellow())
    embed.add_field(name="Cargo", value=depois.name, inline=True)
    embed.add_field(name="ID", value=str(depois.id), inline=True)
    embed.add_field(name="Mudanças", value="\n".join(mudancas), inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_cargos"), embed)
