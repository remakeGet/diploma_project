from rest_framework.throttling import SimpleRateThrottle

class RegisterThrottle(SimpleRateThrottle):
    """
    Тротлинг для регистрации - 5 попыток в час с одного IP
    """
    scope = 'register'
    rate = '1/minute'  # Временно для теста
    
    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        print(f"RegisterThrottle: ident={ident}")
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

class LoginThrottle(SimpleRateThrottle):
    """
    Тротлинг для входа - 10 попыток в минуту с одного IP
    """
    scope = 'login'
    rate = '1/minute'  # Временно для теста
    
    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        print(f"LoginThrottle: ident={ident}")
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

class ImportThrottle(SimpleRateThrottle):
    """
    Тротлинг для импорта товаров - 10 раз в день для магазина
    """
    scope = 'import'
    rate = '1/day'  # Временно для теста
    
    def get_cache_key(self, request, view):
        if request.user.is_authenticated and request.user.type == 'shop':
            ident = f"user_{request.user.pk}"
            print(f"ImportThrottle: ident={ident}")
            return self.cache_format % {
                'scope': self.scope,
                'ident': ident
            }
        return None