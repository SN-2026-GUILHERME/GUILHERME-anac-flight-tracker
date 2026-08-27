#!/usr/bin/env python3
"""
fetch_flights.py

Busca dados de voos programados na API pública do SIROS/ANAC para um ou mais
aeroportos (código ICAO) e envia os registros para uma tabela no Supabase.

Variáveis de ambiente esperadas:
    SUPABASE_URL          -> URL do projeto Supabase (ex: https://xxxx.supabase.co)
    SUPABASE_SERVICE_KEY  -> service_role key do Supabase (NUNCA commitar em texto)
    AIRPORTS              -> códigos ICAO separados por vírgula (ex: "SBCA,SBGR")
    DATA_REFERENCIA       -> opcional, formato ddMMaaaa. Se ausente, usa a data de hoje.

Uso local (exemplo):
    SUPABASE_URL=https://SEU.supabase.co \
    SUPABASE_SERVICE_KEY=SUAKEY \
    AIRPORTS=SBCA \
    python scripts/fetch_flights.py
"""

import os
import sys
import json
from datetime import datetime, timezone

import requests

SIROS_BASE_URL = "https://sas.anac.gov.br/sas/siros_api/api/voos"


def log(msg: str) -> None:
    print(f"[fetch_flights] {msg}")


def obter_data_referencia() -> str:
    """Retorna a data de referência no formato ddMMaaaa exigido pela API do SIROS."""
    valor = os.environ.get("DATA_REFERENCIA")
    if valor:
        return valor
    hoje = datetime.now(timezone.utc)
    return hoje.strftime("%d%m%Y")


def buscar_voos_siros(data_referencia: str, tentativas: int = 3) -> list:
    """
    Consulta a API do SIROS/ANAC para a data de referência informada.
    Tenta novamente em caso de timeout, pois a API pública da ANAC costuma
    apresentar lentidão/instabilidade pontual.
    Retorna uma lista de dicionários (um por voo) ou lista vazia em caso de falha.
    """
    url = f"{SIROS_BASE_URL}?dataReferencia={data_referencia}"

    resposta = None
    for tentativa in range(1, tentativas + 1):
        log(f"Consultando SIROS (tentativa {tentativa}/{tentativas}): {url}")
        try:
            resposta = requests.get(url, timeout=60)
            resposta.raise_for_status()
            break
        except requests.RequestException as exc:
            log(f"ERRO ao consultar a API do SIROS (tentativa {tentativa}): {exc}")
            resposta = None

    if resposta is None:
        log("ERRO: todas as tentativas de conexão com a API do SIROS falharam.")
        return []

    conteudo = resposta.text

    try:
        dados = resposta.json()
    except ValueError:
        log("ERRO: resposta da API não é um JSON válido.")
        return []

    if isinstance(dados, str):
        try:
            dados = json.loads(dados)
        except ValueError:
            log("ERRO: não foi possível decodificar o JSON aninhado da API do SIROS.")
            return []

    if isinstance(dados, dict):
        for chave_possivel in ("value", "registros", "voos", "data"):
            if chave_possivel in dados and isinstance(dados[chave_possivel], list):
                return dados[chave_possivel]
        log("AVISO: resposta é um objeto único, tratando como um único registro.")
        return [dados]

    if isinstance(dados, list):
        return dados

    log("ERRO: formato de resposta inesperado da API do SIROS.")
    return []


def converter_data_hora(valor: str):
    """
    Converte datas no formato brasileiro "dd/mm/aaaa HH:MM" (como retornado
    pela API do SIROS) para o formato ISO 8601 exigido pelo Postgres/Supabase.
    """
    if not valor:
        return None
    try:
        dt = datetime.strptime(valor.strip(), "%d/%m/%Y %H:%M")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def normalizar_registro(registro: dict) -> dict:
    """
    Mapeia os campos reais retornados pela API do SIROS/ANAC (confirmados via
    execução de diagnóstico) para o esquema da nossa tabela `voos`.
    """
    return {
        "numero_voo": str(registro.get("nr_voo", "")).strip(),
        "companhia": registro.get("sg_empresa_icao"),
        "origem": registro.get("sg_icao_origem"),
        "destino": registro.get("sg_icao_destino"),
        "horario_previsto": converter_data_hora(registro.get("dt_partida_prevista_utc")),
        "horario_real": converter_data_hora(registro.get("dt_chegada_prevista_utc")),
        "situacao": registro.get("ds_tipo_servico", "programado"),
    }


def deduplicar(registros: list) -> list:
    """
    Remove registros duplicados com base na combinação (numero_voo, origem/destino,
    horario_previsto) — mesma chave usada como CONSTRAINT UNIQUE no banco.
    """
    vistos = set()
    unicos = []
    for r in registros:
        chave = (r.get("numero_voo"), r.get("icao_aeroporto"), r.get("horario_previsto"))
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(r)
    return unicos


def enviar_para_supabase(registros: list, supabase_url: str, service_key: str) -> int:
    """
    Envia os registros para a tabela `voos` no Supabase via REST API (upsert).
    Retorna a quantidade de registros efetivamente enviados.
    """
    if not registros:
        log("Nenhum registro para enviar ao Supabase.")
        return 0

    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/voos"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    resposta = requests.post(endpoint, headers=headers, json=registros, timeout=30)

    if resposta.status_code not in (200, 201, 204):
        log(f"ERRO ao inserir no Supabase: {resposta.status_code} - {resposta.text}")
        return 0

    return len(registros)


def main() -> int:
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    aeroportos_env = os.environ.get("AIRPORTS", "")

    if not supabase_url or not service_key:
        log("ERRO: SUPABASE_URL e SUPABASE_SERVICE_KEY são obrigatórios.")
        sys.exit(1)

    aeroportos = [a.strip().upper() for a in aeroportos_env.split(",") if a.strip()]
    if not aeroportos:
        log("ERRO: nenhuma variável AIRPORTS informada (ex: AIRPORTS=SBCA,SBGR).")
        sys.exit(1)

    data_referencia = obter_data_referencia()
    total_api = 0
    total_filtrados = 0
    total_enviados = 0

    for icao in aeroportos:
        brutos = buscar_voos_siros(data_referencia)
        total_api += len(brutos)

        normalizados = [normalizar_registro(r) for r in brutos]
        for r in normalizados:
            r["icao_aeroporto"] = icao

        filtrados = [
            r for r in normalizados
            if r.get("origem") == icao or r.get("destino") == icao
        ]
        total_filtrados += len(filtrados)

        unicos = deduplicar(filtrados)
        duplicados_removidos = len(filtrados) - len(unicos)

        enviados = enviar_para_supabase(unicos, supabase_url, service_key)
        total_enviados += enviados

        log(
            f"Aeroporto {icao}: {len(brutos)} recebidos da API, "
            f"{len(filtrados)} filtrados, {duplicados_removidos} duplicados removidos, "
            f"{enviados} enviados ao Supabase."
        )

    log(
        f"RESUMO FINAL -> total_api={total_api}, "
        f"total_filtrados={total_filtrados}, total_enviados={total_enviados}"
    )

    if total_api == 0:
        log("AVISO: nenhum dado retornado pela API do SIROS para a data informada.")

    return 0


if __name__ == "__main__":
    codigo_saida = main()
    sys.exit(codigo_saida)
