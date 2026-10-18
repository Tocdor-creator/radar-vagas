import os

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANCO = os.environ.get("RADAR_DB", os.path.join(PASTA, "radar.db"))

# A Remotive pede no máximo 4 coletas por dia, então 6h serve pra todo mundo.
INTERVALO_COLETA = 6 * 3600
# Botão "atualizar" da tela: no máximo uma coleta a cada 30 min (o site é público).
INTERVALO_MINIMO_MANUAL = 30 * 60
# Vagas publicadas há mais tempo que isso saem do banco.
DIAS_GUARDADOS = 45

USER_AGENT = "radar-vagas/1.0 (+https://github.com/Tocdor-creator/radar-vagas)"

# Cotação aproximada para converter salários em USD. Não precisa ser exata:
# serve só pra comparar vagas em moedas diferentes.
COTACAO_USD = {
    "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "BRL": 0.18, "CAD": 0.73, "AUD": 0.66,
    "NZD": 0.60, "CHF": 1.12, "SEK": 0.095, "NOK": 0.093, "DKK": 0.145, "PLN": 0.25,
    "CZK": 0.043, "HUF": 0.0028, "RON": 0.22, "INR": 0.012, "MXN": 0.055,
    "ARS": 0.001, "COP": 0.00025, "CLP": 0.0011, "JPY": 0.0067, "SGD": 0.74,
    "HKD": 0.128, "CNY": 0.14, "PHP": 0.017, "ZAR": 0.055, "ILS": 0.27, "TRY": 0.03,
}
# Quanto vale 1 USD em reais, pra mostrar o "≈ R$ x/mês" nos cards.
USD_PARA_BRL = 1 / COTACAO_USD["BRL"]
