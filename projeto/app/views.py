# projeto/app/views.py
import os, uuid, threading, io, time, tempfile
from io import BytesIO
from datetime import datetime

from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ImproperlyConfigured

import pandas as pd
import redis

# >>> se sua função está aqui:
from . import consulta_do_simples  # ajuste se o nome do módulo for outro

# ---------- Redis helpers ----------
def _get_redis():
    url = os.getenv("KV_URL")
    if not url:
        raise ImproperlyConfigured(
            "Defina a variável de ambiente KV_URL no serviço Web do Render (Settings → Environment)."
        )
    return redis.from_url(url, decode_responses=False)  # binary-safe

def _set_job(job_id, **fields):
    r = _get_redis()
    r.hset(
        f"job:{job_id}",
        mapping={k: (str(v).encode() if isinstance(v, str) else v) for k, v in fields.items()},
    )

def _get_job(job_id):
    r = _get_redis()
    raw = r.hgetall(f"job:{job_id}")
    return {k.decode(): v.decode() for k, v in raw.items()} if raw else None

def _save_result(job_id, content_bytes: bytes, filename: str, ttl_seconds: int = 3600):
    # guarda o Excel gerado no KV por 1h (ajuste TTL se quiser)
    r = _get_redis()
    r.setex(f"file:{job_id}", ttl_seconds, content_bytes)
    _set_job(job_id, state="SUCCESS", filename=filename)

# ---------- suas páginas ----------
def index(request):
    return render(request, "index.html")

def login_view(request):
    return render(request, "login.html")

def upload_page(request):
    # mantém seu layout do upload
    return render(request, "upload.html")

# ---------- pipeline ----------
def _processar_com_sua_funcao_usando_arquivos(tmp_in_path: str) -> bytes:
    """
    Exemplo: se a sua função espera caminho de arquivo de entrada
    e grava um arquivo de saída. Ajuste a chamada conforme sua assinatura real.
    """
    # cria arquivo temporário de saída
    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp_out_path = tmp_out.name
    tmp_out.close()

    # CHAME SUA FUNÇÃO AQUI:
    # Ex.: consulta_do_simples.executar(tmp_in_path, tmp_out_path)
    # ou consulta_do_simples.processar(tmp_in_path, tmp_out_path)
    # (ajuste o nome da função):
    consulta_do_simples.processar(tmp_in_path, tmp_out_path)

    # lê bytes do arquivo gerado e limpa
    with open(tmp_out_path, "rb") as f:
        saida = f.read()
    os.unlink(tmp_out_path)
    return saida

def _processar_com_sua_funcao_em_memoria(file_bytes: bytes) -> bytes:
    """
    Exemplo alternativo: se sua função trabalhar com DataFrame/bytes e retornar outro DataFrame.
    Aqui só crio uma coluna de exemplo — troque pela sua lógica real.
    """
    df = pd.read_excel(BytesIO(file_bytes))
    df["ProcessadoEm"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultado")
    out.seek(0)
    return out.read()

def _processar_planilha(job_id: str, file_bytes: bytes, filename: str):
    try:
        _set_job(job_id, state="STARTED", progress="5")

        # === Opção A (mais comum): sua função usa CAMINHO de arquivo ===
        tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp_in.write(file_bytes)
        tmp_in.flush()
        tmp_in_path = tmp_in.name
        tmp_in.close()

        _set_job(job_id, progress="20")

        # chame sua função real aqui:
        saida_bytes = _processar_com_sua_funcao_usando_arquivos(tmp_in_path)

        _set_job(job_id, progress="95")

        # limpa o arquivo temporário de entrada
        if os.path.exists(tmp_in_path):
            os.unlink(tmp_in_path)

        _save_result(job_id, saida_bytes, filename=f"resultado_{filename}")

        # === Se quiser usar a Opção B (em memória), comente a A e descomente:
        # saida_bytes = _processar_com_sua_funcao_em_memoria(file_bytes)
        # _save_result(job_id, saida_bytes, filename=f"resultado_{filename}")

    except Exception as e:
        _set_job(job_id, state="FAILURE", error=str(e))

# ---------- endpoints AJAX ----------
@csrf_exempt
def upload(request):
    if request.method != "POST" or "file" not in request.FILES:
        return JsonResponse({"error": 'Envie um arquivo em form-data no campo "file"'}, status=400)

    f = request.FILES["file"]
    content = f.read()
    if not content:
        return JsonResponse({"error": "Arquivo vazio"}, status=400)

    job_id = str(uuid.uuid4())
    _set_job(job_id, state="PENDING", progress="0", original=f.name)

    threading.Thread(
        target=_processar_planilha, args=(job_id, content, f.name), daemon=True
    ).start()

    return JsonResponse({"job_id": job_id})

def status(request, job_id: str):
    data = _get_job(job_id)
    if not data:
        raise Http404("Job não encontrado")
    return JsonResponse(data)

def download(request, job_id: str):
    data = _get_job(job_id)
    if not data or data.get("state") != "SUCCESS":
        raise Http404("Resultado ainda não disponível")

    r = _get_redis()
    blob = r.get(f"file:{job_id}")
    if not blob:
        raise Http404("Resultado expirado")

    filename = data.get("filename", "resultado.xlsx")
    resp = HttpResponse(
        blob,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
