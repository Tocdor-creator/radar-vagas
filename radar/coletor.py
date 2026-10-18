"""Junta as vagas de todas as fontes no banco, de tempos em tempos."""
import json
import threading
import time
import traceback

from . import config
from .db import conecta
from .fontes import FONTES
from .normaliza import (
    detecta_senioridade, detecta_stacks, eh_tecnologia, infere_fusos, resumo, salario_usd_anual,
)

_trava = threading.Lock()
# Muda a cada coleta; a busca usa isso para saber quando recarregar o cache.
versao = {"n": 0}


def monta_vaga(b, agora):
    """Transforma o formato comum das fontes na linha que vai para o banco."""
    fuso_tipo, fusos = b["fusos"] or infere_fusos(b["local"])
    mn = mx = moeda = periodo = usd_min = usd_max = None
    if b["salario"]:
        mn, mx, moeda, periodo = b["salario"]
        if mn and mx and mx > 5 * mn:  # faixa absurda (ex.: 190k a 1.7M), fica só o piso
            mx = mn
        usd_min, usd_max = salario_usd_anual(mn, mx, moeda, periodo)
    return {
        "id": f"{b['fonte']}:{b['id_externo']}",
        "fonte": b["fonte"],
        "titulo": b["titulo"].strip() or "(sem título)",
        "empresa": b["empresa"].strip() or "(empresa não informada)",
        "logo": b["logo"] if b["logo"].startswith("https://") else "",
        "url": b["url"],
        "local": b["local"],
        "publicada_em": min(b["publicada_em"], agora),
        "vista_em": agora,
        "resumo": resumo(b["texto"]),
        "stacks": json.dumps(detecta_stacks(b["titulo"], b["tags"], b["texto"])),
        "tags": json.dumps([t for t in b["tags"] if t][:10]),
        "senioridade": detecta_senioridade(b["titulo"], b["senioridade"]),
        "tecnologia": int(eh_tecnologia(b["titulo"])),
        "tipo": b["tipo"],
        "sal_min": mn, "sal_max": mx, "moeda": moeda, "periodo": periodo,
        "sal_min_usd": usd_min, "sal_max_usd": usd_max,
        "fuso_tipo": fuso_tipo,
        "fusos": json.dumps(fusos),
    }


_COLUNAS = [
    "id", "fonte", "titulo", "empresa", "logo", "url", "local", "publicada_em", "vista_em",
    "resumo", "stacks", "tags", "senioridade", "tecnologia", "tipo", "sal_min", "sal_max",
    "moeda", "periodo", "sal_min_usd", "sal_max_usd", "fuso_tipo", "fusos",
]
_UPSERT = (
    f"INSERT INTO vagas ({', '.join(_COLUNAS)}) VALUES ({', '.join('?' * len(_COLUNAS))}) "
    "ON CONFLICT(id) DO UPDATE SET "
    + ", ".join(f"{c} = excluded.{c}" for c in _COLUNAS if c not in ("id", "vista_em"))
)


def salva(conn, vagas):
    conn.executemany(_UPSERT, [[v[c] for c in _COLUNAS] for v in vagas])


def coleta(fontes=None):
    """Roda todas as fontes. Uma fonte com problema não derruba as outras."""
    if not _trava.acquire(blocking=False):
        return {"ok": False, "motivo": "já tem uma coleta rodando"}
    try:
        resultado = {}
        for nome in fontes or FONTES:
            agora = int(time.time())
            try:
                vagas = [monta_vaga(b, agora) for b in FONTES[nome]()]
                with conecta() as conn:
                    salva(conn, vagas)
                    conn.execute("INSERT INTO coletas (fonte, em, ok, quantidade) VALUES (?, ?, 1, ?)",
                                 (nome, agora, len(vagas)))
                resultado[nome] = len(vagas)
            except Exception as erro:  # noqa: BLE001 - API fora do ar, JSON mudou etc.
                traceback.print_exc()
                with conecta() as conn:
                    conn.execute("INSERT INTO coletas (fonte, em, ok, erro) VALUES (?, ?, 0, ?)",
                                 (nome, agora, f"{type(erro).__name__}: {erro}"[:300]))
                resultado[nome] = None
        with conecta() as conn:
            limite = int(time.time()) - config.DIAS_GUARDADOS * 86400
            conn.execute("DELETE FROM vagas WHERE publicada_em < ?", (limite,))
            conn.execute("DELETE FROM coletas WHERE em < ?", (limite,))
        versao["n"] += 1
        return {"ok": True, "fontes": resultado}
    finally:
        _trava.release()


def ultima_coleta():
    with conecta() as conn:
        linha = conn.execute("SELECT MAX(em) FROM coletas WHERE ok = 1").fetchone()
    return linha[0] or 0


def coletando():
    return _trava.locked()


def inicia_agendador():
    """Thread que coleta ao subir o app (se estiver velho) e depois a cada 6h."""
    def laco():
        while True:
            if time.time() - ultima_coleta() >= config.INTERVALO_COLETA:
                coleta()
            time.sleep(600)

    threading.Thread(target=laco, name="coletor", daemon=True).start()
