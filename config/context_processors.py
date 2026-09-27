from django.conf import settings


def data_mode(request):
    """For the band "Testsystem – nur erfundene Daten" in `base.html` (#26)."""
    return {"synthetic_data": settings.DATA_MODE == "synthetic"}
