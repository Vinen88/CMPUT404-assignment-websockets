#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()        
clients = list()

def set_listener( entity, data ):
    ''' do something with the update ! '''
    world = dict()
    world[str(entity)] = data
    for client in clients:
        client.put(json.dumps(world)) 


myWorld.add_set_listener( set_listener )

#Abram Hindle
#https://github.com/abramhindle/WebSocketsExamples/blob/547b31b1a6873dd67dc5a4a44cbed0a2003d7811/chat.py


def send_all(msg):
    for client in clients:
        client.put( msg )

def send_all_json(obj):
    send_all( json.dumps(obj) )

class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return flask.redirect("/static/index.html")

#Abram Hindle
#https://github.com/abramhindle/WebSocketsExamples/blob/master/chat.py
def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    #print("Entered Read_WS")
    try:
        while True:
            msg = ws.receive()
            print("WS RECV: %s" % msg)
            if (msg is not None):
                packet = json.loads(msg)
                for entity, data in packet.items():
                    myWorld.set(entity, data)
                #ent_id = list(packet.keys())[0]
                #myWorld.set(ent_id, packet[ent_id])
                #send_all_json(packet)
            else:
                break
    except:
        '''Done'''
    return None

#Abram Hindle
#https://github.com/abramhindle/WebSocketsExamples/blob/master/chat.py
@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    #print("ENTERED_FIRST")
    client = Client()
    clients.append(client)
    g = gevent.spawn( read_ws, ws, client )
    #print("ENTERED")
    ws.send(json.dumps(myWorld.world()))  #need the current world!
    try:
        while True:
            # block here
            msg = client.get()
            ws.send(msg)
    except Exception as e:# WebSocketError as e:
        print("WS Error %s" % e)
    finally:
        clients.remove(client)
        gevent.kill(g)


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])

#following functions were taken from my assignment 4 and updated
@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    data = flask_post_json()
    for key, value in data.items():
        myWorld.update(entity, key, value)
    ret_value = myWorld.get(entity)
    #send_all_json(ret_value) #maybe? will see if this works can always be lazy again and send the whole world
    return json.dumps(ret_value), 200 #shouldnt even have to use this?

@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    if request.method == 'POST':
        data = flask_post_json()
        myWorld.clear()
        for key, value in data.items():
            for k, v in value.items():
                myWorld.update(key, k, v)
    #send_all_json(myWorld.world)
    return json.dumps(myWorld.world()), 200

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    return json.dumps(myWorld.get(entity)), 200


@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    #send_all_json(myWorld.world()) #its cleared gotta update clients
    return json.dumps(myWorld.world()), 200



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
