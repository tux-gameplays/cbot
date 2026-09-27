import discord
import logging
from datetime import datetime
from Modulos.webhooks import registrar_log_painel, enviar_ou_editar

def gerar_painel_inicial():
    embed = discord.Embed(
        title="🎲 Painel de Controle",
        description="Escolha uma das opções abaixo para gerenciar o servidor.",
        color=discord.Color.purple()
    )
    embed.add_field(name="💎 VIP", value="Adicione, remova ou acompanhe o VIP de um usuário.", inline=False)
    embed.add_field(name="👥 Amigos", value="Dê ou tire o cargo de Amigo próximo de um usuário.", inline=False)
    embed.add_field(name="🎙️ Call", value="Controle entrada, fala e quem está na call live.", inline=False)
    return embed

class PainelView(discord.ui.View):
    def __init__(self, cfg):
        super().__init__(timeout=None)
        self.add_item(PainelSelectInicial(cfg))

def montar_view_selecionar_alvo(tipo: str, cfg: dict) -> discord.ui.View:
    view = discord.ui.View()

    select = discord.ui.UserSelect(placeholder="Escolha um membro do servidor...")

    async def select_callback(interaction: discord.Interaction):
        membro = select.values[0]
        await abrir_gerenciamento_por_tipo(interaction, tipo, membro.id, cfg, membro)

    select.callback = select_callback
    view.add_item(select)

    botao_manual = discord.ui.Button(label="Digitar ID manualmente", style=discord.ButtonStyle.secondary)

    async def manual_callback(interaction: discord.Interaction):
        if tipo == "vip":
            await interaction.response.send_modal(VIPModal(cfg))
        elif tipo == "amigo":
            await interaction.response.send_modal(AmigoModal(cfg))
        elif tipo == "warn":
            await interaction.response.send_modal(WarnModal(cfg))

    botao_manual.callback = manual_callback
    view.add_item(botao_manual)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await interaction_voltar.response.edit_message(embed=gerar_painel_inicial(), view=PainelView(cfg))
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    return view

async def abrir_gerenciamento_por_tipo(interaction: discord.Interaction, tipo: str, user_id: int, cfg: dict, user: discord.User = None):
    from Modulos.vip import consultar_vip
    if tipo == "vip":
        if user and user.bot:
            await interaction.response.send_message(f"🚫 O usuário {user.mention} é um bot e não pode ter VIP.", ephemeral=True)
            return
        dados_vip = consultar_vip(user_id, cfg["arquivo_vips"])
        await mostrar_gerenciar_vip(interaction, user_id, dados_vip.get("vip", False), cfg, user=user)
    elif tipo == "amigo":
        if user and user.bot:
            await interaction.response.send_message(f"🚫 O usuário {user.mention} é um bot e não pode ter o cargo de Amigo.", ephemeral=True)
            return
        await mostrar_gerenciar_amigo(interaction, user_id, cfg, user=user)
    elif tipo == "warn":
        await mostrar_gerenciar_warns(interaction, user_id, cfg)

class PainelSelectInicial(discord.ui.Select):
    def __init__(self, cfg):
        self.cfg = cfg
        options = [
            discord.SelectOption(label="💎 VIP", description="Gerenciar VIP de um usuário"),
            discord.SelectOption(label="👥 Amigos", description="Gerenciar cargo de Amigo próximo"),
            discord.SelectOption(label="🎙️ Call", description="Gerenciar a call live"),
            discord.SelectOption(label="⚠️ Warns", description="Gerenciar warns de um usuário")
        ]
        super().__init__(placeholder="Escolha uma seção...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "💎 VIP":
            embed = discord.Embed(title="💎 Escolher usuário", description="Selecione um membro do servidor, ou digite o ID manualmente se a pessoa já saiu.", color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=montar_view_selecionar_alvo("vip", self.cfg))
        elif self.values[0] == "👥 Amigos":
            embed = discord.Embed(title="👥 Escolher usuário", description="Selecione um membro do servidor, ou digite o ID manualmente se a pessoa já saiu.", color=discord.Color.teal())
            await interaction.response.edit_message(embed=embed, view=montar_view_selecionar_alvo("amigo", self.cfg))
        elif self.values[0] == "🎙️ Call":
            await mostrar_gerenciar_call(interaction, self.cfg)
        elif self.values[0] == "⚠️ Warns":
            embed = discord.Embed(title="⚠️ Escolher usuário", description="Selecione um membro do servidor, ou digite o ID manualmente.", color=discord.Color.orange())
            await interaction.response.edit_message(embed=embed, view=montar_view_selecionar_alvo("warn", self.cfg))

class WarnModal(discord.ui.Modal, title="⚠️ Gerenciar Warns"):
    usuario_id = discord.ui.TextInput(label="ID do usuário", placeholder="Digite o ID do usuário", required=True)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.usuario_id.value)
        except ValueError:
            await interaction.response.send_message("🚫 ID inválido.", ephemeral=True)
            return
        await mostrar_gerenciar_warns(interaction, user_id, self.cfg)

async def mostrar_gerenciar_warns(interaction: discord.Interaction, user_id: int, cfg: dict):
    from Modulos.warns import checar_warns_expirados, warns_ativos_do_usuario, remover_warn
    checar_warns_expirados(cfg["arquivo_warns"], cfg["fuso_brt"])
    ativos = sorted(warns_ativos_do_usuario(user_id, cfg["arquivo_warns"]), key=lambda w: w["id"])

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
        await interaction_btn.response.send_modal(WarnMotivoModal(user_id, eterno=False, cfg=cfg))

    async def ewarn_callback(interaction_btn: discord.Interaction):
        await interaction_btn.response.send_modal(WarnMotivoModal(user_id, eterno=True, cfg=cfg))

    botao_warn.callback = warn_callback
    botao_ewarn.callback = ewarn_callback
    view.add_item(botao_warn)
    view.add_item(botao_ewarn)

    if ativos:
        botao_remover_ultimo = discord.ui.Button(label="Remover Último Warn", style=discord.ButtonStyle.secondary)

        async def remover_ultimo_callback(interaction_btn: discord.Interaction):
            ultimo = max(ativos, key=lambda w: w["id"])
            warn_removido = remover_warn(ultimo["id"], cfg["arquivo_warns"], cfg["fuso_brt"])
            if warn_removido:
                embed_log = discord.Embed(
                    title="🗑️ Warn removido",
                    description=f"{interaction_btn.user.mention} removeu o warn #{ultimo['id']} de <@{user_id}> pelo painel.",
                    color=discord.Color.red()
                )
                await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_warns(interaction_btn, user_id, cfg)

        botao_remover_ultimo.callback = remover_ultimo_callback
        view.add_item(botao_remover_ultimo)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await interaction_voltar.response.edit_message(embed=gerar_painel_inicial(), view=PainelView(cfg))
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await enviar_ou_editar(interaction, embed, view)

class WarnMotivoModal(discord.ui.Modal, title="⚠️ Motivo do Warn"):
    motivo = discord.ui.TextInput(label="Motivo", placeholder="Descreva o motivo do warn", required=True, style=discord.TextStyle.paragraph)

    def __init__(self, user_id: int, eterno: bool, cfg: dict):
        super().__init__()
        self.user_id = user_id
        self.eterno = eterno
        self.cfg = cfg

    async def on_submit(self, interaction: discord.Interaction):
        from Modulos.warns import criar_warn, warns_ativos_do_usuario, aplicar_punicao_progressao
        warn_criado = await criar_warn(self.user_id, interaction.user.id, self.motivo.value, self.eterno,
                                       self.cfg["bot"], self.cfg["guild_id"], self.cfg["arquivo_warns"], self.cfg["fuso_brt"])
        quantidade_ativos = len(warns_ativos_do_usuario(self.user_id, self.cfg["arquivo_warns"]))
        resultado_punicao = await aplicar_punicao_progressao(
            interaction.guild, self.user_id, quantidade_ativos,
            self.cfg["bot"], self.cfg["guild_id"], self.cfg["vip_role_id"], self.cfg["amigos_role_id"],
            self.cfg["arquivo_vips"], self.cfg["arquivo_amigos"], self.cfg["fuso_brt"]
        )

        embed_log = discord.Embed(
            title="⚠️ Warn aplicado" if not self.eterno else "♾️ Warn eterno aplicado",
            description=f"{interaction.user.mention} aplicou um warn em <@{self.user_id}> (#{warn_criado['id']}) pelo painel.",
            color=discord.Color.orange()
        )
        embed_log.add_field(name="Motivo", value=self.motivo.value, inline=False)
        embed_log.add_field(name="Warns ativos", value=str(quantidade_ativos), inline=True)
        if resultado_punicao:
            embed_log.add_field(name="Punição automática", value=resultado_punicao, inline=False)
        await registrar_log_painel(embed_log, bot=self.cfg["bot"], canal_id=self.cfg.get("logs_painel"))
        await mostrar_gerenciar_warns(interaction, self.user_id, self.cfg)

class VIPModal(discord.ui.Modal, title="💎 Gerenciar VIP"):
    usuario_id = discord.ui.TextInput(label="ID do usuário", placeholder="Digite o ID do usuário", required=True)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

    async def on_submit(self, interaction: discord.Interaction):
        from Modulos.vip import consultar_vip
        user_id = int(self.usuario_id.value)
        user = await interaction.client.fetch_user(user_id)
        if user.bot:
            await interaction.response.send_message(f"🚫 O usuário {user.mention} é um bot e não pode ter VIP.", ephemeral=True)
            return
        dados_vip = consultar_vip(user_id, self.cfg["arquivo_vips"])
        await mostrar_gerenciar_vip(interaction, user_id, dados_vip.get("vip", False), self.cfg, user=user)

class AmigoModal(discord.ui.Modal, title="👥 Gerenciar Amigo"):
    usuario_id = discord.ui.TextInput(label="ID do usuário", placeholder="Digite o ID do usuário", required=True)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

    async def on_submit(self, interaction: discord.Interaction):
        user_id = int(self.usuario_id.value)
        user = await interaction.client.fetch_user(user_id)
        if user.bot:
            await interaction.response.send_message(f"🚫 O usuário {user.mention} é um bot e não pode ter o cargo de Amigo.", ephemeral=True)
            return
        await mostrar_gerenciar_amigo(interaction, user_id, self.cfg, user=user)

async def mostrar_gerenciar_amigo(interaction: discord.Interaction, user_id: int, cfg: dict, user: discord.User = None):
    from Modulos.amigos import consultar_amigo, adicionar_amigo, remover_amigo
    dados_amigo = consultar_amigo(user_id, cfg["arquivo_amigos"])
    tem_amigo = dados_amigo.get("amigo", False)

    embed = discord.Embed(title="👥 Gerenciar Amigo", description=f"👤 <@{user_id}>", color=discord.Color.teal() if tem_amigo else discord.Color.greyple())
    embed.add_field(name="Cargo de Amigo", value="Ativo" if tem_amigo else "Inativo", inline=False)

    if user is None:
        user = await cfg["bot"].fetch_user(user_id)
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

    view = discord.ui.View()

    if tem_amigo:
        botao_remover = discord.ui.Button(label="Remover Amigo", style=discord.ButtonStyle.red)
        async def remover_callback(interaction_btn: discord.Interaction):
            await remover_amigo(user_id, cfg["bot"], cfg["guild_id"], cfg["amigos_role_id"], cfg["arquivo_amigos"])
            embed_log = discord.Embed(title="👥 Amigo removido", description=f"{interaction_btn.user.mention} removeu o cargo de Amigo de <@{user_id}>.", color=discord.Color.red())
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_amigo(interaction_btn, user_id, cfg)
        botao_remover.callback = remover_callback
        view.add_item(botao_remover)
    else:
        botao_add = discord.ui.Button(label="Adicionar Amigo", style=discord.ButtonStyle.green)
        async def adicionar_callback(interaction_btn: discord.Interaction):
            await adicionar_amigo(user_id, cfg["bot"], cfg["guild_id"], cfg["amigos_role_id"], cfg["arquivo_amigos"])
            embed_log = discord.Embed(title="👥 Amigo adicionado", description=f"{interaction_btn.user.mention} adicionou o cargo de Amigo para <@{user_id}>.", color=discord.Color.teal())
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_amigo(interaction_btn, user_id, cfg)
        botao_add.callback = adicionar_callback
        view.add_item(botao_add)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await interaction_voltar.response.edit_message(embed=gerar_painel_inicial(), view=PainelView(cfg))
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await enviar_ou_editar(interaction, embed, view)

async def mostrar_gerenciar_call(interaction: discord.Interaction, cfg: dict):
    guild = cfg["bot"].get_guild(cfg["guild_id"])
    canal = guild.get_channel(cfg["call_live"]) if guild else None

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

    admin_role = guild.get_role(cfg["admin_role_id"])
    canal_reconectar = guild.get_channel(cfg["call_reconectar"])

    def eh_admin(membro):
        return admin_role is not None and any(role.position >= admin_role.position for role in membro.roles)

    membros_nao_admin = [m for m in membros_na_call if not eh_admin(m)]

    embed = discord.Embed(title="🎙️ Gerenciar Call Live", description=f"Canal: {canal.mention}", color=discord.Color.blurple())
    embed.add_field(name="Entrada", value="🔒 Bloqueada" if entrada_bloqueada else "🔓 Liberada", inline=True)
    embed.add_field(name="Fala", value="🔇 Bloqueada" if fala_bloqueada else "🔊 Liberada", inline=True)
    embed.add_field(name="Admins na call", value=str(len(membros_na_call) - len(membros_nao_admin)), inline=True)
    embed.add_field(name="Membros na call", value=str(len(membros_nao_admin)), inline=True)
    embed.add_field(name="Pessoas na call", value=str(len(membros_na_call)), inline=True)

    view = discord.ui.View()

    botao_entrada = discord.ui.Button(label="Liberar Entrada" if entrada_bloqueada else "Bloquear Entrada", style=discord.ButtonStyle.green if entrada_bloqueada else discord.ButtonStyle.red)

    async def entrada_callback(interaction_btn: discord.Interaction):
        novo_overwrite = canal.overwrites_for(everyone)
        novo_overwrite.connect = None if entrada_bloqueada else False
        await canal.set_permissions(everyone, overwrite=novo_overwrite)
        embed_log = discord.Embed(
            title="🔓 Entrada da call liberada" if entrada_bloqueada else "🔒 Entrada da call bloqueada",
            description=f"{interaction_btn.user.mention} {'liberou' if entrada_bloqueada else 'bloqueou'} a entrada em {canal.mention}.",
            color=discord.Color.green() if entrada_bloqueada else discord.Color.red()
        )
        await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
        await mostrar_gerenciar_call(interaction_btn, cfg)

    botao_entrada.callback = entrada_callback
    view.add_item(botao_entrada)

    if not entrada_bloqueada:
        botao_fala = discord.ui.Button(label="Liberar Fala" if fala_bloqueada else "Bloquear Fala", style=discord.ButtonStyle.green if fala_bloqueada else discord.ButtonStyle.red)

        async def fala_callback(interaction_btn: discord.Interaction):
            novo_overwrite = canal.overwrites_for(everyone)
            novo_overwrite.speak = None if fala_bloqueada else False
            await canal.set_permissions(everyone, overwrite=novo_overwrite)
            embed_log = discord.Embed(
                title="🔊 Fala da call liberada" if fala_bloqueada else "🔇 Fala da call bloqueada",
                description=f"{interaction_btn.user.mention} {'liberou' if fala_bloqueada else 'bloqueou'} a fala em {canal.mention}.",
                color=discord.Color.green() if fala_bloqueada else discord.Color.red()
            )
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_call(interaction_btn, cfg)

        botao_fala.callback = fala_callback
        view.add_item(botao_fala)

        botao_mute = discord.ui.Button(label="Desmutar Todos" if todos_mutados else "Mutar Todos", style=discord.ButtonStyle.green if todos_mutados else discord.ButtonStyle.red)

        async def mute_callback(interaction_btn: discord.Interaction):
            membros = list(canal.members)
            afetados = []
            for membro in membros:
                try:
                    await membro.edit(mute=not todos_mutados, reason="Mute geral - painel")
                    afetados.append(membro)
                except Exception as e:
                    from Modulos.webhooks import registrar_log_normal
                    await registrar_log_normal(f"Erro ao mutar/desmutar {membro.id} na call: {e}", tipo="erro", bot=cfg["bot"], canal_id=cfg.get("logs_gerais"))
            embed_log = discord.Embed(
                title="🔊 Todos desmutados" if todos_mutados else "🔇 Todos mutados",
                description=f"{interaction_btn.user.mention} {'desmutou' if todos_mutados else 'mutou'} {len(afetados)} pessoa(s) em {canal.mention}.",
                color=discord.Color.green() if todos_mutados else discord.Color.red()
            )
            if afetados:
                embed_log.add_field(name="Desmutados" if todos_mutados else "Mutados", value="\n".join(m.mention for m in afetados), inline=False)
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_call(interaction_btn, cfg)

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
                    from Modulos.webhooks import registrar_log_normal
                    await registrar_log_normal(f"Erro ao desconectar {membro.id} da call: {e}", tipo="erro", bot=cfg["bot"], canal_id=cfg.get("logs_gerais"))
            embed_log = discord.Embed(title="👢 Todos desconectados da call", description=f"{interaction_btn.user.mention} desconectou {len(afetados)} pessoa(s) de {canal.mention}.", color=discord.Color.orange())
            if afetados:
                embed_log.add_field(name="Desconectados", value="\n".join(m.mention for m in afetados), inline=False)
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_call(interaction_btn, cfg)

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
                    from Modulos.webhooks import registrar_log_normal
                    await registrar_log_normal(f"Erro ao reconectar {membro.id} na call: {e}", tipo="erro", bot=cfg["bot"], canal_id=cfg.get("logs_gerais"))
            embed_log = discord.Embed(title="🔄 Reconexão forçada na call", description=f"{interaction_btn.user.mention} reconectou {len(afetados)} pessoa(s) em {canal.mention}.", color=discord.Color.blurple())
            if afetados:
                embed_log.add_field(name="Reconectados", value="\n".join(m.mention for m in afetados), inline=False)
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_call(interaction_btn, cfg)

        botao_reconectar.callback = reconectar_callback
        view.add_item(botao_reconectar)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await interaction_voltar.response.edit_message(embed=gerar_painel_inicial(), view=PainelView(cfg))
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await enviar_ou_editar(interaction, embed, view)

async def mostrar_setar_tempo_vip(interaction: discord.Interaction, user_id: int, tem_vip: bool, cfg: dict):
    from Modulos.vip import setar_tempo_vip
    embed = discord.Embed(title="🕒 Setar Tempo VIP", description=f"Escolha o tempo exato de VIP para <@{user_id}> (substitui o tempo atual, inclusive se for eterno).", color=discord.Color.gold())
    view = discord.ui.View()

    for label, dias in [("1 Dia", 1), ("3 Dias", 3), ("7 Dias", 7), ("30 Dias", 30)]:
        botao = discord.ui.Button(label=label, style=discord.ButtonStyle.blurple)

        async def callback(interaction_btn: discord.Interaction, dias=dias):
            await setar_tempo_vip(user_id, dias, cfg["bot"], cfg["guild_id"], cfg["vip_role_id"], cfg["arquivo_vips"], cfg["fuso_brt"])
            embed_log = discord.Embed(title="🕒 Tempo de VIP setado", description=f"{interaction_btn.user.mention} setou o VIP de <@{user_id}> para {dias} dia(s), substituindo o tempo anterior.", color=discord.Color.gold())
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_vip(interaction_btn, user_id, True, cfg)

        botao.callback = callback
        view.add_item(botao)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await mostrar_gerenciar_vip(interaction_voltar, user_id, tem_vip, cfg)
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    try:
        await interaction.response.edit_message(embed=embed, view=view)
    except discord.NotFound:
        logging.warning(f"Interação expirou antes de editar a tela de setar tempo VIP para {user_id}.")

async def mostrar_adicionar_vip(interaction: discord.Interaction, user_id: int, tem_vip: bool, cfg: dict):
    from Modulos.vip import adicionar_vip
    embed = discord.Embed(title="➕ Adicionar VIP", description=f"Quanto tempo deseja adicionar a <@{user_id}>?", color=discord.Color.green())
    view = discord.ui.View()

    for label, dias in [("1 Dia", 1), ("3 Dias", 3), ("7 Dias", 7), ("30 Dias", 30), ("Eterno", None)]:
        botao = discord.ui.Button(label=label, style=discord.ButtonStyle.green)

        async def callback(interaction_btn: discord.Interaction, dias=dias):
            await adicionar_vip(user_id, dias, cfg["bot"], cfg["guild_id"], cfg["vip_role_id"], cfg["arquivo_vips"], cfg["fuso_brt"])
            label_tempo = "Eterno" if dias is None else f"{dias} dia(s)"
            embed_log = discord.Embed(title="💎 VIP adicionado", description=f"{interaction_btn.user.mention} adicionou VIP para <@{user_id}>.", color=discord.Color.green())
            embed_log.add_field(name="Tempo", value=label_tempo, inline=True)
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_vip(interaction_btn, user_id, True, cfg)

        botao.callback = callback
        view.add_item(botao)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await mostrar_gerenciar_vip(interaction_voltar, user_id, tem_vip, cfg)
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await interaction.response.edit_message(embed=embed, view=view)

async def mostrar_remover_tempo_vip(interaction: discord.Interaction, user_id: int, tem_vip: bool, cfg: dict):
    from Modulos.vip import remover_tempo_vip
    embed = discord.Embed(title="➖ Remover tempo de VIP", description=f"Quanto tempo deseja remover de <@{user_id}>?", color=discord.Color.orange())
    view = discord.ui.View()

    for label, dias in [("1 Dia", 1), ("3 Dias", 3), ("7 Dias", 7), ("30 Dias", 30)]:
        botao = discord.ui.Button(label=label, style=discord.ButtonStyle.blurple)

        async def callback(interaction_btn: discord.Interaction, dias=dias):
            resultado = await remover_tempo_vip(user_id, dias, cfg["bot"], cfg["guild_id"], cfg["vip_role_id"], cfg["arquivo_vips"], cfg["fuso_brt"])
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
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_vip(interaction_btn, user_id, True, cfg)

        botao.callback = callback
        view.add_item(botao)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await mostrar_gerenciar_vip(interaction_voltar, user_id, tem_vip, cfg)
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await interaction.response.edit_message(embed=embed, view=view)

async def mostrar_gerenciar_vip(interaction: discord.Interaction, user_id: int, tem_vip: bool = None, cfg: dict = None, user: discord.User = None):
    from Modulos.vip import consultar_vip, remover_vip
    dados_vip = consultar_vip(user_id, cfg["arquivo_vips"])
    tem_vip = dados_vip.get("vip", False)

    embed = discord.Embed(title="💎 Gerenciar VIP", description=f"👤 <@{user_id}>", color=discord.Color.gold() if tem_vip else discord.Color.greyple())

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
        user = await cfg["bot"].fetch_user(user_id)
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

    view = discord.ui.View()

    if tem_vip:
        eterno = dados_vip.get("expira_em") is None
        botao_remover = discord.ui.Button(label="Remover VIP", style=discord.ButtonStyle.red)
        botao_setar_tempo = discord.ui.Button(label="Setar Tempo VIP", style=discord.ButtonStyle.gray)

        async def setar_tempo_callback(interaction_btn: discord.Interaction):
            await mostrar_setar_tempo_vip(interaction_btn, user_id, tem_vip, cfg)

        async def remover_callback(interaction_btn: discord.Interaction):
            await remover_vip(user_id, cfg["bot"], cfg["guild_id"], cfg["vip_role_id"], cfg["arquivo_vips"])
            embed_log = discord.Embed(title="🗑️ VIP removido", description=f"{interaction_btn.user.mention} removeu o VIP de <@{user_id}>.", color=discord.Color.red())
            embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
            await registrar_log_painel(embed_log, bot=cfg["bot"], canal_id=cfg.get("logs_painel"))
            await mostrar_gerenciar_vip(interaction_btn, user_id, False, cfg)

        botao_setar_tempo.callback = setar_tempo_callback
        botao_remover.callback = remover_callback

        if not eterno:
            botao_add_tempo = discord.ui.Button(label="Adicionar tempo VIP", style=discord.ButtonStyle.green)
            botao_remover_tempo = discord.ui.Button(label="Remover tempo VIP", style=discord.ButtonStyle.blurple)

            async def adicionar_tempo_callback(interaction_btn: discord.Interaction):
                await mostrar_adicionar_vip(interaction_btn, user_id, tem_vip, cfg)

            async def remover_tempo_callback(interaction_btn: discord.Interaction):
                await mostrar_remover_tempo_vip(interaction_btn, user_id, tem_vip, cfg)

            botao_add_tempo.callback = adicionar_tempo_callback
            botao_remover_tempo.callback = remover_tempo_callback
            view.add_item(botao_add_tempo)
            view.add_item(botao_remover_tempo)

        view.add_item(botao_setar_tempo)
        view.add_item(botao_remover)
    else:
        botao_add = discord.ui.Button(label="Adicionar VIP", style=discord.ButtonStyle.green)

        async def adicionar_callback(interaction_btn: discord.Interaction):
            await mostrar_adicionar_vip(interaction_btn, user_id, tem_vip, cfg)

        botao_add.callback = adicionar_callback
        view.add_item(botao_add)

    voltar_btn = discord.ui.Button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar_callback(interaction_voltar: discord.Interaction):
        await interaction_voltar.response.edit_message(embed=gerar_painel_inicial(), view=PainelView(cfg))
    voltar_btn.callback = voltar_callback
    view.add_item(voltar_btn)

    await enviar_ou_editar(interaction, embed, view)
