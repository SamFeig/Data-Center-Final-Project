
import io
import requests

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

import sys
import cv2
import matplotlib.pyplot as plt


def img_from_url(url):
    return np.array(Image.open(io.BytesIO(requests.get(url).content)))


def img_from_file(path):
    with open(path, "rb") as f:
        return np.array(Image.open(f))


def flatten_and_scale(img):
    return img.reshape((-1, 3)).astype("float32") / 255


def get_clusters(img, n_clusters=8):
    return KMeans(n_clusters).fit(img).cluster_centers_


def unscale(centers):
    return (centers * 255).astype("uint8").tolist()


def url_to_kmeans_palette(url, nclusters=8):
    make_kmeans_palette(img_from_url(url))

def make_kmeans_palette(img, nclusters=8):
    pixels = flatten_and_scale(img)
    centers = get_clusters(pixels, nclusters)

    fig, axs = plt.subplots(2, figsize=(14,14))
    
    # Plot the image
    axs[0].imshow(img)
    axs[0].grid()
    axs[0].axis('off')

    # Plot the palette
    axs[1].imshow(centers[
        np.concatenate([[i] * 100 for i in range(len(centers))]
                       ).reshape((-1, 10)).T
    ])
    axs[1].grid()
    axs[1].axis('off')

    # save to output directory
    plt.savefig('./output/test.png')


def url_to_clusters(url, n_clusters=8):
    img = img_from_url(url)
    data = flatten_and_scale(img)
    centers = get_clusters(data, n_clusters)
    return unscale(centers)


def img_to_clusters(img, n_clusters=8):
    data = flatten_and_scale(img)
    centers = get_clusters(data, n_clusters)
    return unscale(centers)


def mp4_to_images(filename, frequency=1000):
    vidcap = cv2.VideoCapture(filename)
    count = 0
    success = True

    images = []
    while success:
        vidcap.set(cv2.CAP_PROP_POS_MSEC, (count*frequency))
        success, image = vidcap.read()
        count += 1
        print(success, count)
        if success:
            img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            images.append(img)
    return images


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            'USAGE: python3 make_pallete-py [mp4 filename] [image frequency in seconds]')
        exit()

    filename = sys.argv[1]
    frequency = int(float(sys.argv[2]) * 1000)
    images = mp4_to_images(filename, frequency)

    print(images[0], images[0].reshape((-1, 3)).astype("float32") / 255)
    print(make_kmeans_palette(images[0]))
    # print(url_to_kmeans_palette("https://i.imgur.com/AC4n03N.jpg"))
