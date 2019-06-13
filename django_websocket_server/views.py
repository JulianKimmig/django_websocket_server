import base64

from django.http import JsonResponse

from .models import KeyChain


def authenticate(request,port=None):
    ws_server = None
    from . websocket_server import WEBSOCKET_SERVER_INSTANCES
    if len(WEBSOCKET_SERVER_INSTANCES) == 0:
        return JsonResponse({'sucess':False})
    if port is None:
        ws_server = WEBSOCKET_SERVER_INSTANCES[-1]

    if ws_server is None:
        return
    try:
        key_model, new = KeyChain.objects.get_or_create(user = request.user)
        key =  key_model.refresh()
        public_key = key_model.get_public_key_base64()
    except:
        public_key = None
    return JsonResponse({'public_key':public_key,'ws_protocol':ws_server.protocol,'ws_port':ws_server.port,'success':True,'user': request.user.id})