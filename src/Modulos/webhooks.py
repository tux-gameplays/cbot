import discord
import aiohttp
import logging
from datetime import datetime, timezone

_webhook_nome_cache: dict[str, str] = {}

async def obter_nome_webhook(url: str) -> str:
    if url in _webhook_nome_cache:
        return _webhook_nome_cache[url]
    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(url, session=session)
            info = await webhook.fetch()
            nome = info.name or "Sala do Chip"
            _webhook_nome_cache[url] = nome
            return nome
    except Exception:
        return "Sala do Chip"

async def enviar_webhook(url: str, conteudo: str = "", embed: discord.Embed = None,
                         username: str = None, avatar_url: str = None, wait: bool = False):
    if username is None:
        username = await obter_nome_webhook(url)
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(url, session=session)
        return await webhook.send(
            content=conteudo,
            embed=embed,
            username=username,
            avatar_url=avatar_url,
            wait=wait
        )

async def apagar_webhook_msg(url: str, msg_id: int):
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(url, session=session)
        try:
            await webhook.delete_message(msg_id)
            return True
        except discord.NotFound:
            return False
        except Exception as e:
            logging.error(f"Erro ao apagar mensagem webhook: {e}")
            return False

CORES_LOG = {
    "sucesso": discord.Color.green(),
    "info": discord.Color.blurple(),
    "aviso": discord.Color.orange(),
    "erro": discord.Color.red(),
    "neutro": discord.Color.greyple()
}

EMOJIS_LOG = {
    "sucesso": "✅",
    "info": "ℹ️",
    "aviso": "⚠️",
    "erro": "❌",
    "neutro": "🕒"
}

def montar_embed_log(texto: str, tipo: str) -> discord.Embed:
    embed = discord.Embed(
        description=f"{EMOJIS_LOG.get(tipo, 'ℹ️')} {texto}",
        color=CORES_LOG.get(tipo, discord.Color.blurple())
    )
    embed.timestamp = datetime.now(timezone.utc)
    return embed

async def registrar_log_canal(bot, canal_id, embed: discord.Embed):
    if not canal_id:
        return
    try:
        canal = bot.get_channel(int(canal_id))
        if canal:
            await canal.send(embed=embed)
    except Exception as e:
        logging.error(f"Erro ao enviar log no canal {canal_id}: {e}")

async def registrar_log_normal(texto: str, tipo: str = "info", bot=None, canal_id=None):
    logging.info(texto)
    if bot and canal_id:
        await registrar_log_canal(bot, canal_id, montar_embed_log(texto, tipo))

async def registrar_log_codigo(texto: str, tipo: str = "info", bot=None, canal_id=None):
    logging.info(texto)
    if bot and canal_id:
        await registrar_log_canal(bot, canal_id, montar_embed_log(texto, tipo))

async def registrar_log_painel(embed: discord.Embed, bot=None, canal_id=None):
    if bot and canal_id:
        await registrar_log_canal(bot, canal_id, embed)

async def registrar_log_vip(embed: discord.Embed, bot=None, canal_id=None):
    if bot and canal_id:
        await registrar_log_canal(bot, canal_id, embed)

async def registrar_log_amigos(embed: discord.Embed, bot=None, canal_id=None):
    if bot and canal_id:
        await registrar_log_canal(bot, canal_id, embed)

async def registrar_log_punicoes(embed: discord.Embed, bot=None, canal_id=None):
    if bot and canal_id:
        await registrar_log_canal(bot, canal_id, embed)

async def enviar_ou_editar(destino, embed: discord.Embed, view: discord.ui.View):
    if isinstance(destino, discord.Interaction):
        try:
            await destino.response.edit_message(embed=embed, view=view)
        except discord.NotFound:
            logging.warning("Interação expirou antes de editar a mensagem.")
    else:
        await destino.send(embed=embed, view=view)
