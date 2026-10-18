import time

from radar import coletor, fontes
from radar.db import conecta

from .conftest import bruta


def ids(resp):
    return [v["id"] for v in resp.get_json()["vagas"]]


def test_pagina_inicial(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"radar" in resp.data


def test_filtra_por_stack(client, com_vagas):
    com_vagas(
        bruta(id_externo="py", titulo="Python Developer", texto="Django"),
        bruta(id_externo="js", titulo="React Developer", texto="TypeScript"),
    )
    assert ids(client.get("/api/vagas?stacks=Python")) == ["Teste:py"]
    assert ids(client.get("/api/vagas?stacks=React,TypeScript")) == ["Teste:js"]
    assert ids(client.get("/api/vagas?stacks=React,Python")) == []


def test_filtra_por_salario(client, com_vagas):
    com_vagas(
        bruta(id_externo="alto", titulo="Python Dev A", salario=(120000, 150000, "USD", "ano")),
        bruta(id_externo="baixo", titulo="Python Dev B", salario=(30000, 40000, "USD", "ano")),
        bruta(id_externo="sem", titulo="Python Dev C"),
    )
    assert ids(client.get("/api/vagas?sal_min=100000")) == ["Teste:alto"]
    assert set(ids(client.get("/api/vagas?sal_min=100000&sem_salario=1"))) == {"Teste:alto", "Teste:sem"}
    assert ids(client.get("/api/vagas?ordem=salario"))[0] == "Teste:alto"


def test_filtra_por_fuso(client, com_vagas):
    com_vagas(
        bruta(id_externo="br", titulo="Python Dev BR", local="Brazil"),
        bruta(id_externo="eu", titulo="Python Dev EU", local="Germany"),
        bruta(id_externo="mundo", titulo="Python Dev Global", local="Worldwide"),
        bruta(id_externo="nada", titulo="Python Dev ?", local=""),
    )
    achadas = set(ids(client.get("/api/vagas?fuso=-3&tolerancia=2&sem_fuso=0")))
    assert achadas == {"Teste:br", "Teste:mundo"}
    achadas = set(ids(client.get("/api/vagas?fuso=-3&tolerancia=2&sem_fuso=1")))
    assert achadas == {"Teste:br", "Teste:mundo", "Teste:nada"}
    achadas = set(ids(client.get("/api/vagas?fuso=-3&tolerancia=5&sem_fuso=0")))
    assert "Teste:eu" in achadas


def test_fuso_informado_pela_api_vale_mais_que_o_local(client, com_vagas):
    com_vagas(bruta(id_externo="x", local="United States", fusos=("informado", [9.0])))
    assert ids(client.get("/api/vagas?fuso=-5&tolerancia=1&sem_fuso=0")) == []
    assert ids(client.get("/api/vagas?fuso=9&tolerancia=0&sem_fuso=0")) == ["Teste:x"]


def test_so_tecnologia(client, com_vagas):
    com_vagas(
        bruta(id_externo="dev", titulo="Backend Engineer"),
        bruta(id_externo="vendas", titulo="Account Executive"),
    )
    assert ids(client.get("/api/vagas")) == ["Teste:dev"]
    assert len(ids(client.get("/api/vagas?so_tech=0"))) == 2


def test_busca_por_texto_ignora_acento(client, com_vagas):
    com_vagas(bruta(id_externo="a", titulo="Desenvolvedor Python Sênior", empresa="Ação Ltda"))
    assert ids(client.get("/api/vagas?q=acao senior")) == ["Teste:a"]
    assert ids(client.get("/api/vagas?q=golang")) == []


def test_remove_vagas_repetidas_entre_fontes(client, com_vagas):
    com_vagas(
        bruta(fonte="A", id_externo="1", titulo="Python Dev", empresa="ACME"),
        bruta(fonte="B", id_externo="9", titulo="Python Dev!", empresa="Acme",
              salario=(100000, 120000, "USD", "ano")),
    )
    assert ids(client.get("/api/vagas")) == ["B:9"]  # fica a que tem salário


def test_facetas_e_paginacao(client, com_vagas):
    com_vagas(*[bruta(id_externo=str(i), titulo=f"Python Developer {i}") for i in range(35)])
    dados = client.get("/api/vagas").get_json()
    assert dados["total"] == 35 and len(dados["vagas"]) == 30 and dados["tem_mais"]
    assert ["Python", 35] in dados["facetas"]["stacks"]
    dados = client.get("/api/vagas?pagina=2").get_json()
    assert len(dados["vagas"]) == 5 and not dados["tem_mais"]


def test_salario_vem_convertido(client, com_vagas):
    com_vagas(bruta(salario=(5000, 6000, "EUR", "mes")))
    s = client.get("/api/vagas").get_json()["vagas"][0]["salario"]
    assert s["moeda"] == "EUR" and s["periodo"] == "mes"
    assert s["usd_min"] == 64800 and s["usd_max"] == 77760
    assert s["brl_mes_min"] > 25000


def test_faixa_absurda_fica_so_com_o_piso(client, com_vagas):
    com_vagas(bruta(salario=(190000, 1700000, "USD", "ano")))
    s = client.get("/api/vagas").get_json()["vagas"][0]["salario"]
    assert s["usd_max"] == 190000


def test_logo_so_https(client, com_vagas):
    com_vagas(bruta(logo="http://inseguro/logo.png"))
    assert client.get("/api/vagas").get_json()["vagas"][0]["logo"] == ""


def test_coleta_isola_fonte_com_erro(app, client, monkeypatch):
    def quebrada():
        raise TimeoutError("fora do ar")

    monkeypatch.setattr(fontes, "FONTES", {"Boa": lambda: [bruta(fonte="Boa")], "Ruim": quebrada})
    monkeypatch.setattr(coletor, "FONTES", fontes.FONTES)
    resultado = coletor.coleta()
    assert resultado["fontes"] == {"Boa": 1, "Ruim": None}
    assert ids(client.get("/api/vagas")) == ["Boa:1"]


def test_coleta_apaga_vagas_velhas(app, client, monkeypatch):
    velha = bruta(id_externo="velha", publicada_em=int(time.time()) - 90 * 86400)
    monkeypatch.setattr(coletor, "FONTES", {"Teste": lambda: [velha, bruta()]})
    coletor.coleta()
    with conecta() as conn:
        assert [r[0] for r in conn.execute("SELECT id FROM vagas")] == ["Teste:1"]


def test_atualizar_respeita_intervalo(client):
    with conecta() as conn:
        conn.execute("INSERT INTO coletas (fonte, em, ok, quantidade) VALUES ('X', ?, 1, 1)", (int(time.time()),))
    resp = client.post("/api/atualizar")
    assert resp.status_code == 429


def test_status(client):
    dados = client.get("/api/status").get_json()
    assert {f["nome"] for f in dados["fontes"]} == {"Remotive", "Remote OK", "Arbeitnow", "Jobicy", "Himalayas"}
    assert dados["total"] == 0 and dados["pode_atualizar"]
