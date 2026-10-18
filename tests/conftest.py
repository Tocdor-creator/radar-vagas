import time

import pytest

from radar import coletor, config, create_app
from radar.db import conecta


def bruta(**campos):
    """Vaga no formato que as fontes devolvem, com valores padrão."""
    base = {
        "fonte": "Teste", "id_externo": "1", "titulo": "Python Developer", "empresa": "ACME",
        "logo": "", "url": "https://exemplo.com/vaga/1", "local": "Worldwide",
        "publicada_em": int(time.time()) - 3600, "texto": "Python and AWS", "tags": [],
        "tipo": "Full-Time", "salario": None, "fusos": None, "senioridade": "",
    }
    base.update(campos)
    return base


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BANCO", str(tmp_path / "teste.db"))
    app = create_app(coletar=False)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def com_vagas(app):
    """Grava vagas no banco e avisa a busca que os dados mudaram."""
    def grava(*brutas):
        agora = int(time.time())
        with conecta() as conn:
            coletor.salva(conn, [coletor.monta_vaga(b, agora) for b in brutas])
        coletor.versao["n"] += 1
    return grava
