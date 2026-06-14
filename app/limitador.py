from slowapi import Limiter
from slowapi.util import get_remote_address

# Limiter global — identifica o cliente pelo IP
limitador = Limiter(key_func=get_remote_address)