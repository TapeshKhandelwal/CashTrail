import threading
from collections.abc import Callable
from typing import Any

from django.db import connection


def run_concurrently(*calls: Callable[[], Any]) -> list[Any]:
    """Start every call at the same moment, each on its own DB connection.

    Returns each call's result, or the exception it raised, in call order.
    """
    barrier = threading.Barrier(len(calls))
    results: list[Any] = [None] * len(calls)

    def worker(index: int, call: Callable[[], Any]) -> None:
        try:
            barrier.wait()
            results[index] = call()
        except Exception as exc:
            results[index] = exc
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=item) for item in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results
