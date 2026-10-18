import pytest

from radar.normaliza import (
    conserta_acentos, detecta_senioridade, detecta_stacks, eh_tecnologia, fuso_compativel,
    infere_fusos, interpreta_salario, resumo, salario_usd_anual, texto_limpo,
)


# ---------------------------------------------------------------- salário

@pytest.mark.parametrize("texto, esperado", [
    ("$90k - $105k", (90000, 105000, "USD", "ano")),
    ("$10K-$20K", (10000, 20000, "USD", "ano")),
    ("OTE $25k - $35k", (25000, 35000, "USD", "ano")),
    ("$35,3k- $52k", (35300, 52000, "USD", "ano")),
    ("$90 - $150k", (90000, 150000, "USD", "ano")),
    ("$90 - $150 /hour", (90, 150, "USD", "hora")),
    ("$50-$75", (50, 75, "USD", "hora")),  # sem período e valor baixo: é por hora
    ("€50,000 - 60,000/year", (50000, 60000, "EUR", "ano")),
    ("£4.500 per month", (4500, 4500, "GBP", "mes")),
    ("R$ 8.000 a R$ 12.000 mensal", (8000, 12000, "BRL", "mes")),
    ("CAD 120,000", (120000, 120000, "CAD", "ano")),
])
def test_interpreta_salario(texto, esperado):
    assert interpreta_salario(texto) == esperado


@pytest.mark.parametrize("texto", ["", None, "competitive", "DOE"])
def test_salario_sem_numero(texto):
    assert interpreta_salario(texto) is None


def test_salario_em_dolar_por_ano():
    assert salario_usd_anual(100000, 120000, "USD", "ano") == (100000, 120000)
    assert salario_usd_anual(50, 50, "USD", "hora") == (104000, 104000)
    assert salario_usd_anual(10000, 10000, "BRL", "mes") == (21600, 21600)


def test_salario_com_moeda_desconhecida_ou_absurdo():
    assert salario_usd_anual(1000, 2000, "XYZ", "ano") == (None, None)
    assert salario_usd_anual(5, 8, "USD", "ano") == (None, None)


# ---------------------------------------------------------------- fuso

def test_fuso_global():
    assert infere_fusos("Worldwide") == ("global", [])
    assert infere_fusos("Anywhere in the world") == ("global", [])


def test_fuso_desconhecido():
    assert infere_fusos("") == ("desconhecido", [])
    assert infere_fusos("Remote") == ("desconhecido", [])


def test_fuso_por_pais_e_regiao():
    tipo, fusos = infere_fusos("Brazil")
    assert tipo == "estimado" and -3.0 in fusos
    _, fusos = infere_fusos("USA, Canada")
    assert -5.0 in fusos and -3.5 in fusos and 1.0 not in fusos
    _, fusos = infere_fusos("Northern America, LATAM, Europe")
    assert -3.0 in fusos and 1.0 in fusos


def test_fuso_explicito_utc():
    _, fusos = infere_fusos("UTC-3 to UTC+2")
    assert fusos == [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0]
    _, fusos = infere_fusos("GMT+5:30")
    assert fusos == [5.5]


def test_fuso_nao_confunde_palavras():
    # "us" dentro de "Russia" ou "Australia" não pode virar Estados Unidos
    _, fusos = infere_fusos("Australia")
    assert -5.0 not in fusos


def test_fuso_compativel():
    assert fuso_compativel("global", [], -3, 0)
    assert fuso_compativel("estimado", [-5.0, -4.0], -3, 1)
    assert not fuso_compativel("estimado", [1.0, 2.0], -3, 3)


# ---------------------------------------------------------------- stack, área e nível

def test_detecta_stacks_basico():
    s = detecta_stacks("Senior Python Developer", ["django"], "We use PostgreSQL, AWS and React.")
    assert s[:2] == ["Python", "Django"]  # o que está no título/tags vem primeiro
    assert {"PostgreSQL", "AWS", "React"} <= set(s)


def test_stacks_que_confundem():
    assert "Java" not in detecta_stacks("JavaScript Engineer", [], "")
    assert "React" not in detecta_stacks("React Native Developer", [], "")
    assert "React Native" in detecta_stacks("React Native Developer", [], "")
    # "Go" só vale no título; no texto corrido é verbo
    assert "Go" not in detecta_stacks("Backend Engineer", [], "Let's go build things")
    assert "Go" in detecta_stacks("Senior Go Engineer", [], "")
    assert "Go" in detecta_stacks("Backend Engineer", [], "We write Golang")
    assert "C#" in detecta_stacks(".NET Developer", [], "C# and ASP.NET")
    assert ".NET" in detecta_stacks(".NET Developer", [], "")


def test_url_no_texto_nao_conta_como_stack():
    assert "Node.js" not in detecta_stacks("Dev", [], "veja https://empresa.com/node/123")


def test_eh_tecnologia():
    assert eh_tecnologia("Senior Backend Engineer")
    assert eh_tecnologia("Desenvolvedor Full Stack")
    assert eh_tecnologia("Sr. Python Dev")
    assert not eh_tecnologia("Account Executive")
    assert not eh_tecnologia("Psychiatric Nurse Practitioner")


@pytest.mark.parametrize("titulo, informada, esperado", [
    ("Senior Software Engineer", "", "Sênior"),
    ("Sr. Python Dev", "", "Sênior"),
    ("Staff Engineer", "", "Lead/Staff"),
    ("Senior Staff Engineer", "", "Lead/Staff"),
    ("Junior Frontend", "", "Júnior"),
    ("Back-end Developer intern - Python", "", "Estágio"),
    ("Desenvolvedor Pleno", "", "Pleno"),
    ("Backend Developer", "Mid-level", "Pleno"),
    ("Backend Developer", "Midweight", "Pleno"),
    ("Backend Developer", "", None),
])
def test_senioridade(titulo, informada, esperado):
    assert detecta_senioridade(titulo, informada) == esperado


# ---------------------------------------------------------------- texto

def test_texto_limpo_tira_html_e_script():
    html = "<p>Olá &amp; bem-vindo</p><script>alert(1)</script><ul><li>Python</li></ul>"
    assert texto_limpo(html) == "Olá & bem-vindo Python"


def test_conserta_acentos():
    assert conserta_acentos("worldâ\x80\x99s") == "world’s"
    assert conserta_acentos("já está certo") == "já está certo"


def test_resumo_corta_na_palavra():
    r = resumo("palavra " * 100, 30)
    assert r.endswith("…") and len(r) <= 31 and "palavr…" not in r
