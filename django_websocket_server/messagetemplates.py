import json


def simple_message(sender, type="message", target="server", as_string=True, data=None):
    m = {
        "type": type,
        "data": data,
        "from": sender,
        "target": target if isinstance(target, list) else [target],
    }
    if as_string:
        return json.dumps(m)
    return m


def commandmessage(cmd, sender, target="server", as_string=True, *args, **kwargs):
    m = simple_message(
        sender,
        type="cmd",
        as_string=False,
        target=target,
        data={"cmd": cmd, "args": args, "kwargs": kwargs},
    )
    if as_string:
        return json.dumps(m)
    return m


def levelmessage(
    sender, content="", target="server", title="", level="info", as_string=True
):
    m = simple_message(
        sender,
        type="message",
        as_string=False,
        target=target,
        data={"content": content, "title": title, "level": level},
    )
    if as_string:
        return json.dumps(m)
    return m


def datapointmessage(sender, x, y, key, target="server", t=None, as_string=True):
    m = simple_message(
        sender,
        type="data",
        as_string=False,
        data={"key": key, "x": x, "y": y, "t": t},
        target=target,
    )
    if as_string:
        return json.dumps(m)
    return m
