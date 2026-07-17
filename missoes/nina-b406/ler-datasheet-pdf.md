# O problema
Extrair de um datasheet (PDF de 40-90 páginas, 2-7 MB) só o que decide um
projeto — pinagem, limites elétricos, cotas — sem torrar contexto de IA lendo
o documento inteiro, e sem inventar número.

# A solução

**1. Texto e tabelas: PyMuPDF (`fitz`).** Medido no `datasheets/STX3.pdf`
(42 páginas):

| Biblioteca | Tempo | Tabelas | Vetores |
|---|---|---|---|
| pypdf | 1,13 s | ❌ | ❌ |
| pdfplumber | 3,48 s | 49 | ✅ |
| **PyMuPDF** | **0,05 s** | 40 | ✅ |

PyMuPDF é **~70x mais rápido que o pypdf** e ainda entrega tabela e vetor.
É a escolha padrão.

```python
import fitz
doc = fitz.open(pdf)
doc[n].get_text()          # texto
doc[n].find_tables()       # tabelas
doc[n].get_drawings()      # vetores com coordenada exata
len(doc[n].get_images())   # se > 0 e get_drawings() ~ 0 -> figura é raster
```

**2. Se a cota estiver em figura RASTER: renderize SÓ aquela página e use
visão (VLM).**

```python
doc[n].get_pixmap(dpi=300).save("pagina.png")   # 300 dpi: cota legível
```

Uma IA com visão lê melhor que OCR porque entende **linha de chamada** — a
que feature aquele número pertence. OCR devolve números soltos.
Custo: **1 imagem**, não 42 páginas.

**3. Nunca**:
- OCR do PDF inteiro (caro e desnecessário: o texto já é extraível);
- OpenCV/visão computacional para **medir pixels** do desenho.

# Contexto / por que

Medir pixels é errado por construção: o desenho de land pattern quase sempre
está **fora de escala** ("NOT TO SCALE"). A verdade está nos **números
cotados**, não na geometria da figura. Medir a imagem dá a escala do desenho,
não a dimensão da peça — e 3% de erro num footprint é placa no lixo.

Descoberta empírica que refina a regra: o PDF **como um todo** ser vetorial
NÃO garante que a figura que interessa seja. No `STX3.pdf`, o documento tem
70 mil chars de texto real, mas a **Figura 7 (footprint recomendado) é
imagem raster** — `vetores=1, imagens=2` naquela página. Por isso o passo 1
(extrair texto) não basta sozinho: é preciso detectar o caso raster e cair
para o passo 2.

Detecção: numa página, `len(get_drawings()) ≈ 0` + `len(get_images()) > 0`
+ poucos números decimais no texto = a cota está na imagem.

# Implementação futura (scripts/partfinder/)

Pipeline pretendido:
1. PyMuPDF varre o PDF e localiza as seções (`pin configuration`,
   `absolute maximum`, `recommended operating`, `land pattern`, `mechanical`);
2. extrai texto/tabelas dessas seções -> `datasheets/extraidos/<MPN>.md`
   (~3 KB no lugar de ~3 MB: cerca de 100x menos contexto);
3. detecta páginas cuja cota é raster e renderiza **apenas essas** a 300 dpi;
4. a IA lê o resumo; olha a imagem só quando o passo 3 marcou.

Relacionado: `datasheets/README.md` (política da biblioteca) e
`skills/footprint-nao-sai-de-pdf.md`.
