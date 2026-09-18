#!/usr/bin/env bash
# Demo ao vivo do glvalve — CLI de valvulas de gas lift descompressao
cd "$(dirname "$0")"

show() {  # mostra o comando, roda, pausa
  echo ""
  echo -e "\033[1;36m\$ $*\033[0m"
  eval "$@"
  sleep 2.5
}

clear
echo -e "\033[1;93m╔══════════════════════════════════════════════════════╗"
echo    "║   glvalve — calculadora de valvulas gas lift (demo)  ║"
echo    "╚══════════════════════════════════════════════════════╝\033[0m"

echo -e "\n\033[1m[1] Ajuda geral\033[0m"
show python3 -m glvalve --help

echo -e "\n\033[1m[2] Pressao hidrostatica: lama 8.5 ppg em 2500 ft\033[0m"
show python3 -m glvalve hydrostatic 8.5 2500

echo -e "\n\033[1m[3] Profundidade da valvula: p_disc=900, p_tubing=250, grad=0.35, margem=50 psi\033[0m"
show python3 -m glvalve valve --disc 900 --tubing 250 --gradient 0.35 --margin 50

echo -e "\n\033[1m[4] Trem de valvulas (fixed_disc — leitura literal, profundidades decrescem)\033[0m"
show python3 -m glvalve train --disc 900 --tubing 250 --gradient 0.35 --margin 50 --n 4 --spacing 500

echo -e "\n\033[1m[5] Trem de valvulas (fixed_depth — fisico: descem, pressao de disco cresce)\033[0m"
show python3 -m glvalve train --disc 1200 --tubing 250 --gradient 0.35 --margin 50 --n 4 --spacing 500 --mode fixed_depth

echo -e "\n\033[1m[6] Saida JSON estrita (para integracao)\033[0m"
show python3 -m glvalve valve --disc 900 --tubing 250 --gradient 0.35 --margin 50 --json

echo -e "\n\033[1m[7] Validacao: gradiente zero e profundidade impossivel\033[0m"
show python3 -m glvalve valve --disc 900 --tubing 250 --gradient 0 --margin 50
show python3 -m glvalve valve --disc 200 --tubing 250 --gradient 0.35 --margin 50

echo -e "\n\033[1m[8] Os 84 testes rodando\033[0m"
show python3 -m pytest -q

echo -e "\n\033[1;92m═══ Demo concluida. Porta-se aberta para explorar: python3 -m glvalve --help ═══\033[0m"
exec bash
