from django.db import DatabaseError, connection
from django.shortcuts import render


def home(request):
    """Placeholder start page; shows that app and database are running (#4).

    The content pages (#6) replace it.
    """
    try:
        connection.ensure_connection()
        database_ok = True
    except DatabaseError:
        database_ok = False
    return render(
        request,
        "home.html",
        {"database_ok": database_ok},
        status=200 if database_ok else 503,
    )
