# projeto/app/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
import os
import traceback

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "1234")

def index(request):
    return redirect('login')

def login_view(request):
    try:
        if request.method == 'POST':
            usuario = request.POST.get('usuario', '').strip()
            senha   = request.POST.get('senha', '').strip()

            print("DEBUG LOGIN POST:", {"usuario": usuario, "tem_senha": bool(senha)})

            if usuario == ADMIN_USER and senha == ADMIN_PASS:
                request.session['usuario'] = usuario
                return redirect('upload_page')

            # mostra UMA mensagem só
            storage = messages.get_messages(request)
            for _ in storage:
                pass
            messages.error(request, 'Usuário ou senha incorretos')

        return render(request, 'login.html')
    except Exception as e:
        # loga stacktrace no Live Tail e mostra erro amigável
        print("LOGIN ERROR:", e)
        traceback.print_exc()
        storage = messages.get_messages(request)
        for _ in storage:
            pass
        messages.error(request, 'Erro inesperado ao autenticar.')
        return render(request, 'login.html')

def upload_page(request):
    if not request.session.get('usuario'):
        return redirect('login')
    return render(request, 'upload.html')
