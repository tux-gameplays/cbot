import discord
import json
import os
import logging
from datetime import datetime, timedelta, timezone
from Modulos.codigos import agendar_job, aguardar_ate, remover_timer_codigo

DELAY_CHAT_LIVE_PUBLICO = 10
DELAY_ANTECIPADO_PUBLICO = 30
DELAY_CHAT_LIVE_APOS_ANTECIPADO = 15

def carregar_salas(arquivo: str) -> dict:
    if not arquivo or not os.path.exists(arquivo):
        return {"salas": {}}
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"salas": {}}

def salvar_salas(dados: dict, arquivo: str):
    if not arquivo:
        return
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def parsear_conteudo_sala(conteudo: str) -> dict | None:
    linhas = [l.strip() for l in conteudo.strip().splitlines() if l.strip()]
    if len(linhas) < 1:
        return None

    cod = linhas[0].upper()
    if len(cod) != 6 or not cod.isalpha():
        return None

    pessoas = linhas[1] if len(linhas) > 1 else "?/?"
    status = linhas[2] if len(linhas) > 2 else "No Lobby"

    return {"cod": cod, "pessoas": pessoas, "status": status}

def montar_embed_sala(dados_sala: dict, autor_nome: str, autor_avatar: str | None) -> discord.Embed:
    status = dados_sala["status"]
    pessoas = dados_sala["pessoas"]
    cod = dados_sala["cod"]

    cores = {
        "em jogo": discord.Color.red(),
        "no lobby": discord.Color.green(),
        "fechada": discord.Color.dark_grey(),
    }
    cor = cores.get(status.lower(), discord.Color.blue())

    embed = discord.Embed(
        title=f"Sala do {autor_nome}",
        description=cod,
        color=cor
    )
    embed.add_field(name="👥 Pessoas", value=pessoas, inline=True)
    embed.add_field(name="📊 Status", value=status, inline=True)

    if autor_avatar:
        embed.set_author(name=autor_nome, icon_url=autor_avatar)
    else:
        embed.set_author(name=autor_nome)

    embed.set_footer(text="Dica Mobile: Segure no código para copiar")
    embed.timestamp = datetime.now(timezone.utc)
    return embed

def chave_lembrete_sala(sala_id: str) -> str:
    return f"lembrete:sala:{sala_id}"

def agendar_lembrete_sala(sala_id: str, codigo: str, segundos: int, bot, cfg: dict):
    agora = datetime.now(cfg["fuso_brt"])
    job = {
        "tipo": "lembrete",
        "conteudo": codigo,
        "disparar_em": (agora + timedelta(seconds=segundos)).isoformat()
    }
    agendar_job(chave_lembrete_sala(sala_id), job, bot, cfg["arquivo_timers"], cfg["fuso_brt"],
                cfg["webhook_antecipado"], cfg["codigo_antecipado"], cfg["codigo_publico"], cfg["codigo_lembrete"],
                cfg["logs_gerais"], cfg["logs_codigos"], cfg["role_ping_lembrete"])

def cancelar_lembrete_sala(sala_id: str, cfg: dict):
    remover_timer_codigo(chave_lembrete_sala(sala_id), cfg["arquivo_timers"])

def canal_publico_id(cfg: dict) -> int:
    return int(cfg.get("canal_salas_publico") or cfg.get("codigo_publico", 0))

async def apagar_msg_sala(bot, canal_id, msg_id):
    if not canal_id or not msg_id:
        return
    canal = bot.get_channel(int(canal_id))
    if not canal:
        return
    try:
        msg = await canal.fetch_message(msg_id)
        await msg.delete()
    except discord.NotFound:
        pass
    except Exception as e:
        logging.error(f"Erro ao apagar embed de sala: {e}")

async def atualizar_ou_recriar(bot, canal_id, msg_id, embed: discord.Embed):
    canal = bot.get_channel(int(canal_id))
    if not canal:
        return msg_id
    try:
        msg = await canal.fetch_message(msg_id)
        await msg.edit(embed=embed)
        return msg_id
    except discord.NotFound:
        try:
            nova_msg = await canal.send(embed=embed)
            return nova_msg.id
        except Exception as e:
            logging.error(f"Erro ao recriar embed de sala: {e}")
            return msg_id
    except Exception as e:
        logging.error(f"Erro ao editar embed de sala: {e}")
        return msg_id

async def aguardar_e_publicar(sala_id: str, publicar_em: str, bot, cfg: dict):
    await aguardar_ate(publicar_em, cfg["fuso_brt"])

    arquivo = cfg["arquivo_salas"]
    dados = carregar_salas(arquivo)
    sala = dados["salas"].get(sala_id)
    if not sala or not sala.get("publicar_em"):
        return
    sala.pop("publicar_em")
    salvar_salas(dados, arquivo)

    canal = bot.get_channel(canal_publico_id(cfg))
    if not canal:
        logging.error(f"Canal público de salas não encontrado: {canal_publico_id(cfg)}")
        return

    embed = montar_embed_sala(sala["dados_sala"], sala["autor_nome"], sala.get("autor_avatar"))
    try:
        msg_publico = await canal.send(embed=embed)
    except Exception as e:
        logging.error(f"Erro ao publicar sala do antecipado no público: {e}")
        return

    dados = carregar_salas(arquivo)
    sala = dados["salas"].get(sala_id)
    if not sala:
        try:
            await msg_publico.delete()
        except Exception:
            pass
        return

    sala["publico_canal_id"] = canal.id
    sala["publico_msg_id"] = msg_publico.id
    salvar_salas(dados, arquivo)

    agendar_lembrete_sala(sala_id, sala["dados_sala"]["cod"], DELAY_CHAT_LIVE_APOS_ANTECIPADO, bot, cfg)

async def processar_msg_sala(message: discord.Message, bot, cfg: dict, tipo: str):
    arquivo = cfg.get("arquivo_salas")
    if not arquivo:
        return

    conteudo = message.content or ""
    dados_sala = parsear_conteudo_sala(conteudo)
    if not dados_sala:
        return

    if dados_sala["status"].lower() == "fechada":
        return

    autor_nome = message.author.display_name or message.author.name
    autor_avatar = None
    if hasattr(message.author, "avatar") and message.author.avatar:
        autor_avatar = message.author.avatar.url

    embed = montar_embed_sala(dados_sala, autor_nome, autor_avatar)

    if tipo == "antecipado":
        canal_destino_id = cfg.get("canal_salas_antecipado") or cfg.get("codigo_antecipado", 0)
    else:
        canal_destino_id = canal_publico_id(cfg)

    canal_destino = bot.get_channel(int(canal_destino_id)) if canal_destino_id else None
    if not canal_destino:
        logging.error(f"Canal destino de sala não encontrado: {canal_destino_id}")
        return

    try:
        msg_embed = await canal_destino.send(embed=embed)
    except Exception as e:
        logging.error(f"Erro ao enviar embed de sala: {e}")
        return

    sala_id = str(message.id)
    entrada = {
        "embed_canal_id": canal_destino.id,
        "embed_msg_id": msg_embed.id,
        "tipo": tipo,
        "autor_nome": autor_nome,
        "autor_avatar": autor_avatar,
        "dados_sala": dados_sala,
        "criado_em": datetime.now(timezone.utc).isoformat()
    }

    publicar_em = None
    if tipo == "antecipado":
        publicar_em = (datetime.now(cfg["fuso_brt"]) + timedelta(seconds=DELAY_ANTECIPADO_PUBLICO)).isoformat()
        entrada["publicar_em"] = publicar_em

    dados = carregar_salas(arquivo)
    dados["salas"][sala_id] = entrada
    salvar_salas(dados, arquivo)

    if tipo == "antecipado":
        bot.loop.create_task(aguardar_e_publicar(sala_id, publicar_em, bot, cfg))
    else:
        agendar_lembrete_sala(sala_id, dados_sala["cod"], DELAY_CHAT_LIVE_PUBLICO, bot, cfg)

async def processar_edicao_sala(message: discord.Message, bot, cfg: dict):
    arquivo = cfg.get("arquivo_salas")
    if not arquivo:
        return

    sala_id = str(message.id)
    sala = carregar_salas(arquivo)["salas"].get(sala_id)
    if not sala:
        return

    dados_sala = parsear_conteudo_sala(message.content or "")
    if not dados_sala:
        return

    if dados_sala["status"].lower() == "fechada":
        dados = carregar_salas(arquivo)
        sala = dados["salas"].pop(sala_id, None)
        salvar_salas(dados, arquivo)
        cancelar_lembrete_sala(sala_id, cfg)
        if sala:
            await apagar_msg_sala(bot, sala["embed_canal_id"], sala["embed_msg_id"])
            await apagar_msg_sala(bot, sala.get("publico_canal_id"), sala.get("publico_msg_id"))
        return

    embed = montar_embed_sala(dados_sala, sala["autor_nome"], sala.get("autor_avatar"))

    novo_embed_id = await atualizar_ou_recriar(bot, sala["embed_canal_id"], sala["embed_msg_id"], embed)
    novo_publico_id = None
    if sala.get("publico_msg_id"):
        novo_publico_id = await atualizar_ou_recriar(bot, sala["publico_canal_id"], sala["publico_msg_id"], embed)

    dados = carregar_salas(arquivo)
    atual = dados["salas"].get(sala_id)
    if not atual:
        return
    atual["dados_sala"] = dados_sala
    atual["embed_msg_id"] = novo_embed_id
    if novo_publico_id and atual.get("publico_msg_id"):
        atual["publico_msg_id"] = novo_publico_id
    salvar_salas(dados, arquivo)

async def retomar_salas_pendentes(bot, cfg: dict):
    arquivo = cfg.get("arquivo_salas")
    if not arquivo:
        return

    dados = carregar_salas(arquivo)
    if not dados["salas"]:
        return

    pendentes = 0
    for sala_id, sala in dados["salas"].items():
        if sala.get("publicar_em"):
            bot.loop.create_task(aguardar_e_publicar(sala_id, sala["publicar_em"], bot, cfg))
            pendentes += 1

    logging.info(f"🏠 {len(dados['salas'])} sala(s) ativa(s) carregadas do JSON ({pendentes} aguardando publicar)")
