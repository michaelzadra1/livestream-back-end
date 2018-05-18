# -*- coding: utf-8 -*-

import os
import flask
import requests

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

from flask import request
from flask_cors import CORS

import urllib.request

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

CLIENT_SECRET =  "oNMHYzzTTEaAjV9sD-UVhNv1"
CLIENT_ID =  "747325281443-82qc3hh5t0br4941i8bpn56sjiffbt8p.apps.googleusercontent.com"

CREDENTIALS = {}
CREDENTIALS['token'] = "ya29.Glu_BeCYp4GykUyruASrdNzqfdHafBW87ZADMokuw5K7bUuAB-I3IHH6HBooWy8M_JUlhLijboO5uG-uoCSceTZqlEiOLy8KSpGmPJracJ-XHdcpmfEy7Hjzt6Fg"
CREDENTIALS['refresh_token'] = None
CREDENTIALS['token_uri'] = "https://accounts.google.com/o/oauth2/token"
CREDENTIALS['client_id'] = CLIENT_ID
CREDENTIALS['client_secret'] = CLIENT_SECRET
CREDENTIALS['scopes'] = SCOPES

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
  stream_details = {
    'channel_id': stream_object['items'][0]['snippet']['channelId'],
    'stream_title': stream_object['items'][0]['snippet']['title'],
    'stream_description': stream_object['items'][0]['snippet']['description'],
    'chat_id': chat_id
  }
  return stream_details

def build_api_service():
  credentials = google.oauth2.credentials.Credentials(**CREDENTIALS)
  youtube_service = googleapiclient.discovery.build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
  return youtube_service

@app.route('/stream/', methods=["GET","POST"])
def streams_request():
  # Get list of livestreams
  if request.method == "GET":
    youtube_service = build_api_service()
    live_streams = search_list_live_events(youtube_service,
          part='snippet',
          eventType='live',
          maxResults=25,
          q='lofi',
          type='video'
    )
    return flask.jsonify(live_streams['items'])
  
  # Get live stream details
  if request.method == "POST":
    youtube_service = build_api_service()
    video_id = request.data.decode('UTF-8')
    # Live stream
    stream_details = get_livestream_details(youtube_service, video_id)
    if not stream_details['chat_id']:
      chat_messages = None
    else:
      chat_messages = chats_list_by_id(youtube_service,
        liveChatId=stream_details['chat_id'],      
        part='id,snippet,authorDetails'
        #maxResults=250  
      )
    stream = {}
    stream['stream_details'] = stream_details
    stream['chat'] = chat_messages
    return flask.jsonify(stream)

@app.route('/refreshChat/', methods=["POST"])
def refresh_chat():
  if request.method == "POST":
    youtube_service = build_api_service()
    refresh_chat = request.get_json()

    chat_token = refresh_chat['chatToken']
    channel_id = refresh_chat['chatId']
    chat_messages = chats_list_by_id(youtube_service,
        liveChatId=channel_id,      
        part='id,snippet,authorDetails',
        pageToken=chat_token
    )
    return flask.jsonify(chat_messages)



if __name__ == '__main__':
  os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
  app.run()