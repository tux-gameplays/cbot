import discord
import json
import os
import logging
from datetime import datetime, timezone

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
        description=f"```{cod}```",
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
        canal_destino_id = cfg.get("canal_salas_publico") or cfg.get("codigo_publico", 0)

    canal_destino = bot.get_channel(int(canal_destino_id)) if canal_destino_id else None
    if not canal_destino:
        logging.error(f"Canal destino de sala não encontrado: {canal_destino_id}")
        return

    try:
        msg_embed = await canal_destino.send(embed=embed)
    except Exception as e:
        logging.error(f"Erro ao enviar embed de sala: {e}")
        return

    dados = carregar_salas(arquivo)
    dados["salas"][str(message.id)] = {
        "embed_canal_id": canal_destino.id,
        "embed_msg_id": msg_embed.id,
        "tipo": tipo,
        "autor_nome": autor_nome,
        "autor_avatar": autor_avatar,
        "dados_sala": dados_sala,
        "criado_em": datetime.now(timezone.utc).isoformat()
    }
    salvar_salas(dados, arquivo)

async def processar_edicao_sala(message: discord.Message, bot, cfg: dict):
    arquivo = cfg.get("arquivo_salas")
    if not arquivo:
        return

    dados = carregar_salas(arquivo)
    sala = dados["salas"].get(str(message.id))
    if not sala:
        return

    conteudo = message.content or ""
    dados_sala = parsear_conteudo_sala(conteudo)
    if not dados_sala:
        return

    autor_nome = sala["autor_nome"]
    autor_avatar = sala.get("autor_avatar")

    # Status fechada — apaga o embed e remove do JSON
    if dados_sala["status"].lower() == "fechada":
        canal = bot.get_channel(sala["embed_canal_id"])
        if canal:
            try:
                msg_embed = await canal.fetch_message(sala["embed_msg_id"])
                await msg_embed.delete()
            except discord.NotFound:
                pass
            except Exception as e:
                logging.error(f"Erro ao apagar embed de sala fechada: {e}")

        del dados["salas"][str(message.id)]
        salvar_salas(dados, arquivo)
        return

    # Atualiza embed
    embed = montar_embed_sala(dados_sala, autor_nome, autor_avatar)

    canal = bot.get_channel(sala["embed_canal_id"])
    if not canal:
        return

    try:
        msg_embed = await canal.fetch_message(sala["embed_msg_id"])
        await msg_embed.edit(embed=embed)
    except discord.NotFound:
        # Embed foi apagado manualmente — recria
        try:
            nova_msg = await canal.send(embed=embed)
            dados["salas"][str(message.id)]["embed_msg_id"] = nova_msg.id
            salvar_salas(dados, arquivo)
        except Exception as e:
            logging.error(f"Erro ao recriar embed de sala: {e}")
    except Exception as e:
        logging.error(f"Erro ao editar embed de sala: {e}")

    # Atualiza dados salvos
    dados["salas"][str(message.id)]["dados_sala"] = dados_sala
    salvar_salas(dados, arquivo)

async def retomar_salas_pendentes(bot, cfg: dict):
    arquivo = cfg.get("arquivo_salas")
    if not arquivo:
        return

    dados = carregar_salas(arquivo)
    if not dados["salas"]:
        return

    logging.info(f"🏠 {len(dados['salas'])} sala(s) ativa(s) carregadas do JSON")
