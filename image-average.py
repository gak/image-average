#!/usr/bin/env python

import time
import os
from os.path import exists
from os.path import join
import string
import sys
import cPickle as pickle
import json
import urllib
import urllib2
from pprint import pprint
from numpy import *
from StringIO import StringIO
from multiprocessing import Queue, Process
import unicodedata

from PIL import Image

class UrlCache(object):

    def __init__(self):
        self.queue = Queue()
        self.validchars = "%s (-_.) %s" % (string.ascii_letters, string.digits)
        self.cachepath = 'cache'
        if not exists(self.cachepath):
            os.mkdir(self.cachepath)

    def get(self, url, skipcache=False):

        filename = self.clean_filename(url)
        filename = join(self.cachepath, filename)

        if exists(filename) and not skipcache:
            print url, 'cache hit'
            return open(filename, 'rb').read()

        try:
            t = time.time()
            data = urllib2.urlopen(url, timeout=10).read()
            print url, 'done', time.time() - t
        except IOError:
            data = ''
            print url, 'fail', time.time() - t

        open(filename, 'wb').write(data)
        return data

    def _get(self):
        while 1:
            try:
                url = self.queue.get_nowait()
            except:  # XXX: Work out exception name for "Empty"
                break
            self.get(url)

    def get_many(self, urls, count):

        urls = set(urls)

        for url in urls:
            self.queue.put(url)
        workers = []
        for n in xrange(count):
            p = Process(target=self._get)
            p.start()
            workers.append(p)
        for n, p in enumerate(workers):
            print 'waiting', count - n
            p.join()

    def clean_filename(self, filename):
        cleaned = unicodedata.normalize('NFKD', filename). \
            encode('ASCII', 'ignore')
        cleaned = ''.join(c for c in cleaned if c in self.validchars)

        # make sure the filename isn't too long..
        maxlen = 100
        if len(cleaned) > maxlen:
            cleaned = cleaned[:maxlen/2] + cleaned[-maxlen/2:]

        return cleaned

class ImageAverager(object):

    def __init__(self, *args, **kw):
        self.urlcache = UrlCache()
        self.yahoo_app_id = None
        self.images = []
        for key, value in kw.items():
            setattr(self, key, value)

    def set_yahoo_credentials(self, app_id):
        self.yahoo_app_id = app_id

    def get_yahoo_url(self, query, start=1, limit=10, adult=False):
        assert(self.yahoo_app_id)
        query = urllib.quote(query)
        url = 'http://search.yahooapis.com/' + \
            'ImageSearchService/V1/imageSearch' + \
            '?output=json' + \
            '&appid=%s' % self.yahoo_app_id + \
            '&query=%s' % query + \
            '&start=%i' % start + \
            '&results=%i' % limit
        if adult:
            url += '&adult_ok=1'
        return url

    def yahoo_search(self, query, *args, **kw):
        total = kw.get('total', 10)
        del kw['total']
        maxi = 50  # 50 is max results per page
        pages, remainder = divmod(total, maxi)
        for page in xrange(pages):
            self.yahoo_search_single(query, start=page + 1, limit=maxi,
                *args, **kw)
        if remainder:
            self.yahoo_search_single(query, start=pages + 1, limit=remainder,
                *args, **kw)

    def yahoo_search_single(self, query, *args, **kw):
        url = self.get_yahoo_url(query, **kw)
        data = self.urlcache.get(url, skipcache=True)
        response = json.loads(data)
        images = response['ResultSet']['Result']
        for image in images:
            self.images.append(image['Url'])

    def pull_images(self, tasks):
        self.urlcache.get_many(self.images, tasks)

    def create_image(self, output, dims):
        assert(isinstance(dims, (list, tuple)))
        assert(len(dims) == 2)
        mode = 'RGB'

        bytes = dims[0] * dims[1]
        if mode == 'RGB':
            bytes = dims[0] * dims[1] * 3
        t = uint64
        finalimage = zeros(bytes, dtype=t)
        imagecount = 0
        for n, image in enumerate(self.images):
            print float(n) / len(self.images)
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
            im = im.convert(mode)
            im = im.resize(dims)
            imarray = fromstring(im.tostring(), dtype=uint8)
            imarray = imarray.astype(t)
            finalimage += imarray
            imagecount += 1

            if 0:
                intermediateimage = copy(finalimage)
                intermediateimage /= imagecount
                intermediateimage = intermediateimage.astype(uint8)
                im = Image.fromstring(mode, dims, intermediateimage.tostring())
                im.save('tmp/%i.jpg' % imagecount)

        finalimage /= imagecount
        finalimage = finalimage.astype(uint8)
        im = Image.fromstring(mode, dims, finalimage.tostring())
        im.save(output)

def main():
    config = json.load(open('config.json'))

    # oh snap. convert unicode keys to str, to stop this error:
    # TypeError: __init__() keywords must be strings
    for key, val in config.items():
        del config[key]
        config[str(key)] = val

    ia = ImageAverager(**config)
    ia.yahoo_search(sys.argv[1], total=500, adult=True)
    ia.pull_images(tasks=50)
    filename = '%s.jpg' % sys.argv[1]
    ia.create_image(filename, (300, 300))
    os.system('open "%s"' % filename)

if __name__ == '__main__':
    main()
