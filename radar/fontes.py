"""Busca as vagas em cada API pública e deixa tudo no mesmo formato.

Todas as APIs pedem crédito e link para a vaga original. Por isso cada vaga
guarda a `fonte` e a `url` da própria fonte, e a tela sempre manda para lá.
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .config import USER_AGENT
from .normaliza import conserta_acentos, interpreta_salario, periodo_padrao, texto_limpo


def baixa_json(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _epoch(valor):
    """Aceita epoch (int) ou data ISO, com ou sem fuso. Sem fuso = UTC."""
    if valor is None or valor == "":
        return int(time.time())
    if isinstance(valor, (int, float)):
        return int(valor)
    d = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp())


def _vaga(**campos):
    """Formato comum que todas as fontes devolvem."""
    base = {
        "tags": [], "tipo": "", "logo": "", "local": "", "texto": "",
        "salario": None, "fusos": None, "senioridade": "",
    }
    base.update(campos)
    return base


# ---------------------------------------------------------------- Remotive


def remotive():
    dados = baixa_json("https://remotive.com/api/remote-jobs")
    vagas = []
    for j in dados.get("jobs", []):
        vagas.append(_vaga(
            fonte="Remotive",
            id_externo=str(j["id"]),
            titulo=j.get("title", ""),
            empresa=j.get("company_name", ""),
            logo=j.get("company_logo") or "",
            url=j["url"],
            local=j.get("candidate_required_location", ""),
            publicada_em=_epoch(j.get("publication_date")),
            texto=texto_limpo(j.get("description")),
            tags=list(j.get("tags") or []) + [j.get("category") or ""],
            tipo=(j.get("job_type") or "").replace("_", " "),
            salario=interpreta_salario(j.get("salary")),
        ))
    return vagas


# ---------------------------------------------------------------- Remote OK


def remote_ok():
    dados = baixa_json("https://remoteok.com/api")
    vagas = []
    for j in dados:
        if "id" not in j or "position" not in j:  # o 1º item é o aviso legal
            continue
        mn, mx = j.get("salary_min") or 0, j.get("salary_max") or 0
        vagas.append(_vaga(
            fonte="Remote OK",
            id_externo=str(j["id"]),
            titulo=conserta_acentos(j.get("position", "")),
            empresa=conserta_acentos(j.get("company", "")),
            logo=j.get("company_logo") or j.get("logo") or "",
            url=j.get("url") or f"https://remoteok.com/remote-jobs/{j['id']}",
            local=conserta_acentos(j.get("location", "")),
            publicada_em=_epoch(j.get("epoch") or j.get("date")),
            texto=texto_limpo(j.get("description")),
            tags=j.get("tags") or [],
            salario=(mn, mx, "USD", "ano") if (mn or mx) else None,
        ))
    return vagas


# ---------------------------------------------------------------- Arbeitnow


def arbeitnow(paginas=3):
    vagas = []
    for pagina in range(1, paginas + 1):
        dados = baixa_json("https://www.arbeitnow.com/api/job-board-api", {"page": pagina})
        for j in dados.get("data", []):
            if not j.get("remote"):  # o radar é só de vagas remotas
                continue
            vagas.append(_vaga(
                fonte="Arbeitnow",
                id_externo=j["slug"],
                titulo=j.get("title", ""),
                empresa=j.get("company_name", ""),
                url=j["url"],
                local=j.get("location", ""),
                publicada_em=_epoch(j.get("created_at")),
                texto=texto_limpo(j.get("description")),
                tags=j.get("tags") or [],
                tipo=", ".join(j.get("job_types") or []),
            ))
        if not dados.get("links", {}).get("next"):
            break
        time.sleep(1)
    return vagas


# ---------------------------------------------------------------- Jobicy


def jobicy():
    vagas, vistos = [], set()
    for filtro in ({}, {"industry": "engineering"}, {"industry": "data-science"}):
        dados = baixa_json("https://jobicy.com/api/v2/remote-jobs", {"count": 100, **filtro})
        for j in dados.get("jobs", []):
            if j["id"] in vistos:
                continue
            vistos.add(j["id"])
            mn, mx = j.get("salaryMin") or 0, j.get("salaryMax") or 0
            salario = None
            if mn or mx:
                salario = (mn, mx, j.get("salaryCurrency") or "USD", periodo_padrao(j.get("salaryPeriod")))
            vagas.append(_vaga(
                fonte="Jobicy",
                id_externo=str(j["id"]),
                titulo=html_txt(j.get("jobTitle")),
                empresa=html_txt(j.get("companyName")),
                logo=j.get("companyLogo") or "",
                url=j["url"],
                local=j.get("jobGeo", ""),
                publicada_em=_epoch(j.get("pubDate")),
                texto=texto_limpo(j.get("jobDescription") or j.get("jobExcerpt")),
                tags=j.get("jobIndustry") or [],
                tipo=", ".join(j.get("jobType") or []),
                salario=salario,
                senioridade=j.get("jobLevel") or "",
            ))
        time.sleep(1)
    return vagas


def html_txt(t):
    return texto_limpo(t) if t else ""


# ---------------------------------------------------------------- Himalayas

# O feed geral da Himalayas tem de tudo (enfermagem, vendas...). A busca por
# termo traz só o que interessa.
BUSCAS_HIMALAYAS = [
    "developer", "software engineer", "frontend", "backend", "full stack",
    "python", "data engineer", "devops", "mobile", "machine learning",
]


def himalayas(paginas=2):
    vagas, vistos = [], set()
    for termo in BUSCAS_HIMALAYAS:
        for pagina in range(1, paginas + 1):
            dados = baixa_json("https://himalayas.app/jobs/api/search", {"q": termo, "limit": 20, "page": pagina})
            for j in dados.get("jobs", []):
                guid = j.get("guid") or j.get("applicationLink")
                if not guid or guid in vistos:
                    continue
                vistos.add(guid)
                # UTC+14 é o mesmo horário de relógio que UTC-10 (só que no dia seguinte);
                # a Himalayas manda +14 junto com os fusos dos EUA.
                fusos_api = [float(f) - 24 if f > 13 else float(f) for f in j.get("timezoneRestrictions") or []]
                locais = j.get("locationRestrictions") or []
                if fusos_api:
                    fusos = ("informado", sorted(set(fusos_api)))
                elif not locais:
                    fusos = ("global", [])
                else:
                    fusos = None  # deixa o radar estimar pelos países
                mn, mx = j.get("minSalary") or 0, j.get("maxSalary") or 0
                salario = None
                if mn or mx:
                    salario = (mn, mx, j.get("currency") or "USD", periodo_padrao(j.get("salaryPeriod")))
                vagas.append(_vaga(
                    fonte="Himalayas",
                    id_externo=guid.rstrip("/").rsplit("/", 1)[-1],
                    titulo=j.get("title", ""),
                    empresa=j.get("companyName", ""),
                    logo=j.get("companyLogo") or "",
                    url=j.get("applicationLink") or guid,
                    local=", ".join(locais) or "Worldwide",
                    publicada_em=_epoch(j.get("pubDate")),
                    texto=texto_limpo(j.get("description") or j.get("excerpt")),
                    tags=(j.get("categories") or [])[:8],
                    tipo=j.get("employmentType") or "",
                    salario=salario,
                    fusos=fusos,
                    senioridade=" ".join(j.get("seniority") or []),
                ))
            if len(dados.get("jobs", [])) < 20:
                break
            time.sleep(0.5)
    return vagas


FONTES = {
    "Remotive": remotive,
    "Remote OK": remote_ok,
    "Arbeitnow": arbeitnow,
    "Jobicy": jobicy,
    "Himalayas": himalayas,
}

SITES = {
    "Remotive": "https://remotive.com",
    "Remote OK": "https://remoteok.com",
    "Arbeitnow": "https://www.arbeitnow.com",
    "Jobicy": "https://jobicy.com",
    "Himalayas": "https://himalayas.app",
}
