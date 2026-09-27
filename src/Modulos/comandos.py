import discord
from discord.ext import commands
from datetime import datetime, timezone
from Modulos.webhooks import registrar_log_normal, registrar_log_codigo, registrar_log_painel
from Modulos.vip import carregar_vips, consultar_vip
from Modulos.amigos import carregar_amigos
from Modulos.warns import (carregar_warns, warns_ativos_do_usuario, criar_warn,
                            remover_warn, checar_warns_expirados, aplicar_punicao_progressao)
from Modulos.backup import criar_backup_manual, fazer_git_commit
from Modulos.painel import (gerar_painel_inicial, PainelView, mostrar_gerenciar_vip,
                             mostrar_gerenciar_amigo, mostrar_gerenciar_call, mostrar_gerenciar_warns)

def eh_admin_membro(membro: discord.Member, admin_role_id: int) -> bool:
    guild = membro.guild
    admin_role = guild.get_role(admin_role_id)
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

async def checar_dev(ctx: commands.Context, bot, servidor_devs: int, cargo_devs: int) -> bool:
    if servidor_devs == 0 or cargo_devs == 0:
        await ctx.send("🚫 Sistema de dev não configurado.")
        return False
    servidor = bot.get_guild(servidor_devs)
    if servidor is None:
        await ctx.send("🚫 Servidor dos devs não encontrado.")
        return False
    membro = servidor.get_member(ctx.author.id)
    if membro is None:
        try:
            membro = await servidor.fetch_member(ctx.author.id)
        except discord.NotFound:
            membro = None
    if membro is None or not any(role.id == cargo_devs for role in membro.roles):
        await ctx.send("🚫 Você não tem permissão (cargo de dev necessário).")
        return False
    return True

def registrar_comandos(bot: commands.Bot, cfg: dict):

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
        embed = discord.Embed(title=f"Sala do {ctx.author.display_name}", description=conteudo, color=discord.Color.blue())
        embed.set_author(name=autor_nome, icon_url=autor_avatar)
        embed.timestamp = datetime.now(timezone.utc)
        embed.set_footer(text="Dica Mobile: Segure no código para copiar")
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(embed=embed)
        await registrar_log_codigo(f"Código enviado via c+cod por {ctx.author} no canal #{ctx.channel}: {conteudo}", tipo="info", bot=cfg["bot"], canal_id=cfg.get("logs_codigos"))

    @bot.command(name="git")
    async def git_cmd(ctx: commands.Context):
        if not await checar_dev(ctx, bot, cfg["servidor_devs"], cfg["cargo_devs"]):
            return
        resultado = fazer_git_commit(cfg["pasta_bot_raiz"])
        if resultado:
            embed = discord.Embed(title="📦 Git atualizado!", description="Alterações enviadas para o GitHub.", color=discord.Color.green())
            await ctx.send(embed=embed)
        elif resultado is False:
            await ctx.send("⚠️ Nenhuma alteração encontrada.")
        else:
            await ctx.send("❌ Erro ao fazer commit.")

    @bot.command(name="backup")
    async def backup_cmd(ctx: commands.Context):
        if not await checar_dev(ctx, bot, cfg["servidor_devs"], cfg["cargo_devs"]):
            return
        if not cfg["pasta_backup"]:
            await ctx.send("🚫 Pasta de backup não configurada no `.env`.")
            return
        versao = criar_backup_manual(cfg["pasta_backup"], cfg["pasta_src"], cfg["pasta_memorias"], cfg["fuso_brt"])
        if versao:
            embed = discord.Embed(title="💾 Backup criado com sucesso!", description=f"Pasta: **{versao}**", color=discord.Color.green())
            await ctx.send(embed=embed)
            embed_log = discord.Embed(title="💾 Backup da pasta criado", description=f"{ctx.author.mention} criou um backup manualmente ({versao}).", color=discord.Color.green())
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
        elif versao is None:
            await ctx.send("⚠️ Backup já existe com conteúdo idêntico, ignorando.")
        else:
            await ctx.send("❌ Erro ao criar backup.")

    @bot.command(name="ping")
    async def ping(ctx: commands.Context):
        latencia_ms = round(bot.latency * 1000)
        embed = discord.Embed(title="🏓 Pong!", description=f"Latência: {latencia_ms}ms", color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @bot.command(name="uptime")
    async def uptime(ctx: commands.Context):
        if cfg["hora_inicio"] is None:
            await ctx.send("⚠️ Não foi possível calcular o uptime.")
            return
        agora = datetime.now(timezone.utc)
        delta = agora - cfg["hora_inicio"]
        dias, resto = divmod(int(delta.total_seconds()), 86400)
        horas, resto = divmod(resto, 3600)
        minutos, segundos = divmod(resto, 60)
        partes = []
        if dias: partes.append(f"{dias}d")
        if horas: partes.append(f"{horas}h")
        if minutos: partes.append(f"{minutos}m")
        partes.append(f"{segundos}s")
        embed = discord.Embed(title="🕒 Uptime", description=f"Online há {' '.join(partes)}", color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @bot.command(name="vip")
    async def vip_cmd(ctx: commands.Context, alvo: str = None):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        if alvo is None:
            await ctx.send("🚫 Uso: `c+vip @user/id`")
            return
        user_id = await extrair_user_id(ctx, alvo)
        if user_id is None:
            return
        dados_vip = consultar_vip(user_id, cfg["arquivo_vips"])
        await mostrar_gerenciar_vip(ctx, user_id, dados_vip.get("vip", False), cfg)

    @bot.command(name="vips")
    async def vips_cmd(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        dados = carregar_vips(cfg["arquivo_vips"])
        ativos = [uid for uid, info in dados.get("usuarios", {}).items() if info.get("vip")]
        if not ativos:
            await ctx.send("💎 Nenhum usuário com VIP ativo no momento.")
            return
        texto = "\n".join(f"<@{uid}>" for uid in ativos)
        embed = discord.Embed(title="💎 Usuários com VIP", description=texto[:4000], color=discord.Color.gold())
        await ctx.send(embed=embed)

    @bot.command(name="amigo")
    async def amigo_cmd(ctx: commands.Context, alvo: str = None):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        if alvo is None:
            await ctx.send("🚫 Uso: `c+amigo @user/id`")
            return
        user_id = await extrair_user_id(ctx, alvo)
        if user_id is None:
            return
        await mostrar_gerenciar_amigo(ctx, user_id, cfg)

    @bot.command(name="amigos")
    async def amigos_cmd(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        dados = carregar_amigos(cfg["arquivo_amigos"])
        ativos = [uid for uid, info in dados.get("usuarios", {}).items() if info.get("amigo")]
        if not ativos:
            await ctx.send("👥 Nenhum usuário com cargo de Amigo no momento.")
            return
        texto = "\n".join(f"<@{uid}>" for uid in ativos)
        embed = discord.Embed(title="👥 Usuários com Amigo", description=texto[:4000], color=discord.Color.teal())
        await ctx.send(embed=embed)

    @bot.command(name="call")
    async def call_cmd(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        await mostrar_gerenciar_call(ctx, cfg)

    async def resolver_canal_call():
        guild = bot.get_guild(cfg["guild_id"])
        if guild is None:
            return None, None
        canal = guild.get_channel(cfg["call_live"])
        return guild, canal

    @bot.command(name="call_lock")
    async def call_lock_cmd(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
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
        embed_log = discord.Embed(title="🔒 Entrada da call bloqueada", description=f"{ctx.author.mention} bloqueou a entrada em {canal.mention} via comando.", color=discord.Color.red())
        await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))

    @bot.command(name="call_mute")
    async def call_mute_cmd(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
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
        embed_log = discord.Embed(title="🔇 Fala da call bloqueada", description=f"{ctx.author.mention} bloqueou a fala em {canal.mention} via comando.", color=discord.Color.red())
        await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))

    @bot.command(name="call_allmute")
    async def call_allmute_cmd(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
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
                await registrar_log_normal(f"Erro ao mutar {membro.id} na call: {e}", tipo="erro", bot=cfg["bot"], canal_id=cfg.get("logs_gerais"))
        await ctx.send(f"🔇 {len(afetados)} pessoa(s) mutada(s) em {canal.mention}.")
        embed_log = discord.Embed(title="🔇 Todos mutados", description=f"{ctx.author.mention} mutou {len(afetados)} pessoa(s) em {canal.mention} via comando.", color=discord.Color.red())
        if afetados:
            embed_log.add_field(name="Mutados", value="\n".join(m.mention for m in afetados), inline=False)
        await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))

    @bot.command(name="call_allkick")
    async def call_allkick_cmd(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
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
                await registrar_log_normal(f"Erro ao desconectar {membro.id} da call: {e}", tipo="erro", bot=cfg["bot"], canal_id=cfg.get("logs_gerais"))
        await ctx.send(f"👢 {len(afetados)} pessoa(s) desconectada(s) de {canal.mention}.")
        embed_log = discord.Embed(title="👢 Todos desconectados da call", description=f"{ctx.author.mention} desconectou {len(afetados)} pessoa(s) de {canal.mention} via comando.", color=discord.Color.orange())
        if afetados:
            embed_log.add_field(name="Desconectados", value="\n".join(m.mention for m in afetados), inline=False)
        await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))

    @bot.command(name="call_reconnect", aliases=["cr"])
    async def call_reconnect_cmd(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        guild, canal = await resolver_canal_call()
        if canal is None:
            await ctx.send("🚫 Canal da call live não encontrado.")
            return
        canal_reconectar = guild.get_channel(cfg["call_reconectar"])
        if canal_reconectar is None:
            await ctx.send("🚫 Canal de reconexão não encontrado.")
            return
        admin_role = guild.get_role(cfg["admin_role_id"])
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
                await registrar_log_normal(f"Erro ao reconectar {membro.id} na call: {e}", tipo="erro", bot=cfg["bot"], canal_id=cfg.get("logs_gerais"))
        await ctx.send(f"🔄 {len(afetados)} pessoa(s) reconectada(s) em {canal.mention}.")
        embed_log = discord.Embed(title="🔄 Reconexão forçada na call", description=f"{ctx.author.mention} reconectou {len(afetados)} pessoa(s) em {canal.mention} via comando.", color=discord.Color.blurple())
        if afetados:
            embed_log.add_field(name="Reconectados", value="\n".join(m.mention for m in afetados), inline=False)
        await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))

    async def processar_novo_warn(ctx: commands.Context, alvo: str, motivo: str, eterno: bool):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        if not motivo:
            await ctx.send("🚫 Você precisa informar um motivo.")
            return
        user_id = await extrair_user_id(ctx, alvo)
        if user_id is None:
            return
        warn = await criar_warn(user_id, ctx.author.id, motivo, eterno, bot, cfg["guild_id"], cfg["arquivo_warns"], cfg["fuso_brt"])
        quantidade_ativos = len(warns_ativos_do_usuario(user_id, cfg["arquivo_warns"]))
        embed = discord.Embed(
            title="⚠️ Warn aplicado" if not eterno else "♾️ Warn eterno aplicado",
            description=f"<@{user_id}> recebeu um warn (#{warn['id']}).",
            color=discord.Color.orange()
        )
        embed.add_field(name="Motivo", value=motivo, inline=False)
        embed.add_field(name="Warns ativos", value=str(quantidade_ativos), inline=True)
        await ctx.send(embed=embed)
        resultado_punicao = await aplicar_punicao_progressao(
            ctx.guild, user_id, quantidade_ativos, bot, cfg["guild_id"],
            cfg["vip_role_id"], cfg["amigos_role_id"], cfg["arquivo_vips"], cfg["arquivo_amigos"],
            cfg["fuso_brt"]
        )
        embed_log = discord.Embed(
            title="⚠️ Warn aplicado" if not eterno else "♾️ Warn eterno aplicado",
            description=f"{ctx.author.mention} aplicou um warn em <@{user_id}> (#{warn['id']}).",
            color=discord.Color.orange()
        )
        embed_log.add_field(name="Motivo", value=motivo, inline=False)
        embed_log.add_field(name="Warns ativos", value=str(quantidade_ativos), inline=True)
        if resultado_punicao:
            embed_log.add_field(name="Punição automática", value=resultado_punicao, inline=False)
        await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))

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

    @bot.command(name="warns")
    async def warns_cmd(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        checar_warns_expirados(cfg["arquivo_warns"], cfg["fuso_brt"])
        dados = carregar_warns(cfg["arquivo_warns"])
        ativos = [w for w in dados["warns"].values() if w.get("status") == "ativo"]
        if not ativos:
            await ctx.send("✅ Nenhum warn ativo no momento.")
            return
        ativos.sort(key=lambda w: w["id"])
        linhas = [f"{'♾️' if w.get('eterno') else '⏳'} **#{w['id']}** — <@{w['user_id']}>: {w['motivo']}" for w in ativos]
        texto = "\n".join(linhas)
        if len(texto) > 3900:
            texto = texto[:3900] + "\n... (lista truncada)"
        embed = discord.Embed(title="⚠️ Warns ativos", description=texto, color=discord.Color.orange())
        await ctx.send(embed=embed)

    @bot.command(name="warn_remove")
    async def warn_remove(ctx: commands.Context, warn_id: int = None):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        if warn_id is None:
            await ctx.send("🚫 Uso: `c+warn_remove <id>`")
            return
        warn_removido = remover_warn(warn_id, cfg["arquivo_warns"], cfg["fuso_brt"])
        if warn_removido is None:
            await ctx.send(f"🚫 Warn #{warn_id} não encontrado ou já não está ativo.")
            return
        await ctx.send(f"✅ Warn #{warn_id} removido.")
        embed_log = discord.Embed(title="🗑️ Warn removido", description=f"{ctx.author.mention} removeu o warn #{warn_id} de <@{warn_removido['user_id']}>.", color=discord.Color.red())
        embed_log.add_field(name="Motivo original", value=warn_removido["motivo"], inline=False)
        await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))

    @bot.command(name="warn_info")
    async def warn_info(ctx: commands.Context, warn_id: int = None):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        if warn_id is None:
            await ctx.send("🚫 Uso: `c+warn_info <id>`")
            return
        dados = carregar_warns(cfg["arquivo_warns"])
        w = dados["warns"].get(str(warn_id))
        if w is None:
            await ctx.send(f"🚫 Warn #{warn_id} não encontrado.")
            return
        criado_em_fmt = datetime.fromisoformat(w["criado_em"]).strftime("%d/%m/%Y %H:%M")
        expira_em_fmt = "Nunca (eterno)" if w.get("eterno") else (datetime.fromisoformat(w["expira_em"]).strftime("%d/%m/%Y %H:%M") if w.get("expira_em") else "-")
        embed = discord.Embed(title=f"📄 Warn #{w['id']}", description=f"Usuário: <@{w['user_id']}>", color=discord.Color.blurple())
        embed.add_field(name="Motivo", value=w["motivo"], inline=False)
        embed.add_field(name="Aplicado por", value=f"<@{w['autor_id']}>", inline=True)
        embed.add_field(name="Status", value=w["status"].capitalize(), inline=True)
        embed.add_field(name="Eterno", value="Sim" if w.get("eterno") else "Não", inline=True)
        embed.add_field(name="Criado em", value=criado_em_fmt, inline=True)
        embed.add_field(name="Expira em", value=expira_em_fmt, inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="warns_deleted")
    async def warns_deleted(ctx: commands.Context):
        if not eh_admin_membro(ctx.author, cfg["admin_role_id"]):
            await ctx.send("🚫 Você não tem permissão para usar este comando.")
            return
        checar_warns_expirados(cfg["arquivo_warns"], cfg["fuso_brt"])
        dados = carregar_warns(cfg["arquivo_warns"])
        expirados = sorted([w for w in dados["warns"].values() if w.get("status") == "expirado"], key=lambda w: w["id"])
        removidos = sorted([w for w in dados["warns"].values() if w.get("status") == "removido"], key=lambda w: w["id"])
        texto_expirados = "\n".join(f"**#{w['id']}** — <@{w['user_id']}>: {w['motivo']}" for w in expirados) or "Nenhum."
        texto_removidos = "\n".join(f"**#{w['id']}** — <@{w['user_id']}>: {w['motivo']}" for w in removidos) or "Nenhum."
        embed = discord.Embed(title="🗂️ Warns expirados e removidos", color=discord.Color.greyple())
        embed.add_field(name="⏳ Expirados naturalmente", value=texto_expirados[:1024], inline=False)
        embed.add_field(name="🗑️ Removidos manualmente", value=texto_removidos[:1024], inline=False)
        await ctx.send(embed=embed)

    COMANDOS_INFO = {
        "ping": {"uso": "c+ping", "descricao": "Mostra a latência do bot."},
        "uptime": {"uso": "c+uptime", "descricao": "Mostra há quanto tempo o bot está online desde o último restart."},
        "cod": {"uso": "c+cod <código>", "descricao": "Envia um código formatado direto no canal onde o comando foi usado. Qualquer pessoa pode usar."},
        "backup": {"uso": "c+backup", "descricao": "Cria um backup da pasta src e Memoria. Só devs."},
        "git": {"uso": "c+git", "descricao": "Faz commit e push das alterações para o GitHub. Só devs."},
        "vip": {"uso": "c+vip @user/id", "descricao": "Abre a tela de gerenciamento de VIP de um usuário."},
        "vips": {"uso": "c+vips", "descricao": "Lista todos os usuários com VIP ativo."},
        "amigo": {"uso": "c+amigo @user/id", "descricao": "Abre a tela de gerenciamento do cargo de Amigo de um usuário."},
        "amigos": {"uso": "c+amigos", "descricao": "Lista todos os usuários com o cargo de Amigo."},
        "call": {"uso": "c+call", "descricao": "Abre a tela de gerenciamento da call live."},
        "call_lock": {"uso": "c+call_lock", "descricao": "Bloqueia a entrada na call live."},
        "call_mute": {"uso": "c+call_mute", "descricao": "Bloqueia a fala na call live."},
        "call_allmute": {"uso": "c+call_allmute", "descricao": "Muta todos que estão na call live agora."},
        "call_allkick": {"uso": "c+call_allkick", "descricao": "Desconecta todos que estão na call live agora."},
        "call_reconnect": {"uso": "c+call_reconnect (ou c+cr)", "descricao": "Reconecta os não-admins da call."},
        "warn": {"uso": "c+warn @user motivo", "descricao": "Aplica um warn normal, que expira em 60 dias."},
        "ewarn": {"uso": "c+ewarn @user motivo", "descricao": "Aplica um warn eterno, que nunca expira sozinho."},
        "warns": {"uso": "c+warns", "descricao": "Lista todos os warns ativos de todos os usuários."},
        "warn_remove": {"uso": "c+warn_remove <id>", "descricao": "Remove um warn específico pelo ID."},
        "warn_info": {"uso": "c+warn_info <id>", "descricao": "Mostra detalhes completos de um warn específico."},
        "warns_deleted": {"uso": "c+warns_deleted", "descricao": "Lista os warns expirados e removidos, separadamente."},
    }

    ALIASES_HELP = {"cr": "call_reconnect"}

    CATEGORIAS_HELP = {
        "💎 VIP": ["vip", "vips"],
        "👥 Amigos": ["amigo", "amigos"],
        "🎙️ Call": ["call", "call_lock", "call_mute", "call_allmute", "call_allkick", "call_reconnect"],
        "⚠️ Warns": ["warn", "ewarn", "warns", "warn_remove", "warn_info", "warns_deleted"],
        "🔧 Utilidades": ["ping", "uptime", "cod", "backup", "git"]
    }

    def montar_embed_help_geral():
        embed = discord.Embed(title="❓ Central de Ajuda", description="Escolha uma categoria abaixo ou use `c+help <comando>` para detalhes.", color=discord.Color.blurple())
        for categoria, cmds in CATEGORIAS_HELP.items():
            embed.add_field(name=categoria, value=f"{len(cmds)} comando(s)", inline=True)
        return embed

    def montar_embed_categoria_help(categoria: str):
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
            from Modulos.webhooks import enviar_ou_editar
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
            nome = ALIASES_HELP.get(nome.lower(), nome.lower())
            info = COMANDOS_INFO.get(nome)
            if info is None:
                await ctx.send(f"🚫 Comando `{comando}` não encontrado. Use `c+help` para ver a lista.")
                return
            embed = discord.Embed(title=f"❓ Ajuda: {info['uso']}", description=info["descricao"], color=discord.Color.blurple())
            await ctx.send(embed=embed)
            return
        await ctx.send(embed=montar_embed_help_geral(), view=HelpView())

    @bot.tree.command(name="help", description="Ver a lista de comandos do bot", guild=discord.Object(id=cfg["guild_id"]))
    async def help_slash(interaction: discord.Interaction):
        await interaction.response.send_message(embed=montar_embed_help_geral(), view=HelpView(), ephemeral=True)

    @bot.tree.command(name="painel", description="Abrir painel de controle do bot", guild=discord.Object(id=cfg["guild_id"]))
    async def painel(interaction: discord.Interaction):
        admin_role = interaction.guild.get_role(cfg["admin_role_id"])
        if admin_role is None or not any(role.position >= admin_role.position for role in interaction.user.roles):
            await interaction.response.send_message("🚫 Você não tem permissão para usar este comando.", ephemeral=True)
            embed_log = discord.Embed(title="🚨 Tentativa de acesso bloqueada", description=f"Usuário {interaction.user.mention} tentou abrir o painel sem permissão.", color=discord.Color.red())
            embed_log.add_field(name="ID do usuário", value=str(interaction.user.id), inline=True)
            embed_log.add_field(name="Cargo mais alto", value=interaction.user.top_role.name, inline=True)
            embed_log.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            return
        embed = gerar_painel_inicial()
        await interaction.response.send_message(embed=embed, view=PainelView(cfg), ephemeral=True)
        embed_log = discord.Embed(title="📋 Painel aberto", description=f"{interaction.user.mention} abriu o painel de controle.", color=discord.Color.blurple())
        embed_log.add_field(name="ID do usuário", value=str(interaction.user.id), inline=True)
        await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))

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
        import logging
        logging.error(f"Erro não tratado no comando {ctx.command}: {error}")
