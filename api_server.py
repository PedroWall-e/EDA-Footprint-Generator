#!/usr/bin/env python3
# =============================================================================
# api_server.py
# API REST para a EDA Footprint Generator.
#
# Uso:
#   pip install fastapi uvicorn
#   python api_server.py
#   → http://localhost:8042/docs  (Swagger UI)
#
# Endpoints:
#   POST /api/gerar     — Gera .kicad_mod + .kicad_sym + .step
#   POST /api/validar   — Valida YAML (IPC + Schema)
#   GET  /api/padroes   — Lista padrões de footprint
#   GET  /api/tipos-3d  — Lista tipos de modelo 3D
#   GET  /api/presets    — Lista presets disponíveis
#   GET  /api/presets/{nome} — Retorna YAML de um preset
#   GET  /api/schema    — JSON Schema do componente
#   POST /api/batch     — Gera múltiplos componentes
# =============================================================================

import json
import os
import sys
import tempfile
import base64

# Paths do projeto
PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(PROJ_DIR, 'core')
for _p in [PROJ_DIR, CORE_DIR, os.path.join(PROJ_DIR, 'KicadModTree_dev')]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("ERRO: instale fastapi e uvicorn:")
    print("  pip install fastapi uvicorn")
    sys.exit(1)


# =============================================================================
# App FastAPI
# =============================================================================

app = FastAPI(
    title="EDA Footprint Generator API",
    description="API para geração automatizada de componentes eletrônicos (footprint, símbolo, 3D)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Models
# =============================================================================

class GerarRequest(BaseModel):
    dados: dict
    apenas: str | None = None  # 'footprint', 'symbol', '3d'

class ValidarRequest(BaseModel):
    dados: dict

class BatchRequest(BaseModel):
    componentes: list[dict]
    apenas: str | None = None


# =============================================================================
# Helpers
# =============================================================================

def _gerar_componente(dados: dict, saida_dir: str, apenas: str | None = None):
    """Gera arquivos para um componente e retorna resultado."""
    nome = dados.get('nome', 'componente')
    arquivos = {}
    erros = []

    # Footprint
    if not apenas or apenas == 'footprint':
        try:
            kicad_path = os.path.join(saida_dir, f"{nome}.kicad_mod")
            padrao = dados.get('padrao', '')
            tipo = dados.get('tipo', '')
            if padrao:
                from gerador_footprint_v2 import gerar_footprint_universal
                gerar_footprint_universal(dados, kicad_path)
            elif tipo:
                from gerador_footprint import gerar_footprint
                gerar_footprint(dados, kicad_path)
            with open(kicad_path, 'rb') as f:
                arquivos['kicad_mod'] = base64.b64encode(f.read()).decode()
        except Exception as e:
            erros.append(f"Footprint: {e}")

    # Symbol
    if not apenas or apenas == 'symbol':
        try:
            sym_path = os.path.join(saida_dir, f"{nome}.kicad_sym")
            from gerador_symbol import gerar_symbol
            gerar_symbol(dados, sym_path)
            with open(sym_path, 'rb') as f:
                arquivos['kicad_sym'] = base64.b64encode(f.read()).decode()
        except Exception as e:
            erros.append(f"Symbol: {e}")

    # 3D STEP
    if not apenas or apenas == '3d':
        try:
            step_path = os.path.join(saida_dir, f"{nome}.step")
            from gerador_3d import gerar_3d_step
            result = gerar_3d_step(dados, step_path, log_fn=lambda m: None)
            if result and os.path.isfile(result):
                with open(result, 'rb') as f:
                    arquivos['step'] = base64.b64encode(f.read()).decode()
        except ImportError:
            pass  # cadquery não instalado
        except Exception as e:
            erros.append(f"3D: {e}")

    return {
        "ok": len(erros) == 0,
        "nome": nome,
        "arquivos": arquivos,
        "erros": erros,
    }


# =============================================================================
# Endpoints
# =============================================================================

@app.post("/api/gerar", summary="Gerar componente completo")
async def api_gerar(req: GerarRequest):
    """Gera .kicad_mod + .kicad_sym + .step a partir de um dict YAML.

    Os arquivos são retornados como base64 no campo `arquivos`.
    """
    # Validar primeiro
    try:
        from validador_ipc import validar_yaml
        ipc = validar_yaml(req.dados)
        if not ipc.ok:
            return {"ok": False, "erros": ipc.errors}
    except ImportError:
        pass

    with tempfile.TemporaryDirectory() as tmpdir:
        return _gerar_componente(req.dados, tmpdir, req.apenas)


@app.post("/api/validar", summary="Validar YAML (IPC + Schema)")
async def api_validar(req: ValidarRequest):
    """Valida um componente contra regras IPC-7351B e JSON Schema."""
    result = {"ok": True, "erros": [], "avisos": [], "info": []}

    # Schema
    try:
        from validador_schema import validar_schema
        schema_ok, schema_erros = validar_schema(req.dados)
        if not schema_ok:
            result["ok"] = False
            result["erros"].extend([f"Schema: {e}" for e in schema_erros])
    except ImportError:
        pass

    # IPC
    try:
        from validador_ipc import validar_yaml
        ipc = validar_yaml(req.dados)
        if not ipc.ok:
            result["ok"] = False
        result["erros"].extend(ipc.errors)
        result["avisos"].extend(ipc.warnings)
        result["info"].extend(ipc.info)
    except ImportError:
        result["avisos"].append("validador_ipc não disponível")

    return result


@app.get("/api/padroes", summary="Listar padrões de footprint")
async def api_padroes():
    """Retorna os padrões de footprint suportados."""
    from gerador_footprint_v2 import listar_padroes
    return sorted(listar_padroes())


@app.get("/api/tipos-3d", summary="Listar tipos de modelo 3D")
async def api_tipos_3d():
    """Retorna os tipos de modelo 3D disponíveis."""
    try:
        from gerador_3d import listar_tipos_3d
        return listar_tipos_3d()
    except ImportError:
        return []


@app.get("/api/presets", summary="Listar presets disponíveis")
async def api_presets():
    """Retorna lista de presets com nome, padrão e descrição."""
    import yaml
    modulos_dir = os.path.join(PROJ_DIR, 'modulos_config')
    presets = []
    for f in sorted(os.listdir(modulos_dir)):
        if f.startswith('_preset_') and f.endswith(('.yaml', '.yml')):
            path = os.path.join(modulos_dir, f)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    dados = yaml.safe_load(fh)
                presets.append({
                    "arquivo": f,
                    "nome": dados.get('nome', f),
                    "padrao": dados.get('padrao', dados.get('tipo', '')),
                    "descricao": dados.get('kicad', {}).get('descricao', ''),
                })
            except Exception:
                pass
    return presets


@app.get("/api/presets/{nome}", summary="Obter YAML de um preset")
async def api_preset_detalhe(nome: str):
    """Retorna o dict completo de um preset."""
    import yaml
    modulos_dir = os.path.join(PROJ_DIR, 'modulos_config')

    # Tentar encontrar por nome exato ou parcial
    for f in os.listdir(modulos_dir):
        if f.startswith('_preset_') and f.endswith(('.yaml', '.yml')):
            path = os.path.join(modulos_dir, f)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    dados = yaml.safe_load(fh)
                if dados.get('nome') == nome or nome in f:
                    return {"arquivo": f, "dados": dados}
            except Exception:
                pass

    raise HTTPException(status_code=404, detail=f"Preset '{nome}' não encontrado")


@app.get("/api/schema", summary="JSON Schema do componente")
async def api_schema():
    """Retorna o JSON Schema completo para validação de componentes."""
    schema_path = os.path.join(PROJ_DIR, 'schemas', 'component.schema.json')
    if os.path.isfile(schema_path):
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Schema não encontrado")


@app.post("/api/batch", summary="Gerar múltiplos componentes")
async def api_batch(req: BatchRequest):
    """Gera múltiplos componentes de uma vez."""
    resultados = []
    ok_count = 0
    err_count = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        for dados in req.componentes:
            result = _gerar_componente(dados, tmpdir, req.apenas)
            resultados.append(result)
            if result["ok"]:
                ok_count += 1
            else:
                err_count += 1

    return {
        "total": len(req.componentes),
        "sucesso": ok_count,
        "falha": err_count,
        "resultados": resultados,
    }


@app.get("/", summary="Status da API")
async def root():
    """Health check e informações da API."""
    return {
        "nome": "EDA Footprint Generator API",
        "versao": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "POST /api/gerar",
            "POST /api/validar",
            "GET  /api/padroes",
            "GET  /api/tipos-3d",
            "GET  /api/presets",
            "GET  /api/presets/{nome}",
            "GET  /api/schema",
            "POST /api/batch",
        ]
    }


# =============================================================================
# Execução direta
# =============================================================================

if __name__ == '__main__':
    import uvicorn
    print("="*60)
    print("  EDA Footprint Generator API")
    print("  http://localhost:8042")
    print("  Docs: http://localhost:8042/docs")
    print("="*60)
    uvicorn.run(app, host="127.0.0.1", port=8042, log_level="info")
