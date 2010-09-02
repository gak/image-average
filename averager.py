#!/usr/bin/env python

import os
import cPickle as pickle
import json
import urllib
from pprint import pprint
from numpy import *
from StringIO import StringIO
from multiprocessing import *

from PIL import Image


class UrlCache(object):
    def __init__(self):
        self.lock = Lock()
        self.filename = 'url.cache'

    def update(self):
        self.lock.acquire()
        try:
            self.data = pickle.load(open(self.filename, 'rb'))
            print 'loaded cache'
        except IOError:
            self.data = {}
        self.lock.release()

    def save(self):
        self.lock.acquire()
        pickle.dump(self.data, open(self.filename, 'wb'), -1)
        self.lock.release()

    def get(self, url, fetch=True):
        self.update()
        if url in self.data:
            print url, 'cache hit'
            return self.data[url]
        print url, 'cache miss'
        try:
            data = urllib.urlopen(url).read()
        except IOError:
            data = None
        print url, 'done'
        self.data[url] = data
        self.save()
        return data

class ImageAverager(object):

    def __init__(self, *args, **kw):
        self.urlcache = UrlCache()
        self.yahoo_app_id = None
        self.images = []
        for key, value in kw.items():
            setattr(self, key, value)

    def set_yahoo_credentials(self, app_id):
        self.yahoo_app_id = app_id

    def get_yahoo_url(self, query, limit=10):
        assert(self.yahoo_app_id)
        query = urllib.quote(query)
        return 'http://search.yahooapis.com/' + \
            'ImageSearchService/V1/imageSearch' + \
            '?output=json' + \
            '&appid=%s' % self.yahoo_app_id + \
            '&query=%s' % query + \
            '&results=%i' % limit

    def yahoo_search(self, query, *args, **kw):
        url = self.get_yahoo_url(query, **kw)
        data = self.urlcache.get(url)
        response = json.loads(data)
        images = response['ResultSet']['Result']
        for image in images:
            self.images.append(image['Url'])

    def pull_images(self):
        pool = Pool(1)
        hmm = pool.map(f, self.images)
        print hmm

    def create_image(self, output, dims):
        assert(isinstance(dims, (list, tuple)))
        assert(len(dims) == 2)
        bytes = dims[0] * dims[1] * 3
        t = uint64
        finalimage = zeros(bytes, dtype=t)
        imagecount = 0
        for image in self.images:
            data = self.urlcache.get(image)
            if not data:
                continue
            try:
                im = Image.open(StringIO(data))
            except IOError:
                open('hmm', 'wb').write(data)
                print image
                os.system('file hmm')
                continue
            im = im.convert('RGB')
            im = im.resize(dims)
            imarray = fromstring(im.tostring(), dtype=uint8)
            imarray = imarray.astype(t)
            print len(imarray)
            finalimage += imarray
            imagecount += 1
        finalimage /= imagecount
        finalimage = finalimage.astype(uint8)
        im = Image.fromstring('RGB', dims, finalimage.tostring())
        im.save(output)

def main():
    config = json.load(open('config.json'))
    print config.items()

    # oh snap. convert unicode keys to str
    for key, val in config.items():
        del config[key]
        config[str(key)] = val

    ia = ImageAverager(**config)
    ia.yahoo_search('cat face', limit=50)
    ia.pull_images()
    #ia.create_image('catface.jpg', (300, 300))

if __name__ == '__main__':
    main()
