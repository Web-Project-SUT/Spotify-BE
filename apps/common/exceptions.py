from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    fields = None
    if isinstance(detail, dict):
        message = detail.get("detail")
        if message is None:
            fields = detail
            message = "Validation failed."
    elif isinstance(detail, list):
        message = detail[0] if detail else "Error."
    else:
        message = str(detail)

    code = getattr(exc, "default_code", None) or "error"
    if hasattr(exc, "get_codes"):
        codes = exc.get_codes()
        if isinstance(codes, dict):
            code = next(iter(codes.values()), code)
            if isinstance(code, list):
                code = code[0] if code else "error"
        elif isinstance(codes, list):
            code = codes[0] if codes else code
        else:
            code = codes

    response.data = {"detail": str(message), "code": code, "fields": fields}
    return response
