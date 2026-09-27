import discord
import json
import os
import logging
from Modulos.vip import atualizar_info_usuario

def carregar_amigos(arquivo: str):
    if not arquivo or not os.path.exists(arquivo):
        return {"usuarios": {}}
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"usuarios": {}}

def salvar_amigos(dados, arquivo: str):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def consultar_amigo(user_id: int, arquivo: str):
    dados = carregar_amigos(arquivo)
    return dados.get("usuarios", {}).get(str(user_id), {"amigo": False})

async def _get_membro(bot, guild_id, user_id):
    guild = bot.get_guild(guild_id)
    if not guild:
        return None, None
    membro = guild.get_member(user_id)
    if membro is None:
        try:
            membro = await guild.fetch_member(user_id)
        except discord.NotFound:
            membro = None
    return guild, membro

async def atribuir_cargo_amigo(user_id: int, bot, guild_id: int, amigos_role_id: int, cfg: dict = None):
    guild, membro = await _get_membro(bot, guild_id, user_id)
    if not guild:
        return
    cargo = guild.get_role(amigos_role_id)
    if cargo and membro:
        try:
            await membro.add_roles(cargo, reason="Amigo adicionado")
        except Exception as e:
            logging.error(f"Erro ao dar cargo de Amigo a {user_id}: {e}")

async def remover_cargo_amigo(user_id: int, bot, guild_id: int, amigos_role_id: int, cfg: dict = None):
    guild, membro = await _get_membro(bot, guild_id, user_id)
    if not guild:
        return
    cargo = guild.get_role(amigos_role_id)
    if cargo and membro:
        try:
            await membro.remove_roles(cargo, reason="Amigo removido")
        except Exception as e:
            logging.error(f"Erro ao tirar cargo de Amigo de {user_id}: {e}")

async def adicionar_amigo(user_id: int, bot, guild_id: int, amigos_role_id: int, arquivo: str, cfg: dict = None):
    dados = carregar_amigos(arquivo)
    usuarios = dados.get("usuarios", {})
    usuarios[str(user_id)] = {"amigo": True}
    dados["usuarios"] = usuarios

    guild, membro = await _get_membro(bot, guild_id, user_id)
    if guild:
        dados = atualizar_info_usuario(dados, user_id, membro)

    salvar_amigos(dados, arquivo)
    await atribuir_cargo_amigo(user_id, bot, guild_id, amigos_role_id)

async def remover_amigo(user_id: int, bot, guild_id: int, amigos_role_id: int, arquivo: str, cfg: dict = None):
    dados = carregar_amigos(arquivo)
    usuarios = dados.get("usuarios", {})
    if str(user_id) in usuarios:
        usuarios[str(user_id)]["amigo"] = False
    dados["usuarios"] = usuarios
    salvar_amigos(dados, arquivo)
    await remover_cargo_amigo(user_id, bot, guild_id, amigos_role_id)
