import os

from radar import create_app

app = create_app()

if __name__ == "__main__":
    # 0.0.0.0 para aceitar acessos de outros aparelhos da rede (e pelo Tailscale).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5070)))
