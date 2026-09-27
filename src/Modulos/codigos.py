import discord
import json
import os
import asyncio
import logging
from datetime import datetime, timedelta
from Modulos.webhooks import enviar_webhook, apagar_webhook_msg, registrar_log_normal, registrar_log_codigo

def carregar_timers(arquivo: str):
    if not arquivo or not os.path.exists(arquivo):
        return {"codigos": {}}
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"codigos": {}}

def salvar_timers(dados, arquivo: str):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def salvar_timer_codigo(chave: str, job: dict, arquivo: str):
    dados = carregar_timers(arquivo)
    dados.setdefault("codigos", {})[chave] = job
    salvar_timers(dados, arquivo)

def remover_timer_codigo(chave: str, arquivo: str):
    dados = carregar_timers(arquivo)
    codigos = dados.setdefault("codigos", {})
    if chave in codigos:
        del codigos[chave]
        salvar_timers(dados, arquivo)

def montar_embed_codigo(job: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"Sala do {job.get('autor_apelido', job['autor_nome'])}",
        description=job["conteudo"],
        color=discord.Color.blue()
    )
    embed.set_author(name=job["autor_nome"], icon_url=job.get("autor_avatar"))
    embed.timestamp = datetime.fromisoformat(job["criado_em"])
    embed.set_footer(text="Dica Mobile: Segure no código para copiar")
    return embed

async def aguardar_ate(timestamp_iso: str, fuso_brt):
    from datetime import timezone
    dt = datetime.fromisoformat(timestamp_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=fuso_brt)
    agora = datetime.now(fuso_brt)
    restante = (dt - agora).total_seconds()
    if restante > 0:
        await asyncio.sleep(restante)

def agendar_job(chave: str, job: dict, bot, arquivo_timers: str, fuso_brt,
                webhook_antecipado: str, webhook_codigos: str, webhook_lembrete_chat: str,
                logs_gerais, logs_codigos, role_ping_lembrete: str):
    salvar_timer_codigo(chave, job, arquivo_timers)
    bot.loop.create_task(aguardar_e_processar(
        chave, job, bot, arquivo_timers, fuso_brt,
        webhook_antecipado, webhook_codigos, webhook_lembrete_chat,
        logs_gerais, logs_codigos, role_ping_lembrete
    ))

async def aguardar_e_processar(chave: str, job: dict, bot, arquivo_timers: str, fuso_brt,
                                webhook_antecipado: str, webhook_codigos: str, webhook_lembrete_chat: str,
                                logs_gerais, logs_codigos, role_ping_lembrete: str):
    await aguardar_ate(job["disparar_em"], fuso_brt)

    dados = carregar_timers(arquivo_timers)
    job_atual = dados.get("codigos", {}).get(chave)
    if job_atual is None:
        return

    await processar_job(chave, job_atual, bot, arquivo_timers, fuso_brt,
                        webhook_antecipado, webhook_codigos, webhook_lembrete_chat,
                        logs_gerais, logs_codigos, role_ping_lembrete)

async def processar_job(chave: str, job: dict, bot, arquivo_timers: str, fuso_brt,
                        webhook_antecipado: str, webhook_codigos: str, webhook_lembrete_chat: str,
                        logs_gerais, logs_codigos, role_ping_lembrete: str):
    tipo = job.get("tipo")

    try:
        if tipo == "antecipado_expira":
            if await apagar_webhook_msg(webhook_antecipado, job["antecipado_id"]):
                await registrar_log_codigo(f"Mensagem antecipada expirada: {job['conteudo']}", tipo="neutro", bot=bot, canal_id=logs_codigos)
            else:
                await registrar_log_codigo("Mensagem antecipada já apagada antes do timer.", tipo="aviso", bot=bot, canal_id=logs_codigos)

        elif tipo == "publicar":
            import aiohttp
            ainda_existe = True
            try:
                async with aiohttp.ClientSession() as session:
                    webhook = discord.Webhook.from_url(webhook_antecipado, session=session)
                    await webhook.fetch_message(job["antecipado_id"])
            except discord.NotFound:
                ainda_existe = False

            if not ainda_existe:
                await registrar_log_codigo("Mensagem antecipada já apagada, cancelando envio ao público.", tipo="aviso", bot=bot, canal_id=logs_codigos)
            else:
                embed = montar_embed_codigo(job)
                publico_msg = await enviar_webhook(
                    webhook_codigos, embed=embed,
                    username=f"Sala do {job.get('autor_apelido', job['autor_nome'])}", wait=True
                )
                await registrar_log_codigo(f"Mensagem enviada ao público: {job['conteudo']}", tipo="sucesso", bot=bot, canal_id=logs_codigos)

                agora = datetime.now(fuso_brt)
                for nova_chave, novo_job in [
                    (f"publico_expira:{publico_msg.id}", {
                        "tipo": "publico_expira", "publico_id": publico_msg.id,
                        "conteudo": job["conteudo"],
                        "disparar_em": (agora + timedelta(seconds=600)).isoformat()
                    }),
                    (f"lembrete:{publico_msg.id}", {
                        "tipo": "lembrete", "conteudo": job["conteudo"],
                        "disparar_em": (agora + timedelta(seconds=15)).isoformat()
                    })
                ]:
                    salvar_timer_codigo(nova_chave, novo_job, arquivo_timers)
                    bot.loop.create_task(aguardar_e_processar(
                        nova_chave, novo_job, bot, arquivo_timers, fuso_brt,
                        webhook_antecipado, webhook_codigos, webhook_lembrete_chat,
                        logs_gerais, logs_codigos, role_ping_lembrete
                    ))

        elif tipo == "publico_expira":
            if await apagar_webhook_msg(webhook_codigos, job["publico_id"]):
                await registrar_log_codigo(f"Mensagem pública expirada: {job['conteudo']}", tipo="neutro", bot=bot, canal_id=logs_codigos)
            else:
                await registrar_log_codigo("Mensagem pública já apagada antes do timer.", tipo="aviso", bot=bot, canal_id=logs_codigos)

        elif tipo == "lembrete":
            lembrete_embed = discord.Embed(
                title="Lembrete enviar código chat live",
                description=job["conteudo"],
                color=discord.Color.red()
            )
            lembrete_msg = await enviar_webhook(
                webhook_lembrete_chat, conteudo=role_ping_lembrete, embed=lembrete_embed, wait=True
            )
            await registrar_log_codigo(f"Lembrete enviado: {job['conteudo']}", tipo="sucesso", bot=bot, canal_id=logs_codigos)

            agora = datetime.now(fuso_brt)
            nova_chave = f"lembrete_apagar:{lembrete_msg.id}"
            novo_job = {
                "tipo": "lembrete_apagar", "lembrete_id": lembrete_msg.id,
                "conteudo": job["conteudo"],
                "disparar_em": (agora + timedelta(seconds=180)).isoformat()
            }
            salvar_timer_codigo(nova_chave, novo_job, arquivo_timers)
            bot.loop.create_task(aguardar_e_processar(
                nova_chave, novo_job, bot, arquivo_timers, fuso_brt,
                webhook_antecipado, webhook_codigos, webhook_lembrete_chat,
                logs_gerais, logs_codigos, role_ping_lembrete
            ))

        elif tipo == "lembrete_apagar":
            if await apagar_webhook_msg(webhook_lembrete_chat, job["lembrete_id"]):
                await registrar_log_codigo(f"Lembrete expirado: {job['conteudo']}", tipo="neutro", bot=bot, canal_id=logs_codigos)
            else:
                await registrar_log_codigo("Lembrete já apagado antes do timer.", tipo="aviso", bot=bot, canal_id=logs_codigos)

    except Exception as e:
        logging.error(f"Erro ao processar timer '{tipo}': {e}")

    remover_timer_codigo(chave, arquivo_timers)

def retomar_timers_pendentes(bot, arquivo_timers: str, fuso_brt,
                              webhook_antecipado: str, webhook_codigos: str, webhook_lembrete_chat: str,
                              logs_gerais, logs_codigos, role_ping_lembrete: str):
    dados = carregar_timers(arquivo_timers)
    for chave, job in dados.get("codigos", {}).items():
        bot.loop.create_task(aguardar_e_processar(
            chave, job, bot, arquivo_timers, fuso_brt,
            webhook_antecipado, webhook_codigos, webhook_lembrete_chat,
            logs_gerais, logs_codigos, role_ping_lembrete
        ))
