"""模块 B：分辨率感知的过程识别（修订稿 5.2 节）。

对每个事件：
  1. 取通知时刻 τ_n 之后、观测结束之前的残差 r_k = B̂_k − P_k（kW），通知前残差用于估计噪声 σ̂；
  2. 结构候选 M0（无响应）、M1（单平台四阶段）、M2（双平台：中途掉落再响应）；
  3. 初值：采样网格上的线性代价动态规划（6 段分段线性）+ 启发式初值 + 随机起点；
  4. 精修：有界非线性最小二乘，观测模型含精确区间平均算子 A_Δ（template.interval_average）；
  5. 结构选择：M1/M2 按 BIC；M0 对 M1/M2 的似然比统计量与伪事件上标定的临界值比较（把基线误差计入）；
  6. 不确定性：参数自助（残差噪声 + 基线窗口平均区间对应的共同平移），或雅可比近似；
     时序量区间宽度超过 w_max（默认 Δ）标为“该分辨率下不可识别”，不输出点值；
  7. 派生：η（模型辅助积分，缺测与跨边界区间用模型补足）、η_model（由 θ̂ 直接计算）、
     E_reb、A、S、删失 c。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize

from . import _ride_template as tpl

TIMING_KEYS = ("t_start", "t90", "t90_own", "t_rec")


@dataclass
class EventInput:
    s: np.ndarray            # 拟合区间起点（相对 τ_s，分钟）
    e: np.ndarray            # 拟合区间终点
    r: np.ndarray            # 残差 B̂ − P（kW），可含 nan
    q: float
    W: float
    obs_end: float
    a_max: float
    b_max: float
    sigma: float             # 计量与基线局部噪声（kW）
    sB: float                # 基线窗口平均误差的标准差（kW）
    delta: float
    is_ev: int = 1
    event_id: int = -1


# -----------------------------------------------------------------------------
# 初值：线性代价动态规划
# -----------------------------------------------------------------------------
def _seg_cost_matrix(x, y):
    """所有 [i, j) 段的分段线性最小二乘残差平方和，返回 (n+1, n+1) 矩阵（上三角有效）。"""
    n = len(x)
    c = lambda v: np.concatenate([[0.0], np.cumsum(v)])  # noqa: E731
    S1, Sx, Sy, Sxx, Sxy, Syy = c(np.ones(n)), c(x), c(y), c(x * x), c(x * y), c(y * y)
    i = np.arange(n + 1)[:, None]
    j = np.arange(n + 1)[None, :]
    N = S1[j] - S1[i]
    with np.errstate(all="ignore"):
        mx = (Sx[j] - Sx[i]) / N
        my = (Sy[j] - Sy[i]) / N
        vxx = (Sxx[j] - Sxx[i]) - N * mx * mx
        vxy = (Sxy[j] - Sxy[i]) - N * mx * my
        vyy = (Syy[j] - Syy[i]) - N * my * my
        cost = np.where(vxx > 1e-12, vyy - vxy * vxy / vxx, vyy)
    cost = np.where(N >= 1, np.maximum(cost, 0.0), np.inf)
    return cost


def dp_segments(x, y, n_seg=6, max_points=150):
    """线性代价 DP，返回分段边界时刻（长度 n_seg-1）与各段均值。"""
    n = len(x)
    if n > max_points:                                      # 块平均降采样
        f = int(np.ceil(n / max_points))
        m = (n // f) * f
        x = x[:m].reshape(-1, f).mean(1)
        y = y[:m].reshape(-1, f).mean(1)
        n = len(x)
    if n < n_seg + 1:
        return None
    C = _seg_cost_matrix(x, y)
    INF = np.inf
    F = np.full((n_seg + 1, n + 1), INF)
    arg = np.zeros((n_seg + 1, n + 1), int)
    F[0, 0] = 0.0
    for s_ in range(1, n_seg + 1):
        tot = F[s_ - 1][:, None] + C                       # (i, j)
        arg[s_] = np.argmin(tot, axis=0)
        F[s_] = tot[arg[s_], np.arange(n + 1)]
    bps = []
    j = n
    for s_ in range(n_seg, 0, -1):
        i = arg[s_, j]
        bps.append(i)
        j = i
    bps = sorted(bps)[1:]                                   # 去掉起点 0
    edges = [0] + bps + [n]
    means = [y[a:b].mean() if b > a else 0.0 for a, b in zip(edges[:-1], edges[1:])]
    times = [x[b] if b < n else x[-1] for b in bps]
    return np.array(times), np.array(means)


# -----------------------------------------------------------------------------
# 单事件拟合
# -----------------------------------------------------------------------------
def _bounds(ev: EventInput, struct):
    W = ev.W
    lb = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    ub = [W, min(30.0, max(W, 1.0)), max(ev.a_max, 0.05), W, 30.0, max(ev.b_max, 0.02), 180.0]
    if struct == 2:
        lb += [0.0, 0.0]
        ub += [W, W]
    return np.array(lb), np.array(ub)


class _Grid:
    """预先合并区间端点，使每次模型评估只在唯一端点上算一次 F(t)。"""

    def __init__(self, s, e):
        self.s, self.e = s, e
        bnd, inv = np.unique(np.concatenate([s, e]), return_inverse=True)
        self.bnd = bnd
        self.i_s, self.i_e = inv[: len(s)], inv[len(s):]
        self.width = np.maximum(e - s, 1e-12)
        self.mid = 0.5 * (s + e)

    def average(self, theta, W):
        F = tpl.cum_integral(theta, W, self.bnd)
        return (F[self.i_e] - F[self.i_s]) / self.width

    def average_batch(self, TH, W):
        """TH (B, P)：一次算出 B 组参数的区间平均，用于批量差分雅可比。"""
        F = tpl.cum_integral(TH[:, None, :], W, self.bnd[None, :])
        return (F[:, self.i_e] - F[:, self.i_s]) / self.width[None, :]


def _predict(theta, ev: EventInput, s, e, averaging=True, grid=None):
    if averaging:
        if grid is not None:
            return ev.q * grid.average(theta, ev.W)
        return ev.q * tpl.interval_average(theta, ev.W, s, e)
    return ev.q * tpl.point_sample(theta, ev.W, s, e)


def _crossing_init(ev: EventInput, s, e, r):
    """由平滑残差的穿越时刻估计各阶段初值（细分辨率下比 DP 更稳）。"""
    mid = 0.5 * (s + e)
    m = max(1, int(round(1.0 / max(ev.delta, 1e-9))))
    rs = pd.Series(r).rolling(m, center=True, min_periods=1).mean().to_numpy()
    inwin = (mid >= 0) & (mid <= ev.W)
    if inwin.sum() < 1:
        return None
    rw = rs[inwin]
    mx = np.nanmax(rw)
    if not np.isfinite(mx) or mx <= 0:
        return None
    top = rw[rw >= 0.5 * mx]
    L = float(np.nanmedian(top)) if len(top) else mx
    tw = mid[inwin]
    above = np.where(rw >= 0.5 * L)[0]
    if len(above) == 0:
        return None
    t_half_up = tw[above[0]]
    t_last = tw[above[-1]]
    a10 = np.where(rw >= 0.1 * L)[0]
    a90 = np.where(rw >= 0.9 * L)[0]
    t10 = tw[a10[0]] if len(a10) else t_half_up
    t90 = tw[a90[0]] if len(a90) else t_half_up
    T_ru = max((t90 - t10) * 1.25, 0.0)
    delta = max(t_half_up - 0.5 * T_ru, 0.0)
    T_dn = T_ru if ev.is_ev else max(T_ru * 0.5, 1.0)
    T_h = max(t_last - delta - T_ru - 0.5 * T_dn + 0.5 * ev.delta, 0.0)
    after = mid > t_last
    b, T_rb = 0.0, 0.0
    if after.any():
        ra = rs[after]
        mn = np.nanmin(ra)
        if np.isfinite(mn) and mn < 0:
            low = ra[ra <= 0.5 * mn]
            bq = -float(np.nanmedian(low))
            below = np.where(ra <= -0.5 * bq)[0]
            if len(below):
                ta = mid[after]
                T_rb = max(ta[below[-1]] - ta[below[0]] + ev.delta, 0.0)
                b = bq / ev.q
    return np.array([delta, T_ru, np.clip(L / ev.q, 0.0, ev.a_max), T_h, T_dn, np.clip(b, 0, ev.b_max), T_rb])


def _jitter(th, ev, rng, k=3):
    out = []
    for _ in range(k):
        x = th.copy()
        x[0] = max(x[0] + rng.normal(0, max(ev.delta, 0.25)), 0)
        x[1] = x[1] * np.exp(rng.normal(0, 0.5))
        x[3] = max(x[3] + rng.normal(0, max(ev.delta, 0.5)), 0)
        x[6] = x[6] * np.exp(rng.normal(0, 0.3))
        out.append(x)
    return out


def _heuristic_init(ev: EventInput, s, e, r):
    mid = 0.5 * (s + e)
    inwin = (s >= -1e-9) & (e <= ev.W + 1e-9)
    a0 = np.clip(np.nanmedian(r[inwin]) / ev.q if inwin.any() else 0.5, 0.05, ev.a_max)
    post = (s >= ev.W - 1e-9) & (mid <= ev.W + 60)
    b0 = np.clip(-np.nanmean(r[post]) / ev.q if post.any() else 0.0, 0.0, ev.b_max)
    T_ru0 = 1.0 if ev.is_ev else 8.0
    area = a0 * (ev.W - 1.0)
    T_rb0 = min(area / b0, 150.0) if b0 > 0.05 else 0.0
    return np.array([1.0, min(T_ru0, ev.W / 2), a0, ev.W, 2.0, b0, T_rb0])


def _dp_init(ev: EventInput, s, e, r):
    mid = 0.5 * (s + e)
    ok = ~np.isnan(r)
    out = dp_segments(mid[ok], r[ok], n_seg=6)
    if out is None:
        return None
    t, mu = out
    d0 = max(t[0], 0.0)
    th = np.array([d0, max(t[1] - t[0], 0.0), np.clip(mu[2] / ev.q, 0.0, ev.a_max), max(t[2] - t[1], 0.0),
                   max(t[3] - t[2], 0.0), np.clip(-mu[4] / ev.q, 0.0, ev.b_max), max(t[4] - t[3], 0.0)])
    return th


def _random_init(ev, struct, rng):
    th = np.array([rng.uniform(0, ev.W / 3), rng.uniform(0, 15 if not ev.is_ev else 3),
                   rng.uniform(0.1, max(ev.a_max, 0.11)), rng.uniform(0, ev.W), rng.uniform(0, 10 if not ev.is_ev else 3),
                   rng.uniform(0, max(ev.b_max, 0.01)), rng.uniform(0, 90)])
    if struct == 2:
        th = np.concatenate([th, [rng.uniform(0, ev.W / 2), rng.uniform(0, ev.W / 3)]])
    return th


def _fit_one(ev, s, e, r, struct, starts, averaging, optimizer, max_nfev=300, grid=None):
    lb, ub = _bounds(ev, struct)
    sig = max(ev.sigma, 1e-3)
    grid = grid if grid is not None else _Grid(s, e)

    def fun(th):
        return (_predict(th, ev, s, e, averaging, grid) - r) / sig

    def jac_fn(th):
        """批量前向差分：所有扰动参数一次向量化计算（比逐列差分快约 P 倍）。"""
        P = len(th)
        h = 1e-6 * np.maximum(1.0, np.abs(th))
        h = np.where(th + h > ub, -h, h)
        TH = np.vstack([th[None, :], th[None, :] + np.diag(h)])
        if averaging:
            A = ev.q * grid.average_batch(TH, ev.W)
        else:
            A = ev.q * tpl.u_instant(TH[:, None, :], ev.W, grid.mid[None, :])
        return ((A[1:] - A[0][None, :]) / h[:, None]).T / sig

    best = None
    for x0 in starts:
        x0 = np.clip(x0[: len(lb)] if len(x0) >= len(lb) else np.concatenate([x0, np.zeros(len(lb) - len(x0))]),
                     lb, ub)
        if optimizer == "lbfgsb":
            res = minimize(lambda th: 0.5 * np.sum(fun(th) ** 2), x0, method="L-BFGS-B",
                           bounds=list(zip(lb, ub)), options=dict(maxiter=300))
            cost, x = res.fun, res.x
            jac = None
        else:
            res = least_squares(fun, x0, jac=jac_fn, bounds=(lb, ub), method="trf", max_nfev=max_nfev,
                                x_scale=np.maximum(ub - lb, 1e-3) / 10, ftol=1e-6, xtol=1e-6, gtol=1e-6)
            cost, x, jac = res.cost, res.x, res.jac
        if best is None or cost < best[0]:
            best = (cost, x, jac)
    rss = 2 * best[0] * sig ** 2
    return best[1], rss, best[2]


def _derived(theta, ev: EventInput, s, e, r, averaging=True):
    """派生量。η_hat：模型辅助积分（观测区间用残差，缺测区间用模型），窗口边界按重叠比例分摊。"""
    W = ev.W
    th = theta
    model = _predict(th, ev, s, e, averaging) if th is not None else np.zeros_like(r)
    r_fill = np.where(np.isnan(r), model, r)
    ov = np.clip(np.minimum(e, W) - np.maximum(s, 0.0), 0.0, None)          # 与窗口重叠长度
    full = ov >= (e - s) - 1e-9
    # 完全落在窗内的区间直接用残差；部分重叠的区间按模型在重叠段的积分分摊残差偏移
    part_model = np.zeros_like(r)
    if th is not None and (~full & (ov > 0)).any():
        lo = np.maximum(s, 0.0)
        hi = np.minimum(e, W)
        idx = (~full) & (ov > 0)
        part_model[idx] = ev.q * (tpl.cum_integral(th, W, hi[idx]) - tpl.cum_integral(th, W, lo[idx]))
        offset = (r_fill[idx] - model[idx]) * ov[idx]       # 残差相对模型的偏移按重叠长度分摊
        part_model[idx] += offset
    area = np.sum(np.where(full, r_fill * (e - s), 0.0)) + np.sum(part_model)
    covered = np.sum(ov)
    eta_hat = area / (ev.q * W) if covered >= W - 1e-6 else np.nan
    eta_model = float(tpl.eta(th, W)) if th is not None else 0.0
    with np.errstate(all="ignore"):
        eta_direct = np.nanmean(np.where(full & (ov > 0), r, np.nan)) / ev.q if covered >= W - 1e-6 else np.nan
    out = dict(eta_hat=eta_hat, eta_model=eta_model, eta_direct=eta_direct)
    if th is not None:
        tm = tpl.timing(th, W)
        for k in TIMING_KEYS:
            out[k] = float(tm[k])
        out["level"] = float(tm["level"])
        out["Ereb_model"] = float(tpl.rebound_energy_rel(th, W, ev.obs_end)) * ev.q / 60.0
        out["cens_hat"] = int(bool(tpl.censored(th, W, ev.obs_end)) or ev.obs_end < W + 5)
    else:
        for k in TIMING_KEYS:
            out[k] = np.nan
        out["level"], out["Ereb_model"], out["cens_hat"] = 0.0, 0.0, int(ev.obs_end < W + 5)
    post = s >= W - 1e-9
    reb = np.clip(-r_fill[post], 0, None) * (e[post] - s[post])
    out["Ereb_hat"] = np.nansum(reb) / 60.0 if not out["cens_hat"] else np.nan
    return out


def identify_event(ev: EventInput, structures=(0, 1, 2), n_starts=8, optimizer="trf", averaging=True,
                   ci_method="bootstrap", n_boot=30, ci_level=0.90, w_max=None, lr_crit=None, a_min=0.1,
                   seed=0, return_theta_boot=False):
    rng = np.random.default_rng(seed + max(ev.event_id, 0) * 7)
    ok = ~np.isnan(ev.r)
    s, e, r = ev.s[ok], ev.e[ok], ev.r[ok]
    n = len(r)
    out = dict(event_id=ev.event_id, n_obs=n, sigma_hat=ev.sigma)
    if n < 2:
        out.update(struct=0, A_hat=0, LR=0.0, eta_hat=np.nan, eta_model=np.nan, eta_direct=np.nan)
        return out
    rss0 = float(np.sum(r ** 2))
    sig2 = max(ev.sigma, 1e-3) ** 2
    fits = {0: (None, rss0, None)}
    grid = _Grid(s, e)
    init_list = [_heuristic_init(ev, s, e, r)]
    ci = _crossing_init(ev, s, e, r)
    if ci is not None:
        init_list.append(ci)
        init_list += _jitter(ci, ev, rng, k=2)
    dpi = _dp_init(ev, s, e, r)
    if dpi is not None:
        init_list.append(dpi)
    for st in structures:
        if st == 0:
            continue
        p = tpl.N_PARAMS[st]
        if n <= p and st == 2:
            continue
        starts = [x if len(x) == p else np.concatenate([x, [0.3 * ev.W, 0.15 * ev.W]]) for x in init_list]
        while len(starts) < max(n_starts, len(init_list)):
            starts.append(_random_init(ev, st, rng))
        fits[st] = _fit_one(ev, s, e, r, st, starts, averaging, optimizer, grid=grid)
    bic = {st: fits[st][1] / sig2 + tpl.N_PARAMS[st] * np.log(max(n, 2)) for st in fits}
    nonnull = [st for st in fits if st != 0]
    best_nn = min(nonnull, key=lambda st: bic[st]) if nonnull else 0
    th_nn = fits[best_nn][0] if best_nn else None
    # 似然比统计量（广义最小二乘形式）：残差协方差 σ²I + s_B²·11ᵀ，
    # 其中 s_B² 是基线窗口平均误差的方差——共同平移部分不再被当作响应证据
    if th_nn is not None:
        c_ = ev.sB ** 2 / (sig2 + n * ev.sB ** 2)
        Q = lambda x: (np.sum(x ** 2) - c_ * np.sum(x) ** 2) / sig2  # noqa: E731
        LR = Q(r) - Q(r - _predict(th_nn, ev, s, e, averaging, grid))
    else:
        LR = 0.0
    a_hat = float(tpl.timing(th_nn, ev.W)["level"]) if th_nn is not None else 0.0
    if lr_crit is None:      # 未标定时退化为 BIC 判别
        detected = bool(best_nn) and (bic[best_nn] < bic[0]) and (a_hat >= a_min)
    else:
        detected = (LR > lr_crit) and (a_hat >= a_min)
    out.update(struct=best_nn if detected else 0, struct_nonnull=best_nn, A_hat=int(detected), LR=LR,
               bic0=bic[0], bic1=bic.get(1, np.nan), bic2=bic.get(2, np.nan), a_hat=a_hat)
    theta = tpl.pad_m1_to_m2(th_nn) if th_nn is not None else np.zeros(9)
    for k, name in enumerate(tpl.PARAM_NAMES_M2):
        out[f"th_{name}"] = theta[k]
    der = _derived(th_nn, ev, ev.s, ev.e, ev.r, averaging)
    out.update(der)

    # ---------------- 不确定性 ----------------
    if th_nn is not None and ci_method != "none":
        lo_q, hi_q = (1 - ci_level) / 2, 1 - (1 - ci_level) / 2
        keys = ["eta_hat", "eta_model", "Ereb_model"] + list(TIMING_KEYS)
        draws = {k: [] for k in keys}
        thetas = []
        if ci_method == "bootstrap":
            base = _predict(th_nn, ev, s, e, averaging, grid)
            full_mask = ~np.isnan(ev.r)
            for b in range(n_boot):
                shift = rng.normal(0, ev.sB)
                rb = base + shift + rng.normal(0, ev.sigma, n)
                thb, _, _ = _fit_one(ev, s, e, rb, best_nn, [th_nn], averaging, optimizer, max_nfev=200, grid=grid)
                rfull = np.full_like(ev.r, np.nan)
                rfull[full_mask] = rb
                d_b = _derived(thb, ev, ev.s, ev.e, rfull, averaging)
                for k in keys:
                    draws[k].append(d_b.get(k, np.nan))
                thetas.append(tpl.pad_m1_to_m2(thb))
            # 基本（反射）自助区间：自助世界的“真值”是无噪模型给出的派生量 c_k，
            # 区间 = [估计 − (q_hi − c_k), 估计 − (q_lo − c_k)]。直接取分位数会把区间中心放在模型值上，
            # 而 η̂ 是残差积分，二者相差一个窗内噪声均值，会造成覆盖不足。
            rmod = np.full_like(ev.r, np.nan)
            rmod[full_mask] = base
            center = _derived(th_nn, ev, ev.s, ev.e, rmod, averaging)
            for k in keys:
                arr = np.array(draws[k], float)
                est_k, c_k = out.get(k, np.nan), center.get(k, np.nan)
                if np.isfinite(arr).sum() >= max(5, n_boot // 3) and np.isfinite(est_k) and np.isfinite(c_k):
                    q_lo, q_hi = np.nanquantile(arr, lo_q), np.nanquantile(arr, hi_q)
                    out[f"{k}_lo"], out[f"{k}_hi"] = est_k - (q_hi - c_k), est_k - (q_lo - c_k)
                else:
                    out[f"{k}_lo"], out[f"{k}_hi"] = -np.inf, np.inf
            thetas = np.array(thetas)
            for k, name in enumerate(tpl.PARAM_NAMES_M2):
                out[f"th_{name}_lo"] = np.quantile(thetas[:, k], lo_q)
                out[f"th_{name}_hi"] = np.quantile(thetas[:, k], hi_q)
        else:  # 雅可比近似（大规模运行用）
            J = fits[best_nn][2]
            z = 1.6448536 if abs(ci_level - 0.9) < 1e-6 else 1.959964
            if J is None:
                cov = np.full((len(th_nn), len(th_nn)), np.inf)
            else:
                JtJ = J.T @ J
                cov = np.linalg.pinv(JtJ)
                g = cov @ J.T @ (np.ones(n) / max(ev.sigma, 1e-3))
                cov = cov + ev.sB ** 2 * np.outer(g, g)
                lam = np.linalg.eigvalsh(JtJ)
                if lam.min() < 1e-8 * max(lam.max(), 1e-12):
                    # 奇异方向：方差视为无穷，对应分量会被标为不可识别
                    null = np.abs(np.linalg.svd(J, full_matrices=False)[2][-1]) > 0.3
                    cov[np.ix_(null, null)] = np.inf
            for k in keys:
                eps = 1e-4
                f0 = _derived(th_nn, ev, ev.s, ev.e, ev.r, averaging).get(k, np.nan)
                grad = np.zeros(len(th_nn))
                for p_ in range(len(th_nn)):
                    tp = th_nn.copy()
                    tp[p_] += eps
                    grad[p_] = (_derived(tp, ev, ev.s, ev.e, ev.r, averaging).get(k, np.nan) - f0) / eps
                with np.errstate(invalid="ignore"):
                    var = grad @ np.where(np.isfinite(cov), cov, 1e12) @ grad
                sd = np.sqrt(max(var, 0)) if np.isfinite(f0) else np.nan
                out[f"{k}_lo"], out[f"{k}_hi"] = f0 - z * sd, f0 + z * sd
        # 可识别性标记
        wm = ev.delta if w_max is None else w_max
        for k in TIMING_KEYS:
            width = out.get(f"{k}_hi", np.inf) - out.get(f"{k}_lo", -np.inf)
            out[f"{k}_ident"] = int(np.isfinite(width) and width <= wm)
        if return_theta_boot:
            out["_theta_boot"] = thetas
    # 未检测到响应的事件不输出时序点值；不可识别的分量也不输出点值
    for k in TIMING_KEYS:
        out[f"{k}_raw"] = out.get(k, np.nan)
        if not out["A_hat"] or not out.get(f"{k}_ident", 1):
            out[k] = np.nan
    if out.get("cens_hat", 0):
        out["Ereb_model_raw"] = out.get("Ereb_model", np.nan)
        out["Ereb_model"] = np.nan
    out["S_hat"] = int(out.get("eta_hat", 0) >= 0.9) if np.isfinite(out.get("eta_hat", np.nan)) else 0
    return out


# -----------------------------------------------------------------------------
# 批量接口
# -----------------------------------------------------------------------------