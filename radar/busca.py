"""Filtros da tela. São poucas vagas (alguns milhares no máximo), então dá pra
carregar tudo em memória e filtrar em Python, sem SQL complicado."""
import json
import re
import time
import unicodedata
from collections import Counter

from . import coletor
from .config import USD_PARA_BRL
from .db import conecta
from .normaliza import fuso_compativel

_cache = {"versao": None, "vagas": []}
SEM_NIVEL = "Não informada"


def _sem_acento(t):
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def _linha_para_vaga(r):
    v = dict(r)
    v["stacks"] = json.loads(v["stacks"])
    v["tags"] = json.loads(v["tags"])
    v["fusos"] = json.loads(v["fusos"])
    v["_busca"] = _sem_acento(" ".join([v["titulo"], v["empresa"], " ".join(v["stacks"]), " ".join(v["tags"])]))
    return v


def _qualidade(v):
    """Quando a mesma vaga aparece em duas fontes, fica a mais completa."""
    return (v["sal_max_usd"] is not None) * 2 + (v["fuso_tipo"] != "desconhecido"), v["publicada_em"]


def _sem_repetidas(vagas):
    melhores = {}
    for v in vagas:
        chave = re.sub(r"\W+", "", _sem_acento(v["titulo"])) + "|" + re.sub(r"\W+", "", _sem_acento(v["empresa"]))
        if chave not in melhores or _qualidade(v) > _qualidade(melhores[chave]):
            melhores[chave] = v
    return list(melhores.values())


def todas():
    if _cache["versao"] != coletor.versao["n"]:
        with conecta() as conn:
            linhas = conn.execute("SELECT * FROM vagas").fetchall()
        _cache["vagas"] = _sem_repetidas([_linha_para_vaga(r) for r in linhas])
        _cache["versao"] = coletor.versao["n"]
    return _cache["vagas"]


# ---------------------------------------------------------------- parâmetros


def _lista(valor):
    return [x.strip() for x in (valor or "").split(",") if x.strip()]


def _numero(valor, padrao=None):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def _sim(valor):
    return str(valor).lower() in ("1", "true", "sim", "on")


def le_filtros(args):
    return {
        "q": _sem_acento(args.get("q", "")).strip(),
        "stacks": _lista(args.get("stacks")),
        "fontes": _lista(args.get("fontes")),
        "senioridade": _lista(args.get("senioridade")),
        "sal_min": _numero(args.get("sal_min"), 0) or 0,
        "sem_salario": _sim(args.get("sem_salario", "0")),
        "fuso": _numero(args.get("fuso")),
        "tolerancia": max(0, min(12, _numero(args.get("tolerancia"), 3))),
        "sem_fuso": _sim(args.get("sem_fuso", "1")),
        "so_tech": _sim(args.get("so_tech", "1")),
        "dias": _numero(args.get("dias"), 0) or 0,
        "ordem": args.get("ordem", "recentes"),
        "ids": set(_lista(args.get("ids"))),
    }


# ---------------------------------------------------------------- filtro


def passa(v, f, agora):
    if f["ids"] and v["id"] not in f["ids"]:
        return False
    if f["so_tech"] and not v["tecnologia"]:
        return False
    if f["q"] and not all(p in v["_busca"] for p in f["q"].split()):
        return False
    if f["stacks"] and not all(s in v["stacks"] for s in f["stacks"]):
        return False
    if f["fontes"] and v["fonte"] not in f["fontes"]:
        return False
    if f["senioridade"] and (v["senioridade"] or SEM_NIVEL) not in f["senioridade"]:
        return False
    if f["dias"] and v["publicada_em"] < agora - f["dias"] * 86400:
        return False
    if f["sal_min"]:
        if v["sal_max_usd"] is None:
            if not f["sem_salario"]:
                return False
        elif v["sal_max_usd"] < f["sal_min"]:
            return False
    if f["fuso"] is not None:
        if v["fuso_tipo"] == "desconhecido":
            if not f["sem_fuso"]:
                return False
        elif not fuso_compativel(v["fuso_tipo"], v["fusos"], f["fuso"], f["tolerancia"]):
            return False
    return True


def _ordena(vagas, ordem):
    if ordem == "salario":
        return sorted(vagas, key=lambda v: (v["sal_max_usd"] or -1, v["publicada_em"]), reverse=True)
    return sorted(vagas, key=lambda v: v["publicada_em"], reverse=True)


def para_json(v, agora):
    salario = None
    if v["sal_min"] or v["sal_max"]:
        salario = {
            "min": v["sal_min"], "max": v["sal_max"], "moeda": v["moeda"], "periodo": v["periodo"],
            "usd_min": v["sal_min_usd"], "usd_max": v["sal_max_usd"],
            # "≈ R$ x/mês" pra quem pensa em reais
            "brl_mes_min": round(v["sal_min_usd"] * USD_PARA_BRL / 12) if v["sal_min_usd"] else None,
            "brl_mes_max": round(v["sal_max_usd"] * USD_PARA_BRL / 12) if v["sal_max_usd"] else None,
        }
    return {
        "id": v["id"], "fonte": v["fonte"], "titulo": v["titulo"], "empresa": v["empresa"],
        "logo": v["logo"], "url": v["url"], "local": v["local"], "publicada_em": v["publicada_em"],
        "nova": v["publicada_em"] > agora - 2 * 86400,
        "resumo": v["resumo"], "stacks": v["stacks"], "senioridade": v["senioridade"],
        "tipo": v["tipo"], "salario": salario,
        "fuso": {"tipo": v["fuso_tipo"], "fusos": v["fusos"]},
    }


def busca(args, pagina=1, por_pagina=30):
    f = le_filtros(args)
    agora = int(time.time())
    achadas = _ordena([v for v in todas() if passa(v, f, agora)], f["ordem"])
    inicio = (pagina - 1) * por_pagina
    contagem_stacks = Counter(s for v in achadas for s in v["stacks"])
    return {
        "total": len(achadas),
        "pagina": pagina,
        "tem_mais": inicio + por_pagina < len(achadas),
        "vagas": [para_json(v, agora) for v in achadas[inicio:inicio + por_pagina]],
        "facetas": {
            "stacks": contagem_stacks.most_common(40),
            "fontes": Counter(v["fonte"] for v in achadas).most_common(),
            "senioridade": Counter(v["senioridade"] or SEM_NIVEL for v in achadas).most_common(),
            "com_salario": sum(1 for v in achadas if v["sal_max_usd"] is not None),
        },
    }
