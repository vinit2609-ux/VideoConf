from django.utils import timezone

class SessionDurationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        if request.user.is_authenticated and 'login_time' in request.session:
            login_time = request.session['login_time']
            duration_minutes = (timezone.now().timestamp() - login_time) /60
            request.session['session_duration'] = round(duration_minutes, 1)
        
        return response