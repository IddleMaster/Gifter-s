from django.conf import settings

def firebase_ctx(_request):
    return {
        "FB": {
            "WEB_CONFIG": settings.FIREBASE.get("WEB_CONFIG", {}),
            "VAPID_PUBLIC_KEY": settings.FIREBASE.get("VAPID_PUBLIC_KEY", ""),
        }
    }
