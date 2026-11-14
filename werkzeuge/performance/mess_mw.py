import time
from django.db import connection

class Zaehler:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        n0 = len(connection.queries)
        t0 = time.perf_counter()
        r = self.get_response(request)
        dt = (time.perf_counter() - t0) * 1000
        r["X-Mess-Q"] = str(len(connection.queries) - n0)
        r["X-Mess-Ms"] = f"{dt:.1f}"
        r["Access-Control-Expose-Headers"] = "X-Mess-Q, X-Mess-Ms"
        return r
