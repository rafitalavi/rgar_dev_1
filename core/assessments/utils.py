
from rest_framework.response import Response

def ok(message="Success", data=None, status_code=200):
    return Response(
        {"success": True, "message": message, "errors": None, "data": data},
        status=status_code,
    )

def err(message="Invalid request", errors=None, status_code=400):
    return Response(
        {"success": False, "message": message, "errors": errors, "data": None},
        status=status_code,
    )

def flatten_serializer_errors(serializer_errors):
    
    msgs = []
    for v in serializer_errors.values():
        if isinstance(v, list):
            msgs.extend([str(x) for x in v])
        elif isinstance(v, dict):
            # nested errors
            msgs.extend(flatten_serializer_errors(v))
        else:
            msgs.append(str(v))
    return msgs


def serializer_error_response(serializer, status_code=400):
    msgs = flatten_serializer_errors(serializer.errors)
    return err(
        message=msgs[0] if msgs else "Invalid input",
        errors=serializer.errors,
        status_code=status_code,
    )
