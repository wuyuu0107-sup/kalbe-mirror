from django.http import JsonResponse
from django.middleware.csrf import get_token

def csrf(request):
    # sets 'csrftoken' cookie and also returns it in JSON
    return JsonResponse({"csrfToken": get_token(request)})