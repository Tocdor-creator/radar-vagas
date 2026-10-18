import threading
import time

from flask import Flask, jsonify, request, send_from_directory

from . import coletor, config
from .busca import busca, todas
from .db import conecta, cria_tabelas
from .fontes import SITES


def create_app(coletar=True):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.json.ensure_ascii = False
    cria_tabelas()
    if coletar:
        coletor.inicia_agendador()

    @app.get("/")
    def inicio():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/vagas")
    def vagas():
        try:
            pagina = max(1, int(request.args.get("pagina", 1)))
        except ValueError:
            pagina = 1
        return jsonify(busca(request.args, pagina))

    @app.get("/api/status")
    def status():
        with conecta() as conn:
            ultimas = conn.execute(
                "SELECT c.fonte, c.em, c.ok, c.quantidade, c.erro FROM coletas c "
                "JOIN (SELECT fonte, MAX(id) AS id FROM coletas GROUP BY fonte) u ON u.id = c.id"
            ).fetchall()
        por_fonte = {r["fonte"]: dict(r) for r in ultimas}
        ultima = coletor.ultima_coleta()
        return jsonify({
            "total": len(todas()),
            "coletando": coletor.coletando(),
            "ultima_coleta": ultima or None,
            "proxima_coleta": (ultima + config.INTERVALO_COLETA) if ultima else None,
            "pode_atualizar": time.time() - ultima >= config.INTERVALO_MINIMO_MANUAL,
            "usd_para_brl": config.USD_PARA_BRL,
            "fontes": [
                {"nome": nome, "site": site, **{k: por_fonte.get(nome, {}).get(k) for k in ("em", "ok", "quantidade", "erro")}}
                for nome, site in SITES.items()
            ],
        })

    @app.post("/api/atualizar")
    def atualizar():
        if coletor.coletando():
            return jsonify({"ok": True, "motivo": "a coleta já está rodando"}), 202
        espera = config.INTERVALO_MINIMO_MANUAL - (time.time() - coletor.ultima_coleta())
        if espera > 0:
            return jsonify({"ok": False, "motivo": f"atualizado há pouco, tente em {int(espera // 60) + 1} min"}), 429
        threading.Thread(target=coletor.coleta, daemon=True).start()
        return jsonify({"ok": True, "motivo": "coleta iniciada"}), 202

    return app

