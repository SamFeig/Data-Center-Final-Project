#!/usr/bin/env python3
# 
#
# A sample REST client for the face match application
#
import requests
import json
import time
import sys, os
import jsonpickle

def uploadImage(addr, filename, freq, debug=False):
    # prepare headers for http request
    headers = {'content-type': 'video/mp4'}
    img = open(filename, 'rb').read()
    # send http request with image and receive response
    image_url = addr + '/upload' + "/" + os.path.basename(filename)
    response = requests.post(image_url, data=img, headers=headers)
    if debug:
        # decode response
        print("Response is", response)
        print(json.loads(response.text))

def paletteMatch(addr, hashval, debug=False):
    url = addr + "/palette/" + hashval
    response = requests.get(url)
    if debug:
        # decode response
        print("Response is", response)
        print(json.loads(response.text))

host = sys.argv[1]
cmd = sys.argv[2]

addr = 'http://{}'.format(host)

if cmd == 'upload':
    filename = sys.argv[3]
    freq = int(sys.argv[4])
    #start = time.perf_counter()
    #for x in range(reps):
    uploadImage(addr, filename, freq, True)
    #delta = ((time.perf_counter() - start)/reps)*1000
    #print("Took", delta, "ms per operation")
elif cmd == 'palette':
    hashval = sys.argv[3]
    #reps = int(sys.argv[4])
    #start = time.perf_counter()
    #for x in range(reps):
    paletteMatch(addr, hashval, True)
    #delta = ((time.perf_counter() - start)/reps)*1000
    #print("Took", delta, "ms per operation")
else:
    print("Unknown option", cmd)