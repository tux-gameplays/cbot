import discord
import json
import os
import re
import logging
from Modulos.webhooks import registrar_log_normal, registrar_log_painel

def carregar_banco_state(arquivo: str):
    if not arquivo or not os.path.exists(arquivo):
        return {"ultima_msg_id": None}
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"ultima_msg_id": None}

def salvar_banco_state(msg_id: int, arquivo: str):
    if not arquivo:
        return
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump({"ultima_msg_id": msg_id}, f)

async def processar_msg_banco(message: discord.Message, bot, guild_id: int, vip_role_id: int,
                               arquivo_vips: str, arquivo_banco_av: str, fuso_brt, cfg: dict = None):
    from Modulos.vip import adicionar_vip

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

    logs_vip = cfg.get("logs_vip") if cfg else None
    logs_gerais = cfg.get("logs_gerais") if cfg else None

    if user_id:
        await adicionar_vip(user_id, dias, bot, guild_id, vip_role_id, arquivo_vips, fuso_brt)

        label_tempo = "Eterno" if dias is None else f"{dias} dia(s)"
        embed_confirmacao = discord.Embed(
            title="💎 VIP ativado com sucesso!",
            description=f"<@{user_id}>, seu VIP de **{label_tempo}** foi ativado automaticamente.",
            color=discord.Color.green()
        )
        canal = bot.get_channel(message.channel.id)
        if canal:
            await canal.send(content=f"<@{user_id}>", embed=embed_confirmacao)

        embed_log = discord.Embed(
            title="💎 VIP adicionado automaticamente",
            description=f"VIP de <@{user_id}> adicionado automaticamente após compra no banco.",
            color=discord.Color.green()
        )
        embed_log.add_field(name="Tempo", value=label_tempo, inline=True)
        embed_log.add_field(name="ID do usuário", value=str(user_id), inline=True)
        await registrar_log_painel(embed_log, bot=bot, canal_id=logs_vip)
    else:
        await registrar_log_normal(
            "⚠️ VIP vendido no banco mas não foi possível identificar o comprador.",
            tipo="aviso", bot=bot, canal_id=logs_gerais
        )

    salvar_banco_state(message.id, arquivo_banco_av)

async def retomar_msgs_banco(bot, canal_banco_id: int, bot_banco_id: int, guild_id: int,
                              vip_role_id: int, arquivo_vips: str, arquivo_banco_av: str,
                              fuso_brt, cfg: dict = None):
    if not canal_banco_id or not bot_banco_id:
        return

    canal = bot.get_channel(canal_banco_id)
    if canal is None:
        return

    logs_gerais = cfg.get("logs_gerais") if cfg else None
    state = carregar_banco_state(arquivo_banco_av)
    ultima_id = state.get("ultima_msg_id")

    kwargs = {"limit": 50}
    if ultima_id:
        kwargs["after"] = discord.Object(id=ultima_id)

    try:
        msgs = [m async for m in canal.history(**kwargs)]
        msgs.sort(key=lambda m: m.id)

        pendentes = [
            m for m in msgs
            if m.author.id == bot_banco_id
            and m.embeds
            and "You have used 1 💎 VIP" in (m.embeds[0].description or "")
        ]

        for m in pendentes:
            await processar_msg_banco(m, bot, guild_id, vip_role_id, arquivo_vips, arquivo_banco_av, fuso_brt, cfg)

        if pendentes:
            await registrar_log_normal(
                f"🏦 {len(pendentes)} compra(s) de VIP processada(s) retroativamente ao ligar.",
                tipo="sucesso", bot=bot, canal_id=logs_gerais
            )
    except Exception as e:
        logging.error(f"Erro ao retomar mensagens do banco: {e}")
