import asyncio
import base64
import json
import logging
import os
import tempfile
import threading
import time
from logging.handlers import RotatingFileHandler

import websockets
from filter_dict import filter_dict

from .messagetemplates import commandmessage
SOCKETPORT = 8888

TEMPDIR = os.path.join(tempfile.gettempdir(), "SockerServer")
WEBSOCKET_SERVER_INSTANCES = []
class Connection:
    def __init__(self, ws, server,user_id,disable_encryption=False):
        self.disable_encryption = disable_encryption
        self.user_id = user_id
        self.server = server
        self.server.logger.debug("create connection")
        self.ws = ws
        self.identified = False
        self.name = "unknown"
        self.loop = asyncio.get_event_loop()
        self.public_key=None




    def ask_for_identification(self):
        self.server.logger.debug("ask for identification")
        self.sendMsg(commandmessage(sender="server", cmd="indentify"))

    def sendMsg(self, msg,encrypted=True):
        if self.disable_encryption:
            encrypted = False
        if encrypted:
            from nacl.public import Box
        if encrypted and not self.disable_encryption:
            if self.public_key is not None:
                from django_websocket_server.models import KeyChain
                private_key = KeyChain.objects.get(id=self.user_id).get_private_key()
                public_key = self.public_key

                bob_box = Box(private_key, public_key)
                msg = base64.b64encode(bytes(bob_box.encrypt(msg.encode('utf-8')))).decode("utf-8")
                msg = json.dumps({'encrypted':True,'msg':msg})
        coro = self.ws.send(msg)
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)

    async def recive(self):
        try:
            async for message in self.ws:
                self.validate_message(message)
                if not self.identified:
                    self.ask_for_identification()
        except asyncio.IncompleteReadError:
            pass

    def validate_message(self, msg):
        self.server.logger.debug(self.name + " recived message: " + msg)
        try:
            jmsg = json.loads(msg)
            if not self.identified:
                if "cmd" not in jmsg["data"]:
                    return
                if jmsg["data"]["cmd"] != "indentify":
                    return
            if "server" in jmsg["target"]:
                if jmsg["type"] == "cmd":
                    self.run_command(jmsg)
                elif jmsg["type"] == "data":
                    pass
                else:
                    self.server.logger.error("unknown message type " + msg)
            return self.server.send_to_names(jmsg["target"], msg)
        except:
            self.server.logger.exception(Exception)
            pass

    def run_command(self, data):
        cmd_data = data["data"]
        if cmd_data["cmd"] == "indentify":
            self.identify(data)
        else:
            self.server.run_cmd(cmd_data)

    def identify(self, data):
        if not self.disable_encryption:
            from nacl.public import PublicKey
        cmd_data = data["data"]
        try:
            self.name = cmd_data["kwargs"]["name"]
            print(cmd_data["kwargs"]["public_key"],len(cmd_data["kwargs"]["public_key"]))
            if not self.disable_encryption:
                self.public_key = PublicKey(bytes([int(x) for x in base64.b64decode(cmd_data["kwargs"]["public_key"]).decode('utf-8').split(',')]))
            self.identified = True
            self.sendMsg(
                commandmessage(sender="server", cmd="set_time", time=self.server.t0)
            )
        except Exception as e:
            self.server.logger.exception(e)



class SocketServer:
    def __init__(self, host="0.0.0.0", port=SOCKETPORT, local_connections_only=False, data_dir=None, logger=None,
                 wss=False,start_in_background=False,disable_encryption = False):
        self.disable_encryption = disable_encryption
        if local_connections_only:
            host = "127.0.0.1"

        if data_dir is None:
            data_dir = TEMPDIR
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        logging.getLogger("websocket").setLevel(logging.ERROR)
        logging.getLogger("asyncio").setLevel(logging.ERROR)
        logging.getLogger("asyncio.coroutines").setLevel(logging.ERROR)
        logging.getLogger("websockets.server").setLevel(logging.ERROR)
        logging.getLogger("websockets.protocol").setLevel(logging.ERROR)
        self.running = True
        self.all_connections = {}

        if logger is None:
            logger = logging.getLogger("sockerserver_" + str(host) + ":" + str(port))
            file_handler = RotatingFileHandler(
                os.path.join(self.data_dir, "".join(x for x in logger.name if x.isalnum()) + "_log.txt"), maxBytes=2 ** 16,
                backupCount=100)
            formatter = logging.Formatter(
                '%(asctime)s\t%(filename)s\t%(lineno)d\t%(name)s\t%(levelname)-8s\t%(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        self.logger = logger

        self.host = host
        self.port = port
        self.protocol = "wss:" if wss else "ws:"

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        ws_serv = websockets.serve(
            self.add_connection, host=host, port=port, max_size=2 ** 25
        )

        self._cmds = {}

        self.t0 = time.time()
        self.loop.run_until_complete(ws_serv)
        self.logger.info("Socket created at " + host + ":" + str(port))
        self.ws_server = ws_serv.ws_server

        if start_in_background:
            self.run_in_background()

    def send_to_names(self, names, message):
        while "server" in names:
            names.remove("server")
        reached = []
        for ws, c in self.all_connections.items():
            if c.name in names:
                reached.append(c.name)
                c.sendMsg(message)
        diff = set(names).difference(set(reached))
        if len(diff) > 0:
            self.logger.error("targets not found: " + ", ".join(diff))

    def send_to_all(self, message):
        for ws, c in self.all_connections.items():
            c.sendMsg(message)

    async def add_connection(self, ws, path):
        path=list(filter(None, path.split("/")))
        print(path)
        if ws not in self.all_connections:
            self.all_connections[ws] = Connection(ws, self,user_id=path[0],disable_encryption=self.disable_encryption)
            self.all_connections[ws].ask_for_identification()
        connection = self.all_connections[ws]
        try:
            while 1:
                await connection.recive()

        except Exception as e:
            self.logger.error("Conenction Error " + connection.name)
            self.logger.exception(e)
            del self.all_connections[ws]
            del connection

    def run_in_background(self):
        threading.Thread(target=self.run_forever).start()

    def run_forever(self):
        WEBSOCKET_SERVER_INSTANCES.append(self)
        self.loop.run_forever()

    def force_stop(self):
        self.loop.stop()
        for i in range(10):
            if not self.loop.is_running():
                break
            time.sleep(1)
        WEBSOCKET_SERVER_INSTANCES.remove(self)
        self.ws_server.close()

    def register_cmd(self, cmd, func):
        self._cmds[cmd] = self._cmds.get(cmd, []) + [func]

    def run_cmd(self, cmd_data):
        if cmd_data["cmd"] not in self._cmds:
            self.logger.error("unknown command: " + str(cmd_data["cmd"]))
            return

        for func in self._cmds[cmd_data["cmd"]]:
            func(**filter_dict(cmd_data.get('kwargs', {}), func))



def connect_to_first_free_port(startport=SOCKETPORT, **kwargs):
    notconnected = True
    socketserver = None

    while notconnected:
        try:
            socketserver = SocketServer(port=startport, **kwargs)
            notconnected = False
        except OSError as e:
            startport += 1
    return socketserver
