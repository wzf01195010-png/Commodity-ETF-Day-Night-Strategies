import numpy as np, pandas as pd, pickle, itertools
from engine import *
import statsmodels.api as sm
from arch.bootstrap import SPA, StationaryBootstrap, StepM
rng=np.random.default_rng(20260928)
COSTS=[0,1e-4,2e-4]
STRATS=[(N,D) for N in RULES for D in RULES]
def nw_mean(x,lags=None):
    x=np.asarray(x,float); x=x[~np.isnan(x)]
    if lags is None: lags=int(np.floor(4*(len(x)/100)**(2/9)))
    m=sm.OLS(x,np.ones(len(x))).fit(cov_type='HAC',cov_kwds={'maxlags':lags})
    return m.params[0], m.tvalues[0], m.pvalues[0]
def nw_reg(y,X,lags=None):
    X=sm.add_constant(X); 
    if lags is None: lags=int(np.floor(4*(len(y)/100)**(2/9)))
    m=sm.OLS(y,X,missing='drop').fit(cov_type='HAC',cov_kwds={'maxlags':lags})
    return m
def sb_indices(T,B,L=10):
    p=1/L; idx=np.empty((B,T),dtype=np.int64)
    start=rng.integers(0,T,size=(B,T)); newblk=rng.random((B,T))<p; newblk[:,0]=True
    cur=start[:,0].copy()
    for t in range(T):
        cur=np.where(newblk[:,t],start[:,t],(cur+1)%T); idx[:,t]=cur
    return idx
def run_sub(df,N,D,cost,start,end):
    full=df
    mask=(df.Date>=start)&(df.Date<=end)
    i0=np.where(mask)[0][0]
    sub=df[mask].reset_index(drop=True)
    lagN0=full.rN.values[i0-1] if i0>0 else df.attrs['pre'].overnight_adjusted_return.values[-1]
    lagD0=full.rD.values[i0-1] if i0>0 else df.attrs['pre'].daytime_return.values[-1]
    return backtest(sub,N,D,cost,lagN0=lagN0,lagD0=lagD0)

R={}
B=2000
for t in TICKERS:
    df=load(t); T=len(df); out={'T':T,'start':df.Date.min(),'end':df.Date.max()}
    raw=pd.read_csv(f'{DATA}/{t}_daily.csv',parse_dates=['Date']); raw=raw[raw.in_sample].reset_index(drop=True)
    # ---------- descriptive
    desc={}
    for k,col in [('N','rN'),('D','rD'),('C','rC')]:
        x=df[col].values; m,tt,p=nw_mean(x)
        desc[k]=dict(mean=m,t=tt,p=p,sd=x.std(ddof=1),pos=(x>0).mean(),skew=pd.Series(x).skew(),kurt=pd.Series(x).kurt(),ann=m*252,annvol=x.std(ddof=1)*np.sqrt(252),cum=100*np.prod(1+x))
    dm,dt,dp=nw_mean(df.rN.values-df.rD.values)
    desc['diff']=dict(mean=dm,t=dt,p=dp)
    # weekend split of overnight
    gap=(df.Date-raw.Date.shift(1)).dt.days.values.copy(); gap[0]=(df.Date.iloc[0]-df.attrs['pre'].Date.iloc[-1]).days
    wk=gap>1
    for k,msk in [('N_wkday',~wk),('N_wkend',wk)]:
        m,tt,p=nw_mean(df.rN.values[msk]); desc[k]=dict(mean=m,t=tt,p=p,n=int(msk.sum()))
    # overnight vs daytime per-hour normalization not used
    # liquidity: Abdi-Ranaldo CHL spread, dollar volume
    c=np.log(raw.Close.values); h=np.log(raw.High.values); l=np.log(raw.Low.values); eta=(h+l)/2
    prod=(c[:-1]-eta[:-1])*(c[:-1]-eta[1:])
    mon=pd.Series(prod,index=raw.Date.values[:-1]).groupby(pd.Grouper(freq='ME')).mean()
    s2=4*mon; spread=np.sqrt(np.maximum(s2,0))
    desc['AR_spread_bps']=spread.mean()*1e4
    desc['AR_spread_med_bps']=spread.median()*1e4
    desc['dvol_musd']=(raw.Close*raw.Volume).median()/1e6
    out['desc']=desc
    # ---------- predictability
    pred={}
    for s,col in [('N','rN'),('D','rD')]:
        x=df[col].values; lag=np.r_[np.nan,x[:-1]]
        m=nw_reg(x[1:],lag[1:]); pred[s+'_ar']=dict(b=m.params[1],t=m.tvalues[1],p=m.pvalues[1])
        sg=np.sign(lag[1:]); y=x[1:]
        up=y[sg>0].mean(); dn=y[sg<0].mean()
        revret=-sg*y; mm,tt,pp=nw_mean(revret)
        pred[s+'_sign']=dict(up=up,dn=dn,revmean=mm,revt=tt,revp=pp,hit=(np.sign(y)==-sg)[sg!=0].mean())
    # cross-session: daytime on same-day overnight; next overnight on daytime
    m=nw_reg(df.rD.values,df.rN.values); pred['D_on_N']=dict(b=m.params[1],t=m.tvalues[1],p=m.pvalues[1])
    m=nw_reg(df.rN.values[1:],df.rD.values[:-1]); pred['N_on_Dlag']=dict(b=m.params[1],t=m.tvalues[1],p=m.pvalues[1])
    # daytime on both own lag and same-day overnight
    X=np.column_stack([df.rD.values[:-1],df.rN.values[1:]]); m=nw_reg(df.rD.values[1:],X)
    pred['D_multi']=dict(b1=m.params[1],t1=m.tvalues[1],b2=m.params[2],t2=m.tvalues[2])
    out['pred']=pred
    # ---------- strategies
    strat={}; daily={}
    for cst in COSTS:
        for (N,D) in STRATS:
            r=run(df,N,D,cst); mt=metrics(r['daily'],r['sessW'])
            strat[(N,D,cst)]=dict(TW=r['TW'],trades=r['trades'],turnover=r['turnover'],**mt)
            daily[(N,D,cst)]=r['daily']
    out['strat']=strat
    # break-even cost vs B&H and vs cash
    be={}
    def tw(N,D,c): return run(df,N,D,c)['TW']
    for (N,D) in STRATS:
        if (N,D) in [('Cash','Cash'),('Long','Long')]: continue
        f=lambda c: np.log(tw(N,D,c))-np.log(tw('Long','Long',c))
        g=lambda c: np.log(tw(N,D,c))-np.log(100)
        res={}
        for nm,fn in [('bh',f),('cash',g)]:
            lo,hi=0.0,0.01
            if fn(lo)<=0: res[nm]=np.nan; continue
            for _ in range(50):
                mid=(lo+hi)/2
                if fn(mid)>0: lo=mid
                else: hi=mid
            res[nm]=lo*1e4
        be[(N,D)]=res
    out['breakeven']=be
    # ---------- pairwise vs B&H (differential mean & Sharpe) with stationary bootstrap
    idx=sb_indices(T,B,10)
    pw={}
    for cst in [0,2e-4]:
        bh=daily[('Long','Long',cst)]
        for (N,D) in STRATS:
            if (N,D) in [('Cash','Cash'),('Long','Long')]: continue
            x=daily[(N,D,cst)]; d=x-bh
            mu,tt,_=nw_mean(d)
            dbar=d[idx].mean(1)
            p_mean=((dbar-d.mean())>=d.mean()).mean()   # one-sided H1: mean>0
            sr=lambda a: a.mean(-1)/a.std(-1,ddof=1)*np.sqrt(252)
            dsr=sr(x)-sr(bh); xb=x[idx]; bb=bh[idx]; dsrb=sr(xb)-sr(bb)
            p_sr=(np.abs(dsrb-dsr)>=abs(dsr)).mean()
            pw[(N,D,cst)]=dict(dmean_ann=mu*252,t=tt,p_boot=p_mean,dSR=dsr,p_SR=p_sr)
    out['pairwise']=pw
    # ---------- SPA / StepM (loss = -return), 24 active strategies incl. Cash/Cash? exclude cash/cash & BH
    spa={}
    for cst in COSTS:
        bh=-daily[('Long','Long',cst)]
        names=[(N,D) for (N,D) in STRATS if (N,D)!=('Long','Long')]
        L=np.column_stack([-daily[(N,D,cst)] for (N,D) in names])
        sp=SPA(bh,L,block_size=10,reps=5000,bootstrap='stationary',seed=int(rng.integers(1e9)))
        sp.compute()
        st=StepM(bh,L,size=0.05,block_size=10,reps=5000,bootstrap='stationary',seed=int(rng.integers(1e9)))
        st.compute()
        sup=[names[int(str(c).replace('model.',''))] if not isinstance(c,(int,np.integer)) else names[c] for c in st.superior_models] if st.superior_models is not None else []
        best=max(names,key=lambda k: strat[(k[0],k[1],cst)]['TW'])
        spa[cst]=dict(p_c=sp.pvalues['consistent'],p_l=sp.pvalues['lower'],p_u=sp.pvalues['upper'],stepm=sup,best=best)
    out['spa']=spa
    # ---------- subperiods
    subs=[('2007-01-01','2012-12-31'),('2013-01-01','2019-12-31'),('2020-01-01','2025-12-31')]
    sub={}
    for (a,b) in subs:
        msk=(df.Date>=a)&(df.Date<=b)
        e={}
        for k,col in [('N','rN'),('D','rD')]:
            m,tt,p=nw_mean(df[col].values[msk]); e[k]=dict(ann=m*252,t=tt)
        x=df.rD.values; lag=np.r_[np.nan,x[:-1]]; rv=-np.sign(lag)*x
        m,tt,p=nw_mean(rv[msk]); e['Drev']=dict(ann=m*252,t=tt)
        x=df.rN.values; lag=np.r_[np.nan,x[:-1]]; rv=-np.sign(lag)*x
        m,tt,p=nw_mean(rv[msk]); e['Nrev']=dict(ann=m*252,t=tt)
        for (N,D) in [('Long','Long'),('Long','Cash'),('Cash','Long'),('Cash','Reversal'),('Long','Short'),('Long','Reversal'),('Reversal','Reversal')]:
            for cst in [0,2e-4]:
                r=run_sub(df,N,D,cst,a,b); e[(N,D,cst)]=r['TW']
        sub[(a[:4],b[:4])]=e
    out['sub']=sub
    # series for figures
    out['series']={'Date':df.Date.values,'N':np.cumprod(1+df.rN.values)*100,'D':np.cumprod(1+df.rD.values)*100,'C':np.cumprod(1+df.rC.values)*100,
                   'LR0':100*np.cumprod(1+daily[('Long','Reversal',0)]),'LR2':100*np.cumprod(1+daily[('Long','Reversal',2e-4)]),'BH':100*np.cumprod(1+daily[('Long','Long',0)])}
    R[t]=out
    print(t,'done',flush=True)
pickle.dump(R,open('results.pkl','wb'))
