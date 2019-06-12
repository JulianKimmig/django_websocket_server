i = -1
if __name__.split(".")[i] == "django_app":
    i = -2

default_app_config = (
    __name__
    + ".apps."
    + "".join(x.capitalize() or "_" for x in __name__.split(".")[i].split("_"))
    + "Config"
)