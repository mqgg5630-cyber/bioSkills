"""limma lmFit + eBayes 的 Python 实现（两组比较）。"""
import numpy as np
from scipy import stats, special, optimize

def fit_fdist(var, df1):
    """Smyth 2004 fitFDist: 由每基因方差估计先验 s0^2 与 d0。"""
    ok = np.isfinite(var) & (var > 0)
    x = var[ok]
    z = np.log(x)
    e = z - special.digamma(df1/2) + np.log(df1/2)
    emean = e.mean()
    evar  = e.var(ddof=1) - special.polygamma(1, df1/2)
    if evar > 0:
        # 解 trigamma(d0/2) = evar
        f = lambda y: special.polygamma(1, np.exp(y)/2) - evar
        try:
            y = optimize.brentq(f, -40, 40)
            d0 = np.exp(y)
        except ValueError:
            d0 = np.inf
        s02 = np.exp(emean + special.digamma(d0/2) - np.log(d0/2)) if np.isfinite(d0) \
              else np.exp(emean)
    else:
        d0, s02 = np.inf, np.exp(emean)
    return s02, d0

def lmfit_ebayes(E, group, ref, alt):
    """E: genes x samples；group: 长度=样本数。返回 logFC / t / p / B 等。"""
    g = np.asarray(group)
    i_ref, i_alt = g == ref, g == alt
    n1, n2 = i_ref.sum(), i_alt.sum()
    X = np.column_stack([np.ones(len(g)), i_alt.astype(float)])  # ~ 1 + alt
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = E @ X @ XtX_inv.T
    resid = E - beta @ X.T
    df_res = len(g) - X.shape[1]
    sigma2 = (resid**2).sum(axis=1) / df_res
    stdev_unscaled = np.sqrt(XtX_inv[1, 1])

    s02, d0 = fit_fdist(sigma2, df_res)
    if np.isfinite(d0):
        s2_post = (d0*s02 + df_res*sigma2) / (d0 + df_res)
        df_total = df_res + d0
    else:
        s2_post = np.full_like(sigma2, s02); df_total = np.inf
    t_mod = beta[:, 1] / (stdev_unscaled * np.sqrt(s2_post))
    p = 2 * stats.t.sf(np.abs(t_mod), df_total)
    return dict(logFC=beta[:, 1], AveExpr=E.mean(axis=1), t=t_mod,
                P_Value=p, sigma2=sigma2, s2_post=s2_post, s02=s02, d0=d0,
                df_total=df_total, n1=n1, n2=n2)

def bh(p):
    p = np.asarray(p); n = len(p); o = np.argsort(p); r = np.empty(n, int); r[o] = np.arange(1, n+1)
    q = p * n / r
    qs = np.minimum.accumulate(q[o][::-1])[::-1]
    out = np.empty(n); out[o] = np.clip(qs, 0, 1); return out
