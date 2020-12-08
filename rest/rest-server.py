##
from flask import Flask, request, Response, send_file
import jsonpickle, pickle
import platform
import io, os, sys
import pika, redis
import hashlib, requests
from json import dumps as json_dumps
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

#colormath
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000

#sys.path.append("..")
from util import log, sendToWorker, uploadToGCS, downloadFromGCS

##
## Configure test vs. production
##
matplotlib.use('Agg')
redisHost = os.getenv("REDIS_HOST") or "localhost"
rabbitMQHost = os.getenv("RABBITMQ_HOST") or "localhost"
print("Connecting to rabbitmq({}) and redis({})".format(rabbitMQHost,redisHost))

# Initialize the Flask application
app = Flask(__name__)

###REST API ROUTES###

@app.route('/', methods=['GET'])
def hello():
    return '<h1> Movie Color Palette Picker Server</h1><p> Use a valid endpoint </p>'

#Image upload endpoint
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

    #Upload file to Google Cloud Storage Bucket
    uploadToGCS(filename, file, file_type, 'csci4253finalproject', m.hexdigest())

    #Return Hash to client and send message to worker
    response = { 
        "hash" : m.hexdigest()
    }
    response_pickled = jsonpickle.encode(response)
    sendToWorker({ 'hash' : m.hexdigest(), 'name' : filename, 'frequency' : freq, 'task' : 'split-file'})#, 'image' : file})

    log('POST /upload/%s HTTP/1.1 200' % (filename), True)
    return Response(response=response_pickled, status=200, mimetype="application/json")

@app.route('/match/<hash>/<int:R>/<int:G>/<int:B>' , methods=['GET'])
def matchValues(hash, R, B, G):
    log("Attempting API request on /match/%s/%d/%d/%d" % (hash, R, G, B), True)

    redisVidHashToImageHash = redis.Redis(host=redisHost, db=1, decode_responses=True)
    redisImageHashToColorPalette = redis.Redis(host=redisHost, db=3, decode_responses=True)

    imageList = list(redisVidHashToImageHash.smembers(hash))

    R /= 255.0
    G /= 255.0
    B /= 255.0
    color1_rgb = sRGBColor(R, G, B)
    # Convert from RGB to Lab Color Space
    color1_lab = convert_color(color1_rgb, LabColor)

    fig, axs = plt.subplots(len(imageList)*2, figsize=(14,14))
    for i in range(len(imageList)*2):
        axs[i].grid()
        axs[i].axis('off')

    buf = io.BytesIO()
    subplt = 0
    for imageHash in imageList:
        #Get color centers from redis db
        centers = [i.split(' ') for i in redisImageHashToColorPalette.get(imageHash).split(',')]
        centers = np.array([np.array([float(n) for n in i])for i in centers])

        for RGB in centers:
            color2_rgb = sRGBColor(RGB[0], RGB[1], RGB[2])
            # Convert from RGB to Lab Color Space
            color2_lab = convert_color(color2_rgb, LabColor)
            # Find the color difference
            delta_e = delta_e_cie2000(color1_lab, color2_lab)
            print(delta_e)
            if delta_e <= 10:
                img = downloadFromGCS(imageHash, 'csci4253finalproject', '%s/%s' % (hash,imageHash), file_perms='w+b')

                #Plot the image
                axs[subplt].imshow(np.array(Image.open(img)))
                axs[subplt].grid()
                axs[subplt].axis('off')

                subplt += 1
                # Plot the palette
                axs[subplt].imshow(centers[
                    np.concatenate([[i] * 100 for i in range(len(centers))]).reshape((-1, 10)).T
                ])
                axs[subplt].grid()
                axs[subplt].axis('off')
                subplt += 1

                img.close()
                os.remove(img.name)

    plt.savefig(buf, format='jpg')
    buf.seek(0)

    log('GET /match/%s/%d/%d/%d HTTP/1.1 200' % (hash, R, G, B), True)
    return send_file(buf, mimetype='image/jpg', 
                                as_attachment=False, attachment_filename='results_%s.jpg' % hash)

#Final endpoint to get results from a video hash
@app.route('/palette/<hash>' , methods=['GET'])
def matchHash(hash):
    log("Attempting API request on /palette/%s" % (hash), True)

    redisVidHashToImageHash = redis.Redis(host=redisHost, db=1, decode_responses=True)
    redisImgHashToTimestamp = redis.Redis(host=redisHost, db=2, decode_responses=True)
    redisImageHashToColorPalette = redis.Redis(host=redisHost, db=3, decode_responses=True)

    imageList = sorted(list(redisVidHashToImageHash.smembers(hash)), key= lambda item: int(redisImgHashToTimestamp.get(item)))

    fig, axs = plt.subplots(len(imageList)*2, figsize=(14,14 if len(imageList) == 0 else len(imageList) * 14))

    buf = io.BytesIO()
    subplt = 0
    for imageHash in imageList:
        #Download image
        img = downloadFromGCS(imageHash, 'csci4253finalproject', '%s/%s' % (hash,imageHash), file_perms='w+b')

        #Get color centers from redis db
        centers = [i.split(' ') for i in redisImageHashToColorPalette.get(imageHash).split(',')]
        centers = np.array([np.array([float(n) for n in i])for i in centers])

        #Plot the image
        axs[subplt].imshow(np.array(Image.open(img)))
        axs[subplt].grid()
        axs[subplt].set_title("Timestamp: %s ms" %(redisImgHashToTimestamp.get(imageHash)), fontsize=40)
        axs[subplt].axis('off')

        subplt += 1
        # Plot the palette
        axs[subplt].imshow(centers[
            np.concatenate([[i] * 100 for i in range(len(centers))]).reshape((-1, 10)).T
        ])
        axs[subplt].grid()
        axs[subplt].axis('off')
        subplt += 1

        img.close()
        os.remove(img.name)

    #plt.savefig('results_%s.jpg' % hash)  
    plt.savefig(buf, format='jpg')
    buf.seek(0)

    log('GET /palette/%s HTTP/1.1 200' % (hash), True)
    return send_file(buf, mimetype='image/jpg', 
                                as_attachment=False, attachment_filename='results_%s.jpg' % hash)

# start flask app
app.run(host="0.0.0.0", port=5000)
