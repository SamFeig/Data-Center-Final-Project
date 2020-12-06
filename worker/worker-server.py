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
sys.path.append("..")
from util import log, sendToWorker, downloadFromGCS, uploadToGCS

import make_palette

##
# Configure test vs. production
##
redisHost = os.getenv("REDIS_HOST") or "localhost"
rabbitMQHost = os.getenv("RABBITMQ_HOST") or "localhost"

print("Connecting to rabbitmq({}) and redis({})".format(rabbitMQHost, redisHost))


redisVidHashToImgHash = redis.Redis(host=redisHost, db=1, decode_responses=True)
redisImgHashToTimestamp = redis.Redis(host=redisHost, db=1, decode_responses=True)
redisImgHashToColorPalette = redis.Redis(host=redisHost, db=1, decode_responses=True)

def handle_progressless_iter(error, progressless_iters):
    if progressless_iters > 5:
        print('Failed to make progress for too many consecutive iterations.')
        raise error

    sleeptime = random.random() * (2**progressless_iters)
    print('Caught exception (%s). Sleeping for %s seconds before retry #%d.' %
          (str(error), sleeptime, progressless_iters))
    time.sleep(sleeptime)


def callback(ch, method, properties, body):
    data = jsonpickle.decode(body)
    print(" [x] Received %r" % data)

    task = data['task']

    if task == 'split-file':
        name = data['name']
        frequency = int(float(data['frequency'])*1000)

        bucket_name = 'csci4253finalproject'
        vid_hash = data['hash']
        object_name = data['hash']
        filename = data['hash']
        f = downloadFromGCS(filename, bucket_name, object_name)

        images = make_palette.mp4_to_images(filename, frequency)
        encoded_images = make_palette.encode_images(images)

        for index, image in enumerate(encoded_images):
            m = hashlib.sha256()
            m.update(image)
            img_hash = m.hexdigest()

            redisVidHashToImgHash.sadd(vid_hash, img_hash)
            redisImgHashToTimestamp.set(img_hash, frequency * index)

            uploadToGCS(img_hash, image, 'image/jpeg', bucket_name,  vid_hash + '/' + img_hash)
            sendToWorker({ 'task': 'process-color', 'image_hash': img_hash, 'video_hash': vid_hash })
        f.close()
        os.remove(f.name)

    elif task == 'process-color':
        bucket_name = 'csci4253finalproject'
        vid_hash = data['video_hash']
        img_hash = data['image_hash']
        object_name = vid_hash + '/' + img_hash
        filename = data['image_hash']
        f = downloadFromGCS(filename, bucket_name, object_name)

        img = make_palette.img_from_file(filename)
        clusters = make_palette.img_to_clusters(img, un_scale=False)
        str_clusters = ','.join([' '.join([str(val) for val in rgb]) for rgb in clusters])
        print(clusters)
        
        redisImgHashToColorPalette.set(img_hash, str_clusters)
        f.close()
        os.remove(f.name)
    else:
        print(task)
        log('No task found for worker with data', data)

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
