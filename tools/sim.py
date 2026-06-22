import json, math, statistics, random

raw=open('/home/zonief/IdeaProjects/cadastria-proto/data.js').read()
DATA=json.loads(raw.split('=',1)[1].rstrip().rstrip(';'))
CELLS0=DATA['cells']

P=dict(multMax=2.5,k=6,pnjInflCap=4.5,totalInflCap=8,commerceSchoolBonus=2.0,captureBare=0.30,captureBuilt=1.0,
 builderBonus=1.3,renteRate=0.05,renteExp=0.8,fricheTaxRate=0.03,maintRate=0.10,buildBase=50,buildDens=10,pnjBuyMarkup=1.15)
WEIGHT=dict(RESIDENTIEL=0,COMMERCE=1,ECOLE=1,PARC=1.5,TRANSPORT=2)
OP=dict(RESIDENTIEL=2,COMMERCE=5,ECOLE=3,PARC=3,TRANSPORT=4)
TYPES=['COMMERCE','ECOLE','PARC','TRANSPORT','RESIDENTIEL']
PNJ=['p0','p1','p2','p3','p4']
def lvlF(l): return 1.0 if l<=1 else (1.5 if l==2 else 1.8)

def gdist(a,b):
    return math.hypot((a['lat']-b['lat'])*111320,(a['lon']-b['lon'])*111320*math.cos(a['lat']*math.pi/180))

class Game:
    def __init__(self,seed,params,goal=5000,start=1500,days=30):
        self.R=random.Random(seed); self.P=params; self.goal=goal; self.days=days
        self.cells=[dict(i=c['i'],socle=c['socle'],area=c['area'],cat=c['cat'],near=c['near'],
                         lat=c['lat'],lon=c['lon'],nbr=c['nbr'],owner=None,amenity=None,boost=1.0) for c in CELLS0]
        self.money=start; self.pending=0.0; self.day=1; self.events=[]
        self.rival=self.R.choice(PNJ)
        self.seedPNJ()
    def seedPNJ(self):
        hot=sorted([c for c in self.cells if c['socle']>=88],key=lambda c:-c['socle'])
        pick=[]
        for c in hot:
            if len(pick)>=18: break
            if any(gdist(u,c)<70 for u in pick): continue
            pick.append(c)
        for idx,c in enumerate(pick):
            c['owner']=PNJ[idx%len(PNJ)]
            t='TRANSPORT' if c['cat']=='transport' else 'PARC' if c['cat']=='parc' else 'ECOLE' if c['cat']=='ecole' else 'COMMERCE'
            c['amenity']=dict(type=t,level=1+(1 if self.R.random()<0.3 else 0))
    def ownerKind(self,c): return 'HUMAN' if c['owner']=='me' else ('PNJ' if c['owner'] else None)
    def hasSchool(self,c):
        for j,k in c['nbr']:
            if k>=0.5:
                a=self.cells[j]['amenity']
                if a and a['type']=='ECOLE': return True
        return False
    def contrib(self,a,c,k):
        w=WEIGHT[a['type']]
        if w<=0: return 0
        if a['type']=='COMMERCE' and self.hasSchool(c): w*=self.P['commerceSchoolBonus']
        return w*k*lvlF(a['level'])
    def influence(self,c):
        pnj=hum=0.0
        if c['amenity']:
            ct=self.contrib(c['amenity'],c,1.0)
            if self.ownerKind(c)=='PNJ': pnj+=ct
            else: hum+=ct
        for j,k in c['nbr']:
            o=self.cells[j]
            if not o['amenity']: continue
            ct=self.contrib(o['amenity'],o,k)
            if self.ownerKind(o)=='PNJ': pnj+=ct
            else: hum+=ct
        pnj=min(pnj,self.P['pnjInflCap'])
        return min(pnj+hum,self.P['totalInflCap'])
    def value(self,c):
        cap=self.P['captureBuilt'] if c['amenity'] else self.P['captureBare']
        base=min(c['socle']*(1+cap*self.P['multMax']*math.tanh(self.influence(c)/self.P['k'])), c['socle']*(1+self.P['multMax']))
        return base*c.get('boost',1.0)
    def rente(self,v): return self.P['renteRate']*(v**self.P['renteExp'])
    def builderOp(self,a): return OP[a['type']]*lvlF(a['level'])*self.P['builderBonus']
    def maint(self,a): return self.P['maintRate']*OP[a['type']]*lvlF(a['level'])
    def fricheTax(self,c): return self.P['fricheTaxRate']*c['socle']
    def buyCost(self,c): return round(self.value(c)*(self.P['pnjBuyMarkup'] if (c['owner'] and c['owner']!='me') else 1))
    def buildCost(self,c,level):
        d=sum(1 for j,k in c['nbr'] if self.cells[j]['amenity'])
        return round((self.P['buildBase']+self.P['buildDens']*d)*lvlF(level))
    def mine(self): return [c for c in self.cells if c['owner']=='me']
    def empire(self): return round(sum(self.value(c) for c in self.mine()))
    def dailyNet(self):
        s=0
        for c in self.mine():
            v=self.value(c)
            if c['amenity']: s+=self.rente(v)+self.builderOp(c['amenity'])-self.maint(c['amenity'])
            else: s+=self.rente(v)-self.fricheTax(c)
        return s
    # events
    def recomputeBoosts(self):
        for c in self.cells: c['boost']=1.0
        for ev in self.events:
            for i in ev['cells']: self.cells[i]['boost']*=ev['factor']
    def applyEvent(self):
        kinds=[1.20,1.15,1.12,1.14,0.85]; durs=[4,5,3,4,3]
        ki=self.R.randrange(5); f=kinds[ki]; d=durs[ki]
        named=[c for c in self.cells if c['near']]
        center=self.R.choice(named) if named else self.R.choice(self.cells)
        aff=[c['i'] for c in self.cells if gdist(c,center)<=150]
        if aff: self.events.append(dict(cells=aff,factor=f,until=self.day+d))
    def pnjAct(self,p):
        mine=self.mine(); isRival=(p==self.rival)
        own=[c for c in self.cells if c['owner']==p and c['amenity'] and c['amenity']['level']<3]
        if own and self.R.random()<0.45:
            self.R.choice(own)['amenity']['level']+=1; return
        pool=[c for c in self.cells if not c['owner']]
        if isRival and mine:
            pool.sort(key=lambda c:min(gdist(c,x) for x in mine)); pool=pool[:10]
        else:
            pool.sort(key=lambda c:-c['socle']); pool=pool[:12]
        if not pool: return
        tg=pool[self.R.randrange(len(pool))]; tg['owner']=p
        ty='TRANSPORT' if tg['cat']=='transport' else 'PARC' if tg['cat']=='parc' else 'ECOLE' if tg['cat']=='ecole' else 'COMMERCE'
        tg['amenity']=dict(type=ty,level=1)
    def nextDay(self):
        self.pending+=self.dailyNet(); self.day+=1
        self.events=[e for e in self.events if e['until']>=self.day]
        if self.R.random()<0.6: self.applyEvent()
        self.recomputeBoosts()
        actors=PNJ[:]; self.R.shuffle(actors)
        for p in actors[:2]: self.pnjAct(p)
    # ---- BOT (joueur correct) ----
    def best_build(self):
        best=None
        for c in self.mine():
            cur=c['amenity']
            cands=[]
            if cur is None:
                for t in TYPES: cands.append((t,1))
            elif cur['level']<3:
                cands.append((cur['type'],cur['level']+1))
            if not cands: continue
            ownNb=[self.cells[j] for j,k in c['nbr'] if self.cells[j]['owner']=='me']
            scope=[c]+ownNb
            before={id(x):self.value(x) for x in scope}
            for (t,lvl) in cands:
                cost=self.buildCost(c,lvl)
                c['amenity']=dict(type=t,level=lvl)
                gain=sum(self.value(x)-before[id(x)] for x in scope)
                c['amenity']=cur
                if cost>0 and gain>0:
                    roi=gain/cost
                    if best is None or roi>best[0]: best=(roi,c,t,lvl,cost,gain)
        return best
    def best_buy(self):
        mine=self.mine()
        pool=[c for c in self.cells if not c['owner']]
        def score(c):
            s=c['socle']
            if mine: s-=0.04*min(gdist(c,x) for x in mine)
            return s
        pool.sort(key=score,reverse=True)
        for c in pool:
            if self.buyCost(c)<=self.money: return (c,self.buyCost(c))
        return None
    def botTurn(self):
        self.money+=math.floor(self.pending); self.pending=0
        acts=0
        while acts<4:
            if not self.mine():
                buy=self.best_buy()
                if buy: c,cost=buy; c['owner']='me'; self.money-=cost; acts+=1; continue
                break
            bb=self.best_build(); buy=self.best_buy()
            if bb and bb[4]<=self.money and bb[0]>=0.15:
                _,c,t,lvl,cost,gain=bb; c['amenity']=dict(type=t,level=lvl); self.money-=cost; acts+=1
            elif buy and buy[1]<=self.money:
                c,cost=buy; c['owner']='me'; self.money-=cost; acts+=1
            else: break
    def play(self):
        winDay=None
        for d in range(self.days):
            self.botTurn()
            if winDay is None and self.empire()>=self.goal: winDay=self.day
            self.nextDay()
        self.botTurn()
        if winDay is None and self.empire()>=self.goal: winDay=self.day
        return dict(win=winDay is not None, winDay=winDay, empire=self.empire(), money=round(self.money), owned=len(self.mine()))

def run(N=80,**kw):
    res=[Game(s,P,**kw).play() for s in range(N)]
    wins=[r for r in res if r['win']]
    emp=sorted(r['empire'] for r in res)
    def pct(a,p): return a[int(len(a)*p)] if a else 0
    return dict(N=N, winRate=round(100*len(wins)/N), 
        medWinDay=(statistics.median(r['winDay'] for r in wins) if wins else None),
        medEmpire=pct(emp,0.5), p25=pct(emp,0.25), p75=pct(emp,0.9),
        medOwned=statistics.median(r['owned'] for r in res))

import sys
print('BASELINE (goal=5000, start=1500, 30j):')
print(run(80))

print()
print('--- Recherche de réglage (cible ~55-65% pour un bot correct) ---')
configs=[
 ('baseline goal5000 start1500', dict(goal=5000,start=1500)),
 ('goal4500 start1500', dict(goal=4500,start=1500)),
 ('goal4000 start1500', dict(goal=4000,start=1500)),
 ('goal4500 start2000', dict(goal=4500,start=2000)),
 ('goal5000 start2000', dict(goal=5000,start=2000)),
]
for name,kw in configs:
    r=run(80,**kw); print(f"{name:28s} -> win {r['winRate']}% | medWinDay {r['medWinDay']} | medEmpire {r['medEmpire']} (p25 {r['p25']} / p90 {r['p75']}) | owned {r['medOwned']}")

print()
print('--- Réglage fin (cible ~58-63%) ---')
def runp(N,params,**kw):
    res=[Game(s,params,**kw).play() for s in range(N)]
    wins=[r for r in res if r['win']]; emp=sorted(r['empire'] for r in res)
    pct=lambda a,p:(a[int(len(a)*p)] if a else 0)
    return dict(winRate=round(100*len(wins)/N),medWinDay=(statistics.median(r['winDay'] for r in wins) if wins else None),medEmpire=pct(emp,0.5))
import copy
def withp(**ov):
    p=copy.deepcopy(P); p.update(ov); return p
variants=[
 ('start1600 goal5000', withp(), dict(goal=5000,start=1600)),
 ('start1700 goal5000', withp(), dict(goal=5000,start=1700)),
 ('start1500 goal4800', withp(), dict(goal=4800,start=1500)),
 ('start1500 goal5000 rente0.055', withp(renteRate=0.055), dict(goal=5000,start=1500)),
 ('start1600 goal5000 rente0.055', withp(renteRate=0.055), dict(goal=5000,start=1600)),
]
for name,p,kw in variants:
    r=runp(80,p,**kw); print(f"{name:34s} -> win {r['winRate']}% | medWinDay {r['medWinDay']} | medEmpire {r['medEmpire']}")
