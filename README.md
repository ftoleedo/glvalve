# glvalve

CLI (stdlib-only, Python ≥ 3.10) para pressão hidrostática e trem de válvulas
de unloading (IPO) em gas lift.

## Uso

```bash
python3 -m glvalve hydrostatic 15 3500                      # 2730.00 psi
python3 -m glvalve valve --disc 1200 --tubing 300 --gradient 0.4 --margin 100
                                                            # 2000.00 ft
python3 -m glvalve train --disc 1200 --tubing 300 --gradient 0.4 \
        --margin 100 --n 4 --spacing 500                    # tabela
python3 -m glvalve train ... --mode fixed_depth --json       # JSON estrito
```

Flags em todos os subcomandos: `--decimals N` (0..12, default 2,
arredondamento half-up sobre o decimal digitado) e `--json` (strict JSON,
`allow_nan=False`).

## Fórmulas e unidades

| Grandeza | Símbolo | Unidade |
|---|---|---|
| Pressão | `p_*` | psi |
| Profundidade (TVD, poço vertical) | `D` | ft |
| Gradiente do fluido | `G` | psi/ft |
| Massa de lama | `MW` | ppg |

- Hidrostática: `P = 0.052 · MW · TVD`
- Gradiente: `G = 0.052 · MW` (`gradient_psi_per_ft`)
- Profundidade da válvula: `D = (p_disc − margin − p_tubing) / G`, `G > 0`, `D > 0`
- `p_tubing_psi` = pressão da linha de fluxo/tubing vista no cálculo de abertura
  da válvula (não é a hidrostática da coluna — essa é `G`).

## Modelos do trem (DECISAO:D-001 — ver `DECISOES.md`)

- **`fixed_disc`** (default, leitura literal do requisito): `p_disc` fixo,
  `T_i = T₁ + (i−1)·G·spacing`, profundidades **decrescem** (2000→500 ft).
- **`fixed_depth`** (trem físico): espaçamento em profundidade
  `D_i = D₁ + (i−1)·spacing`; a pressão de disco requerida cresce
  `G·spacing` por válvula (1200→1800 psi).

Em ambos os modos vale o invariante do `Valve`:
`(p_disc − margin − p_tubing) / G == depth` (testado).

## Exit codes

| Código | Significado |
|---|---|
| 0 | sucesso |
| 1 | erro de domínio (`GlValveError`) — mensagem em stderr, stdout intacta |
| 2 | erro de uso (argparse: flag faltando / subcomando inexistente) |

## Desenvolvimento

```bash
python3 -m pytest -q                                  # 84 testes
./gate.sh                                             # compile/import/cli/tests
./demo.sh                                             # demo ao vivo no terminal
```

Erros: todo erro de domínio é `GlValveError` (`ValidationError` = entrada
inválida; `ValveTrainError` = resultado derivado do trem inválido, com índice
e profundidade, em qualquer índice). `core.py` é puro: sem `print`/`input`/`sys.exit`.
