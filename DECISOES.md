# DECISÕES — agent-chain-test

## D-001 — Modelo do trem de válvulas (req. 3 ambíguo)

**Questão**: "cada válvula subsequente usa p_tubing na profundidade da anterior + gradient·spacing"
admite duas leituras matematicamente distintas, e o exemplo do plano (T sobe 200 psi enquanto D cai
500 ft → gradiente implícito −0,4 psi/ft) é inconsistente com a hidrostática do próprio módulo.

**Opção A — `fixed_disc` (leitura literal)**: `p_disc` fixo; `T_i = T_1 + (i−1)·G·spacing`;
`D_i = (p_disc − margin − T_i)/G` → profundidades **decrescem** (2000 → 1500 → 1000 → 500 ft).
Perfil de pressão inconsistente com coluna hidrostática; é o contrato literal do requisito.

**Opção B — `fixed_depth` (trem físico real)**: espaçamento em **profundidade**
(`D_i = D_1 + (i−1)·spacing`); a pressão de disco **requerida** cresce `G·spacing` por válvula
(1200 → 1400 → 1600 → 1800 psi no exemplo). Coerente com a skill gas-lift-theory
("quanto mais profunda, maior a produção; limite = pressão de injeção disponível").
Exige `p_disc_psi` variável por válvula.

**Recomendação**: B (`fixed_depth`) — coerência física.

**Premissa adotada enquanto não responde**: implementar **ambos** os modos
(`mode="fixed_disc" | "fixed_depth"`), default `fixed_disc` (literal = contrato), marcado
`DECISAO:D-001` no código. O invariant do `Valve`
`(p_disc − margin − p_tubing)/gradient == depth` vale nos DOIS modos (testado).

**Custo de retrabalho se a resposta for outra**: baixo — mudar o default é 1 linha; remover o modo
não escolhido custa os testes daquele modo (~10 testes) e uma seção do README.

**Status**: ⏳ aguardando Fabricio. Implementação segue com os dois modos.
