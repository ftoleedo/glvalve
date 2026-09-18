#!/usr/bin/env bash
# gate for agent-chain-test — EXECUTÁVEL DIRETO: ./gate.sh  ou  bash gate.sh
#
# ATENCAO (licao 17/09/2026, Claude Code): o arquivo .gate antigo usava formato
# "nome :: comando" de outro runner. Rodado com `bash .gate`, a linha
#   import :: python3 -c "import glvalve"
# executou o `import` do ImageMagick, que abriu o display e TRAVOU 8 minutos
# esperando clique de captura de tela (bash do PI nao tem timeout proprio).
# Regras deste script:
#   1. Nada de rotulos "::" — comandos shell reais.
#   2. Todo comando envolto em `timeout` (nunca travar indefinidamente).
#   3. Nome do arquivo sem ponto na frente (gate.sh) para nao virar dotfile esquecido.

set -u
cd "$(dirname "$0")"

fail=0
run() {
  local desc="$1"; shift
  if timeout 120 "$@" >/dev/null 2>&1; then
    echo "OK   $desc"
  else
    echo "FAIL $desc (exit $?)"
    fail=1
  fi
}

run "compile" python3 -m compileall -q glvalve tests
run "import"  python3 -c "import glvalve"
run "cli"     bash -c "python3 -m glvalve hydrostatic 15 3500 | grep -q '2730.00 psi'"
run "tests"   python3 -m pytest -q

if [ "$fail" -eq 0 ]; then echo "GATE: PASS"; else echo "GATE: FAIL"; fi
exit "$fail"
