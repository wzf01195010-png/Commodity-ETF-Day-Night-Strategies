import numpy as np, pandas as pd
TICKERS=['DBA','DBB','DBC','DBE','DBO','DBP','GLD','SLV','USO']
RULES=['Cash','Long','Short','Momentum','Reversal']
DATA='data'  # folder containing TICKER_daily.csv files
def load(t):
    d=pd.read_csv(f'{DATA}/{t}_daily.csv',parse_dates=['Date'])
    full=d.copy()
    d=d[d.in_sample].reset_index(drop=True)
    out=pd.DataFrame({'Date':d.Date,'rN':d.overnight_adjusted_return.astype(float),'rD':d.daytime_return.astype(float),'rC':d.close_to_close_adjusted_return.astype(float),'Volume':d.Volume})
    pre=full[~full.in_sample]
    out.attrs['pre']=pre
    return out
def positions(rule, r, lag0=np.nan):
    n=len(r)
    if rule=='Cash': return np.zeros(n)
    if rule=='Long': return np.ones(n)
    if rule=='Short': return -np.ones(n)
    lag=np.r_[lag0, r[:-1]]
    s=np.sign(np.nan_to_num(lag,nan=0.0))
    return s if rule=='Momentum' else -s
def backtest(df, ruleN, ruleD, cost, lagN0=np.nan, lagD0=np.nan, return_detail=False):
    rN=df.rN.values; rD=df.rD.values; n=len(df)
    zN=positions(ruleN,rN,lagN0); zD=positions(ruleD,rD,lagD0)
    z=np.empty(2*n); z[0::2]=zN; z[1::2]=zD
    r=np.empty(2*n); r[0::2]=rN; r[1::2]=rD
    zprev=np.r_[0,z[:-1]]
    Q=np.abs(z-zprev)
    g=(1+z*r)*(1-cost*Q)-1
    final_q=abs(z[-1])
    W=100*np.cumprod(1+g)
    W_end=W[-1]*(1-cost*final_q)
    daily=(1+g[0::2])*(1+g[1::2])-1
    daily[-1]=(1+daily[-1])*(1-cost*final_q)-1
    res=dict(TW=W_end, turnover=Q.sum()+final_q, trades=int((Q>0).sum()+(final_q>0)), daily=daily, sessW=W, z=z, gN=g[0::2], gD=g[1::2])
    return res
def metrics(daily, sessW=None):
    W=100*np.cumprod(1+daily)
    WW=W if sessW is None else sessW
    peak=np.maximum.accumulate(np.r_[100,WW])[1:]
    mdd=-(WW/peak-1).min()
    vol=daily.std(ddof=1)*np.sqrt(252)
    sr=daily.mean()/daily.std(ddof=1)*np.sqrt(252) if daily.std()>0 else np.nan
    yrs=len(daily)/252
    cagr=(W[-1]/100)**(1/yrs)-1
    return dict(MDD=mdd,Vol=vol,SR=sr,CAGR=cagr)

def run(df, N, D, cost):
    pre=df.attrs['pre']
    return backtest(df,N,D,cost,lagN0=pre.overnight_adjusted_return.values[-1],lagD0=pre.daytime_return.values[-1])
