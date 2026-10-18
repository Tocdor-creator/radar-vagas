#!/data/data/com.termux/files/usr/bin/sh
# Liga/desliga o radar/vagas em segundo plano no Termux.
# Uso: sh ~/radar-vagas/servidor.sh iniciar | parar | reiniciar | status | log
# O app roda dentro de um laço "vigia": se o Python cair, ele volta em 5s.
cd "$(dirname "$0")"
PID_FILE=app.pid
export PORT="${PORT:-5070}"

rodando() { [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; }

iniciar() {
  if rodando; then echo "Já está rodando (PID $(cat $PID_FILE))."; return 0; fi
  termux-wake-lock 2>/dev/null   # impede o Android de pausar o Termux
  setsid nohup sh -c 'while true; do
      python "$PWD/app.py"   # caminho completo: o parar identifica este app por ele
      echo "[vigia] $(date "+%d/%m %H:%M:%S") app saiu (código $?), reiniciando em 5s"
      sleep 5
    done' >> app.log 2>&1 < /dev/null &
  echo $! > "$PID_FILE"
  sleep 3
  if rodando; then echo "radar/vagas iniciado (PID $(cat $PID_FILE)) na porta $PORT."; else echo "Falhou ao iniciar. Veja: sh servidor.sh log"; return 1; fi
}

parar() {
  if rodando; then
    VIGIA="$(cat "$PID_FILE")"
    FILHOS="$(pgrep -P "$VIGIA")"   # o python que roda dentro do vigia
    kill "$VIGIA" 2>/dev/null       # primeiro o vigia, para ele não reiniciar o python
    [ -n "$FILHOS" ] && kill $FILHOS 2>/dev/null
    sleep 1
    pkill -f "python $(pwd)/app.py" 2>/dev/null  # garantia: nenhum python deste app sobrando
    rm -f "$PID_FILE"; echo "radar/vagas parado."
  else
    echo "Não estava rodando."
  fi
}

case "$1" in
  iniciar) iniciar ;;
  parar) parar ;;
  reiniciar) parar; sleep 1; iniciar ;;
  status) if rodando; then echo "Rodando (PID $(cat $PID_FILE))."; else echo "Parado."; fi ;;
  log) tail -n 40 app.log ;;
  *) echo "Uso: sh servidor.sh iniciar | parar | reiniciar | status | log"; exit 1 ;;
esac
