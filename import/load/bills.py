"""
load bill data

from: data/crawl/govtrack/us/*/{bills,rolls}
"""
from __future__ import with_statement
import os, sys, glob, anydbm
from psycopg2 import IntegrityError #@@level-breaker
import xmltramp
import web
from tools import govtrackp
from settings import db
import schema

DATA_DIR = '../data'
GOVTRACK_CRAWL = DATA_DIR+'/crawl/govtrack'

class NotDone(Exception): pass

def makemarkdone(done):
    def markdone(func):
        def internal(fn, *a, **kw):
            mtime = str(os.stat(fn).st_mtime)
            if not done.has_key(fn) or done[fn] != mtime:
                    try:
                        func(fn)
                        done[fn] = mtime
                    except NotDone:
                        pass
        return internal
    return markdone

def fixvote(s):
    try: return {'0': None, '+': 1, '-': -1, 'P': 0}[s]
    except: return None

def bill2dict(bill):
    d = web.storage()
    d.id = 'us/%s/%s%s' % (bill('session'), bill('type'), bill('number'))
    d.session = bill('session')
    d.type = bill('type')
    d.number = bill('number')
    d.introduced = bill.introduced('datetime')
    titles = [unicode(x) for x in bill.titles['title':] 
      if x('type') == 'short']
    if not titles:
        titles = [unicode(x) for x in bill.titles['title':]]
    d.title = titles[0]

    summaries = [unicode(x) for x in bill.titles['title':] 
      if x('type') == 'official']
    if not summaries:
        summaries = [unicode(x) for x in bill.titles['title':]]
    d.summary = summaries[0]
    
    d.sponsor_id = govtrackp(bill.sponsor().get('id'))
    return d

def loadbill(fn, maplightid=None):
    bill = xmltramp.load(fn)
    d = bill2dict(bill)
    d.maplightid = maplightid
    
    try:
        bill_id = d.id
        db.insert('bill', seqname=False, **d)
    except IntegrityError:
        bill_id = d.pop('id')
        db.update('bill', where="id=" + web.sqlquote(bill_id), **d)
    
    positions = {}
    for vote in bill.actions['vote':]:
        if not vote().get('roll'): continue
        
        rolldoc = '/us/%s/rolls/%s%s-%s.xml' % (
          d.session, vote('where'), vote('datetime')[:4], vote('roll'))
        roll = xmltramp.load(GOVTRACK_CRAWL + rolldoc)
        for voter in roll['voter':]:
            positions[govtrackp(voter('id'))] = fixvote(voter('vote'))

    if None in positions: del positions[None]
    with db.transaction():
        for p, v in positions.iteritems():
            db.insert('position', seqname=False, 
              bill_id=bill_id, politician_id=p, vote=v)
        

def loadroll(fn):
    roll = web.storage()
    roll.id = fn.split('/')[-1].split('.')[0]
    vote = xmltramp.load(fn)
    if vote['bill':]:
        b = vote.bill
        roll.bill_id = 'us/%s/%s%s' % (b('session'), b('type'), b('number'))
    else:
        roll.bill_id = None
    roll.type = str(vote.type)
    roll.question = str(vote.question)
    roll.required = str(vote.required)
    roll.result = str(vote.result)
    
    try:
        db.insert('roll', seqname=False, **roll)
    except IntegrityError:
        if not db.update('roll', where="id=" + web.sqlquote(roll.id), bill_id=roll.bill_id):
            print "\nMissing bill:", roll.bill_id
            raise NotDone
    
    with db.transaction():
        for voter in vote['voter':]:
            rep = govtrackp(voter('id'))
            if rep:
                db.insert('vote', seqname=False, 
                  politician_id=rep, roll_id=roll.id, vote=fixvote(voter('vote')))
            else:
                pass #@@!--check again after load_everyone
                # print "\nMissing rep: %s" % voter('id')

def main(session):
    done = anydbm.open('.bills', 'c')
    markdone = makemarkdone(done)
        
    db.delete('position', '1=1')
    for fn in sorted(glob.glob(GOVTRACK_CRAWL+'/us/%s/bills/*.xml' % session)):
        print >>sys.stderr,'\r  %-25s    ' % fn,; sys.stderr.flush()
        markdone(loadbill)(fn)
    schema.Position.create_indexes()

    db.delete('vote', '1=1')
    for fn in sorted(glob.glob(GOVTRACK_CRAWL+'/us/%s/rolls/*.xml' % session)):
        print >>sys.stderr,'\r  %-25s    ' % fn,; sys.stderr.flush()
        markdone(loadroll)(fn)
    print >>sys.stderr, '\r' + ' '*72

if __name__ == "__main__":
    from settings import current_session
    if current_session:
	    session = current_session # load nth session bills and rolls, specified in settings
    else:
	    session = '*' 	# load all bills and rolls sessions

    main(session)
