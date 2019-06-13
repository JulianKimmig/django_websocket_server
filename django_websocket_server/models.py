import base64

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class KeyChain(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    private_key = models.TextField()


    def get_public_key(self):
        return self.get_private_key().public_key

    def get_public_key_base64(self):
        return base64.b64encode(bytes(self.get_public_key())).decode("utf-8")

    def get_private_key(self):
        from nacl.public import PrivateKey
        return PrivateKey(base64.b64decode(self.private_key.encode("utf-8")))

    def set_private_key(self,key):
        self.private_key = base64.b64encode(bytes(key)).decode("utf-8")
        self.save()

    def refresh(self):
        from nacl.public import PrivateKey
        key = PrivateKey.generate()
        self.set_private_key(key)
        return key

    def decrypt(self,encrypted,public_key):
        from nacl.public import Box
        key = self.private_key
        box = Box(key, public_key)
        return box.decrypt(encrypted)


def key_delete(sender, user, **kwargs):
    try:
        user.keychain.delete()
    except ObjectDoesNotExist: pass
    except AttributeError: pass


user_logged_in.connect(key_delete)
user_logged_out.connect(key_delete)