from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from .tasks import process_planilha
from celery.result import AsyncResult

def upload_file(request):
    if request.method == "POST" and request.FILES.get("file"):
        file_bytes = request.FILES["file"].read()
        task = process_planilha.delay(file_bytes)
        return JsonResponse({"task_id": task.id, "status": "processing"})
    return render(request, "upload.html")

def check_status(request, task_id):
    task = AsyncResult(task_id)
    if task.state == "SUCCESS":
        file_bytes = task.result
        response = HttpResponse(file_bytes, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response['Content-Disposition'] = 'attachment; filename="consulta_simples.xlsx"'
        return response
    return JsonResponse({"status": task.state})
