---
name: data-frontier-component-generator
description: |
  Skill para criar componentes eletrônicos (footprint KiCad, símbolo esquemático, modelo 3D STEP)
  usando a EDA Footprint Generator. Use esta skill quando o usuário pedir para criar,
  gerar ou projetar um componente eletrônico, footprint, símbolo, ou modelo 3D para KiCad.
  Palavras-chave: componente, footprint, KiCad, PCB, SMD, PTH, BGA, SOIC, DIP, STEP, 3D,
  esquemático, símbolo, resistor, capacitor, CI, conector, diodo, LED, transistor.
---

# Skill: Gerador de Componentes Eletrônicos

## Visão Geral

Esta plataforma gera automaticamente **3 arquivos** para cada componente eletrônico:
- `.kicad_mod` — Footprint 2D (pads, silkscreen, courtyard)
- `.kicad_sym` — Símbolo esquemático
- `.step` — Modelo 3D

Tudo a partir de um **arquivo YAML** que descreve o componente.

## Como Usar

### Método 1: CLI (recomendado para automação)

```bash
# Gerar componente completo
python cli.py gerar componente.yaml --dry-run  # validate only
python cli.py gerar modulos_config/NE555_DIP8.yaml -o saida/

# Gerar com saída JSON (para parsing programático)
python cli.py --json gerar componente.yaml -o saida/

# Gerar a partir de stdin (agente envia JSON/YAML direto)
echo '<yaml_content>' | python cli.py --json gerar --stdin -o saida/

# Validar antes de gerar
python cli.py --json validar componente.yaml

# Listar padrões e tipos
python cli.py --json padroes
python cli.py --json tipos-3d

# Batch: gerar todos de uma pasta
python cli.py batch modulos_config/ -o saida/

# Obter JSON Schema
python cli.py schema
```

### Método 2: Python direto

```python
import sys
sys.path.insert(0, 'core')
sys.path.insert(0, 'KicadModTree_dev')

from gerador_footprint_v2 import gerar_footprint_universal
from gerador_symbol import gerar_symbol
from gerador_3d import gerar_3d_step
from validador_ipc import validar_yaml

dados = { ... }  # dict com dados do componente

# 1. Validar
result = validar_yaml(dados)
if result.ok:
    # 2. Gerar
    gerar_footprint_universal(dados, "saida/comp.kicad_mod")
    gerar_symbol(dados, "saida/comp.kicad_sym")
    gerar_3d_step(dados, "saida/comp.step")
```

### Método 3: API REST

```bash
python api_server.py  # → http://localhost:8042/docs
```

```bash
# Gerar via HTTP
curl -X POST http://localhost:8042/api/gerar \
  -H "Content-Type: application/json" \
  -d '{"dados": {"nome": "R100", "padrao": "axial_pth", ...}}'

# Validar via HTTP
curl -X POST http://localhost:8042/api/validar \
  -d '{"dados": {"nome": "R100", ...}}'
```

## Estrutura do YAML

O componente é descrito como um dict/YAML com esta estrutura. Leia `schemas/component.schema.json` para o schema completo.

### Campos obrigatórios

- `nome` — Nome único, sem espaços (ex: `NE555_DIP8`)
- `padrao` ou `tipo` — Define o layout dos pads

### `kicad.modelo_3d` — como o footprint acha o 3D

| Valor | Efeito |
|---|---|
| **omitido** | referencia `"<nome>.step"` — que é o arquivo que o `cli.py` gera |
| `""` (vazio) | não referencia 3D nenhum |
| contém `/` ou `$` | tratado como **caminho completo** |
| nome simples | recebe o prefixo `${KIPRJMOD}/` (ou `kicad.modelo_3d_path`) |

> ⚠️ **Biblioteca compartilhada**: `${KIPRJMOD}` é a pasta do **projeto** KiCad.
> Se o `.step` mora numa biblioteca (e não junto do `.kicad_pro`), o caminho não
> resolve e o 3D não aparece. Use uma variável do KiCad (Preferences → Configure
> Paths): `modelo_3d: "${MINHA_LIB_3DSHAPES}/Peca.step"`.

### Padrões disponíveis (`padrao`)

| Padrão | Descrição | Exemplo |
|--------|-----------|---------|
| `axial_pth` | 2 pads inline (resistor, diodo) | Resistor_470R |
| `radial_pth` | 3+ pads agrupados (TO-92, TO-220) | TO220_3pin |
| `dual_pth` | 2 fileiras PTH (DIP) | DIP14 |
| `dual_smd` | 2 fileiras SMD (SOIC, SOT-23) | SMD_0805, SOT23_3 |
| `quad_smd` | 4 lados SMD (QFP, QFN) | QFN16_4x4, TQFP44 |
| `single_row_pth` | 1 fileira PTH (pin header 1xN) | Conn_01x06 |
| `custom` | Posições arbitrárias | Battery_CR2032 |
| `bga` | Ball Grid Array | BGA256_17x17 |

### Tipos preset (`tipo`)

`resistor_pth`, `diodo_pth`, `led_pth`, `capacitor_pth`, `transistor_to92`,
`crystal_hc49`, `conector_pth`, `ci_dip`, `ci_soic`, `castellated`

### Exemplo: Resistor axial PTH

```yaml
nome: Resistor_100R
padrao: axial_pth

pinos:
  espacamento: 10.16    # distância entre furos (mm)
  diametro_pad: 1.6
  diametro_furo: 0.8

corpo:
  comprimento: 6.5
  diametro: 2.5
  formato: cilindro

margens:
  courtyard: 0.5
  silkscreen: 0.12
  fab_line: 0.10

kicad:
  referencia: "R?"
  valor: "100R"
  descricao: "Resistor axial PTH 100 Ohm"
  tags: "resistor pth axial"
  modelo_3d: "Resistor_100R.step"   # opcional — ver nota abaixo

simbolo: resistor
```

### Exemplo: SMD 0805

```yaml
nome: SMD_0805_Custom
padrao: dual_smd

pinos:
  total: 2
  pitch: 0
  tamanho_pad:
    largura: 1.0
    altura: 1.3
  afastamento_colunas: 1.7

corpo:
  largura: 2.0
  comprimento: 1.25

margens:
  courtyard: 0.25
  silkscreen: 0.12

kicad:
  referencia: "R?"
  valor: "0805"

tipo_3d: smd_chip
simbolo: resistor
```

### Exemplo: CI DIP-8

```yaml
nome: MeuCI_DIP8
tipo: ci_dip

pinos:
  total: 8
  pitch: 2.54
  diametro_pad: 1.7
  diametro_furo: 0.9

corpo:
  largura: 6.35
  comprimento: 9.78
  afastamento_colunas: 7.62

kicad:
  referencia: "U?"
  valor: "MeuCI"
  descricao: "CI DIP-8 custom"
```

### Exemplo: BGA-256

```yaml
nome: BGA256_Custom
padrao: bga

pinos:
  linhas: 16
  colunas: 16
  pitch: 1.0
  diametro_pad: 0.5

corpo:
  largura: 17.0
  comprimento: 17.0
  altura_3d: 1.4

kicad:
  referencia: "U?"
  valor: "BGA256"

tipo_3d: bga
simbolo: bga
```

## Presets Disponíveis

Para duplicar um preset como ponto de partida, copie um arquivo de `modulos_config/_preset_*.yaml`:

| Preset | Padrão | Descrição |
|--------|--------|-----------|
| SMD_0402 | dual_smd | Chip 0402 |
| SMD_0603 | dual_smd | Chip 0603 |
| SMD_0805 | dual_smd | Chip 0805 |
| SMD_1206 | dual_smd | Chip 1206 |
| SOT23_3 | dual_smd | SOT-23 3 pinos |
| SOT23_5 | dual_smd | SOT-23-5 pinos |
| SOT223 | dual_smd | SOT-223 |
| SSOP20 | dual_smd | SSOP-20 |
| DPAK_TO252 | dual_smd | DPAK power |
| SMA_DO214AC | dual_smd | SMA diodo |
| SOD123 | dual_smd | SOD-123 |
| DIP14/16/28 | ci_dip | DIP genérico |
| QFN16_4x4 | quad_smd | QFN-16 |
| TQFP44 | quad_smd | TQFP-44 |
| BGA256_17x17 | bga | BGA-256 |
| TO220_3pin | radial_pth | TO-220 |
| TO247_3pin | radial_pth | TO-247 |
| Conn_01x06 | conector_pth | Pin header 1x6 |
| Conn_02x05 | ci_dip | Box header 2x5 |
| Battery_CR2032 | custom | Bateria CR2032 |
| Supercap_1F | custom | Supercapacitor |
| Antena_Patch_GPS | custom | Antena patch GPS |

## Workflow Recomendado para o Agente

1. **Entender o pedido** — Qual componente? Que package? SMD ou PTH?
2. **Escolher o padrão** — Consultar tabela acima ou `python cli.py padroes`
3. **Usar preset como base** — Copiar de `modulos_config/_preset_*.yaml` se houver similar
4. **Montar o YAML** — Preencher campos conforme schema
5. **Validar** — `python cli.py --json validar componente.yaml`
6. **Gerar** — `python cli.py --json gerar componente.yaml -o saida/`
7. **Verificar saída** — Confirmar que os 3 arquivos foram gerados
8. **Atualizar docs (se aplicável)** — Se a mudança alterou padrões, tipos 3D, campos YAML, presets ou comandos, atualize as tabelas desta SKILL, o `README.md`/`README.pt-BR.md`, o `schemas/component.schema.json` e o `CHANGELOG.md`. Ver a **Disciplina de Documentação** em `.agents/AGENTS.md`.

> ⚠️ **Disciplina de documentação:** esta skill lista padrões, tipos 3D e presets. Sempre que `_PADROES`, `TEMPLATES_3D` ou os arquivos `_preset_*.yaml` mudarem, estas tabelas **devem** ser atualizadas na mesma alteração — caso contrário o agente passará a gerar com informação errada.

## Referências

- Schema completo: `schemas/component.schema.json`
- Manual YAML: `docs/MANUAL_YAML_REFERENCIA.yaml`
- Exemplos reais: `modulos_config/*.yaml`
