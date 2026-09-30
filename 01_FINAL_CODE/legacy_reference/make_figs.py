import pickle, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from engine import *
R=pickle.load(open('./results.pkl','rb'))
BLUE,ORANGE,AQUA,GRAY,INK='#2a78d6','#eb6834','#1baf7a','#6b6b6b','#333333'
plt.rcParams.update({'font.family':'serif','font.size':9,'axes.edgecolor':'#999999','axes.labelcolor':INK,'xtick.color':INK,'ytick.color':INK,'axes.spines.top':False,'axes.spines.right':False})
OUT='../Figures/'
# Fig: cumulative session wealth
fig,axs=plt.subplots(3,3,figsize=(7.2,6.6),sharex=True)
for ax,t in zip(axs.flat,TICKERS):
    s=R[t]['series']; d=pd.to_datetime(s['Date'])
    ax.plot(d,s['C'],color=GRAY,lw=1.2,label='Buy-and-hold (close-to-close)')
    ax.plot(d,s['N'],color=BLUE,lw=1.5,label='Overnight only (Long/Cash)')
    ax.plot(d,s['D'],color=ORANGE,lw=1.5,label='Daytime only (Cash/Long)')
    ax.set_yscale('log'); ax.axhline(100,color='#cccccc',lw=0.8,zorder=0)
    ax.set_title(t,fontsize=10,color=INK); ax.grid(axis='y',color='#eeeeee',lw=0.6,which='major')
    ax.xaxis.set_major_locator(mdates.YearLocator(6)); ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,p: f'{v:,.0f}'))
    ax.yaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10,subs=(1,2,5)))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
for ax in axs[:,0]: ax.set_ylabel('Wealth (log scale)')
h,l=axs[0,0].get_legend_handles_labels()
fig.legend(h,l,loc='lower center',ncol=3,frameon=False,fontsize=8.5)
fig.tight_layout(rect=(0,0.05,1,1)); fig.savefig(OUT+'session_wealth.png',dpi=300); plt.close()
# Fig: terminal wealth vs cost
grid=np.linspace(0,5e-4,21)
fig,axs=plt.subplots(3,3,figsize=(7.2,6.6),sharex=True)
for ax,t in zip(axs.flat,TICKERS):
    df=load(t)
    for (N,D),c,lab in [(('Long','Long'),GRAY,'Buy-and-hold'),(('Long','Cash'),BLUE,'Long/Cash'),(('Long','Reversal'),AQUA,'Long/Reversal'),(('Cash','Reversal'),ORANGE,'Cash/Reversal')]:
        y=[run(df,N,D,g)['TW'] for g in grid]
        ax.plot(grid*1e4,y,color=c,lw=1.6,label=lab)
    ax.axhline(100,color='#999999',lw=0.8,ls='--',zorder=0)
    ax.set_yscale('log'); ax.set_title(t,fontsize=10,color=INK); ax.grid(axis='y',color='#eeeeee',lw=0.6)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,p: f'{v:,.0f}' if v>=1 else f'{v:g}'))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
for ax in axs[:,0]: ax.set_ylabel('Terminal wealth (log)')
for ax in axs[-1]: ax.set_xlabel('Cost per unit of turnover (bps)')
h,l=axs[0,0].get_legend_handles_labels()
fig.legend(h,l,loc='lower center',ncol=4,frameon=False,fontsize=8.5)
fig.tight_layout(rect=(0,0.05,1,1)); fig.savefig(OUT+'tw_vs_cost.png',dpi=300); plt.close()
print('figs done')
