import discord
import json
import os
import re
import logging
import asyncio
import aiohttp
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

TOKEN_FILE = "token_youtube.json"


def autenticar_oauth(client_secret_file: str) -> Credentials:
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def obter_servico_youtube(client_secret_file: str) -> object:
    creds = autenticar_oauth(client_secret_file)
    return build("youtube", "v3", credentials=creds)


def carregar_youtube(arquivo: str) -> dict:
    if not arquivo or not os.path.exists(arquivo):
        return {"ultimo_video_id": None, "ultimo_short_id": None, "ultima_live_id": None, "live_programada_id": None, "live_off_notificada": False}
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"ultimo_video_id": None, "ultimo_short_id": None, "ultima_live_id": None, "live_programada_id": None, "live_off_notificada": False}


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
    padrao = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duracao)
    if not padrao:
        return 0
    horas = int(padrao.group(1) or 0)
    minutos = int(padrao.group(2) or 0)
    segundos = int(padrao.group(3) or 0)
    return horas * 3600 + minutos * 60 + segundos


async def checar_lives(api_key: str, canal_id: str, dados: dict, arquivo: str, cfg: dict):
    live_ativa = False

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
            live_ativa = True
            if not dados.get("live_off_notificada"):
                pass  # já estava False, não precisa salvar
            elif dados.get("live_off_notificada"):
                dados["live_off_notificada"] = False
                salvar_youtube(dados, arquivo)

            if dados.get("ultima_live_id") == video_id:
                continue
            dados["ultima_live_id"] = video_id
            dados["live_off_notificada"] = False
            salvar_youtube(dados, arquivo)
            await anunciar_live(video_id, titulo, thumbnail, inicio_agendado, "ao_vivo", cfg)

    if not live_ativa and dados.get("ultima_live_id") and not dados.get("live_off_notificada"):
        dados["live_off_notificada"] = True
        dados["ultima_live_id"] = None
        salvar_youtube(dados, arquivo)
        await anunciar_live_off(cfg)


async def anunciar_live_off(cfg: dict):
    bot = cfg["bot"]
    canal_id = cfg.get("canal_anuncio_lives")
    canal = bot.get_channel(int(canal_id)) if canal_id else None
    if not canal:
        return

    ping_id = cfg.get("ping_live_ao_vivo")
    embed = discord.Embed(
        description="A live encerrou! Obrigado a todos que participaram 💜",
        color=discord.Color.dark_gray()
    )
    embed.set_author(name="⚫ Live Encerrada")
    embed.timestamp = datetime.now(timezone.utc)

    ping = f"<@&{ping_id}>" if ping_id else ""
    await canal.send(content=ping, embed=embed)


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


async def monitorar_chat_live(cfg: dict):
    api_key = cfg.get("youtube_api_key")
    canal_id = cfg.get("youtube_canal_id")
    if not api_key or not canal_id:
        return

    live_chat_id = await obter_live_chat_id(api_key, canal_id)
    if not live_chat_id:
        return

    client_secret = cfg.get("youtube_client_secret", "client_secret.json")
    servico = obter_servico_youtube(client_secret)

    page_token = None
    while True:
        try:
            req = servico.liveChatMessages().list(
                liveChatId=live_chat_id,
                part="snippet,authorDetails",
                pageToken=page_token
            )
            resposta = req.execute()

            for msg in resposta.get("items", []):
                await processar_mensagem_chat(msg, cfg, servico)

            page_token = resposta.get("nextPageToken")
            intervalo = resposta.get("pollingIntervalMillis", 5000) / 1000
            await asyncio.sleep(intervalo)

        except Exception as e:
            logging.error(f"Erro ao monitorar chat: {e}")
            await asyncio.sleep(10)


async def obter_live_chat_id(api_key: str, canal_id: str) -> str | None:
    url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?key={api_key}&channelId={canal_id}&part=snippet,id"
        f"&eventType=live&type=video&maxResults=1"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resultado = await resp.json()
        items = resultado.get("items", [])
        if not items:
            return None
        video_id = items[0]["id"].get("videoId")
        if not video_id:
            return None

        url2 = (
            f"https://www.googleapis.com/youtube/v3/videos"
            f"?key={api_key}&id={video_id}&part=liveStreamingDetails"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url2) as resp:
                resultado2 = await resp.json()
        items2 = resultado2.get("items", [])
        if not items2:
            return None
        return items2[0].get("liveStreamingDetails", {}).get("activeLiveChatId")
    except Exception as e:
        logging.error(f"Erro ao obter live chat ID: {e}")
        return None


async def processar_mensagem_chat(msg: dict, cfg: dict, servico):
    autor = msg.get("authorDetails", {})
    snippet = msg.get("snippet", {})

    autor_id = autor.get("channelId", "")
    nome = autor.get("displayName", "")
    texto = snippet.get("displayMessage", "")
    eh_moderador = autor.get("isChatModerator", False)
    eh_membro = autor.get("isChatSponsor", False)
    eh_dono = autor.get("isChatOwner", False)

    await sincronizar_cargo_discord(autor_id, eh_moderador, eh_membro, eh_dono, cfg)

    await processar_comandos_chat(texto, autor_id, nome, eh_moderador, eh_dono, msg, cfg, servico)


async def sincronizar_cargo_discord(yt_channel_id: str, eh_moderador: bool, eh_membro: bool, eh_dono: bool, cfg: dict):
    bot = cfg["bot"]
    guild_id = cfg.get("guild_id")
    cargo_membro_id = cfg.get("cargo_membro_yt")
    cargo_mod_id = cfg.get("cargo_moderador_yt")

    if not guild_id:
        return

    guild = bot.get_guild(int(guild_id))
    if not guild:
        return

    for membro_dc in guild.members:
        conexoes = await obter_conexoes_discord(membro_dc.id, cfg)
        if not conexoes:
            continue

        yt_conectado = next(
            (c for c in conexoes if c.get("type") == "youtube" and c.get("id") == yt_channel_id),
            None
        )
        if not yt_conectado:
            continue

        cargo_membro = guild.get_role(int(cargo_membro_id)) if cargo_membro_id else None
        cargo_mod = guild.get_role(int(cargo_mod_id)) if cargo_mod_id else None

        if eh_membro and cargo_membro and cargo_membro not in membro_dc.roles:
            await membro_dc.add_roles(cargo_membro)
        if (eh_moderador or eh_dono) and cargo_mod and cargo_mod not in membro_dc.roles:
            await membro_dc.add_roles(cargo_mod)


async def obter_conexoes_discord(user_id: int, cfg: dict) -> list:
    token = cfg.get("discord_bot_token")
    if not token:
        return []
    url = f"https://discord.com/api/v10/users/{user_id}/connections"
    headers = {"Authorization": f"Bot {token}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return []


async def processar_comandos_chat(texto: str, autor_id: str, nome: str, eh_mod: bool, eh_dono: bool, msg: dict, cfg: dict, servico):
    if not texto.startswith("!"):
        return

    partes = texto.strip().split(maxsplit=1)
    cmd = partes[0].lower()
    args = partes[1] if len(partes) > 1 else ""

    live_chat_id = msg["snippet"].get("liveChatId", "")

    if cmd == "!codigo":
        codigo = cfg.get("codigo_sala_atual")
        resposta = f"🎮 Código da sala: {codigo}" if codigo else "Nenhum código disponível no momento."
        await enviar_mensagem_chat(live_chat_id, resposta, servico)

    elif cmd == "!discord":
        link = cfg.get("link_discord", "https://discord.gg/seuservidor")
        await enviar_mensagem_chat(live_chat_id, f"💬 Entre no Discord: {link}", servico)

    elif cmd == "!ban" and (eh_mod or eh_dono):
        pass

    elif cmd == "!timeout" and (eh_mod or eh_dono):
        pass


async def enviar_mensagem_chat(live_chat_id: str, mensagem: str, servico):
    try:
        servico.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {"messageText": mensagem}
                }
            }
        ).execute()
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem no chat: {e}")


def definir_codigo_sala(codigo: str, cfg: dict):
    cfg["codigo_sala_atual"] = codigo
    logging.info(f"Código da sala atualizado: {codigo}")
