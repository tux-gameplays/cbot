import discord
import asyncio
import logging
from datetime import datetime, timezone, timedelta

_pending_channel_updates = {}
_pending_role_updates = {}
_pending_server_updates = {}

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

def diff_permissoes(antes: discord.PermissionOverwrite, depois: discord.PermissionOverwrite) -> list[str]:
    linhas = []
    perm_nomes = {
        "view_channel": "Ver canal",
        "send_messages": "Enviar mensagens",
        "read_message_history": "Ver histórico",
        "connect": "Conectar",
        "speak": "Falar",
        "manage_messages": "Gerenciar mensagens",
        "mention_everyone": "Mencionar todos",
        "attach_files": "Anexar arquivos",
        "embed_links": "Incorporar links",
        "add_reactions": "Adicionar reações",
        "use_external_emojis": "Emojis externos",
        "mute_members": "Mutar membros",
        "deafen_members": "Ensurdecer membros",
        "move_members": "Mover membros",
        "administrator": "Administrador",
        "manage_channels": "Gerenciar canais",
        "manage_roles": "Gerenciar cargos",
        "kick_members": "Expulsar membros",
        "ban_members": "Banir membros",
    }
    antes_dict = dict(iter(antes)) if antes else {}
    depois_dict = dict(iter(depois)) if depois else {}
    todas = set(antes_dict) | set(depois_dict)
    for perm in todas:
        v_antes = antes_dict.get(perm)
        v_depois = depois_dict.get(perm)
        if v_antes != v_depois:
            nome = perm_nomes.get(perm, perm)
            icone_antes = "✅" if v_antes else ("❌" if v_antes is False else "➖")
            icone_depois = "✅" if v_depois else ("❌" if v_depois is False else "➖")
            linhas.append(f"`{nome}`: {icone_antes} → {icone_depois}")
    return linhas

# ---------- Logs de Membros ----------

async def log_entrada_membro(member: discord.Member, cfg: dict):
    agora = datetime.now(timezone.utc)
    criado_em = member.created_at
    delta = agora - criado_em
    conta_nova = delta.total_seconds() < 86400

    embed = discord.Embed(color=discord.Color.green() if not conta_nova else discord.Color.red())
    embed.set_author(name=f"{member.display_name} entrou no servidor", icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Usuário", value=f"{member.mention} (`{member.name}`)", inline=True)
    embed.add_field(name="ID", value=str(member.id), inline=True)
    embed.add_field(name="Conta criada em", value=f"<t:{int(criado_em.timestamp())}:R>", inline=True)
    if conta_nova:
        embed.add_field(name="⚠️ Conta nova", value="Conta criada no mesmo dia da entrada!", inline=False)
    embed.timestamp = agora

    await enviar_log(cfg["bot"], cfg.get("logs_membros"), embed)

async def log_saida_membro(member: discord.Member, cfg: dict):
    tempo_no_server = datetime.now(timezone.utc) - member.joined_at if member.joined_at else None
    cargos = [r.name for r in member.roles if r.name != "@everyone"]

    embed = discord.Embed(color=discord.Color.orange())
    embed.set_author(name=f"{member.display_name} saiu do servidor", icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Usuário", value=f"{member.mention} (`{member.name}`)", inline=True)
    embed.add_field(name="ID", value=str(member.id), inline=True)
    if tempo_no_server:
        embed.add_field(name="Tempo no servidor", value=f"{tempo_no_server.days} dia(s)", inline=True)
    if cargos:
        embed.add_field(name="Cargos que tinha", value=", ".join(cargos[:15]), inline=False)
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
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Usuário", value=f"{member.mention} (`{member.name}`)", inline=True)
    embed.add_field(name="ID", value=str(member.id), inline=True)
    if adicionados:
        embed.add_field(name="➕ Adicionados", value=", ".join(r.mention for r in adicionados), inline=False)
    if removidos:
        embed.add_field(name="➖ Removidos", value=", ".join(r.mention for r in removidos), inline=False)
    embed.timestamp = datetime.now(timezone.utc)

    await enviar_log(cfg["bot"], cfg.get("logs_membros"), embed)

async def log_apelido_alterado(antes: discord.Member, depois: discord.Member, cfg: dict):
    if antes.display_name == depois.display_name:
        return

    embed = discord.Embed(title="✏️ Apelido alterado", color=discord.Color.yellow())
    embed.set_thumbnail(url=depois.avatar.url if depois.avatar else depois.default_avatar.url)
    embed.add_field(name="Usuário", value=f"{depois.mention} (`{depois.name}`)", inline=True)
    embed.add_field(name="ID", value=str(depois.id), inline=True)
    embed.add_field(name="Antigo apelido", value=f"`{antes.display_name}`", inline=False)
    embed.add_field(name="Novo apelido", value=f"`{depois.display_name}`", inline=False)
    embed.timestamp = datetime.now(timezone.utc)

    await enviar_log(cfg["bot"], cfg.get("logs_membros"), embed)

# ---------- Logs de Mensagens ----------

async def log_mensagem_apagada(message: discord.Message, cfg: dict):
    if message.author.bot:
        return
    if not message.content and not message.attachments:
        return

    embed = discord.Embed(title="🗑️ Mensagem apagada", color=discord.Color.red())
    embed.set_author(name=f"{message.author.display_name}", icon_url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)
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
    embed.set_author(name=f"{antes.author.display_name}", icon_url=antes.author.avatar.url if antes.author.avatar else antes.author.default_avatar.url)
    embed.add_field(name="Autor", value=f"{antes.author.mention} (`{antes.author.name}`)", inline=True)
    embed.add_field(name="Canal", value=antes.channel.mention, inline=True)

    antes_curto = antes.content[:500] + ("..." if len(antes.content) > 500 else "")
    depois_curto = depois.content[:500] + ("..." if len(depois.content) > 500 else "")

    embed.add_field(name="Antes", value=f"```{antes_curto}```" if antes_curto else "*vazio*", inline=False)
    embed.add_field(name="Depois", value=f"```{depois_curto}```" if depois_curto else "*vazio*", inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=f"ID da msg: {antes.id}")

    await enviar_log(cfg["bot"], cfg.get("logs_mensagens"), embed)

# ---------- Logs de Calls ----------

async def log_call(membro: discord.Member, tipo: str, canal_antes=None, canal_depois=None, cfg: dict = None):
    titulos = {
        "entrou": ("📞 Entrou na call", discord.Color.green()),
        "saiu": ("📴 Saiu da call", discord.Color.red()),
        "movido": ("↔️ Movido entre calls", discord.Color.blurple()),
        "expulso": ("👢 Expulso da call", discord.Color.orange()),
        "mute_admin": ("🔇 Mutado por admin", discord.Color.dark_red()),
        "surdo_admin": ("🔕 Ensurdecido por admin", discord.Color.dark_red()),
        "desmute_admin": ("🔊 Desmutado por admin", discord.Color.green()),
        "dessurdo_admin": ("🔔 Desensurdecido por admin", discord.Color.green()),
    }

    titulo, cor = titulos.get(tipo, ("🎙️ Evento de call", discord.Color.greyple()))
    embed = discord.Embed(title=titulo, color=cor)
    embed.set_thumbnail(url=membro.avatar.url if membro.avatar else membro.default_avatar.url)
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
    canal_antes = antes.channel
    canal_depois = depois.channel

    # Detecta mute/surdo por admin (diferente de si mesmo)
    if canal_antes == canal_depois and canal_depois:
        if antes.mute != depois.mute:
            tipo = "mute_admin" if depois.mute else "desmute_admin"
            await log_call(membro, tipo, canal_depois=canal_depois, cfg=cfg)
            return
        if antes.deaf != depois.deaf:
            tipo = "surdo_admin" if depois.deaf else "dessurdo_admin"
            await log_call(membro, tipo, canal_depois=canal_depois, cfg=cfg)
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

async def _flush_server_update(guild_id: int, cfg: dict):
    await asyncio.sleep(5)
    data = _pending_server_updates.pop(guild_id, None)
    if not data:
        return
    antes, depois = data

    mudancas = []
    if antes.name != depois.name:
        mudancas.append(f"**Nome:** `{antes.name}` → `{depois.name}`")
    if antes.icon != depois.icon:
        mudancas.append("**Ícone:** alterado")
    if antes.description != depois.description:
        mudancas.append(f"**Descrição:** alterada")
    if antes.afk_channel != depois.afk_channel:
        mudancas.append(f"**Canal AFK:** alterado")
    if antes.verification_level != depois.verification_level:
        mudancas.append(f"**Nível de verificação:** `{antes.verification_level}` → `{depois.verification_level}`")
    if antes.default_notifications != depois.default_notifications:
        mudancas.append(f"**Notificações padrão:** alteradas")

    if not mudancas:
        return

    embed = discord.Embed(title="🏠 Servidor atualizado", color=discord.Color.blurple())
    embed.add_field(name="Mudanças", value="\n".join(mudancas), inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_servidor"), embed)

async def log_servidor_atualizado(antes: discord.Guild, depois: discord.Guild, cfg: dict):
    _pending_server_updates[depois.id] = (antes, depois)
    asyncio.get_event_loop().create_task(_flush_server_update(depois.id, cfg))

# ---------- Logs de Canais ----------

async def _flush_channel_update(canal_id: int, cfg: dict):
    await asyncio.sleep(5)
    data = _pending_channel_updates.pop(canal_id, None)
    if not data:
        return
    antes, depois = data

    mudancas = []
    if antes.name != depois.name:
        mudancas.append(f"**Nome:** `{antes.name}` → `{depois.name}`")

    if hasattr(antes, "topic") and hasattr(depois, "topic") and antes.topic != depois.topic:
        mudancas.append("**Tópico:** alterado")

    if hasattr(antes, "overwrites") and hasattr(depois, "overwrites"):
        todos_targets = set(antes.overwrites) | set(depois.overwrites)
        for target in todos_targets:
            ow_antes = antes.overwrites.get(target, discord.PermissionOverwrite())
            ow_depois = depois.overwrites.get(target, discord.PermissionOverwrite())
            diffs = diff_permissoes(ow_antes, ow_depois)
            if diffs:
                nome_target = getattr(target, "mention", getattr(target, "name", str(target)))
                mudancas.append(f"**Permissões de {nome_target}:**\n" + "\n".join(diffs[:5]))

    if not mudancas:
        return

    embed = discord.Embed(title="✏️ Canal atualizado", color=discord.Color.yellow())
    embed.add_field(name="Canal", value=depois.mention if hasattr(depois, "mention") else depois.name, inline=True)
    embed.add_field(name="Mudanças", value="\n".join(mudancas)[:1024], inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_canais"), embed)

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
    _pending_channel_updates[depois.id] = (antes, depois)
    asyncio.get_event_loop().create_task(_flush_channel_update(depois.id, cfg))

# ---------- Logs de Cargos ----------

async def _flush_role_update(role_id: int, cfg: dict):
    await asyncio.sleep(5)
    data = _pending_role_updates.pop(role_id, None)
    if not data:
        return
    antes, depois = data

    mudancas = []
    if antes.name != depois.name:
        mudancas.append(f"**Nome:** `{antes.name}` → `{depois.name}`")
    if antes.color != depois.color:
        mudancas.append(f"**Cor:** `{antes.color}` → `{depois.color}`")
    if antes.hoist != depois.hoist:
        mudancas.append(f"**Exibir separado:** `{antes.hoist}` → `{depois.hoist}`")
    if antes.mentionable != depois.mentionable:
        mudancas.append(f"**Mencionável:** `{antes.mentionable}` → `{depois.mentionable}`")

    # Diff de permissões do cargo
    perms_antes = dict(antes.permissions)
    perms_depois = dict(depois.permissions)
    perm_nomes = {
        "administrator": "Administrador", "manage_guild": "Gerenciar servidor",
        "manage_channels": "Gerenciar canais", "manage_roles": "Gerenciar cargos",
        "manage_messages": "Gerenciar mensagens", "kick_members": "Expulsar membros",
        "ban_members": "Banir membros", "mention_everyone": "Mencionar todos",
        "view_audit_log": "Ver auditoria", "send_messages": "Enviar mensagens",
    }
    for perm, nome in perm_nomes.items():
        v_antes = perms_antes.get(perm, False)
        v_depois = perms_depois.get(perm, False)
        if v_antes != v_depois:
            mudancas.append(f"**{nome}:** {'✅' if v_depois else '❌'}")

    if not mudancas:
        return

    embed = discord.Embed(title="✏️ Cargo atualizado", color=discord.Color.yellow())
    embed.add_field(name="Cargo", value=f"{depois.mention} (`{depois.name}`)", inline=True)
    embed.add_field(name="ID", value=str(depois.id), inline=True)
    embed.add_field(name="Mudanças", value="\n".join(mudancas[:10]), inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    await enviar_log(cfg["bot"], cfg.get("logs_cargos"), embed)

async def log_cargo_criado(cargo: discord.Role, cfg: dict):
    embed = discord.Embed(title="➕ Cargo criado", color=discord.Color.green())
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
    _pending_role_updates[depois.id] = (antes, depois)
    asyncio.get_event_loop().create_task(_flush_role_update(depois.id, cfg))
