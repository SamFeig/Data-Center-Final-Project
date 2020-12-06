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

def uploadFile(addr, filename, freq, debug=False):
    # prepare headers for http request
    headers = {'content-type': 'video/mp4', 'Frequency': str(freq)}
    file = open(filename, 'rb').read()
    url = "%s/upload/%s" % (addr, os.path.basename(filename))
    response = requests.post(url, data=file, headers=headers)
    if debug:
        # decode response
        print("Response is", response)
        print(json.loads(response.text))

def imageProcess(addr, hashval, R, G, B, debug=False):
    url = "%s/match/%s/%d/%d/%d" % (addr, hash, R, G,B)
    response = requests.post(url)
    if debug:
        # decode response
        print("Response is", response)
        print(json.loads(response.text))

def paletteMatch(addr, hashval, debug=False):
    url = "%s/palette/%s" % (addr, hashval)
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
    uploadFile(addr, filename, freq, True)
elif cmd == 'match':
    hashval = sys.argv[3]
    R = sys.argv[4]
    G = sys.argv[5]
    B = sys.argv[6]
    imageProcess(addr, hashval, R, G, B, True)
elif cmd == 'palette':
    hashval = sys.argv[3]
    paletteMatch(addr, hashval, True)
else:
    print("Unknown option", cmd)