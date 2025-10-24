# projeto/views.py
import os, uuid, threading, io, time
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import redis

# Conecta no Render Key Value (Redis-compatível)
r = redis.from_url(os.environ["KV_URL"], decode_responses=False)  # binary-safe

def _set_job(job_id, **fields):
    r.hset(f"job:{job_id}", mapping={k: (str(v).encode() if isinstance(v, str) else v) for k, v in fields.items()})

def _get_job(job_id):
    raw = r.hgetall(f"job:{job_id}")
    return {k.decode(): v.decode() for k, v in raw.items()} if raw else None

def _save_result(job_id, content_bytes: bytes, filename: str, ttl_seconds: int = 3600):
    # Simples: guarda o binário no KV com TTL (1h)
    r.setex(f"file:{job_id}", ttl_seconds, content_bytes)
    _set_job(job_id, state="SUCCESS", filename=filename)

def _processar_planilha(job_id: str, file_bytes: bytes, filename: str):
    try:
        _set_job(job_id, state="STARTED", progress="0")
        # TODO: coloque aqui seu processamento real da planilha ----------------
        # Exemplo de “trabalho” com progresso:
        for pct in range(0, 101, 5):
            _set_job(job_id, progress=str(pct))
            time.sleep(1)  # simula trabalho; REMOVA no real
        resultado = file_bytes  # troque pelos bytes do Excel gerado
        # ---------------------------------------------------------------------
        _save_result(job_id, resultado, filename=f"resultado_{filename}")
    except Exception as e:
        _set_job(job_id, state="FAILURE", error=str(e))

def index(request):
    # Renderize seu template com o formulário de upload
    return render(request, 'index.html')

@csrf_exempt
def upload(request):
    if request.method != 'POST' or 'file' not in request.FILES:
        return JsonResponse({'error': 'Envie um arquivo em form-data com o campo "file"'}, status=400)
    f = request.FILES['file']
    content = f.read()
    if not content:
        return JsonResponse({'error': 'Arquivo vazio'}, status=400)
    job_id = str(uuid.uuid4())
    _set_job(job_id, state="PENDING", progress="0", original=f.name)
    threading.Thread(target=_processar_planilha, args=(job_id, content, f.name), daemon=True).start()
    return JsonResponse({'job_id': job_id})

def status(request, job_id: str):
    data = _get_job(job_id)
    if not data:
        raise Http404("Job não encontrado")
    return JsonResponse(data)

def download(request, job_id: str):
    data = _get_job(job_id)
    if not data or data.get("state") != "SUCCESS":
        raise Http404("Resultado ainda não disponível")
    blob = r.get(f"file:{job_id}")
    if not blob:
        raise Http404("Resultado expirado")
    filename = data.get("filename", "resultado.xlsx")
    resp = HttpResponse(blob, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
