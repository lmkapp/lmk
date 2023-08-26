"""
Patches for generated classes
"""
from functools import wraps

from lmk.generated.models.notification_channel_response_payload import (
    NotificationChannelResponsePayload,
)
from lmk.generated.models.email_channel_payload import EmailChannelPayload
from lmk.generated.models.notification_channel_response import (
    NotificationChannelResponse,
)
from lmk.generated.models.text_message_channel_payload import TextMessageChannelPayload


def unpatch():
    pass


def patch():
    """
    This method does not patch globals or do anything dangerous.
    It is patching the __repr__ methods for a few of the generated
    classes from the OpenAPI spec. Patching specific things
    seems more attractive maintaining the classes myself
    """
    global unpatch

    originals = {}

    def patch_method(cls, method):
        original = getattr(cls, method)
        originals.setdefault(cls, {})[method] = original

        def dec(func):
            wrapped = wraps(original)(func)
            setattr(cls, method, wrapped)
            return wrapped

        return dec

    @patch_method(NotificationChannelResponsePayload, "__repr__")
    def create_notification_channel_repr(self):
        return repr(self.actual_instance)

    @patch_method(EmailChannelPayload, "__repr__")
    def email_channel_payload_repr(self):
        fields = []
        for field_name in ["type", "email_address"]:
            fields.append(f"{field_name}={repr(getattr(self, field_name))}")
        return f"{type(self).__name__}({', '.join(fields)})"

    @patch_method(TextMessageChannelPayload, "__repr__")
    def text_message_payload_repr(self):
        fields = []
        for field_name in ["type", "phone_number"]:
            fields.append(f"{field_name}={repr(getattr(self, field_name))}")
        return f"{type(self).__name__}({', '.join(fields)})"

    @patch_method(NotificationChannelResponse, "__repr__")
    def notification_channel_response_repr(self):
        fields = []
        for field_name in ["name", "payload", "notification_channel_id", "is_default"]:
            fields.append(f"{field_name}={repr(getattr(self, field_name))}")
        return f"{type(self).__name__}({', '.join(fields)})"

    def unpatch():
        for cls, methods in originals.items():
            for name, value in methods.items():
                setattr(cls, name, value)
