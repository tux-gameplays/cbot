import discord
import json
import os
from datetime import datetime, timedelta, timezone

DIAS_EXPIRACAO_WARN = 60

TEMPOS_TIMEOUT = {
    1: timedelta(minutes=30),
    2: timedelta(hours=1),
    3: timedelta(days=1)
}

def carregar_warns(arquivo: str):
    if not arquivo or not os.path.exists(arquivo):
        return {"proximo_id": 1, "warns": {}}
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("proximo_id", 1)
            dados.setdefault("warns", {})
            return dados
    except json.JSONDecodeError:
        return {"proximo_id": 1, "warns": {}}

def salvar_warns(dados, arquivo: str):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def warns_ativos_do_usuario(user_id: int, arquivo: str):
    dados = carregar_warns(arquivo)
    return [
        w for w in dados["warns"].values()
        if str(w.get("user_id")) == str(user_id) and w.get("status") == "ativo"
    ]

async def criar_warn(user_id: int, autor_id: int, motivo: str, eterno: bool, bot, guild_id: int, arquivo: str, fuso_brt):
    dados = carregar_warns(arquivo)
    novo_id = dados["proximo_id"]
    agora = datetime.now(fuso_brt)

    warn = {
        "id": novo_id,
        "user_id": user_id,
        "autor_id": autor_id,
        "motivo": motivo,
        "eterno": eterno,
        "criado_em": agora.isoformat(),
        "expira_em": None if eterno else (agora + timedelta(days=DIAS_EXPIRACAO_WARN)).isoformat(),
        "status": "ativo"
    }

    dados["warns"][str(novo_id)] = warn
    dados["proximo_id"] = novo_id + 1

    guild = bot.get_guild(guild_id)
    if guild:
        membro = guild.get_member(user_id)
        if membro is None:
            try:
                membro = await guild.fetch_member(user_id)
            except discord.NotFound:
                membro = None
        if "info_usuarios" not in dados:
            dados["info_usuarios"] = {}
        if membro:
            agora_utc = datetime.now(timezone.utc).isoformat()
            info = dados["info_usuarios"].get(str(user_id), {})
            tempo_desde = (datetime.now(timezone.utc) - datetime.fromisoformat(info.get("ultima_atualizacao_info", "1970-01-01T00:00:00+00:00"))).total_seconds()
            if tempo_desde >= 3600 or "apelido" not in info:
                dados["info_usuarios"][str(user_id)] = {
                    "apelido": membro.display_name,
                    "nome_usuario": membro.name,
                    "ultima_atualizacao_info": agora_utc
                }

    salvar_warns(dados, arquivo)
    return warn

def remover_warn(warn_id: int, arquivo: str, fuso_brt):
    dados = carregar_warns(arquivo)
    warn = dados["warns"].get(str(warn_id))
    if not warn or warn.get("status") != "ativo":
        return None
    warn["status"] = "removido"
    warn["removido_em"] = datetime.now(fuso_brt).isoformat()
    dados["warns"][str(warn_id)] = warn
    salvar_warns(dados, arquivo)
    return warn

def checar_warns_expirados(arquivo: str, fuso_brt):
    dados = carregar_warns(arquivo)
    agora = datetime.now(fuso_brt)
    expirados = []

    for warn in dados["warns"].values():
        if warn.get("status") == "ativo" and warn.get("expira_em"):
            if datetime.fromisoformat(warn["expira_em"]) <= agora:
                warn["status"] = "expirado"
                expirados.append(warn)

    if expirados:
        salvar_warns(dados, arquivo)

    return expirados

async def aplicar_punicao_progressao(guild: discord.Guild, user_id: int, quantidade_ativos: int,
                                      bot, guild_id: int, vip_role_id: int, amigos_role_id: int,
                                      arquivo_vips: str, arquivo_amigos: str, fuso_brt, webhook_logs: str):
    from Modulos.vip import remover_vip
    from Modulos.amigos import remover_amigo

    membro = guild.get_member(user_id)
    if membro is None:
        try:
            membro = await guild.fetch_member(user_id)
        except discord.NotFound:
            membro = None

    if membro is None:
        return f"Membro {user_id} não encontrado no servidor para aplicar punição."

    try:
        if quantidade_ativos in TEMPOS_TIMEOUT:
            await membro.timeout(TEMPOS_TIMEOUT[quantidade_ativos], reason=f"Warn #{quantidade_ativos}")
            return f"Timeout de {TEMPOS_TIMEOUT[quantidade_ativos]} aplicado a {membro.mention}."

        elif quantidade_ativos == 4:
            await remover_vip(user_id, bot, guild_id, vip_role_id, arquivo_vips, webhook_logs)
            await remover_amigo(user_id, bot, guild_id, amigos_role_id, arquivo_amigos, webhook_logs)
            await membro.kick(reason="4º warn - remoção de cargos e kick automático")
            return f"{membro.mention} perdeu VIP, Amigos e foi expulso do servidor (4º warn)."

        elif quantidade_ativos >= 5:
            await guild.ban(membro, reason="5º warn - ban automático")
            return f"{membro.mention} foi banido permanentemente (5º warn)."

    except Exception as e:
        return f"Erro ao aplicar punição a {user_id}: {e}"

    return None
