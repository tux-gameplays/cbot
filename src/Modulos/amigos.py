import discord
import json
import os
from Modulos.webhooks import registrar_log_normal
from Modulos.vip import atualizar_info_usuario

def carregar_amigos(arquivo: str):
    if not os.path.exists(arquivo):
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

async def atribuir_cargo_amigo(user_id: int, bot, guild_id: int, amigos_role_id: int, webhook_logs: str):
    guild = bot.get_guild(guild_id)
    if guild is None:
        await registrar_log_normal(f"Guild não encontrada ao tentar dar cargo de Amigo a {user_id}.", tipo="erro", webhook_logs=webhook_logs)
        return
    cargo = guild.get_role(amigos_role_id)
    membro = guild.get_member(user_id)
    if membro is None:
        try:
            membro = await guild.fetch_member(user_id)
        except discord.NotFound:
            membro = None
    if cargo and membro:
        try:
            await membro.add_roles(cargo, reason="Amigo adicionado")
        except Exception as e:
            await registrar_log_normal(f"Erro ao dar cargo de Amigo a {user_id}: {e}", tipo="erro", webhook_logs=webhook_logs)

async def remover_cargo_amigo(user_id: int, bot, guild_id: int, amigos_role_id: int, webhook_logs: str):
    guild = bot.get_guild(guild_id)
    if guild is None:
        await registrar_log_normal(f"Guild não encontrada ao tentar tirar cargo de Amigo de {user_id}.", tipo="erro", webhook_logs=webhook_logs)
        return
    cargo = guild.get_role(amigos_role_id)
    membro = guild.get_member(user_id)
    if membro is None:
        try:
            membro = await guild.fetch_member(user_id)
        except discord.NotFound:
            membro = None
    if cargo and membro:
        try:
            await membro.remove_roles(cargo, reason="Amigo removido")
        except Exception as e:
            await registrar_log_normal(f"Erro ao tirar cargo de Amigo de {user_id}: {e}", tipo="erro", webhook_logs=webhook_logs)

async def adicionar_amigo(user_id: int, bot, guild_id: int, amigos_role_id: int, arquivo: str, webhook_logs: str):
    dados = carregar_amigos(arquivo)
    usuarios = dados.get("usuarios", {})
    usuarios[str(user_id)] = {"amigo": True}
    dados["usuarios"] = usuarios

    guild = bot.get_guild(guild_id)
    if guild:
        membro = guild.get_member(user_id)
        if membro is None:
            try:
                membro = await guild.fetch_member(user_id)
            except discord.NotFound:
                membro = None
        dados = atualizar_info_usuario(dados, user_id, membro)

    salvar_amigos(dados, arquivo)
    await atribuir_cargo_amigo(user_id, bot, guild_id, amigos_role_id, webhook_logs)

async def remover_amigo(user_id: int, bot, guild_id: int, amigos_role_id: int, arquivo: str, webhook_logs: str):
    dados = carregar_amigos(arquivo)
    usuarios = dados.get("usuarios", {})
    if str(user_id) in usuarios:
        usuarios[str(user_id)]["amigo"] = False
    dados["usuarios"] = usuarios
    salvar_amigos(dados, arquivo)
    await remover_cargo_amigo(user_id, bot, guild_id, amigos_role_id, webhook_logs)
