# radar/vagas

Procurar vaga remota é abrir dez abas, cada site com um filtro diferente e metade das vagas sem dizer quanto paga ou de que fuso aceita gente. Resolvi juntar tudo num lugar só e filtrar do jeito que eu queria.

O radar busca vagas em 5 APIs públicas, organiza tudo no mesmo formato e deixa filtrar por **stack**, **salário** e **fuso horário**. Fiz pro portfólio, mas também uso na minha própria busca.

## O que ele faz

- **Junta 5 fontes**: [Remotive](https://remotive.com), [Remote OK](https://remoteok.com), [Arbeitnow](https://www.arbeitnow.com), [Jobicy](https://jobicy.com) e [Himalayas](https://himalayas.app). Quando a mesma vaga aparece em duas, fica só a versão mais completa.
- **Descobre a stack** lendo título, tags e descrição. Tem uns casos chatos que tratei: "Java" não pode casar com "JavaScript", "React" não é "React Native", e "Go" só conta no título, porque no texto quase sempre é verbo.
- **Põe todo salário na mesma moeda.** Cada fonte manda de um jeito: "$90k - $105k", "€50,000/year", "$40-60 /hour", ou mínimo e máximo em PLN por ano. O radar lê tudo isso e converte pra **US$ por ano**, e no card mostra também o **≈ R$ por mês**.
- **Fuso horário**: quando a API informa, usa direto. Quando não, estima pelo local da vaga ("USA, Canada", "LATAM", "UTC-3 to UTC+2"...). Você escolhe seu fuso e a tolerância (±h), e cada card tem uma régua das 24h mostrando onde a vaga aceita gente e onde você está.
- **Senioridade**: tira do título (Sr., Staff, Intern…) ou do que a fonte informou.
- **Favoritas e ocultas** ficam salvas no navegador. **"Salvar como meu filtro"** faz o radar abrir sempre com os seus filtros, e a URL guarda o filtro atual, então dá pra compartilhar uma busca.

## Como funciona

```
APIs públicas ──► fontes.py ──► normaliza.py ──► SQLite ──► busca.py ──► /api/vagas ──► tela (JS puro)
                 (1 função     (stack, salário,  (cache)    (filtros e
                  por fonte)    fuso, nível)                 facetas)
```

- Uma thread coleta ao subir o app e depois **a cada 6h**. A Remotive pede no máximo 4 coletas por dia, e nenhuma fonte muda mais rápido que isso.
- O botão "atualizar" da tela respeita um intervalo mínimo de 30 min, pra ninguém usar o site pra martelar as APIs.
- Se uma fonte cair, as outras seguem normalmente, e a tela mostra qual está fora do ar.
- Vagas com mais de 45 dias saem do banco.
- Só usa a biblioteca padrão do Python + Flask, então roda até no Termux do meu celular, que é o meu servidor caseiro.

### Sobre os termos das APIs

Todas pedem crédito e link pra vaga original, então cada card diz de qual fonte veio e o botão leva pro anúncio lá. O radar não guarda a descrição completa, só um resumo de 280 caracteres.

## Organização

```
radar-vagas/
├── app.py              # sobe o servidor (porta 5070)
├── radar/
│   ├── __init__.py     # rotas da API
│   ├── fontes.py       # uma função por API
│   ├── normaliza.py    # stack, salário, fuso, senioridade
│   ├── coletor.py      # salva no banco e agenda as coletas
│   ├── busca.py        # filtros, facetas, remoção de repetidas
│   ├── db.py / config.py
│   └── static/         # index.html, app.js, style.css
├── tests/              # pytest
├── servidor.sh         # liga/desliga no Termux
└── deploy.ps1          # manda pro servidor caseiro
```

## API

| Rota | O que faz |
|---|---|
| `GET /api/vagas` | Lista com filtros: `q`, `stacks=Python,React`, `sal_min` (US$/ano), `sem_salario`, `fuso=-3`, `tolerancia=2`, `sem_fuso`, `senioridade`, `fontes`, `dias`, `so_tech`, `ordem=recentes\|salario`, `pagina` |
| `GET /api/status` | Total de vagas e última coleta de cada fonte |
| `POST /api/atualizar` | Pede uma coleta nova (no máximo 1 a cada 30 min) |

## Pra rodar

```bash
python -m venv .venv
.venv\Scripts\activate          # no Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt
python app.py                   # http://localhost:5070
```

Na primeira vez ele já começa a coletar sozinho (leva uns 30s). Testes:

```bash
pytest
```

## Feito com

Python, Flask, SQLite, HTML/CSS/JS puro.
