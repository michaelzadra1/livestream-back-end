# -*- coding: utf-8 -*-

import os
import flask
import requests
import threading

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

from googleapiclient.discovery import build

import oauth2client
import httplib2

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from flask import request
from flask_cors import CORS

import urllib.request


SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

CLIENT_SECRET =  "oNMHYzzTTEaAjV9sD-UVhNv1"
CLIENT_ID =  "747325281443-82qc3hh5t0br4941i8bpn56sjiffbt8p.apps.googleusercontent.com"

CREDENTIALS = {}
CREDENTIALS['auth_token'] = "ya29.GlvBBb0snrTypKUZ_62QZF-kOk6UVsSJIf8JH67IV3f-6lLYNlJVUdDgdNuiMf3KO0jCKDgCQGy6aFEaLxDjxiUvVMpBiYVCW5eJq-TUjUVyUM15ibiiceYaGWl4"
CREDENTIALS['refresh_token'] = "1/6LFPhvU94uv4DKIS2KnrLhxMCsuQcqSyyzqpZKr9US0"
CREDENTIALS['token_uri'] = "https://accounts.google.com/o/oauth2/token"
CREDENTIALS['client_id'] = CLIENT_ID
CREDENTIALS['client_secret'] = CLIENT_SECRET
CREDENTIALS['scopes'] = SCOPES

# Firebase Database
cred = credentials.Certificate('firebase_client.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# YouTube API
creds = oauth2client.client.GoogleCredentials(
  CREDENTIALS['auth_token'],
  CREDENTIALS['client_id'],
  CREDENTIALS['client_secret'],
  CREDENTIALS['refresh_token'],
  "",
  CREDENTIALS['token_uri'],
  ""
)
youtube_service = build(API_SERVICE_NAME, API_VERSION, credentials=creds)


app = flask.Flask(__name__)
CORS(app)


def remove_empty_kwargs(**kwargs):
  good_kwargs = {}
  if kwargs is not None:
    for key, value in kwargs.items():
      if value:
        good_kwargs[key] = value
  return good_kwargs

def search_list_live_events(client, **kwargs):
  kwargs = remove_empty_kwargs(**kwargs)
  response = client.search().list(
    **kwargs
  ).execute()
  return response

def videos_list_by_id(client, **kwargs):
  kwargs = remove_empty_kwargs(**kwargs)
  response = client.videos().list(
    **kwargs
  ).execute()
  return response

def chats_list_by_id(client, **kwargs):
  kwargs = remove_empty_kwargs(**kwargs)
  response = client.liveChatMessages().list(
    **kwargs
  ).execute()
  return response

def get_livestream_details(youtube_service, video_id):
  stream_object = videos_list_by_id(youtube_service,
    part='snippet,liveStreamingDetails',
    id=video_id
  )
  # Try to get chat ID
  chat_id = None
  try:
    chat_id = stream_object['items'][0]['liveStreamingDetails']['activeLiveChatId']
  except:
    pass
  # Create stream details object for front end
  try:
    stream_details = {
      'channel_id': stream_object['items'][0]['snippet']['channelId'],
      'stream_title': stream_object['items'][0]['snippet']['title'],
      'stream_description': stream_object['items'][0]['snippet']['description'],
      'chat_id': chat_id
    }
  except:
    stream_details = None
  return stream_details

def refresh_creds():
  # Refresh token every 30 minutes to prevent expiration
  threading.Timer(3500, refresh_creds).start()
  http = creds.authorize(httplib2.Http())
  creds.refresh(http)
  youtube_service = build(API_SERVICE_NAME, API_VERSION, credentials=creds)

def firebase_store_chats(messages): 
  batch = db.batch()
  
  for message in messages:
    message_user_id = message['authorDetails']['channelId']
    message_id = message['id'].replace('.', '-') #firebase can't handle periods in keys
    data = {
      message_id: {
        "message_text": message['snippet']['displayMessage'],
        "message_username": message['authorDetails']['displayName'],
        "chat_id": message['snippet']['liveChatId'],
      }
    }
    # Update batch object
    ref = db.collection(u'messages').document(message_user_id)
    batch.update(ref, data, firestore.CreateIfMissingOption(True))

  batch.commit()

@app.before_first_request
def start_refresh_poll():
  refresh_creds()

@app.route('/user/', methods=["POST"])
def get_user_chats():
  # Gets livestream properties
  if request.method == "POST":
    user_id = request.data.decode('UTF-8')
    ref = db.collection('messages').document(user_id)
    message_details = []    
    try:
      messages = ref.get().to_dict()
      for key, value in messages.items():
        message_details.append(value)
    except google.cloud.exceptions.NotFound:
      pass
  return flask.jsonify(message_details)


@app.route('/stream/', methods=["GET","POST"])
def streams_request():

  # Loads list of livestreams
  if request.method == "GET":
    live_streams = search_list_live_events(youtube_service,
          part='snippet',
          eventType='live',
          maxResults=25,
          q='lofi',
          type='video'
    )
    return flask.jsonify(live_streams['items'])
  
  # Gets livestream properties
  if request.method == "POST":
    video_id = request.data.decode('UTF-8')

    stream_details = get_livestream_details(youtube_service, video_id)
    if not stream_details:
      return flask.jsonify(None)
    # Fetch chat messages for stream
    if not stream_details['chat_id']:
      chat_messages = None
    else:
      chat_messages = chats_list_by_id(youtube_service,
        liveChatId=stream_details['chat_id'],      
        part='id,snippet,authorDetails',
      )
      # Store messages in database
      firebase_store_chats(chat_messages['items'])
    
    # Return strem details and chat details to front-end
    stream = {}
    stream['stream_details'] = stream_details
    stream['chat'] = chat_messages

    return flask.jsonify(stream)

# Refreshes a chat given a token for the chat
@app.route('/refreshChat/', methods=["POST"])
def refresh_chat():
  if request.method == "POST":
    refresh_chat = request.get_json()

    chat_token = refresh_chat['chatToken']
    channel_id = refresh_chat['chatId']

    chat_messages = chats_list_by_id(youtube_service,
        liveChatId=channel_id,      
        part='id,snippet,authorDetails',
        pageToken=chat_token
    )
    # Store new messages in database
    firebase_store_chats(chat_messages['items'])

    return flask.jsonify(chat_messages)

if __name__ == '__main__':
  os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
  app.run()
  