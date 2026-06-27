from slowapi import Limiter
from slowapi.util import get_remote_address

# Limiter global — identifica o cliente pelo IP.
# default_limits vale pra TODO endpoint que não tem um @limitador.limit(...)
# próprio (os 5 de autenticação já tinham limites mais estritos definidos
# antes) — funciona como rede de segurança contra abuso/scraping no resto
# da API, que hoje não tinha limite nenhum.
limitador = Limiter(key_func=get_remote_address, default_limits=["100/minute"])