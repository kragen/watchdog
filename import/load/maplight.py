"""
load maplight info

from: data/crawl/maplight/
"""

from __future__ import with_statement

import csv
from tools import db
import bills
    
def load_data():
    c = csv.reader(file('../data/crawl/maplight/uniq_map_export_bill_research.csv'))
    supportdict = {'0': -1, '1': 1, '2': 0 } #0: oppose ; 1: support; 2: not known (from README)
    
    with db.transaction():
        db.delete('interest_group_bill_support', '1=1')
        for line in c:
            if not line[0].startswith('#'):
                category_id, longname, maplightid, session, measure, support = line
                support = supportdict[support]
                if support == 0: continue
                typenumber = measure.lower().replace(' ', '')
                    
                r = db.select('interest_group', what="id", where="longname=$longname", vars=locals())
                if r:
                    groupid = r[0].id
                else:
                    groupid = db.insert('interest_group', longname=longname, category_id=category_id)
                    
                bill_id = 'us/%s/%s' % (session, typenumber)
                r = db.select('bill', where="id=$bill_id", vars=locals())
                if not r:
                    filename = "../data/crawl/govtrack/us/%s/bills/%s.xml" % (session, typenumber)
                    bills.loadbill(filename, maplightid=maplightid)
                else:
                    db.update('bill', maplightid=maplightid, where="id=$bill_id", vars=locals())
                    
                try:
                    #print '\r', bill_id,
                    db.insert('interest_group_bill_support', seqname=False, bill_id=bill_id, group_id=groupid, support=support)
                except:
                    print '\n Duplicate row with billid %s groupid %s support %s longname %s' % (bill_id, groupid, support, longname)
                    raise
       
def load_categories():
    c = csv.reader(file('../data/crawl/maplight/CRP_Categories.csv'))
    with db.transaction():
        db.delete('category', '1=1')
        for line in c:
            if not line[0].startswith('#'):
                cid, cname, industry, sector, empty = line
                db.insert('category', seqname=False, id=cid, name=cname, industry=industry, sector=sector)
         
def main():
    load_categories()
    load_data()
                                     
if __name__ == "__main__":
    main()
