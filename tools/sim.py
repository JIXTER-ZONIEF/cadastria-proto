import json, math, statistics, random
DATA=json.loads(open('/home/zonief/IdeaProjects/cadastria-proto/data.js').read().split('=',1)[1].rstrip().rstrip(';'))
CELLS0=DATA['cells']
P=dict(multMax=2.5,k=6,pnjInflCap=4.5,totalInflCap=8,commerceSchoolBonus=2.0,captureBare=0.30,captureBuilt=1.0,
 builderBonus=1.3,renteRate=0.055,renteExp=0.8,fricheTaxRate=0.03,maintRate=0.10,buildBase=50,buildDens=10,pnjBuyMarkup=1.15)
WEIGHT=dict(RESIDENTIEL=0,COMMERCE=1,ECOLE=1,PARC=1.5,TRANSPORT=2)
OP=dict(RESIDENTIEL=2,COMMERCE=5,ECOLE=3,PARC=3,TRANSPORT=4)
TYPES=['COMMERCE','ECOLE','PARC','TRANSPORT','RESIDENTIEL']; PNJ=['p0','p1','p2','p3','p4']
CAP={}; ZONE_R=160  # définis dynamiquement
def lvlF(l): return 1.0 if l<=1 else (1.5 if l==2 else 1.8)
def gdist(a,b): return math.hypot((a['lat']-b['lat'])*111320,(a['lon']-b['lon'])*111320*math.cos(a['lat']*math.pi/180))
class G:
    def __init__(self,seed,goal=5000,start=1500,days=30):
        self.R=random.Random(seed); self.goal=goal; self.days=days
        self.cells=[dict(i=c['i'],socle=c['socle'],area=c['area'],cat=c['cat'],near=c['near'],lat=c['lat'],lon=c['lon'],nbr=c['nbr'],owner=None,amenity=None,boost=1.0,forSale=False,ask=0) for c in CELLS0]
        self.money=start; self.day=1; self.events=[]; self.rival=self.R.choice(PNJ); self.seedPNJ()
    def seedPNJ(self):
        hot=sorted([c for c in self.cells if c['socle']>=88],key=lambda c:-c['socle']); pick=[]
        for c in hot:
            if len(pick)>=18: break
            if any(gdist(u,c)<70 for u in pick): continue
            pick.append(c)
        for i,c in enumerate(pick):
            c['owner']=PNJ[i%5]; t='TRANSPORT' if c['cat']=='transport' else 'PARC' if c['cat']=='parc' else 'ECOLE' if c['cat']=='ecole' else 'COMMERCE'
            c['amenity']=dict(type=t,level=1+(1 if self.R.random()<0.3 else 0))
    def ok(self,c): return 'HUMAN' if c['owner']=='me' else ('PNJ' if c['owner'] else None)
    def school(self,c):
        for j,k in c['nbr']:
            if k>=0.5 and self.cells[j]['amenity'] and self.cells[j]['amenity']['type']=='ECOLE': return True
        return False
    def contrib(self,a,c,k):
        w=WEIGHT[a['type']]
        if w<=0: return 0
        if a['type']=='COMMERCE' and self.school(c): w*=P['commerceSchoolBonus']
        return w*k*lvlF(a['level'])
    def infl(self,c):
        pnj=hum=0.0
        if c['amenity']:
            ct=self.contrib(c['amenity'],c,1.0); pnj,hum=(pnj+ct,hum) if self.ok(c)=='PNJ' else (pnj,hum+ct)
        for j,k in c['nbr']:
            o=self.cells[j]
            if not o['amenity']: continue
            ct=self.contrib(o['amenity'],o,k); pnj,hum=(pnj+ct,hum) if self.ok(o)=='PNJ' else (pnj,hum+ct)
        return min(min(pnj,P['pnjInflCap'])+hum,P['totalInflCap'])
    def val(self,c):
        cap=P['captureBuilt'] if c['amenity'] else P['captureBare']
        return min(c['socle']*(1+cap*P['multMax']*math.tanh(self.infl(c)/P['k'])),c['socle']*(1+P['multMax']))*c['boost']
    def rente(self,v): return P['renteRate']*(v**P['renteExp'])
    def bop(self,a): return OP[a['type']]*lvlF(a['level'])*P['builderBonus']
    def maint(self,a): return P['maintRate']*OP[a['type']]*lvlF(a['level'])
    def friche(self,c): return P['fricheTaxRate']*c['socle']
    def buyCost(self,c): return round(self.val(c)*(P['pnjBuyMarkup'] if (c['owner'] and c['owner']!='me') else 1))
    def buildCost(self,c,lvl): return round((P['buildBase']+P['buildDens']*sum(1 for j,k in c['nbr'] if self.cells[j]['amenity']))*lvlF(lvl))
    def zoneCount(self,c,t): return sum(1 for o in self.cells if o is not c and o['amenity'] and o['amenity']['type']==t and gdist(o,c)<=ZONE_R)
    def canBuild(self,c,t):
        if t not in CAP: return True
        if c['amenity'] and c['amenity']['type']==t: return True
        return self.zoneCount(c,t)<CAP[t]
    def mine(self): return [c for c in self.cells if c['owner']=='me']
    def empire(self): return round(sum(self.val(c) for c in self.mine()))
    def recompute(self):
        for c in self.cells: c['boost']=1.0
        for ev in self.events:
            for i in ev['cells']: self.cells[i]['boost']*=ev['factor']
    def event(self):
        f=[1.20,1.15,1.12,1.14,0.85]; d=[4,5,3,4,3]; ki=self.R.randrange(5)
        named=[c for c in self.cells if c['near']]; center=self.R.choice(named)
        aff=[c['i'] for c in self.cells if gdist(c,center)<=150]
        if aff: self.events.append(dict(cells=aff,factor=f[ki],until=self.day+d[ki]))
    def pnjAct(self,p):
        mine=self.mine()
        own=[c for c in self.cells if c['owner']==p and c['amenity'] and c['amenity']['level']<3]
        if own and self.R.random()<0.45: self.R.choice(own)['amenity']['level']+=1; return
        pool=[c for c in self.cells if not c['owner']]
        if p==self.rival and mine: pool.sort(key=lambda c:min(gdist(c,x) for x in mine)); pool=pool[:10]
        else: pool.sort(key=lambda c:-c['socle']); pool=pool[:12]
        if not pool: return
        tg=pool[self.R.randrange(len(pool))]; tg['owner']=p
        ty='TRANSPORT' if tg['cat']=='transport' else 'PARC' if tg['cat']=='parc' else 'ECOLE' if tg['cat']=='ecole' else 'COMMERCE'
        if not self.canBuild(tg,ty): ty='COMMERCE' if self.canBuild(tg,'COMMERCE') else 'RESIDENTIEL'
        tg['amenity']=dict(type=ty,level=1)
    def nextDay(self):
        rev=cost=0
        for c in self.mine():
            v=self.val(c)
            if c['amenity']: rev+=self.rente(v)+self.bop(c['amenity']); cost+=self.maint(c['amenity'])
            else: rev+=self.rente(v); cost+=self.friche(c)
        self.money+=rev-cost
        self.day+=1; self.events=[e for e in self.events if e['until']>=self.day]
        if self.R.random()<0.6: self.event()
        self.recompute()
        a=PNJ[:]; self.R.shuffle(a)
        for p in a[:2]: self.pnjAct(p)
    def bestBuild(self):
        best=None
        for c in self.mine():
            cur=c['amenity']
            cands=[(t,1) for t in TYPES] if cur is None else ([(cur['type'],cur['level']+1)] if cur['level']<3 else [])
            ownNb=[self.cells[j] for j,k in c['nbr'] if self.cells[j]['owner']=='me']; scope=[c]+ownNb
            bef={id(x):self.val(x) for x in scope}
            for (t,lvl) in cands:
                if not self.canBuild(c,t): continue
                cost=self.buildCost(c,lvl); c['amenity']=dict(type=t,level=lvl)
                gain=sum(self.val(x)-bef[id(x)] for x in scope); c['amenity']=cur
                if cost>0 and gain>0:
                    roi=gain/cost
                    if best is None or roi>best[0]: best=(roi,c,t,lvl,cost)
        return best
    def bestBuy(self):
        mine=self.mine(); pool=[c for c in self.cells if not c['owner']]
        pool.sort(key=lambda c:c['socle']-(0.04*min(gdist(c,x) for x in mine) if mine else 0),reverse=True)
        for c in pool:
            if self.buyCost(c)<=self.money: return (c,self.buyCost(c))
        return None
    def bot(self):
        acts=0
        while acts<4:
            if not self.mine():
                b=self.bestBuy()
                if b: b[0]['owner']='me'; self.money-=b[1]; acts+=1; continue
                break
            bb=self.bestBuild(); by=self.bestBuy()
            if bb and bb[4]<=self.money and bb[0]>=0.15: bb[1]['amenity']=dict(type=bb[2],level=bb[3]); self.money-=bb[4]; acts+=1
            elif by and by[1]<=self.money: by[0]['owner']='me'; self.money-=by[1]; acts+=1
            else: break
    def play(self):
        wd=None
        for _ in range(self.days):
            self.bot()
            if wd is None and self.empire()>=self.goal: wd=self.day
            self.nextDay()
        self.bot()
        if wd is None and self.empire()>=self.goal: wd=self.day
        # vérif zonage : aucun secteur ne dépasse les caps
        viol=0
        for c in self.cells:
            if c['amenity'] and c['amenity']['type'] in CAP:
                if self.zoneCount(c,c['amenity']['type'])+1>CAP[c['amenity']['type']]+2: viol+=1
        return dict(win=wd is not None,winDay=wd,empire=self.empire(),owned=len(self.mine()),viol=viol)

import statistics as st
def runcfg(zr,cap,goal,N=70):
    global ZONE_R,CAP
    ZONE_R=zr; CAP=cap
    res=[G(s,goal=goal).play() for s in range(N)]
    wins=[r for r in res if r['win']]; emp=sorted(r['empire'] for r in res)
    return dict(R=zr,goal=goal,win=round(100*len(wins)/N),wd=(st.median(r['winDay'] for r in wins) if wins else None),medEmp=emp[len(emp)//2])
LEN=dict(ECOLE=3,TRANSPORT=3,PARC=4,COMMERCE=12)
for g in [4700,4500,4300,4100]:
    print(runcfg(160,LEN,g))
