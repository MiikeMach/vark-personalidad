from django.middleware.clickjacking import XFrameOptionsMiddleware


class AdminPopupXFrameOptionsMiddleware(XFrameOptionsMiddleware):
    def process_response(self, request, response):
        if request.path.startswith("/admin/") and (
            request.GET.get("_popup") == "1" or request.path == "/admin/login/"
        ):
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            return response
        return super().process_response(request, response)
