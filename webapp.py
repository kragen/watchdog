#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re, sys
import web

from utils import zip2rep, simplegraphs, apipublish, users, writerep, se, wyrapp, api
import blog
import petition
import settings
from settings import db, render, production_mode
import schema
import config
import os, simplejson

if not production_mode:
	web.config.debug = True
	db.printing = True

options = r'(?:\.(html|xml|rdf|n3|json))'
urls = (
  r'/', 'index',
  r'/us/(?:index%s)?' % options, 'find',
  r'/us/([A-Z][A-Z])', 'redistrict',
  r'/us/([a-z][a-z])%s?' % options, 'state',
  r'/us/([A-Z][A-Z]-\d+)', 'redistrict',
  r'/us/([a-z][a-z]-\d+)%s?' % options, 'district',
  r'/(us|p)/by/(.*)/distribution\.png', 'sparkdist',
  r'/(us|p)/by/(.*)', 'dproperty',
  r'/p/(.*?)/lobby', 'politician_lobby',
  r'/p/(.*?)/earmarks', 'politician_earmarks',
  r'/p/(.*?)/introduced', 'politician_introduced',
  r'/p/(.*?)/groups', 'politician_groups',
  r'/p/(.*?)/contribs', 'politician_contribs',
  r'/p/(.*?)/contrib-employers', 'politician_contrib_employers',
  r'/p/(.*?)/(\d+)', 'politician_group',
  r'/p/(.*?)%s?' % options, 'politician',
  r'/e/(.*?)%s?' % options, 'earmark',
  r'/b/(.*?)%s?' % options, 'bill',
  r'/contrib/(distribution\.png|)', 'contributions',
  r'/contrib/(\d+)/(.*?)' , 'contributor',
  r'/occupation/(.*?)/candidates' , 'occupation_candidates',
  r'/occupation/(.*?)/committees' , 'occupation_committees',
  r'/occupation/(.*?)' , 'occupation',
  r'/empl/(.*?)%s?' % options, 'employer',
  r'/r/us/(.*?)%s?' % options, 'roll',
  r'/lob/c/?(.*?)', 'lob_contrib',
  r'/lob/f/?(.*?)', 'lob_filing',
  r'/lob/o/?(.*?)', 'lob_org',
  r'/lob/pa/?(.*?)', 'lob_pac',
  r'/lob/pe/?(.*?)', 'lob_person',
  r'/writerep', wyrapp.app,
  r'/api', api.app,
  r'/about(/?)', 'about',
  r'/about/team', 'aboutteam',
  r'/about/help', 'abouthelp',
  r'/about/api', 'aboutapi',
  r'/about/feedback', 'feedback',
  r'/contribute(/?)', 'contribute',
  r'/blog', blog.app,
  r'/share', 'petition.share',
  r'/data/(.*)', 'staticdata',
  r'/bbauth/', 'contacts.auth_yahoo',
  r'/authsub', 'contacts.auth_google',
  r'/auth/msn', 'contacts.auth_msn',
  r'/c', petition.app,
  r'/u', users.app,
)

class index:
    def GET(self):
        return render.index()

class about:
    def GET(self, endslash=None):
        if not endslash: raise web.seeother('/about/')
        return render.about()

class aboutapi:
    def GET(self):
        return render.about_api()

class aboutteam:
    def GET(self):
        return render.about_team()

class abouthelp:
    def GET(self):
        return render.about_help()

class contribute:
    def GET(self, endslash=None):
        if not endslash: raise web.seeother('/contribute/')
        return render.contribute()

class feedback:
    def GET(self):
        return render.feedback()

    def POST(self):
        i = web.input(email='info@watchdog.net')
        web.sendmail('Feedback <%s>' % i.email, 'Watchdog <info@watchdog.net>',
          'watchdog.net feedback',
          i.content +'\n\n' + web.ctx.ip)

        return render.feedback_thanks()

class find:
    def GET(self, format=None):
        i = web.input(address=None)
        pzip5 = re.compile(r'\d{5}')
        pzip4 = re.compile(r'\d{5}-\d{4}')
        pdist = re.compile(r'[a-zA-Z]{2}\-\d{2}')
        
        dists = None
        if not i.get('q'):
            i.q = i.get('zip')

        if i.q:
            if pzip4.match(i.q):
                zip, plus4 = i.q.split('-')
                dists = [x.district_id for x in
                  db.select('zip4', where='zip=$zip and plus4=$plus4', vars=locals())]
            
            elif pzip5.match(i.q):
                try:
                    dists = zip2rep.zip2dist(i.q, i.address)
                except zip2rep.BadAddress:
                    return render.find_badaddr(i.q, i.address)
            
            if dists:
                d_dists = list(schema.District.select(where=web.sqlors('name=', dists)))
                out = apipublish.publish(d_dists, format)
                if out: return out

                if len(dists) == 1:
                    raise web.seeother('/us/%s' % dists[0].lower())
                elif len(dists) == 0:
                    return render.find_none(i.q)
                else:
                    return render.find_multi(i.q, d_dists)

            if pdist.match(i.q):
                raise web.seeother('/us/%s' % i.q)
            
            results = se.query(i.q)
            reps = schema.Politician.select(where=web.sqlors('id=', results))
            if len(reps) > 1:
                return render.find_multi_reps(reps, congress_ranges)
            else:
                try:
                    rep = reps[0]
                    web.seeother('/p/%s' % rep.id)
                except IndexError:
                    raise web.notfound()

        else:
            index = list(schema.District.select(order='name asc'))
            for i in index:
                i.politician = list(db.select('curr_politician', where='district_id = $i.name', vars=locals()))
            out = apipublish.publish(index, format)
            if out: return out

            return render.districtlist(index)

class state:
    def GET(self, state, format=None):
        try:
            state = schema.State.where(code=state.upper())[0]
            state.senators = db.select('curr_politician', where='district_id = $state.code', vars=locals())
        except IndexError:
            raise web.notfound()

        out = apipublish.publish([state], format)
        if out: return out

        return render.state(state)

class redistrict:
    def GET(self, district):
        return web.seeother('/us/' + district.lower())

class district:
    def GET(self, district, format=None):
        try:
            d = schema.District.where(name=district.upper())[0]
            d.politician = list(db.select('curr_politician', where='district_id = $d.name', vars=locals()))[0]
        except IndexError:
            raise web.notfound()

        out = apipublish.publish([d], format)
        if out: return out
        
        return render.district(d, sparkpos)

def group_politician_similarity(politician_id, limit=None):
    if limit is not None:
        limit_clause = web.db.sqlliteral('limit %d' % limit)
    else:
        limit_clause = web.db.sqlliteral('')
    return db.query(similarity_query, vars=locals()).list()

similarity_query = '''
    select *, cast(agreed as float)/total as agreement from (
        select  igbp.group_id, position.politician_id,
           count(case when vote = support then 1 else null end) as agreed,
           count(*) as total
        from  interest_group_bill_support as igbp,
              position
        where  igbp.bill_id = position.bill_id
        and    politician_id = $politician_id
        group by  group_id, politician_id
        order by total desc
        $limit_clause
    ) as foo,
         interest_group
    where interest_group.id = group_id
    order by agreement desc, total desc
'''

def politician_contributors(polid):
    return db.query("""SELECT cn.name, cn.zip, 
            sum(cn.amount) as amt FROM committee cm, politician_fec_ids pfi, 
            politician p, contribution cn WHERE cn.recipient_id = cm.id 
            AND cm.candidate_id = pfi.fec_id AND pfi.politician_id = p.id 
            AND p.id = $polid AND cn.employer_stem != '' GROUP BY cn.name, cn.zip 
            ORDER BY amt DESC""", vars=locals())

def politician_contributor_employers(polid):
    return db.query("""SELECT cn.employer_stem, 
            sum(cn.amount) as amt FROM committee cm, politician_fec_ids pfi, 
            politician p, contribution cn WHERE cn.recipient_id = cm.id 
            AND cm.candidate_id = pfi.fec_id AND pfi.politician_id = p.id 
            AND p.id = $polid AND cn.employer_stem != '' GROUP BY cn.employer_stem 
            ORDER BY amt DESC""", vars=locals())

def candidates_by_occupation(occupation, limit=None):
    query = """SELECT sum(amount) AS amt, p.firstname, 
            p.lastname, p.id as polid, p.party FROM contribution cn, 
            committee cm, politician_fec_ids pfi, politician p 
            WHERE cn.recipient_id = cm.id AND cm.candidate_id = pfi.fec_id 
            AND pfi.politician_id = p.id 
            AND lower(cn.occupation) = lower($occupation)
            GROUP BY polid, p.lastname, p.firstname, p.party 
            ORDER BY amt DESC"""
    if limit: query += " limit 5"
    return db.query(query, vars=locals())

def committees_by_occupation(occupation, limit=None):
    query = """SELECT sum(amount) AS amt, cm.id, cm.name
            FROM contribution cn, committee cm 
            WHERE cn.recipient_id = cm.id 
            AND lower(cn.occupation) = lower($occupation)
            GROUP BY cm.id, cm.name
            ORDER BY amt DESC"""
    if limit: query += " limit 5"
    return db.query(query, vars=locals())

def politician_lob_contributions(polid, page, limit):
    return db.select(['lob_organization', 'lob_filing', 'lob_contribution', 'lob_person'], 
                where="politician_id = $polid and lob_filing.id = filing_id and lob_organization.id = org_id and lob_person.id = lobbyist_id", 
                order='amount desc', limit=limit, offset=page*limit,
                vars=locals())


def bill_list(format, page=0, limit=50):
    bills = schema.Bill.select(limit=limit, offset=page*limit, order='session desc, introduced desc, number desc')

    out = apipublish.publish(bills, format)
    if out: return out
    #@@ add link to next page

    return render.bill_list(bills, limit)

class roll:
    def GET(self, roll_id, format=None):
        try:
            b = schema.Roll.where(id=roll_id)[0]
            votes = schema.Vote.where(roll_id=b.id)
        except IndexError:
            raise web.notfound()

        out = apipublish.publish([b], format)
        if out: return out
        
        def votepct(pvotes):
            s = (float(pvotes.get(1, 0)) / sum(pvotes.values()))
            return str(s * 100)[:4].rstrip('.') + '%'

        return render.roll(b, votes, votepct)

class bill:
    def GET(self, bill_id, format=None):
        if bill_id == "" or bill_id == "index":
            i = web.input(page=0)
            return bill_list(format, int(i.page))
        
        try:
            b = schema.Bill.where(id=bill_id)[0]
        except IndexError:
            raise web.notfound()
        
        out = apipublish.publish([b], format)
        if out: return out
        
        return render.bill(b)
        
class contributor:
    def GET(self, zipcode, name):
        names = name.lower().replace('_', ' ').split(' ')
        if len(names) > 1: name = names[-1]+', '+' '.join(names[:-1])
        else: name = names[0]
        candidates = list(db.query("""SELECT count(*) AS how_many, 
            sum(amount) AS how_much, p.firstname, p.lastname, 
            cm.name AS committee, cm.id as committee_id, occupation, 
            employer_stem, employer, p.id as polid ,
            min(cn.sent) as from_date, max(cn.sent) as to_date 
            FROM contribution cn, committee cm, politician_fec_ids pfi, 
            politician p WHERE cn.recipient_id = cm.id 
            AND cm.candidate_id = pfi.fec_id AND pfi.politician_id = p.id 
            AND lower(cn.name) = $name AND cn.zip = $zipcode 
            GROUP BY cm.id, cm.name, p.lastname, p.firstname, cn.occupation, 
            cn.employer_stem, cn.employer, p.id ORDER BY lower(cn.employer_stem), 
            lower(occupation), to_date DESC, how_much DESC""", vars=locals()))
        committees = list(db.query("""SELECT count(*) AS how_many, 
            sum(amount) AS how_much, cm.name, cm.id, occupation, 
            employer_stem, employer, max(cn.sent) as to_date, min(cn.sent) as from_date 
            FROM contribution cn, committee cm WHERE cn.recipient_id = cm.id 
            AND lower(cn.name) = $name AND cn.zip = $zipcode 
            GROUP BY cm.id, cm.name, cn.occupation, cn.employer_stem, cn.employer
            ORDER BY lower(cn.employer_stem), 
            lower(occupation), to_date DESC, how_much DESC""", vars=locals()))
        return render.contributor(candidates, committees, zipcode, name)

class occupation:
    def GET(self, occupation):
        if occupation != occupation.lower(): raise web.seeother('/occupation/%s' % occupation.lower())
        candidates = candidates_by_occupation(occupation, 5)
        committees = committees_by_occupation(occupation, 5)
        return render.occupation(candidates, committees, occupation) 

class occupation_candidates:
    def GET(self, occupation):
        candidates = candidates_by_occupation(occupation)
        return render.occupation_candidates(candidates, occupation)     

class occupation_committees:
    def GET(self, occupation):
        committees = committees_by_occupation(occupation)
        return render.occupation_committees(committees, occupation)     

class contributions:
    """from a corp to a pol"""
    def GET(self, img=None):
        i = web.input()
        frm, to = i.get('from', ''), i.get('to', '')
        if frm and to:
            contributions = db.query("""SELECT sum(amount) AS amount,
                p.firstname, p.lastname, p.id as polid,
                employer_stem as employer, date_part('year', sent) as year
                FROM contribution cn, committee cm, politician_fec_ids pfi, politician p 
                WHERE cn.recipient_id = cm.id AND cm.candidate_id = pfi.fec_id 
                AND pfi.politician_id = p.id AND cn.employer_stem = $frm AND p.id=$to 
                GROUP BY year, p.lastname, p.firstname, cn.employer_stem, p.id
                ORDER BY year""", vars=locals()).list()
            
            if img:
                points = [c.amount for c in contributions]
                web.header('Content-Type', 'image/png')
                return simplegraphs.sparkline(points, i.get('point', 0))
            return render.contributions(frm, to, contributions)
        else:
            raise web.notfound()
  
class employer:
    def GET(self, corp_id, format=None):
        corp_id = corp_id.lower().replace('_', ' ')
        contributions = db.query("""SELECT count(*) as how_many, 
            sum(amount) as how_much, p.firstname, p.lastname, p.id as polid
            FROM contribution cn, committee cm, politician_fec_ids pfi, 
            politician p WHERE cn.recipient_id = cm.id 
            AND cm.candidate_id = pfi.fec_id AND pfi.politician_id = p.id 
            AND lower(cn.employer_stem) = $corp_id
            GROUP BY p.lastname, p.firstname, p.id 
            ORDER BY how_much DESC""", vars=locals())
        total_num = db.select('contribution', 
                            what='count(*)',
                            where='lower(employer_stem)=lower($corp_id)', 
                            vars=locals())[0].count
        return render.employer(contributions, corp_id, total_num)

def earmark_list(format, page=0, limit=50):
    earmarks = schema.Earmark.select(limit=limit, offset=page*limit, order='id')

    out = apipublish.publish(earmarks, format)
    if out: return out
    return render.earmark_list(earmarks, limit)
def earmark_pol_list(pol_id, format, page=0, limit=50):
    earmarks = db.select(['earmark_sponsor', 'earmark'], what='earmark.*', 
            where='politician_id = $pol_id AND earmark_id=earmark.id', 
            order='final_amt desc', vars=locals())
    if not earmarks:
        # @@TODO: something better here. 
        raise web.notfound()
    out = apipublish.publish(earmarks, format)
    if out: return out
    return render.earmark_list(earmarks, limit)

class politician_earmarks:
    def GET(self, polid, format=None):
        try:
            em = schema.Politician.where(id=polid)[0]
        except IndexError:
            raise web.notfound()
        return earmark_pol_list(polid, format)
class earmark:
    def GET(self, earmark_id, format=None):
        # No earmark id, show list
        if earmark_id == "" or earmark_id == "index":
            # Show earmark list
            i = web.input(page=0)
            return earmark_list(format, int(i.page))
        # Display the specific earmark
        try:
            em = schema.Earmark.where(id=int(earmark_id))[0]
        except IndexError:
            raise web.notfound()
        except ValueError:
            raise web.notfound()
        return render.earmark(em)


class politician:
    def GET(self, polid, format=None):
        if polid != polid.lower():
            raise web.seeother('/p/' + polid.lower())
        
        i = web.input()
        idlookup = False
        for k in ['votesmartid', 'bioguideid', 'opensecretsid', 'govtrackid']:
            if i.get(k):
                idlookup = True
                ps = schema.Politician.where(**{k: i[k]})
                if ps: raise web.seeother('/p/' + ps[0].id)

        if idlookup:
            # we were looking up by ID but nothing matched
            raise web.notfound()

        if polid == "" or polid == "index":
            polids = tuple(x.id for x in db.query('select id from curr_politician'))
            p = schema.Politician.select(where='id in $polids', order='district_id asc', vars=locals())
            out = apipublish.publish(p, format)
            if out: return out

            return render.pollist(p)

        try:
            p = schema.Politician.where(id=polid)[0]
        except IndexError:
            raise web.notfound()

        #@@move into schema
        p.fec_ids = [x.fec_id for x in db.select('politician_fec_ids', what='fec_id',
          where='politician_id=$polid', vars=locals())]

        p.related_groups = group_politician_similarity(polid, limit=20)
        p.contributors = list(politician_contributors(polid))[0:5]
        p.contributor_employers = list(politician_contributor_employers(polid))[0:5]
        p.lob_contribs = politician_lob_contributions(polid, 0, 5)
        p.capitolwords = p.bioguideid and get_capitolwords(p.bioguideid)
        out = apipublish.publish([p], format)
        if out: return out

        return render.politician(p, sparkpos)

def get_capitolwords(bioguideid):
    capitolwords_path = 'data/crawl/capitolwords'
    fn = "%s/%s.json" % (capitolwords_path, bioguideid)
    if os.path.isfile(fn):
        words = simplejson.load(file(fn))
        return [web.storage(w) for w in words]
    
class politician_lobby:
    def GET(self, polid, format=None):
        limit = 50
        page = int(web.input(page=0).page)
        #c = schema.lob_contribution.select(where='politician_id=$polid', limit=limit, offset=page*limit, order='amount desc', vars=locals())
        a = db.select(['lob_filing', 'lob_contribution'], 
                what='SUM(amount)',
                where="politician_id = $polid AND lob_filing.id = filing_id",
                vars=locals())[0].sum
        c = politician_lob_contributions(polid, page, limit)
        return render.politician_lobby(c, a, limit)

class lob_filing:
    def GET(self, filing_id):
        limit = 50
        try:
            filing_id = int(filing_id or 0)
            page = int(web.input(page=0).page)
        except ValueError:
            raise web.notfound()
        if filing_id:
            f = schema.lob_filing.select(where='id=$filing_id', limit=limit, offset=page*limit, vars=locals())
        else:
            f = schema.lob_filing.select(limit=limit, offset=page*limit)

        if not f: raise web.notfound()
        return render.lob_filings(f, limit)

class lob_contrib:
    def GET(self, filing_id):
        limit = 50
        page = int(web.input(page=0).page)
        if filing_id:
            c = schema.lob_contribution.select(where='filing_id=$filing_id', limit=limit, offset=page*limit, order='amount desc', vars=locals())
        else:
            c = schema.lob_contribution.select(limit=limit, offset=page*limit, order='amount desc')

        if not c: raise web.notfound()
        return render.lob_contributions(c, limit)

class lob_pac:
    def GET(self, pac_id):
        limit = 50
        i = web.input(page=0)
        page = int(i.page)
        if 'filing_id' in i:
            p = [x.pac for x in schema.lob_pac_filings.select(where='filing_id=$i.filing_id',limit=limit, offset=page*limit, vars=locals())]
        elif pac_id:
            p = schema.lob_pac.select(where='id=$pac_id',limit=limit, offset=page*limit, vars=locals())
        else:
            p = schema.lob_pac.select(limit=limit, offset=page*limit)

        if not p: raise web.notfound()
        return render.lob_pacs(p, limit)

class lob_org:
    def GET(self, org_id):
        limit = 50
        i = web.input(page=0)
        page = int(i.page)
        if org_id:
            o = schema.lob_organization.select(where='id=$org_id', limit=limit, offset=page*limit, order='name asc', vars=locals())
        else:
            o = schema.lob_organization.select(limit=limit, offset=page*limit, order='name asc')

        if not o: raise web.notfound()
        return render.lob_orgs(o,limit)

class lob_person:
    def GET(self, person_id):
        limit = 50
        i = web.input(page=0)
        page = int(i.page)
        if person_id:
            p = schema.lob_person.select(where='id=$person_id', limit=limit, offset=page*limit, order='lastname asc', vars=locals())
        else:
            p = schema.lob_person.select(limit=limit, offset=page*limit, order='lastname asc')

        if not p: raise web.notfound()
        return render.lob_person(p, limit)

class politician_introduced:
    def GET(self, politician_id):
        try:
            pol = schema.Politician.where(id=politician_id)[0]
        except IndexError:
            raise web.notfound()
        return render.politician_introduced(pol)

class politician_groups:
    def GET(self, politician_id):
        related = group_politician_similarity(politician_id)
        try:
            pol = schema.Politician.where(id=politician_id)[0]
        except IndexError:
            raise web.notfound()
        return render.politician_groups(pol, related)

class politician_contribs:
  def GET(self, polid):
    try:
        pol = schema.Politician.where(id=polid)[0]
    except IndexError:
        raise web.notfound()
    contribs = politician_contributors(polid)
    return render.politician_contribs(pol, contribs)

class politician_contrib_employers:
  def GET(self, polid):
    try:
        pol = schema.Politician.where(id=polid)[0]
    except IndexError:
        raise web.notfound()
    contribs = politician_contributor_employers(polid)
    return render.politician_contrib_employers(pol, contribs)

class politician_group:
    def GET(self, politician_id, group_id):
        votes = db.select(['position', 'interest_group_bill_support', 'bill'],
          where="interest_group_bill_support.bill_id = position.bill_id AND "
                 "position.bill_id = bill.id AND "
                "politician_id = $politician_id AND group_id = $group_id",
         order='vote = support desc',
          vars=locals())
        
        pol = schema.Politician.where(id=politician_id)
        group = schema.Interest_Group.where(id=group_id)
        if not (pol and group):
            raise web.notfound()
        return render.politician_group(votes, pol[0].name, group[0].longname)


r_safeproperty = re.compile('^[a-z0-9_]+$')
table_map = {'us': 'district', 'p': 'politician'}

class dproperty:
    def GET(self, table, what):
        try:
            table = table_map[table]
        except KeyError:
            raise web.notfound()
        if not r_safeproperty.match(what): raise web.notfound()

        #if `what` is not there in the `table` (provide available options rather than 404???)
        try:
            maxnum = float(db.select(table,
                                 what='max(%s) as m' % what,
                                 vars=locals())[0].m)
        except:
            raise web.notfound()

        items = db.select(table,
                          what="*, 100*(%s/$maxnum) as pct" % what,
                          order='%s desc' % what,
                          where='%s is not null' % what,
                          vars=locals()).list()
        for item in items:
            if table == 'district':
                item.id = 'd' + item.name
                item.path = '/us/' + item.name.lower()
            elif table == 'politician':
                state = '-'+item.district_id.split('-')[0] if item.district_id else ''
                item.name = '%s %s (%s%s)' % (item.firstname, item.lastname,
                  (item.party or 'I')[0], state)
                item.path = '/p/' + item.id
        return render.dproperty(items, what)

def sparkpos(table, what, id):
    if table == 'district':
        id_col = 'name'
        id = id.upper()
    elif table == 'politician':
        id_col= 'id'
    else: return 0
    assert table in table_map.values()
    if not r_safeproperty.match(what): raise web.notfound()
    
    item = db.query("select count(*) as position from %(table)s, \
      (select * from %(table)s where %(id_col)s=$id) as a \
      where %(table)s.%(what)s > a.%(what)s" % 
      {'table':table, 'what':what, 'id_col':id_col}, vars={'id': id})[0]
    return item.position + 1 # '#1' looks better than '#0'

class sparkdist:
    def GET(self, table, what):
        try:
            table = table_map[table]
        except KeyError:
            raise web.notfound()
        if not r_safeproperty.match(what): raise web.notfound()

        inp = web.input(point=None)
        points = db.select(table, what=what, order=what+' asc', where=what+' is not null')
        points = [x[what] for x in points.list()]

        web.header('Content-Type', 'image/png')
        return simplegraphs.sparkline(points, inp.point)
        
class staticdata:
    def GET(self, path):
        if not web.config.debug:
            raise web.notfound()

        assert '..' not in path, 'security'
        return file('data/' + path).read()

app = web.application(urls, globals())
def notfound():
    web.ctx.status = '404 Not Found'
    return web.notfound(getattr(render, '404')())

def internalerror():
    return web.internalerror(file('templates/500.html').read())

def and_join(phrases):
    """Format a list of phrases as an English list.

    This must already exist in web.py but I can't find it."""
    phrases = list(phrases)
    assert len(phrases) > 0          # caller should special-case this
    if len(phrases) == 1:
        return phrases[0]
    elif len(phrases) == 2:
        return ' and '.join(phrases)
    else:
        return ', '.join(phrases[:-1] + ['and ' + phrases[-1]])

def pluralize(noun, plural, number):
    """Inflect a noun for number."""
    if number == 1:
        return noun
    else:
        return plural

def divide_into_ranges(ints):
    """Summarize a sorted sequence of ints as a sequence of contiguous ranges.

    Return value is a list of lists of the form `[start, stop]`, where `stop`
    is one more than the last item in the range.
    """
    rv = []

    for item in ints:
        if len(rv) == 0:
            rv.append([item, item+1])
        elif item == rv[-1][1]:
            rv[-1][1] += 1
        else:
            rv.append([item, item+1])

    return rv

def congress_ranges(congresses):
    """Format a list of Congress ordinal numbers
    as a coalesced English sequence of ranges."""

    nthstr = web.utils.nthstr

    if not congresses:
        return "no known Congresses"

    ranges = divide_into_ranges(congresses)
    phrases = []
    for start, stop in ranges:
        if stop == start + 1:
            phrases.append(nthstr(start))
        elif stop == start + 2:
            phrases.append(nthstr(start))
            phrases.append(nthstr(start+1))
        else:
            phrases.append('%s–%s' % (nthstr(start), nthstr(stop-1)))

    return "the %s %s" % (and_join(phrases),
                          pluralize("Congress", "Congresses", len(congresses)))

app.notfound = notfound
if production_mode:
    app.internalerror = web.emailerrors(config.send_errors_to, internalerror)

if __name__ == "__main__": app.run()
