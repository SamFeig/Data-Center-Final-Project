#
# Worker server
#
import jsonpickle
import pickle
import platform
from PIL import Image
import io
import os
import sys
import pika
import redis
import hashlib
import time
import json

# Google Cloud Auth
import googleapiclient.discovery
import google.auth
import google.oauth2.service_account as service_account

import urllib.request
import urllib.error

from apiclient.http import MediaIoBaseDownload


import make_palette

hostname = platform.node()

CHUNKSIZE = 2 * 1024 * 1024
RETRYABLE_ERRORS = (urllib.error.HTTPError, IOError)

##
# Configure test vs. production
##
redisHost = os.getenv("REDIS_HOST") or "localhost"
rabbitMQHost = os.getenv("RABBITMQ_HOST") or "localhost"

print("Connecting to rabbitmq({}) and redis({})".format(rabbitMQHost, redisHost))


redisVidHashToImgHash = redis.Redis(host=redisHost, db=1, decode_responses=True)
redisImgHashToTimestamp = redis.Redis(host=redisHost, db=1, decode_responses=True)

def handle_progressless_iter(error, progressless_iters):
    if progressless_iters > 5:
        print('Failed to make progress for too many consecutive iterations.')
        raise error

    sleeptime = random.random() * (2**progressless_iters)
    print('Caught exception (%s). Sleeping for %s seconds before retry #%d.' %
          (str(error), sleeptime, progressless_iters))
    time.sleep(sleeptime)


def log(message, debug=False):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(rabbitMQHost))
    channel = connection.channel()
    channel.exchange_declare(exchange='logs', exchange_type='topic')

    routing_key = '%s.rest.%s' % (rabbitMQHost, 'debug' if debug else 'info')
    channel.basic_publish(
        exchange='logs', routing_key=routing_key, body=message)
    print(" [x] Sent %r:%r" % (routing_key, message))
    channel.close()
    connection.close()


def callback(ch, method, properties, body):
    data = jsonpickle.decode(body)
    print(" [x] Received %r" % data)

    name = data['name']
    frequency = int(float(data['frequency'])*1000)

    credentials = service_account.Credentials.from_service_account_file(
        filename='../service-credentials.json')
    project = os.environ["GCLOUD_PROJECT"] = "CSCI-4253"
    service = googleapiclient.discovery.build(
        'storage', 'v1', credentials=credentials)

    bucket_name = 'csci4253finalproject'
    vid_hash = data['hash']
    object_name = data['hash']
    filename = 'temp'
    f = open(filename, 'wb')

    request = service.objects().get_media(bucket=bucket_name, object=object_name)
    media = MediaIoBaseDownload(f, request, chunksize=CHUNKSIZE)
    print('Downloading bucket: %s object: %s to file: %s' %
          (bucket_name, object_name, filename))

    progressless_iters = 0
    done = False
    while not done:
        error = None
        try:
            progress, done = media.next_chunk()
            if progress:
                print('Download %d%%.' % int(progress.progress() * 100))
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
    print('\nDownload complete!')

    images = make_palette.mp4_to_images(filename, frequency)

    for index, image in enumerate(images):
        m = hashlib.sha256()
        m.update(bytes(image))
        img_hash = m.hexdigest()

        redisVidHashToImgHash.sadd(vid_hash, img_hash)
        
        print(vid_hash, img_hash)
        print(img_hash, frequency * index)
        redisImgHashToTimestamp.set(img_hash, frequency * index)

    f.close()
    os.remove(f.name)

    print(" [x] Done")
    ch.basic_ack(delivery_tag=method.delivery_tag)


connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=rabbitMQHost))
channel = connection.channel()

channel.queue_declare(queue='toWorker', durable=True)
print(' [*] Waiting for messages. To exit press CTRL+C')

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='toWorker', on_message_callback=callback)

channel.start_consuming()
