import pickle, numpy as np, pandas as pd
from engine import TICKERS, RULES
R=pickle.load(open('./results.pkl','rb'))
OUT='../Tables/'
ORDER=[('Cash','Cash'),('Long','Cash'),('Short','Cash'),('Cash','Long'),('Cash','Short'),('Long','Long'),('Short','Short'),('Short','Long'),('Long','Short'),
 ('Cash','Momentum'),('Cash','Reversal'),('Momentum','Cash'),('Reversal','Cash'),('Momentum','Momentum'),('Momentum','Reversal'),('Reversal','Momentum'),('Reversal','Reversal'),
 ('Long','Momentum'),('Long','Reversal'),('Short','Momentum'),('Short','Reversal'),('Momentum','Long'),('Reversal','Long'),('Momentum','Short'),('Reversal','Short')]
GROUP_BREAKS={1,5,9,13,17,21}
def stars(p): return '$^{***}$' if p<0.01 else ('$^{**}$' if p<0.05 else ('$^{*}$' if p<0.10 else ''))
def fmt_int(x):
    if x>=100: return f'{x:,.0f}'
    if x>=10: return f'{x:.0f}' if False else f'{x:,.0f}'
    return f'{x:.1f}' if x<10 else f'{x:.0f}'
def header(ncols_label='\\#'):
    h='\\toprule\n\\multirow{2}{*}{\\#} & \\multicolumn{2}{c}{\\textbf{Strategy}} & '+' & '.join(f'\\multirow{{2}}{{*}}{{\\textbf{{{t}}}}}' for t in TICKERS)+' \\\\\n'
    h+='\\cmidrule(lr){2-3}\n & \\textbf{Overnight} & \\textbf{Daytime} '+'& '*9+'\\\\\n\\midrule\n'
    return h
def matrix_table(key,cost,label,caption,notes,fmt,better,colored=True,metric_src='strat'):
    s='\\begin{table}[H]\n\\centering\n\\caption{'+caption+'}\n\\label{'+label+'}\n\\resizebox{\\textwidth}{!}{%\n\\begin{tabular}{c ll rrrrrrrrr}\n'+header()
    for i,(N,D) in enumerate(ORDER):
        if i in GROUP_BREAKS: s+='\\midrule\n'
        cells=[]
        for t in TICKERS:
            v=R[t]['strat'][(N,D,cost)][key]; bh=R[t]['strat'][('Long','Long',cost)][key]
            txt=fmt(v)
            if not colored or (N,D)==('Cash','Cash'): cells.append(txt); continue
            if (N,D)==('Long','Long'): col='blue!20'
            else: col='green!20' if better(v,bh) else 'red!12'
            cells.append(f'\\cellcolor{{{col}}}{txt}')
        s+=f'{i} & {N} & {D} & '+' & '.join(cells)+' \\\\\n'
    s+='\\bottomrule\n\\end{tabular}%\n}\n\\begin{flushleft}\n\\footnotesize\n\\textit{Notes:} '+notes+'\n\\end{flushleft}\n\\end{table}\n'
    return s
common='Strategy labels report the overnight position first and the daytime position second. Strategy~0 (Cash/Cash) is the zero-exposure benchmark, and blue cells mark buy-and-hold (Long/Long). '
tw=lambda v: f'{v:,.0f}' if v>=10 else f'{v:.1f}'
for cost,tag in [(0,'0bps'),(1e-4,'1bp'),(2e-4,'2bps')]:
    bps={0:'0 bps',1e-4:'1 bp',2e-4:'2 bps'}[cost]
    open(OUT+f'tw_{tag}.tex','w').write(matrix_table('TW',cost,f'tab:tw_{tag}',f'Terminal Wealth of Commodity ETF Strategies at {bps}, 2007--2025',
      'Terminal wealth from an initial wealth index of 100, after deducting proportional costs of '+bps+' per unit of turnover (including the final liquidation). '+common+'Green cells exceed buy-and-hold terminal wealth for the same ETF and cost level; red cells do not.',tw,lambda v,b:v>b))
open(OUT+'trades.tex','w').write(matrix_table('trades',0,'tab:trades','Number of Trades of Commodity ETF Strategies, 2007--2025',
  'A trade is any session boundary at which the position changes, including the initial entry and the final liquidation. A switch between long and short counts as one trade but two units of turnover. '+common+'Static strategies (rows 0--8) trade on a fixed schedule and therefore have identical counts across ETFs; dynamic strategies depend on the sign sequence of each ETF\'s lagged session returns. Each ETF sample contains 4,776 trading days (9,552 sessions).',lambda v: f'{v:,.0f}',None,colored=False))
open(OUT+'mdd.tex','w').write(matrix_table('MDD',0,'tab:mdd','Maximum Drawdown of Commodity ETF Strategies at 0 bps, 2007--2025',
  'Maximum drawdown (\\%) is the largest peak-to-trough decline in the session-level wealth index over the full sample, reported as a positive loss. '+common+'Green cells have a smaller drawdown than buy-and-hold for the same ETF.',lambda v: f'{abs(100*v):.1f}',lambda v,b:v<b))
open(OUT+'vol.tex','w').write(matrix_table('Vol',0,'tab:vol','Annualized Volatility of Commodity ETF Strategies at 0 bps, 2007--2025',
  'Annualized volatility (\\%) of daily strategy returns, using 252 trading days per year. '+common+'Green cells have lower volatility than buy-and-hold for the same ETF.',lambda v: f'{100*v:.1f}',lambda v,b:v<b))
open(OUT+'sharpe.tex','w').write(matrix_table('SR',0,'tab:sharpe','Sharpe Ratio of Commodity ETF Strategies at 0 bps, 2007--2025',
  'Annualized Sharpe ratio of daily strategy returns with a zero risk-free rate, $\\sqrt{252}\\,\\bar{G}/\\hat\\sigma(G)$. '+common+'Green cells exceed the buy-and-hold Sharpe ratio for the same ETF. The Cash/Cash Sharpe ratio is undefined.',lambda v: '--' if v!=v else f'{v:.2f}',lambda v,b:v>b))
open(OUT+'sharpe_2bps.tex','w').write(matrix_table('SR',2e-4,'tab:sharpe_2bps','Sharpe Ratio of Commodity ETF Strategies at 2 bps, 2007--2025',
  'As in Table~\\ref{tab:sharpe}, but computed from daily returns net of 2 bps per unit of turnover. '+common,lambda v: '--' if v!=v else f'{v:.2f}',lambda v,b:v>b))

# ---------- descriptive table
s='\\begin{table}[H]\n\\centering\n\\caption{Overnight and Daytime Returns of Commodity ETFs, 2007--2025}\n\\label{tab:desc}\n\\resizebox{\\textwidth}{!}{%\n\\begin{tabular}{l rr rr rr rr rrr}\n\\toprule\n'
s+=' & \\multicolumn{2}{c}{\\textbf{Overnight}} & \\multicolumn{2}{c}{\\textbf{Daytime}} & \\multicolumn{2}{c}{\\textbf{Difference}} & \\multicolumn{2}{c}{\\textbf{Volatility (\\%)}} & \\multicolumn{3}{c}{\\textbf{Growth of 100}} \\\\\n'
s+='\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-9}\\cmidrule(lr){10-12}\n'
s+='\\textbf{ETF} & Mean & $t$ & Mean & $t$ & Mean & $t$ & Night & Day & Night & Day & Close \\\\\n\\midrule\n'
for t in TICKERS:
    d=R[t]['desc']
    s+=f"{t} & {100*d['N']['ann']:.2f} & {d['N']['t']:.2f}{stars(d['N']['p'])} & {100*d['D']['ann']:.2f} & {d['D']['t']:.2f}{stars(d['D']['p'])} & {100*252*d['diff']['mean']:.2f} & {d['diff']['t']:.2f}{stars(d['diff']['p'])} & {100*d['N']['annvol']:.1f} & {100*d['D']['annvol']:.1f} & {d['N']['cum']:,.0f} & {d['D']['cum']:,.0f} & {d['C']['cum']:,.0f} \\\\\n"
s+='\\bottomrule\n\\end{tabular}%\n}\n\\begin{flushleft}\n\\footnotesize\n\\textit{Notes:} Means are annualized arithmetic means of daily simple session returns (\\% per year, $252\\times$ daily mean). The overnight return runs from the previous close to the current open, adjusted for distributions; the daytime return runs from the open to the close. ``Difference'' is the annualized mean of $r^{N}_t-r^{D}_t$. $t$-statistics use Newey--West standard errors with $\\lfloor 4(T/100)^{2/9}\\rfloor=8$ lags. $^{*}$, $^{**}$ and $^{***}$ denote two-sided significance at 10\\%, 5\\% and 1\\%. Growth of 100 compounds each session return separately (equivalent to Long/Cash, Cash/Long and Long/Long at 0 bps). $T=4{,}776$ trading days, 9 January 2007--31 December 2025.\n\\end{flushleft}\n\\end{table}\n'
open(OUT+'desc.tex','w').write(s)
# holm on diff
from statsmodels.stats.multitest import multipletests
ph=multipletests([R[t]['desc']['diff']['p'] for t in TICKERS],method='holm')[1]
pN=multipletests([R[t]['desc']['N']['p'] for t in TICKERS],method='holm')[1]
pickle.dump({'holm_diff':dict(zip(TICKERS,ph)),'holm_N':dict(zip(TICKERS,pN))},open('./holm.pkl','wb'))
# ---------- weekend table + distribution extras
s='\\begin{table}[H]\n\\centering\n\\caption{Distributional Properties of Session Returns and the Weekend Component of Overnight Returns}\n\\label{tab:weekend}\n\\resizebox{\\textwidth}{!}{%\n\\begin{tabular}{l rr rr rr rrr rrr}\n\\toprule\n'
s+=' & \\multicolumn{2}{c}{\\textbf{\\% Positive}} & \\multicolumn{2}{c}{\\textbf{Skewness}} & \\multicolumn{2}{c}{\\textbf{Excess kurtosis}} & \\multicolumn{3}{c}{\\textbf{Weekday overnight}} & \\multicolumn{3}{c}{\\textbf{Weekend/holiday overnight}} \\\\\n'
s+='\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-10}\\cmidrule(lr){11-13}\n'
s+='\\textbf{ETF} & Night & Day & Night & Day & Night & Day & $n$ & Mean & $t$ & $n$ & Mean & $t$ \\\\\n\\midrule\n'
for t in TICKERS:
    d=R[t]['desc']
    s+=f"{t} & {100*d['N']['pos']:.1f} & {100*d['D']['pos']:.1f} & {d['N']['skew']:.2f} & {d['D']['skew']:.2f} & {d['N']['kurt']:.1f} & {d['D']['kurt']:.1f} & {d['N_wkday']['n']:,} & {1e4*d['N_wkday']['mean']:.2f} & {d['N_wkday']['t']:.2f}{stars(d['N_wkday']['p'])} & {d['N_wkend']['n']:,} & {1e4*d['N_wkend']['mean']:.2f} & {d['N_wkend']['t']:.2f}{stars(d['N_wkend']['p'])} \\\\\n"
s+='\\bottomrule\n\\end{tabular}%\n}\n\\begin{flushleft}\n\\footnotesize\n\\textit{Notes:} ``\\% Positive'' is the share of sessions with a strictly positive return. Weekend/holiday overnight sessions are those in which more than one calendar day separates the previous close from the current open (Mondays and post-holiday sessions); the remainder are weekday overnight sessions. Means are in basis points per session; $t$-statistics are Newey--West with 8 lags.\n\\end{flushleft}\n\\end{table}\n'
open(OUT+'weekend.tex','w').write(s)
# ---------- predictability
s='\\begin{table}[H]\n\\centering\n\\caption{Conditional Predictability of Session Returns}\n\\label{tab:pred}\n\\resizebox{\\textwidth}{!}{%\n\\begin{tabular}{l rr rrr rr rrr rr}\n\\toprule\n'
s+=' & \\multicolumn{5}{c}{\\textbf{Daytime session}} & \\multicolumn{5}{c}{\\textbf{Overnight session}} & \\multicolumn{2}{c}{\\textbf{Cross-session}}\\\\\n\\cmidrule(lr){2-6}\\cmidrule(lr){7-11}\\cmidrule(lr){12-13}\n'
s+=' & \\multicolumn{2}{c}{AR(1)} & \\multicolumn{3}{c}{Reversal rule} & \\multicolumn{2}{c}{AR(1)} & \\multicolumn{3}{c}{Reversal rule} & $r^{D}_t$ on $r^{N}_t$ & $r^{N}_{t}$ on $r^{D}_{t-1}$ \\\\\n\\cmidrule(lr){2-3}\\cmidrule(lr){4-6}\\cmidrule(lr){7-8}\\cmidrule(lr){9-11}\\cmidrule(lr){12-12}\\cmidrule(lr){13-13}\n'
s+='\\textbf{ETF} & $\\hat\\beta$ & $t$ & Mean & $t$ & Hit & $\\hat\\beta$ & $t$ & Mean & $t$ & Hit & $\\hat\\beta$ ($t$) & $\\hat\\beta$ ($t$) \\\\\n\\midrule\n'
for t in TICKERS:
    p=R[t]['pred']
    s+=f"{t} & {p['D_ar']['b']:.3f} & {p['D_ar']['t']:.2f}{stars(p['D_ar']['p'])} & {100*252*p['D_sign']['revmean']:.2f} & {p['D_sign']['revt']:.2f}{stars(p['D_sign']['revp'])} & {100*p['D_sign']['hit']:.1f} & {p['N_ar']['b']:.3f} & {p['N_ar']['t']:.2f}{stars(p['N_ar']['p'])} & {100*252*p['N_sign']['revmean']:.2f} & {p['N_sign']['revt']:.2f}{stars(p['N_sign']['revp'])} & {100*p['N_sign']['hit']:.1f} & {p['D_on_N']['b']:.3f} ({p['D_on_N']['t']:.2f}){stars(p['D_on_N']['p'])} & {p['N_on_Dlag']['b']:.3f} ({p['N_on_Dlag']['t']:.2f}){stars(p['N_on_Dlag']['p'])} \\\\\n"
s+='\\bottomrule\n\\end{tabular}%\n}\n\\begin{flushleft}\n\\footnotesize\n\\textit{Notes:} AR(1) reports the slope from regressing a session return on the previous realization of the same session, $r^{s}_{t}=a+\\beta r^{s}_{t-1}+e_t$. ``Reversal rule'' is the gross return of the same-session reversal position, $-\\mathrm{sign}(r^{s}_{t-1})\\,r^{s}_{t}$, reported as an annualized mean (\\% per year) with its Newey--West $t$-statistic; the Momentum rule earns exactly the negative of this series before costs. ``Hit'' is the percentage of sessions in which the sign of $r^{s}_t$ is opposite to that of $r^{s}_{t-1}$. The cross-session columns regress the daytime return on the same day\'s overnight return, and the overnight return on the preceding daytime return. All $t$-statistics are Newey--West with 8 lags; stars as in Table~\\ref{tab:desc}.\n\\end{flushleft}\n\\end{table}\n'
open(OUT+'pred.tex','w').write(s)
# ---------- break-even & summary of cost sensitivity
KEY=[('Long','Cash'),('Cash','Short'),('Long','Short'),('Cash','Reversal'),('Reversal','Reversal'),('Long','Reversal'),('Reversal','Short')]
s='\\begin{table}[H]\n\\centering\n\\caption{Transaction-Cost Sensitivity: Strategies Beating Buy-and-Hold and Break-Even Costs}\n\\label{tab:breakeven}\n\\resizebox{\\textwidth}{!}{%\n\\begin{tabular}{l '+'r'*9+'}\n\\toprule\n & '+' & '.join(f'\\textbf{{{t}}}' for t in TICKERS)+' \\\\\n\\midrule\n'
s+='\\multicolumn{10}{l}{\\textit{Panel A. Number of the 23 active strategies with terminal wealth above buy-and-hold}}\\\\\n'
for cost,lab in [(0,'0 bps'),(1e-4,'1 bp'),(2e-4,'2 bps')]:
    row=[]
    for t in TICKERS:
        bh=R[t]['strat'][('Long','Long',cost)]['TW']
        row.append(str(sum(R[t]['strat'][(N,D,cost)]['TW']>bh for (N,D) in ORDER if (N,D) not in [('Cash','Cash'),('Long','Long')])))
    s+=lab+' & '+' & '.join(row)+' \\\\\n'
s+='Buy-and-hold TW (2 bps) & '+' & '.join(f"{R[t]['strat'][('Long','Long',2e-4)]['TW']:,.0f}" for t in TICKERS)+' \\\\\n'
s+='Best strategy TW (2 bps) & '+' & '.join(f"{max(R[t]['strat'][(N,D,2e-4)]['TW'] for (N,D) in ORDER if (N,D)!=('Long','Long')):,.0f}" for t in TICKERS)+' \\\\\n'
s+='Best strategy (2 bps) & '+' & '.join('{\\scriptsize '+'/'.join(x[0] for x in max([(N,D) for (N,D) in ORDER if (N,D)!=('Long','Long')],key=lambda k:R[t]['strat'][(k[0],k[1],2e-4)]['TW']))+'}' for t in TICKERS)+' \\\\\n'
s+='\\midrule\n\\multicolumn{10}{l}{\\textit{Panel B. Break-even cost versus buy-and-hold (bps per unit of turnover)}}\\\\\n'
for (N,D) in KEY:
    s+=f'{N}/{D} & '+' & '.join('--' if np.isnan(R[t]['breakeven'][(N,D)]['bh']) else f"{R[t]['breakeven'][(N,D)]['bh']:.2f}" for t in TICKERS)+' \\\\\n'
s+='\\midrule\n\\multicolumn{10}{l}{\\textit{Panel C. Break-even cost versus cash, i.e., terminal wealth of 100 (bps per unit of turnover)}}\\\\\n'
for (N,D) in KEY:
    s+=f'{N}/{D} & '+' & '.join('--' if np.isnan(R[t]['breakeven'][(N,D)]['cash']) else f"{R[t]['breakeven'][(N,D)]['cash']:.2f}" for t in TICKERS)+' \\\\\n'
s+='\\bottomrule\n\\end{tabular}%\n}\n\\begin{flushleft}\n\\footnotesize\n\\textit{Notes:} Panel~A counts the active strategies (excluding Cash/Cash and Long/Long) whose terminal wealth exceeds that of buy-and-hold at each cost level, and reports buy-and-hold and the best alternative at 2 bps. The best strategy is selected among all 24 alternatives, including Cash/Cash, and is abbreviated with the overnight rule first (C = Cash, L = Long, S = Short, M = Momentum, R = Reversal). Panels~B and~C report the proportional cost per unit of turnover at which a strategy\'s terminal wealth equals that of buy-and-hold (B) or the initial wealth of 100 (C), found by bisection. ``--'' indicates that the strategy does not beat the relevant benchmark even at zero cost.\n\\end{flushleft}\n\\end{table}\n'
open(OUT+'breakeven.tex','w').write(s)
# ---------- pairwise significance
s='\\begin{table}[H]\n\\centering\n\\caption{Pairwise Comparison of Selected Strategies with Buy-and-Hold}\n\\label{tab:pairwise}\n\\resizebox{\\textwidth}{!}{%\n\\begin{tabular}{ll '+'r'*9+'}\n\\toprule\n\\textbf{Strategy} & & '+' & '.join(f'\\textbf{{{t}}}' for t in TICKERS)+' \\\\\n\\midrule\n'
for cost,lab in [(0,'0 bps'),(2e-4,'2 bps')]:
    s+=f'\\multicolumn{{11}}{{l}}{{\\textit{{Panel {"A" if cost==0 else "B"}. Transaction cost of {lab}}}}}\\\\\n'
    for (N,D) in [('Long','Cash'),('Long','Short'),('Cash','Reversal'),('Long','Reversal'),('Reversal','Reversal')]:
        a=[R[t]['pairwise'][(N,D,cost)] for t in TICKERS]
        s+=f'{N}/{D} & $\\Delta\\mu$ & '+' & '.join(f"{100*x['dmean_ann']:.1f}{stars(x['p_boot'])}" for x in a)+' \\\\\n'
        s+=f' & $\\Delta SR$ & '+' & '.join(f"{x['dSR']:.2f}{stars(x['p_SR'])}" for x in a)+' \\\\\n'
    if cost==0: s+='\\midrule\n'
s+='\\bottomrule\n\\end{tabular}%\n}\n\\begin{flushleft}\n\\footnotesize\n\\textit{Notes:} $\\Delta\\mu$ is the annualized mean of the daily return differential between the strategy and buy-and-hold (\\% per year); stars refer to one-sided stationary-bootstrap $p$-values for $H_0\\!:\\,\\Delta\\mu\\le 0$. $\\Delta SR$ is the difference in annualized Sharpe ratios; stars refer to two-sided stationary-bootstrap $p$-values for $H_0\\!:\\,\\Delta SR=0$ in the spirit of \\citet{cmd_ledoit_wolf_2008}. Both use 2,000 paired resamples of trading days with an expected block length of 10 days \\citep{cmd_politis_romano_1994}. $^{*}$, $^{**}$ and $^{***}$ denote significance at 10\\%, 5\\% and 1\\%. Strategy labels list the overnight rule first.\n\\end{flushleft}\n\\end{table}\n'
open(OUT+'pairwise.tex','w').write(s)
# ---------- SPA
s='\\begin{table}[H]\n\\centering\n\\caption{Superior Predictive Ability Tests Against Buy-and-Hold}\n\\label{tab:spa}\n\\resizebox{\\textwidth}{!}{%\n\\begin{tabular}{l ccc c ccc c ccc}\n\\toprule\n & \\multicolumn{3}{c}{\\textbf{0 bps}} && \\multicolumn{3}{c}{\\textbf{1 bp}} && \\multicolumn{3}{c}{\\textbf{2 bps}}\\\\\n\\cmidrule(lr){2-4}\\cmidrule(lr){6-8}\\cmidrule(lr){10-12}\n\\textbf{ETF} & Best & $p_{\\mathrm{SPA}}$ & StepM && Best & $p_{\\mathrm{SPA}}$ & StepM && Best & $p_{\\mathrm{SPA}}$ & StepM \\\\\n\\midrule\n'
ab=lambda k: k[0][0]+'/'+k[1][0]
for t in TICKERS:
    row=[]
    for c in [0,1e-4,2e-4]:
        x=R[t]['spa'][c]
        row.append(f"{ab(x['best'])} & {x['p_c']:.3f} & {len(x['stepm'])}")
    s+=t+' & '+' && '.join(row)+' \\\\\n'
s+='\\bottomrule\n\\end{tabular}%\n}\n\\begin{flushleft}\n\\footnotesize\n\\textit{Notes:} For each ETF and cost level, the benchmark is buy-and-hold and the candidate set contains the other 24 strategies (including Cash/Cash); the loss is the negative daily net return. ``Best'' is the strategy with the highest terminal wealth among the candidates (overnight rule first; C = Cash, L = Long, S = Short, M = Momentum, R = Reversal). $p_{\\mathrm{SPA}}$ is the consistent $p$-value of \\citet{cmd_hansen_2005} for the null that no candidate has a higher expected daily return than buy-and-hold. StepM is the number of candidates identified as superior by the stepwise procedure of \\citet{cmd_romano_wolf_2005} at a family-wise error rate of 5\\%. Both use 5,000 stationary-bootstrap replications with an expected block length of 10 days.\n\\end{flushleft}\n\\end{table}\n'
open(OUT+'spa.tex','w').write(s)
# ---------- subperiods
subs=list(R['GLD']['sub'].keys())
s='\\begin{table}[H]\n\\centering\n\\caption{Subperiod Results}\n\\label{tab:sub}\n\\resizebox{\\textwidth}{!}{%\n\\begin{tabular}{ll '+'r'*9+'}\n\\toprule\n & & '+' & '.join(f'\\textbf{{{t}}}' for t in TICKERS)+' \\\\\n\\midrule\n'
for j,sp in enumerate(subs):
    s+=f'\\multicolumn{{11}}{{l}}{{\\textit{{Panel {chr(65+j)}. {sp[0]}--{sp[1]}}}}}\\\\\n'
    e=[R[t]['sub'][sp] for t in TICKERS]
    s+='Overnight mean & (\\%/yr) & '+' & '.join(f"{100*x['N']['ann']:.1f}{stars(2*(1-__import__('scipy').stats.norm.cdf(abs(x['N']['t']))))}" for x in e)+' \\\\\n'
    s+='Daytime mean & (\\%/yr) & '+' & '.join(f"{100*x['D']['ann']:.1f}{stars(2*(1-__import__('scipy').stats.norm.cdf(abs(x['D']['t']))))}" for x in e)+' \\\\\n'
    s+='Daytime reversal & (\\%/yr) & '+' & '.join(f"{100*x['Drev']['ann']:.1f}{stars(2*(1-__import__('scipy').stats.norm.cdf(abs(x['Drev']['t']))))}" for x in e)+' \\\\\n'
    for (N,D) in [('Long','Long'),('Long','Cash'),('Long','Short'),('Long','Reversal')]:
        s+=f'{N}/{D} & TW 0 / 2 bps & '+' & '.join(f"{x[(N,D,0)]:,.0f} / {x[(N,D,2e-4)]:,.0f}" for x in e)+' \\\\\n'
    if j<len(subs)-1: s+='\\midrule\n'
s+='\\bottomrule\n\\end{tabular}%\n}\n\\begin{flushleft}\n\\footnotesize\n\\textit{Notes:} Session means are annualized arithmetic means; ``Daytime reversal'' is the gross return of the same-session daytime reversal position. Stars denote Newey--West significance (10\\%, 5\\%, 1\\%). Terminal wealth (TW) restarts at 100 at the beginning of each subperiod and is reported at 0 bps and 2 bps per unit of turnover. Strategy labels list the overnight rule first.\n\\end{flushleft}\n\\end{table}\n'
open(OUT+'sub.tex','w').write(s)
# ---------- universe table
info={'DBA':('Invesco DB Agriculture Fund','Agriculture futures (corn, wheat, soybeans, sugar, cocoa, coffee, cattle, hogs, etc.)','Commodity pool (futures)'),
'DBB':('Invesco DB Base Metals Fund','Aluminum, zinc and copper futures','Commodity pool (futures)'),
'DBC':('Invesco DB Commodity Index Tracking Fund','Diversified index of 14 energy, metal and agricultural futures','Commodity pool (futures)'),
'DBE':('Invesco DB Energy Fund','WTI and Brent crude, heating oil, RBOB gasoline, natural gas futures','Commodity pool (futures)'),
'DBO':('Invesco DB Oil Fund','WTI crude oil futures','Commodity pool (futures)'),
'DBP':('Invesco DB Precious Metals Fund','Gold and silver futures','Commodity pool (futures)'),
'GLD':('SPDR Gold Shares','Physical gold bullion','Grantor trust (physical)'),
'SLV':('iShares Silver Trust','Physical silver bullion','Grantor trust (physical)'),
'USO':('United States Oil Fund','Near-month WTI crude oil futures','Commodity pool (futures)')}
s='\\begin{table}[H]\n\\centering\n\\caption{Commodity Exchange-Traded Products in the Sample}\n\\label{tab:universe}\n\\small\n\\begin{tabularx}{\\linewidth}{l >{\\raggedright\\arraybackslash}p{4.2cm} >{\\raggedright\\arraybackslash}X >{\\raggedright\\arraybackslash}p{2.6cm} r}\n\\toprule\n\\textbf{Ticker} & \\textbf{Fund} & \\textbf{Exposure} & \\textbf{Structure} & \\textbf{Med. \\$ vol.} \\\\\n\\midrule\n'
for t in TICKERS:
    a,b,c=info[t]; s+=f"{t} & {a} & {b} & {c} & {R[t]['desc']['dvol_musd']:,.1f} \\\\\n"
s+='\\bottomrule\n\\end{tabularx}\n\\begin{flushleft}\n\\footnotesize\n\\textit{Notes:} All products are listed on NYSE Arca. The Invesco DB funds track Deutsche Bank commodity indices through exchange-traded futures with rules-based (``optimum yield'') roll schedules. ``Med. \\$ vol.'' is the median daily dollar trading volume (USD millions, close price $\\times$ shares traded) over 2007--2025, computed from the sample data.\n\\end{flushleft}\n\\end{table}\n'
open(OUT+'universe.tex','w').write(s)
import glob
for f in glob.glob(OUT+'*.tex'):
    t=open(f).read()
    t=t.replace('\\begin{table}[H]\n','\\begin{table}[H]\n\\begin{adjustwidth}{-\\extralength}{0cm}\n',1).replace('\\end{table}','\\end{adjustwidth}\n\\end{table}').replace('\\resizebox{\\textwidth}','\\resizebox{\\linewidth}')
    open(f,'w').write(t)
print('tables written')
