import discord
import json
import logging
import os

_cache = {}

def _carregar(arquivo):
    if arquivo in _cache:
        return _cache[arquivo]
    ids = set()
    if arquivo and os.path.exists(arquivo):
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                ids = {int(x) for x in json.load(f).get("canais", [])}
        except (json.JSONDecodeError, ValueError, AttributeError):
            ids = set()
    _cache[arquivo] = ids
    return ids

def _salvar(arquivo):
    if not arquivo:
        return
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump({"canais": sorted(_cache.get(arquivo, set()))}, f, indent=4)

def canal_ativo(canal_id: int, arquivo) -> bool:
    return canal_id in _carregar(arquivo)

def alternar_canal(canal_id: int, arquivo) -> bool:
    ids = _carregar(arquivo)
    if canal_id in ids:
        ids.discard(canal_id)
        ativo = False
    else:
        ids.add(canal_id)
        ativo = True
    _salvar(arquivo)
    return ativo

async def publicar_mensagem(message: discord.Message):
    if message.flags.crossposted:
        return
    try:
        await message.publish()
    except discord.Forbidden:
        logging.warning(f"Autoanúncio: sem permissão para publicar mensagem em {message.channel.id}")
    except discord.HTTPException as e:
        logging.error(f"Autoanúncio: erro ao publicar mensagem em {message.channel.id}: {e}")

def agendar_publicacao(message: discord.Message, cfg: dict):
    if message.guild is None or message.guild.id != cfg["guild_id"]:
        return
    if not canal_ativo(message.channel.id, cfg.get("arquivo_autoanuncio")):
        return
    if message.type not in (discord.MessageType.default, discord.MessageType.reply):
        return
    cfg["bot"].loop.create_task(publicar_mensagem(message))
