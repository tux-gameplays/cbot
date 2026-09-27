import discord
import json
import os
import logging
import aiohttp
from datetime import datetime, timezone

def carregar_youtube(arquivo: str) -> dict:
    if not arquivo or not os.path.exists(arquivo):
        return {"ultimo_video_id": None, "ultimo_short_id": None, "ultima_live_id": None, "live_programada_id": None}
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"ultimo_video_id": None, "ultimo_short_id": None, "ultima_live_id": None, "live_programada_id": None}

def salvar_youtube(dados: dict, arquivo: str):
    if not arquivo:
        return
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

async def checar_youtube(cfg: dict):
    api_key = cfg.get("youtube_api_key")
    canal_id = cfg.get("youtube_canal_id")
    arquivo = cfg.get("arquivo_youtube")

    if not api_key or not canal_id:
        return

    dados = carregar_youtube(arquivo)

    await checar_videos_novos(api_key, canal_id, dados, arquivo, cfg)
    await checar_lives(api_key, canal_id, dados, arquivo, cfg)

async def checar_videos_novos(api_key: str, canal_id: str, dados: dict, arquivo: str, cfg: dict):
    url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?key={api_key}&channelId={canal_id}&part=snippet,id"
        f"&order=date&maxResults=5&type=video"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logging.warning(f"YouTube API retornou {resp.status}")
                    return
                resultado = await resp.json()
    except Exception as e:
        logging.error(f"Erro ao checar YouTube: {e}")
        return

    items = resultado.get("items", [])
    if not items:
        return

    for item in reversed(items):
        video_id = item["id"].get("videoId")
        if not video_id:
            continue

        snippet = item["snippet"]
        titulo = snippet.get("title", "Sem título")
        thumbnail = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
        publicado_em = snippet.get("publishedAt", "")

        duracao = await obter_duracao_video(api_key, video_id)
        eh_short = duracao is not None and duracao <= 60

        if eh_short:
            if dados.get("ultimo_short_id") == video_id:
                continue
            dados["ultimo_short_id"] = video_id
            salvar_youtube(dados, arquivo)
            await anunciar_video(video_id, titulo, thumbnail, publicado_em, "short", cfg)
        else:
            if dados.get("ultimo_video_id") == video_id:
                continue
            dados["ultimo_video_id"] = video_id
            salvar_youtube(dados, arquivo)
            await anunciar_video(video_id, titulo, thumbnail, publicado_em, "video", cfg)

async def obter_duracao_video(api_key: str, video_id: str):
    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?key={api_key}&id={video_id}&part=contentDetails"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resultado = await resp.json()
        items = resultado.get("items", [])
        if not items:
            return None
        duracao_iso = items[0]["contentDetails"]["duration"]
        return parsear_duracao_iso(duracao_iso)
    except Exception:
        return None

def parsear_duracao_iso(duracao: str) -> int:
    import re
    padrao = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duracao)
    if not padrao:
        return 0
    horas = int(padrao.group(1) or 0)
    minutos = int(padrao.group(2) or 0)
    segundos = int(padrao.group(3) or 0)
    return horas * 3600 + minutos * 60 + segundos

async def checar_lives(api_key: str, canal_id: str, dados: dict, arquivo: str, cfg: dict):
    for tipo_evento in ["live", "upcoming"]:
        url = (
            f"https://www.googleapis.com/youtube/v3/search"
            f"?key={api_key}&channelId={canal_id}&part=snippet,id"
            f"&eventType={tipo_evento}&type=video&maxResults=1"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    resultado = await resp.json()
        except Exception as e:
            logging.error(f"Erro ao checar lives YouTube: {e}")
            continue

        items = resultado.get("items", [])
        if not items:
            continue

        item = items[0]
        video_id = item["id"].get("videoId")
        snippet = item["snippet"]
        titulo = snippet.get("title", "Sem título")
        thumbnail = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
        inicio_agendado = snippet.get("publishedAt", "")

        if tipo_evento == "upcoming":
            if dados.get("live_programada_id") == video_id:
                continue
            dados["live_programada_id"] = video_id
            salvar_youtube(dados, arquivo)
            await anunciar_live(video_id, titulo, thumbnail, inicio_agendado, "programada", cfg)

        elif tipo_evento == "live":
            if dados.get("ultima_live_id") == video_id:
                continue
            dados["ultima_live_id"] = video_id
            salvar_youtube(dados, arquivo)
            await anunciar_live(video_id, titulo, thumbnail, inicio_agendado, "ao_vivo", cfg)

async def anunciar_video(video_id: str, titulo: str, thumbnail: str, publicado_em: str, tipo: str, cfg: dict):
    bot = cfg["bot"]
    url_video = f"https://www.youtube.com/watch?v={video_id}"

    if tipo == "short":
        canal_id = cfg.get("canal_anuncio_videos")
        ping_id = cfg.get("ping_shorts_novo")
        label = "🩳 Novo Short"
        cor = discord.Color.red()
    else:
        canal_id = cfg.get("canal_anuncio_videos")
        ping_id = cfg.get("ping_video_novo")
        label = "🎬 Novo Vídeo"
        cor = discord.Color.red()

    canal = bot.get_channel(int(canal_id)) if canal_id else None
    if not canal:
        return

    embed = discord.Embed(title=titulo, url=url_video, color=cor)
    embed.set_author(name=label)
    if thumbnail:
        embed.set_image(url=thumbnail)
    embed.timestamp = datetime.now(timezone.utc)

    ping = f"<@&{ping_id}>" if ping_id else ""
    await canal.send(content=ping, embed=embed)

async def anunciar_live(video_id: str, titulo: str, thumbnail: str, inicio: str, tipo: str, cfg: dict):
    bot = cfg["bot"]
    url_video = f"https://www.youtube.com/watch?v={video_id}"

    canal_id = cfg.get("canal_anuncio_lives")
    canal = bot.get_channel(int(canal_id)) if canal_id else None
    if not canal:
        return

    if tipo == "programada":
        ping_id = cfg.get("ping_live_programada")
        label = "📅 Live Programada"
        cor = discord.Color.blurple()
        descricao = "Uma live foi agendada! Fique de olho 👀"
    else:
        ping_id = cfg.get("ping_live_ao_vivo")
        label = "🔴 Live ao Vivo AGORA"
        cor = discord.Color.red()
        descricao = "A live está acontecendo agora! Entra lá 🎮"

    embed = discord.Embed(title=titulo, url=url_video, description=descricao, color=cor)
    embed.set_author(name=label)
    if thumbnail:
        embed.set_image(url=thumbnail)
    embed.timestamp = datetime.now(timezone.utc)

    ping = f"<@&{ping_id}>" if ping_id else ""
    await canal.send(content=ping, embed=embed)
