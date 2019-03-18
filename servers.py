# -*- coding:utf-8 -*-
from tornado.web import url, Application
from tornado.web import RequestHandler
from tornado.websocket import WebSocketHandler
import tornado.ioloop
import tornado.httpserver
import os
import json
import random
import string

BASE_DIR = os.path.dirname(__file__)
setting = {
    'debug': True,
    'static_path': os.path.join(BASE_DIR, 'static'),
    'template_path': os.path.join(BASE_DIR, 'templates'),
}

USER_SET = {}  # 注册的用户信息 {id(WS): {name:'随机用户名', img:'https://www.baidu.com', socket:WS, ip:''}}

# 一波头像 http://www.gpqqtx.com/uploads/allimg/150925/0041205560-0.jpg
HEAD_IMG_LIST = ['0041205560-0.jpg', '0041202H4-1.jpg', '00412033W-2.jpg', '0041202249-3.jpg', '41205622-4.jpg',
                 '0041204517-5.jpg', 'http://www.gpqqtx.com/uploads/allimg/150925/004120O44-6.jpg']


class IndexHandler(RequestHandler):

    def get(self, *args, **kwargs):
        self.render('index.html')


class CliendSocket(WebSocketHandler):

    def __init__(self, application, request, **kwargs):
        super(CliendSocket, self).__init__(application, request, **kwargs)

    def open(self, *args, **kwargs):
        print('客户端连接过来了', args, kwargs, self.request.remote_ip)

    def on_message(self, message):
        """
        消息类型：
        USER_SET[key] = {'socket': self, 'ip': ip, 'img': img, 'public_key': public_key}
        {msgType:1, node:'客户端向服务器发送公钥进行注册!', data:{publicKey:{h: h, e: e, f: f, p: p}}}
             {'msgType': 2, 'node': '注册成功，服务端返回注册信息以及其他在线用户给客户端','data': {'userInfo': {'userId': key, 'ip': ip, 'img': img},'otherUser':[{'ip': value['ip'], 'img': value['img'], 'userId': key}]}}
             {msgType:3, node:'服务器向在线用户发送新注册的用户信息！', data:{'userId': key, 'ip': ip, 'img': img}}
             {'msgType':4, 'node':'服务器向在线用户发送用户离线信息', 'data':userId}
        {msgType:5, node:'服客户端向服务器索要指定用户的公钥', data:{userId: userId}};
            {msgType:6, node:'服务器向客户端发送指定用户的公钥', data:{publicKey:{h: h, e: e, f: f, p: p}}};
        {msgType: 7, node: '客户端发送给加密数据给指定的联系人', data: {toUserId: userId, msg: msg}}
            {msgType: 8, node: '中专客户端消息，', data: {recvUserId: userId, msg: msg}}
        {msgType: 9, node: '客户端给指定用户发送文件消息', data: {toUserId: userId, filename: filename, filetext:filetext}};

        """
        print('客户端发送过来的消息:', message)

        recv_message = json.loads(message)  # 客户端发送过来的数据

        send_data = ''  # 需要发送给客户端的数据

        msg_type = recv_message['msgType']
        # 客户端是来进行注册的
        if msg_type == 1:
            # 生成注册信息
            public_key = recv_message['data']['publicKey']
            key = str(id(self))
            ip = self.request.remote_ip
            img = '/static/img/%s.jpg' % random.choice(random.choice(list(string.ascii_lowercase[:12])))

            USER_SET[key] = {'socket': self, 'ip': ip, 'img': img, 'public_key': public_key}
            # 注册信息发送给客户端
            send_data = {
                'msgType': 2, 'node': '注册成功，服务端返回注册信息以及其他在线用户给客户端',
                'data': {
                    'userInfo': {'userId': key, 'ip': ip, 'img': img},
                    'otherUser': []
                }
            }
            for key, value in USER_SET.items():
                if key != str(id(self)):
                    send_data['data']['otherUser'].append({'ip': value['ip'], 'img': value['img'], 'userId': key})
                    # 向此用户发送新注册的用户

                    # {'msgType':3, 'node':'服务器向在线用户发送新注册的用户信息！', data:send_data['data']['userInfo']}
                    value['socket'].write_message(
                        json.dumps(
                            {
                                'msgType': 3, 'node': '服务器向在线用户发送新注册的用户信息！',
                                'data': [send_data['data']['userInfo']]
                            }
                        )
                    )

            self.write_message(json.dumps(send_data))
        # 客户端是来索要公钥的
        elif msg_type == 5:
            user_id = recv_message['data']['userId']
            user_obj = USER_SET.get(str(user_id))
            if user_obj:
                public_key = user_obj['public_key']
                send_data = {'msgType': 6, 'node': '服务器向客户端发送指定用户的公钥', 'data': {'publicKey': public_key}}
                self.write_message(json.dumps(send_data))
        # 客户端给另一个客户端发送消息
        elif msg_type == 7:
            to_userid = recv_message['data']['toUserId']
            msg = recv_message['data']['msg']
            socket = USER_SET[str(to_userid)]['socket']
            send_data = {'msgType': 8, 'node': '服务器向客户端发送指定用户的公钥', 'data': {'recvUserId': str(id(self)), 'msg': msg}}
            socket.write_message(json.dumps(send_data))
        elif msg_type == 9:
            to_userid = recv_message['data']['toUserId']
            socket = USER_SET[str(to_userid)]['socket']
            filename = recv_message['data']['filename']
            filetext = recv_message['data']['filetext']
            send_data = {'msgType': 10, 'node': '服务器转发文件消息', 'data': {'recvUserId': str(id(self)), 'filename': filename, 'filetext': filetext}}
            socket.write_message(json.dumps(send_data))

    def check_origin(self, origin):
        # 是否允许跨域请求
        return True

    def on_close(self):
        key = str(id(self))
        print('客户端走了:', USER_SET.pop(key))
        for k, value in USER_SET.items():
            value['socket'].write_message(json.dumps({'msgType': 4, 'node': '服务器向在线用户发送用户离线信息', 'data': key}))


class FileHandeler(RequestHandler):

    def post(self, *args, **kwargs):
        print(dir(self.request.files))
        print(self.request.files)
        self.write('ok')


urls = [
    url(r'^/$', IndexHandler, name='index'),
    url(r'^/client$', CliendSocket, name='client'),
    url(r'^/handelfile$', FileHandeler, name='handelfile'),
]

app = Application(urls, **setting)

if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(app, xheaders=True)
    http_server.listen(8888)
    http_server.start()
    tornado.ioloop.IOLoop.current().start()
