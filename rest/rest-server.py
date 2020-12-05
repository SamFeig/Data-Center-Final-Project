##
from flask import Flask, request, Response
import jsonpickle, pickle
import platform
import io, os, sys
import pika, redis
import hashlib, requests

#S3
#from froala_editor import File
#from froala_editor import FlaskAdapter

#Google Cloud Storage
from gcloud import storage
from apiclient.discovery import build as discovery_build
from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload, MediaIoBaseUpload
from apiclient.http import MediaIoBaseDownload
from json import dumps as json_dumps
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage as CredentialStorage
from oauth2client.tools import run_flow as run_oauth2

import googleapiclient.discovery
import google.auth
import google.oauth2.service_account as service_account

import urllib.request
import urllib.error



##
## Configure test vs. production
##
redisHost = os.getenv("REDIS_HOST") or "localhost"
rabbitMQHost = os.getenv("RABBITMQ_HOST") or "localhost"
print("Connecting to rabbitmq({}) and redis({})".format(rabbitMQHost,redisHost))

credentials = service_account.Credentials.from_service_account_file(filename='service-credentials.json')
project = os.environ["GCLOUD_PROJECT"] = "CSCI-4253"
service = googleapiclient.discovery.build('storage', 'v1', credentials=credentials)

# Retry transport and file IO errors.
RETRYABLE_ERRORS = (urllib.error.HTTPError, IOError)
# Number of times to retry failed downloads.
NUM_RETRIES = 5
# Number of bytes to send/receive in each request.
CHUNKSIZE = 2 * 1024 * 1024
# Mimetype to use if one can't be guessed from the file extension.
DEFAULT_MIMETYPE = 'application/octet-stream'

# Initialize the Flask application
app = Flask(__name__)

##
## You provide this
##
def log(message, debug=False):
    connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitMQHost))
    channel = connection.channel()
    channel.exchange_declare(exchange='logs', exchange_type='topic')

    routing_key = '%s.rest.%s'% (rabbitMQHost, 'debug' if debug else 'info')
    channel.basic_publish(exchange='logs', routing_key=routing_key, body=message)
    print(" [x] Sent %r:%r" % (routing_key, message))
    channel.close()
    connection.close()

def sendToWorker(message):
    connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitMQHost))
    channel = connection.channel()
    channel.queue_declare(queue='topic', durable=True)

    channel.basic_publish(
        exchange='',
        routing_key = 'toWorker',
        body=jsonpickle.encode(message),
        properties=pika.BasicProperties(delivery_mode=2))
    channel.close()
    connection.close()

def handle_progressless_iter(error, progressless_iters):
  if progressless_iters > NUM_RETRIES:
    log('ERROR:Failed to make progress for too many consecutive iterations.')
    raise error

  sleeptime = random.random() * (2**progressless_iters)
  log('Caught exception (%s). Sleeping for %s seconds before retry #%d.'
         % (str(error), sleeptime, progressless_iters))
  time.sleep(sleeptime)

def print_with_carriage_return(s):
  sys.stdout.write('\r' + s)
  sys.stdout.flush()


###REST API ROUTES###

@app.route('/', methods=['GET'])
def hello():
    return '<h1> Movie Color Palette Picker Server</h1><p> Use a valid endpoint </p>'

@app.route('/upload/<filename>' , methods=['POST'])
def uploadImage(filename):
    log("Attempting API request on /upload/%s" % (filename), True)

    file = request.data
    #print(type(file))
    file_type = request.headers['Content-Type']
    freq = int(request.headers['Frequency'])
    #print(request.headers)
    m = hashlib.sha256()
    m.update(file)

    #Save file to Google bucket
    bucket_name = 'csci4253finalproject'
    object_name = m.hexdigest()

    media = MediaIoBaseUpload(io.BytesIO(file), file_type, chunksize=CHUNKSIZE, resumable=True)
    if not media.mimetype():
        media = MediaIoBaseUpload(io.BytesIO(file), DEFAULT_MIMETYPE, chunksize=CHUNKSIZE, resumable=True)
    request1 = service.objects().insert(bucket=bucket_name, name=object_name, media_body=media)

    log('Uploading file: %s to bucket: %s object: %s ' % (filename, bucket_name, object_name))

    progressless_iters = 0
    response1 = None
    while response1 is None:
        error = None
        try:
            progress1, response1 = request1.next_chunk()
            if progress1:
                print_with_carriage_return('Upload %d%%' % (100 * progress1.progress()))
        except urllib.error.HTTPError as err:
            error = err
            if err.resp.status < 500:
                raise
        except RETRYABLE_ERRORS as err:
            error = err

        if error:
            progressless_iters += 1
            handle_progressless_iter(error, progressless_iters)
        else:
            progressless_iters = 0
    print('\n')
    log('Upload complete!')

    #Return Hash to client and send to worker
    response = { 
        "hash" : m.hexdigest()
    }
    response_pickled = jsonpickle.encode(response)
    sendToWorker({ 'hash' : m.hexdigest(), 'name' : filename, 'frequency' : freq})#, 'image' : file})

    log('POST /upload/%s HTTP/1.1 200' % (filename), True)
    return Response(response=response_pickled, status=200, mimetype="application/json")

@app.route('/palette/<hash>' , methods=['GET'])
def matchHash(hash):
    redisHashToHashSet = redis.Redis(host=redisHost, db=4, decode_responses=True)

    response = { 
        "match" : list(redisHashToHashSet.smembers(hash))
    }

    response_pickled = jsonpickle.encode(response)

    log('GET /palette/%s HTTP/1.1 200' % (hash), True)
    return Response(response=response_pickled, status=200, mimetype="application/json")


# start flask app
app.run(host="0.0.0.0", port=5000)
