import os, glob
import simplejson
import web

DATA_DIR = '../data/parse'
db = web.database(dbn=os.environ.get('DATABASE_ENGINE', 'postgres'), db='watchdog_dev')

def unidecode(d):
    newd = {}
    for k, v in d.iteritems():
        newd[k.encode('utf8')] = v
    return newd

def load():
    districts = simplejson.load(file(DATA_DIR + '/districts/index.json'))
    
    for name, district in districts.iteritems():
        db.insert('district', seqname=False, name=name, **unidecode(district))
    
    for fn in ['almanac', 'shapes']:
        districts = simplejson.load(file(DATA_DIR + '/districts/%s.json' % fn))
        for name, district in districts.iteritems():
            db.update('district', where='name = $name', vars=locals(), **unidecode(district))

if __name__ == "__main__": load()