"""A parte "inteligente" do radar.

Cada API devolve a vaga de um jeito. Aqui ficam as funções que olham para o
texto da vaga e tiram dele o que importa para filtrar: stack, salário em uma
moeda só, fuso horário e senioridade.
"""
import html
import re

from .config import COTACAO_USD

# ---------------------------------------------------------------- texto


def texto_limpo(conteudo):
    """Tira o HTML da descrição e devolve só o texto."""
    if not conteudo:
        return ""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", conteudo, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", conserta_acentos(t)).strip()


def conserta_acentos(t):
    """Algumas APIs mandam UTF-8 lido como Latin-1 ("worldâ\x80\x99s"). Desfaz isso."""
    if t and ("Ã" in t or "â\x80" in t):
        try:
            return t.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return t


def resumo(texto, limite=280):
    if len(texto) <= limite:
        return texto
    corte = texto.rfind(" ", 0, limite)
    return texto[: corte if corte > 0 else limite].rstrip(" ,.;:") + "…"


# ---------------------------------------------------------------- stack

# (nome, regex, onde procurar). "titulo" = só no título e nas tags, para
# palavras que confundem no meio de um texto corrido ("Go", "Unity"...).
_STACKS = [
    ("Python", r"\bpython\b", "tudo"),
    ("JavaScript", r"\bjavascript\b|\bjs\b|\becmascript\b", "tudo"),
    ("TypeScript", r"\btypescript\b", "tudo"),
    ("React", r"\breact(?:\.?js)?\b(?!\s*native)", "tudo"),
    ("React Native", r"\breact\s*native\b", "tudo"),
    ("Next.js", r"\bnext\.?js\b", "tudo"),
    ("Vue", r"\bvue(?:\.?js)?\b|\bnuxt\b", "tudo"),
    ("Angular", r"\bangular(?:js)?\b", "tudo"),
    ("Svelte", r"\bsvelte(?:kit)?\b", "tudo"),
    ("Node.js", r"\bnode(?:\.?js)?\b|\bnestjs\b|\bexpress\.?js\b", "tudo"),
    ("Java", r"\bjava\b(?!\s*script)", "tudo"),
    ("Kotlin", r"\bkotlin\b", "tudo"),
    ("Spring", r"\bspring\s*boot\b|\bspring\s+(?:framework|mvc|cloud)\b", "tudo"),
    ("Swift", r"\bswift(?:ui)?\b", "tudo"),
    ("Go", r"\bgolang\b", "tudo"),
    ("Go", r"\bgo\b(?![-'’])", "titulo"),
    ("Rust", r"\brust\b", "tudo"),
    ("C#", r"(?<![\w])c#|\bc\s?sharp\b", "tudo"),
    (".NET", r"(?<![\w.])\.net\b|\bdotnet\b|\basp\.net\b", "tudo"),
    ("C++", r"(?<![\w])c\+\+", "tudo"),
    ("PHP", r"\bphp\b", "tudo"),
    ("Laravel", r"\blaravel\b", "tudo"),
    ("Ruby", r"\bruby\b", "tudo"),
    ("Rails", r"\brails\b", "tudo"),
    ("Django", r"\bdjango\b", "tudo"),
    ("Flask", r"\bflask\b", "tudo"),
    ("FastAPI", r"\bfastapi\b", "tudo"),
    ("Elixir", r"\belixir\b|\bphoenix\s+framework\b", "tudo"),
    ("Scala", r"\bscala\b", "tudo"),
    ("Flutter", r"\bflutter\b", "tudo"),
    ("Android", r"\bandroid\b", "tudo"),
    ("iOS", r"\bios\b", "tudo"),
    ("SQL", r"\bsql\b", "tudo"),
    ("PostgreSQL", r"\bpostgres(?:ql)?\b", "tudo"),
    ("MySQL", r"\bmysql\b", "tudo"),
    ("MongoDB", r"\bmongo(?:db)?\b", "tudo"),
    ("Redis", r"\bredis\b", "tudo"),
    ("GraphQL", r"\bgraphql\b", "tudo"),
    ("AWS", r"\baws\b|\bamazon web services\b", "tudo"),
    ("GCP", r"\bgcp\b|\bgoogle cloud\b", "tudo"),
    ("Azure", r"\bazure\b", "tudo"),
    ("Docker", r"\bdocker\b", "tudo"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b", "tudo"),
    ("Terraform", r"\bterraform\b", "tudo"),
    ("Linux", r"\blinux\b", "tudo"),
    ("Kafka", r"\bkafka\b", "tudo"),
    ("Spark", r"\b(?:py)?spark\b", "tudo"),
    ("Airflow", r"\bairflow\b", "tudo"),
    ("dbt", r"\bdbt\b", "tudo"),
    ("Snowflake", r"\bsnowflake\b", "tudo"),
    ("Pandas", r"\bpandas\b", "tudo"),
    ("Machine Learning", r"\bmachine learning\b|\bml\b|\bpytorch\b|\btensorflow\b|\bscikit", "tudo"),
    ("IA / LLM", r"\bllms?\b|\bgenai\b|\bgenerative ai\b|\blangchain\b|\bopenai\b|\brag\b|\bai agents?\b", "tudo"),
    ("Power BI", r"\bpower\s?bi\b", "tudo"),
    ("Figma", r"\bfigma\b", "tudo"),
    ("Salesforce", r"\bsalesforce\b|\bapex\b", "titulo"),
    ("WordPress", r"\bwordpress\b", "tudo"),
    ("Shopify", r"\bshopify\b", "titulo"),
    ("Unity", r"\bunity\b", "titulo"),
    ("QA / Testes", r"\bcypress\b|\bplaywright\b|\bselenium\b|\bqa\b|\btest automation\b", "tudo"),
    ("Web3", r"\bsolidity\b|\bweb3\b|\bblockchain\b|\bsmart contracts?\b", "tudo"),
]
STACKS = [(nome, re.compile(rx, re.I), onde) for nome, rx, onde in _STACKS]


def detecta_stacks(titulo, tags, texto):
    """Devolve as tecnologias citadas na vaga, na ordem da lista acima."""
    curto = " ".join([titulo or "", " ".join(tags or [])])
    longo = curto + " " + re.sub(r"https?://\S+", " ", texto or "")
    no_titulo, no_texto = [], []
    for nome, rx, onde in STACKS:
        if nome in no_titulo or nome in no_texto:
            continue
        if rx.search(curto):
            no_titulo.append(nome)
        elif onde == "tudo" and rx.search(longo):
            no_texto.append(nome)
    # o que está no título/tags é o principal da vaga, então vem primeiro
    return no_titulo + no_texto


# ---------------------------------------------------------------- área e senioridade

_TECH = re.compile(
    r"engineer|engenheir|developer|\bdevs?\b|desenvolvedor|programador|programmer|devops|\bsre\b|"
    r"software|architect|arquitet|data (?:scien|engineer|analy)|analytics engineer|"
    r"machine learning|\bml\b|\bai\b|\bqa\b|tester|test automation|front[- ]?end|"
    r"back[- ]?end|full[- ]?stack|mobile|android|\bios\b|\bweb\b|cloud|platform|infra|"
    r"security|cyber|sysadmin|\bdba\b|database|tech lead|\bcto\b|blockchain|game dev",
    re.I,
)


def eh_tecnologia(titulo):
    return bool(_TECH.search(titulo or ""))


_NIVEIS = [
    ("Estágio", r"\bintern(ship)?\b|est[aá]gi|\btrainee\b"),
    ("Júnior", r"\bjunior\b|\bjr\b\.?|j[uú]nior|entry[- ]?level|\bgraduate\b"),
    ("Lead/Staff", r"\blead\b|\bstaff\b|\bprincipal\b|\bhead of\b|\bdirector\b|\bvp\b|\bmanager\b"),
    ("Sênior", r"\bsenior\b|\bsr\b\.?|s[eê]nior"),
    ("Pleno", r"\bmid(?:[- ]?level|weight)?\b|\bpleno\b|\bintermediate\b"),
]
NIVEIS = [(nome, re.compile(rx, re.I)) for nome, rx in _NIVEIS]


def detecta_senioridade(titulo, informada=""):
    """Olha primeiro o título; se não disser nada, usa o que a API informou."""
    for texto in (titulo, informada):
        for nome, rx in NIVEIS:
            if texto and rx.search(texto):
                return nome
    return None


# ---------------------------------------------------------------- salário

HORAS_ANO = {"hora": 2080, "dia": 260, "semana": 52, "mes": 12, "ano": 1}

_PERIODOS = {
    "hourly": "hora", "hour": "hora", "daily": "dia", "day": "dia",
    "weekly": "semana", "week": "semana", "monthly": "mes", "month": "mes",
    "yearly": "ano", "year": "ano", "annual": "ano", "annually": "ano",
}


def periodo_padrao(periodo):
    return _PERIODOS.get((periodo or "").strip().lower(), "ano")


_MOEDAS = [
    (r"R\$|\bBRL\b|reais", "BRL"),
    (r"C\$|CA\$|\bCAD\b", "CAD"),
    (r"A\$|AU\$|\bAUD\b", "AUD"),
    (r"€|\bEUR\b|euros?", "EUR"),
    (r"£|\bGBP\b", "GBP"),
    (r"₹|\bINR\b", "INR"),
    (r"zł|\bPLN\b", "PLN"),
]


def _moeda(texto):
    for rx, moeda in _MOEDAS:
        if re.search(rx, texto, re.I):
            return moeda
    for codigo in re.findall(r"\b[A-Z]{3}\b", texto):
        if codigo in COTACAO_USD:
            return codigo
    return "USD"


def _periodo_texto(texto):
    t = texto.lower()
    if re.search(r"/\s*h(?:ou)?r\b|/\s*h\b|per hour|hourly|an hour|/hora|por hora", t):
        return "hora"
    if re.search(r"/\s*day\b|per day|daily|/dia", t):
        return "dia"
    if re.search(r"/\s*week|per week|weekly", t):
        return "semana"
    if re.search(r"/\s*mo\b|month|monthly|/m[eê]s|mensal", t):
        return "mes"
    if re.search(r"year|annual|/\s*yr\b|/ano|anual|\bpa\b", t):
        return "ano"
    return None


def _numero(bruto):
    s = bruto.strip(".,")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):  # 120,000 / 120.000
        return float(re.sub(r"[.,]", "", s))
    if re.fullmatch(r"\d+[.,]\d{1,2}", s):  # 35,3 / 52.5
        return float(s.replace(",", "."))
    return float(re.sub(r"\D", "", s) or 0)


def interpreta_salario(texto):
    """Lê salários escritos à mão ("$90k - $105k", "€50,000/year", "$40-60 /hour").

    Devolve (minimo, maximo, moeda, periodo) ou None se não der pra entender.
    """
    if not texto or not re.search(r"\d", texto):
        return None
    achados = re.findall(r"(\d[\d.,]*)\s*([kK])?(?![\w])", texto.replace(" ", " "))
    valores = []
    for numero, k in achados:
        v = _numero(numero)
        if v > 0:
            valores.append([v, bool(k)])
    if not valores:
        return None
    # "$90 - $150k": o "k" do último vale para os dois
    if any(k for _, k in valores):
        for par in valores:
            if not par[1] and par[0] < 1000:
                par[1] = True
    nums = [v * 1000 if k else v for v, k in valores][:2]
    minimo, maximo = min(nums), max(nums)
    periodo = _periodo_texto(texto)
    if periodo is None:
        periodo = "hora" if maximo < 300 else "ano"
    return minimo, maximo, _moeda(texto), periodo


def salario_usd_anual(minimo, maximo, moeda, periodo):
    """Converte para dólares por ano. Devolve (None, None) se ficar absurdo."""
    if not (minimo or maximo):
        return None, None
    taxa = COTACAO_USD.get((moeda or "USD").upper())
    if taxa is None:
        return None, None
    fator = taxa * HORAS_ANO.get(periodo, 1)
    minimo = minimo or maximo
    maximo = maximo or minimo
    a, b = round(minimo * fator), round(maximo * fator)
    if b < 1000 or a > 2_000_000:
        return None, None
    return min(a, b), max(a, b)


# ---------------------------------------------------------------- fuso horário


def _faixa(a, b):
    return [float(x) for x in range(a, b + 1)]


# Fusos de cada região/país (UTC, horário padrão e de verão).
_REGIOES = {
    "north america": _faixa(-10, -4), "northern america": _faixa(-10, -4),
    "usa": _faixa(-10, -4), "us": _faixa(-10, -4), "u.s.": _faixa(-10, -4),
    "united states": _faixa(-10, -4), "united states of america": _faixa(-10, -4),
    "canada": _faixa(-8, -4) + [-3.5],
    "mexico": _faixa(-8, -5), "central america": [-6.0],
    "latam": _faixa(-6, -3), "latin america": _faixa(-6, -3),
    "south america": _faixa(-5, -3), "americas": _faixa(-10, -3),
    "brazil": _faixa(-5, -2), "brasil": _faixa(-5, -2),
    "argentina": [-3.0], "uruguay": [-3.0], "chile": [-4.0, -3.0], "paraguay": [-4.0, -3.0],
    "bolivia": [-4.0], "venezuela": [-4.0], "colombia": [-5.0], "peru": [-5.0], "ecuador": [-5.0],
    "costa rica": [-6.0], "guatemala": [-6.0], "panama": [-5.0],
    "europe": _faixa(0, 3), "eu": _faixa(0, 3), "emea": _faixa(0, 4),
    "uk": [0.0, 1.0], "united kingdom": [0.0, 1.0], "england": [0.0, 1.0],
    "ireland": [0.0, 1.0], "portugal": [0.0, 1.0],
    "spain": [1.0, 2.0], "france": [1.0, 2.0], "germany": [1.0, 2.0], "italy": [1.0, 2.0],
    "netherlands": [1.0, 2.0], "belgium": [1.0, 2.0], "austria": [1.0, 2.0],
    "switzerland": [1.0, 2.0], "poland": [1.0, 2.0], "czechia": [1.0, 2.0],
    "czech republic": [1.0, 2.0], "hungary": [1.0, 2.0], "croatia": [1.0, 2.0],
    "serbia": [1.0, 2.0], "sweden": [1.0, 2.0], "norway": [1.0, 2.0], "denmark": [1.0, 2.0],
    "nigeria": [1.0],
    "romania": [2.0, 3.0], "bulgaria": [2.0, 3.0], "greece": [2.0, 3.0], "finland": [2.0, 3.0],
    "ukraine": [2.0, 3.0], "estonia": [2.0, 3.0], "latvia": [2.0, 3.0], "lithuania": [2.0, 3.0],
    "cyprus": [2.0, 3.0], "israel": [2.0, 3.0], "egypt": [2.0, 3.0], "south africa": [2.0],
    "turkey": [3.0], "türkiye": [3.0], "kenya": [3.0], "saudi arabia": [3.0],
    "uae": [4.0], "united arab emirates": [4.0], "dubai": [4.0],
    "pakistan": [5.0], "india": [5.5], "sri lanka": [5.5],
    "vietnam": [7.0], "thailand": [7.0], "indonesia": _faixa(7, 9),
    "philippines": [8.0], "singapore": [8.0], "malaysia": [8.0], "china": [8.0],
    "hong kong": [8.0], "taiwan": [8.0], "japan": [9.0], "south korea": [9.0], "korea": [9.0],
    "australia": _faixa(8, 11), "new zealand": [12.0, 13.0],
    "asia": [5.5] + _faixa(7, 9), "apac": [5.5] + _faixa(7, 12), "asia pacific": [5.5] + _faixa(7, 12),
    "africa": _faixa(0, 3),
    # cidades que aparecem muito (a Arbeitnow é bem focada na Alemanha)
    "london": [0.0, 1.0], "lisbon": [0.0, 1.0], "dublin": [0.0, 1.0],
    "berlin": [1.0, 2.0], "munich": [1.0, 2.0], "münchen": [1.0, 2.0], "hamburg": [1.0, 2.0],
    "frankfurt": [1.0, 2.0], "cologne": [1.0, 2.0], "köln": [1.0, 2.0], "stuttgart": [1.0, 2.0],
    "düsseldorf": [1.0, 2.0], "vienna": [1.0, 2.0], "wien": [1.0, 2.0], "zurich": [1.0, 2.0],
    "zürich": [1.0, 2.0], "amsterdam": [1.0, 2.0], "paris": [1.0, 2.0], "madrid": [1.0, 2.0],
    "barcelona": [1.0, 2.0], "warsaw": [1.0, 2.0], "prague": [1.0, 2.0],
    "são paulo": [-3.0], "sao paulo": [-3.0], "buenos aires": [-3.0],
    "new york": [-5.0, -4.0], "san francisco": [-8.0, -7.0], "toronto": [-5.0, -4.0],
    # siglas de fuso
    "est": [-5.0, -4.0], "edt": [-4.0], "eastern time": [-5.0, -4.0],
    "cst": [-6.0, -5.0], "central time": [-6.0, -5.0], "mst": [-7.0, -6.0],
    "pst": [-8.0, -7.0], "pacific time": [-8.0, -7.0],
    "cet": [1.0, 2.0], "cest": [2.0], "bst": [1.0], "brt": [-3.0], "ist": [5.5], "aest": [10.0, 11.0],
}
_CHAVES = sorted(_REGIOES, key=len, reverse=True)
_GLOBAL = re.compile(r"\b(?:worldwide|anywhere|global(?:ly)?|world ?wide|international|all countries)\b", re.I)
_UTC = re.compile(r"\b(?:utc|gmt)\s*([+\-−–]\s*\d{1,2}(?:[:.]30)?)?", re.I)


def _offset(bruto):
    s = bruto.replace(" ", "").replace("−", "-").replace("–", "-")
    sinal = -1 if s.startswith("-") else 1
    s = s.lstrip("+-")
    if ":" in s or "." in s:
        h, m = re.split(r"[:.]", s)
        return sinal * (int(h) + int(m) / 60)
    return float(sinal * int(s))


def infere_fusos(local):
    """Estima os fusos aceitos a partir do texto de localização da vaga.

    Devolve ("global", []), ("estimado", [fusos]) ou ("desconhecido", []).
    """
    if not local:
        return "desconhecido", []
    texto = conserta_acentos(local).lower()
    if _GLOBAL.search(texto):
        return "global", []
    fusos = set()
    explicitos = [_offset(m.group(1)) if m.group(1) else 0.0 for m in _UTC.finditer(texto)]
    if len(explicitos) >= 2:  # "UTC-3 to UTC+2": tudo que está no meio vale
        fusos.update(_faixa(int(min(explicitos)), int(max(explicitos))))
    fusos.update(explicitos)
    ocupado = []
    for chave in _CHAVES:
        for m in re.finditer(r"(?<![a-zà-ü])" + re.escape(chave) + r"(?![a-zà-ü])", texto):
            if any(m.start() < f and m.end() > i for i, f in ocupado):
                continue
            ocupado.append(m.span())
            fusos.update(_REGIOES[chave])
    if not fusos:
        return "desconhecido", []
    return "estimado", sorted(fusos)


def fuso_compativel(tipo, fusos, meu_fuso, tolerancia):
    """A vaga aceita alguém em `meu_fuso`, com até `tolerancia` horas de diferença?"""
    if tipo == "global":
        return True
    return any(abs(f - meu_fuso) <= tolerancia for f in fusos)
