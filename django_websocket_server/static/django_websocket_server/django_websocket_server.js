if(typeof logger === "undefined")
    logger = console;

var wscs={
    ws:null,
    server_key: null,
    RECONNECT_TIME: 10000,
    reconnect_timer: null,
    websocket_connect(url) {
        if(this.ws!==null)
            this.ws.close();

        if(this.reconnect_timer){
            clearTimeout(this.reconnect_timer);
            this.reconnect_timer = null;
        }

        this.ws = new WebSocket(url);
        this.ws.onopen = function() {
            for(let i=0;i<this.on_connect_functions.length;i++) {
                this.on_connect_functions[i]();
            }
        }.bind(this);

        this.ws.onmessage = function(e) {
            try {
                var data = JSON.parse(e.data);
                if(data.encrypted) {
                    console.log(wscs.server_key, wscs.keys.privateKey);
                    data = sodium.crypto_box_seal_open(
                        Uint8Array.from(atob(data.msg), c => c.charCodeAt(0)), wscs.server_key, wscs.keys.privateKey
                    );
                }
                if(typeof this.type_function[data.type] !== "undefined")
                    this.type_function[data.type](data);
                else logger.warn('Unknown command type:', data.type, data);
            }catch(err) {
                logger.debug('Message:', e.data);
                logger.debug(err);
            }
        }.bind(this);

        this.ws.onclose = function(e) {
            logger.info('Socket is closed. Reconnect will be attempted in '+(this.RECONNECT_TIME/1000.0)+' second.', e.reason);
            this.reconnect_timer=setTimeout(function() {
                this.websocket_connect(url);
            }.bind(this), this.RECONNECT_TIME);
        }.bind(this);

        this.ws.onerror = function(err) {
            logger.error('Socket encountered error: ', err.message, 'Closing socket');
            this.ws.close();
        }.bind(this);
    },


    identify_functions :[],
    identified:false,
    type_function:{},

    cmd_functions:{"disconnect":function(data){this.ws.close()}.bind(this)},
    on_connect_functions:[],
    simple_message(sender, type="message", target="server", as_string=true, data=null) {
        m = {
            "type": type,
            "data": data,
            "from": sender,
            "target": Array.isArray(target)?target:[target],
        };
        if(as_string){
            return JSON.stringify(m);
        }
        return m
    },
    commandmessage(cmd, sender, target="server", as_string=true, args = [], kwargs={}){
        m = this.simple_message(
            sender,
            "cmd",
            target,
            false,
            data={"cmd": cmd, "args": args, "kwargs": kwargs},
        );
        if(as_string){
            return JSON.stringify(m);
        }
        return m
    },
    parse_socket_command(data) {
        var cmd = data.data;
        logger.debug('Command:', cmd);
        if(typeof this.cmd_functions[cmd.cmd] !== "undefined"){
            this.cmd_functions[cmd.cmd](data);
        }
        else logger.warn('Unknown command:',cmd.cmd);
    },

    add_on_connect_function(ocf) {
        this.on_connect_functions.push(ocf)
    },
    add_on_indentify_function(func) {
        this.identify_functions.push(func)
    },
    add_cmd_funcion(name,callback){
        this.cmd_functions[name]=callback;
    },
    add_type_funcion(name,callback){
        this.type_function[name]=callback;
    },
    send(data){
        logger.debug(data);
        this.ws.send(data)
    },
};

wscs.add_type_funcion('cmd', wscs.parse_socket_command.bind(wscs));









$.getJSON( window.location.protocol + "//" + window.location.host + "/django_websocket_server/authenticate", function( data ) {
    if(!data.success)
        return;
    if(data.ws_protocol !== undefined && data.ws_port !== undefined && data.user !== undefined) {

        wscs.server_key = data.public_key === null?null:Uint8Array.from(atob(data.public_key), c => c.charCodeAt(0));
        wscs.websocket_connect(data.ws_protocol+"//"+ window.location.hostname+":"+data.ws_port+"/"+data.user);
    }

});



wscs.add_cmd_funcion("indentify", function (data) {
    wscs.keys=sodium.crypto_box_keypair();
    wscs.ws.send(wscs.commandmessage(cmd = "indentify", sender = "gui", "server", true, [], {name: "gui",public_key:btoa(wscs.keys.publicKey)}));
    wscs.identified=true;
    let t=new Date().getTime();
    while (new Date().getTime()-t<1000){}
    for (let i=0;i<wscs.identify_functions.length;i++){
        wscs.identify_functions[i]();
    }
}.bind(wscs));

wscs.add_cmd_funcion("set_time", function (data) {
    wscs.global_t = data.data.kwargs.time
}.bind(wscs));
wscs.add_cmd_funcion("password_reset", function (data) {
    location.reload();
}.bind(wscs));

