from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.shortcuts import render_to_response, redirect

def server_error(request):
    """
    Custom HTTP 500 handler which includes MEDIA_URL, etc.
    Must be careful not to include anything in any way fragile.
    """
    # don't risk running context processors
    context = dict(settings.TEMPLATE_CONSTANTS)
    context['MEDIA_URL'] = settings.MEDIA_URL
    return render_to_response('500.html', context)

def logout(request):
    auth_logout(request)
    messages.success(request, 'You are now logged out')
    return redirect('/')
