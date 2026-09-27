import discord
import json
import os
from datetime import datetime, timedelta, timezone

def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def carregar_vips(arquivo: str):
    if not arquivo or not os.path.exists(arquivo):
        return {"usuarios": {}}
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"usuarios": {}}

def salvar_vips(dados, arquivo: str):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def consultar_vip(user_id: int, arquivo: str):
    dados = carregar_vips(arquivo)
    return dados.get("usuarios", {}).get(str(user_id), {"vip": False})

def atualizar_info_usuario(dados: dict, user_id: int, membro: discord.Member = None):
    user_id_str = str(user_id)
    if user_id_str not in dados["usuarios"]:
        dados["usuarios"][user_id_str] = {}

    usuario = dados["usuarios"][user_id_str]
    agora = datetime.now(timezone.utc)
    agora_iso = agora.isoformat()

    ultima_str = usuario.get("ultima_atualizacao_info", "1970-01-01T00:00:00+00:00")
    tempo_desde_update = (agora - _parse_dt(ultima_str)).total_seconds()

    if tempo_desde_update >= 3600 or "apelido" not in usuario:
        if membro:
            usuario["apelido"] = membro.display_name
            usuario["nome_usuario"] = membro.name
        usuario["ultima_atualizacao_info"] = agora_iso

    return dados

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

async def atribuir_cargo_vip(user_id: int, bot, guild_id: int, vip_role_id: int, cfg: dict = None):
    guild, membro = await _get_membro(bot, guild_id, user_id)
    if not guild:
        return
    cargo = guild.get_role(vip_role_id)
    if cargo and membro:
        try:
            await membro.add_roles(cargo, reason="VIP ativado")
        except Exception as e:
            import logging
            logging.error(f"Erro ao dar cargo VIP a {user_id}: {e}")

async def remover_cargo_vip(user_id: int, bot, guild_id: int, vip_role_id: int, cfg: dict = None):
    guild, membro = await _get_membro(bot, guild_id, user_id)
    if not guild:
        return
    cargo = guild.get_role(vip_role_id)
    if cargo and membro:
        try:
            await membro.remove_roles(cargo, reason="VIP desativado")
        except Exception as e:
            import logging
            logging.error(f"Erro ao tirar cargo VIP de {user_id}: {e}")

async def adicionar_vip(user_id: int, dias, bot, guild_id: int, vip_role_id: int, arquivo: str, fuso_brt, cfg: dict = None):
    dados = carregar_vips(arquivo)
    usuarios = dados.get("usuarios", {})
    agora = datetime.now(fuso_brt)
    info = usuarios.get(str(user_id), {})
    ja_tinha_vip = info.get("vip", False)
    ja_eterno = ja_tinha_vip and info.get("expira_em") is None
    ativo_em = info.get("ativo_em") if ja_tinha_vip else agora.isoformat()

    if dias is None:
        usuarios[str(user_id)] = {"vip": True, "ativo_em": ativo_em, "expira_em": None, "eterno": True}
    elif ja_eterno:
        pass
    else:
        base = agora
        if ja_tinha_vip and info.get("expira_em"):
            expira_atual = _parse_dt(info["expira_em"])
            if expira_atual.tzinfo is None:
                expira_atual = expira_atual.replace(tzinfo=fuso_brt)
            if expira_atual > agora:
                base = expira_atual
        usuarios[str(user_id)] = {
            "vip": True,
            "ativo_em": ativo_em,
            "expira_em": (base + timedelta(days=dias)).isoformat(),
            "eterno": False
        }

    dados["usuarios"] = usuarios
    guild, membro = await _get_membro(bot, guild_id, user_id)
    if guild:
        dados = atualizar_info_usuario(dados, user_id, membro)

    salvar_vips(dados, arquivo)
    if not ja_tinha_vip:
        await atribuir_cargo_vip(user_id, bot, guild_id, vip_role_id)

async def remover_vip(user_id: int, bot, guild_id: int, vip_role_id: int, arquivo: str, cfg: dict = None):
    dados = carregar_vips(arquivo)
    usuarios = dados.get("usuarios", {})
    if str(user_id) in usuarios:
        usuarios[str(user_id)]["vip"] = False
        usuarios[str(user_id)]["expira_em"] = None
        usuarios[str(user_id)]["eterno"] = False
    dados["usuarios"] = usuarios
    salvar_vips(dados, arquivo)
    await remover_cargo_vip(user_id, bot, guild_id, vip_role_id)

async def setar_tempo_vip(user_id: int, dias: int, bot, guild_id: int, vip_role_id: int, arquivo: str, fuso_brt, cfg: dict = None):
    dados = carregar_vips(arquivo)
    usuarios = dados.get("usuarios", {})
    info = usuarios.get(str(user_id), {})
    ja_tinha_vip = info.get("vip", False)
    agora = datetime.now(fuso_brt)
    ativo_em = info.get("ativo_em") if ja_tinha_vip else agora.isoformat()

    usuarios[str(user_id)] = {
        "vip": True,
        "ativo_em": ativo_em,
        "expira_em": (agora + timedelta(days=dias)).isoformat(),
        "eterno": False
    }

    dados["usuarios"] = usuarios
    salvar_vips(dados, arquivo)
    if not ja_tinha_vip:
        await atribuir_cargo_vip(user_id, bot, guild_id, vip_role_id)

async def remover_tempo_vip(user_id: int, dias: int, bot, guild_id: int, vip_role_id: int, arquivo: str, fuso_brt, cfg: dict = None):
    dados = carregar_vips(arquivo)
    usuarios = dados.get("usuarios", {})
    info = usuarios.get(str(user_id))

    if not info or not info.get("vip"):
        return "sem_vip"
    if info.get("expira_em") is None:
        return "eterno"

    expira = _parse_dt(info["expira_em"])
    nova_expira = expira - timedelta(days=dias)
    agora = datetime.now(fuso_brt)

    if nova_expira.tzinfo is None:
        nova_expira = nova_expira.replace(tzinfo=fuso_brt)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=fuso_brt)

    if nova_expira <= agora:
        info["vip"] = False
        info["expira_em"] = None
        info["eterno"] = False
        resultado = "desativado"
    else:
        info["expira_em"] = nova_expira.isoformat()
        resultado = "reduzido"

    usuarios[str(user_id)] = info
    dados["usuarios"] = usuarios
    salvar_vips(dados, arquivo)

    if resultado == "desativado":
        await remover_cargo_vip(user_id, bot, guild_id, vip_role_id)
    return resultado

async def checar_vips_expirados(bot, guild_id: int, vip_role_id: int, arquivo: str, fuso_brt, cfg: dict = None):
    dados = carregar_vips(arquivo)
    usuarios = dados.get("usuarios", {})
    agora = datetime.now(fuso_brt)
    expirados = []

    for user_id, info in usuarios.items():
        if info.get("vip") and info.get("expira_em"):
            expira = _parse_dt(info["expira_em"])
            if expira.tzinfo is None:
                expira = expira.replace(tzinfo=fuso_brt)
            if expira <= agora:
                info["vip"] = False
                info["expira_em"] = None
                info["eterno"] = False
                expirados.append(user_id)

    if expirados:
        dados["usuarios"] = usuarios
        salvar_vips(dados, arquivo)
        for user_id in expirados:
            await remover_cargo_vip(int(user_id), bot, guild_id, vip_role_id)

    return expirados
