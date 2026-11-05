"""四阶段分段线性响应模板及其精确区间平均算子 A_Δ。

时间单位一律为分钟，原点取请求开始时刻 τ_s（t' = t - τ_s）。
幅度以请求减载量 q 的倍数表示（相对单位），乘以 q 后为 kW。

参数 θ（M1，7 个）：
    delta  延迟 δ           T_ru 爬坡时长        a   相对幅度
    T_h    保持时长          T_dn 释放时长        b   反弹相对幅度
    T_rb   反弹时长
M2（中途掉落再响应）另加 2 个：
    g_s    掉落起点（相对爬坡结束的偏移） g_len 掉落时长

u(t) 连续部分为 (δ,0)→(t1c,L)→(t_x,L)→(t_x+T_dn,0) 的折线，
t_x = min(δ+T_ru+T_h, W)，若请求窗结束时爬坡尚未完成，则从已达水平 L 开始释放；
反弹为 [t_x+T_dn, t_x+T_dn+T_rb) 上高度为 -b 的矩形块；M2 在保持段内挖去一段矩形。

所有函数对参数做广播：theta 形状 (..., P)，t 可与 theta[..., 0] 广播。
"""
from __future__ import annotations

import numpy as np

PARAM_NAMES_M1 = ("delta", "T_ru", "a", "T_h", "T_dn", "b", "T_rb")
PARAM_NAMES_M2 = PARAM_NAMES_M1 + ("g_s", "g_len")
N_PARAMS = {0: 0, 1: 7, 2: 9}


def _unpack(theta, W):
    theta = np.asarray(theta, dtype=float)
    P = theta.shape[-1]
    d, Tru, a, Th, Tdn, b, Trb = (theta[..., i] for i in range(7))
    W = np.asarray(W, dtype=float)
    t0 = d
    tx = np.minimum(d + Tru + Th, W)
    tx = np.maximum(tx, t0)                       # 延迟超过请求窗时退化为无响应
    Tru_s = np.where(Tru > 1e-9, Tru, 1e-9)
    L = a * np.clip((tx - t0) / Tru_s, 0.0, 1.0)  # 释放开始时的实际水平
    t1c = np.minimum(t0 + Tru, tx)
    r0 = tx + Tdn
    out = dict(t0=t0, t1c=t1c, tx=tx, L=L, Tdn=Tdn, r0=r0, b=b, Trb=Trb, a=a, Tru=Tru)
    if P >= 9:
        g0 = t1c + theta[..., 7]
        g1 = np.minimum(g0 + theta[..., 8], tx)
        out["g0"] = np.minimum(g0, tx)
        out["g1"] = np.maximum(g1, out["g0"])
    return out


def _seg_int(t, xa, ya, xb, yb):
    """线段 (xa,ya)-(xb,yb) 从 xa 积分到 t 的值（t 超出右端时取全段面积）。"""
    Ls = xb - xa
    s = np.clip(t - xa, 0.0, None)
    s = np.minimum(s, Ls)
    good = Ls > 1e-12
    slope = np.where(good, (yb - ya) / np.where(good, Ls, 1.0), 0.0)
    return ya * s + 0.5 * slope * s * s


def cum_integral(theta, W, t):
    """F(t) = ∫_{-∞}^{t} u(s; θ) ds（相对单位 × 分钟）。"""
    k = _unpack(theta, W)
    z = np.zeros_like(k["L"])
    F = (_seg_int(t, k["t0"], z, k["t1c"], k["L"])
         + _seg_int(t, k["t1c"], k["L"], k["tx"], k["L"])
         + _seg_int(t, k["tx"], k["L"], k["tx"] + k["Tdn"], z))
    F = F - k["b"] * np.clip(t - k["r0"], 0.0, k["Trb"])
    if "g0" in k:
        F = F - k["L"] * np.clip(t - k["g0"], 0.0, k["g1"] - k["g0"])
    return F


def u_instant(theta, W, t):
    """瞬时调节功率 u(t)（相对单位）。"""
    k = _unpack(theta, W)
    t = np.asarray(t, dtype=float)
    ramp_len = np.maximum(k["t1c"] - k["t0"], 1e-12)
    rel_dn = np.where(k["Tdn"] > 1e-12, (t - k["tx"]) / np.where(k["Tdn"] > 1e-12, k["Tdn"], 1.0), 1.0)
    u = np.select(
        [t < k["t0"], t < k["t1c"], t < k["tx"], t < k["tx"] + k["Tdn"]],
        [0.0 * t, k["L"] * (t - k["t0"]) / ramp_len, k["L"] + 0.0 * t, k["L"] * (1.0 - rel_dn)],
        default=0.0 * t,
    )
    u = u - k["b"] * ((t >= k["r0"]) & (t < k["r0"] + k["Trb"]))
    if "g0" in k:
        u = u - k["L"] * ((t >= k["g0"]) & (t < k["g1"]))
    return u


def interval_average(theta, W, starts, ends):
    """精确区间平均算子 A_Δ：[(F(e)-F(s))/(e-s)]。starts/ends 可为 (K,) 或可广播数组。"""
    starts = np.asarray(starts, dtype=float)
    ends = np.asarray(ends, dtype=float)
    width = np.maximum(ends - starts, 1e-12)
    th = np.asarray(theta, dtype=float)
    if th.ndim == 1:
        return (cum_integral(th, W, ends) - cum_integral(th, W, starts)) / width
    thb = th[..., None, :]                       # (..., 1, P)
    Wb = np.asarray(W, dtype=float)[..., None] if np.ndim(W) else W
    return (cum_integral(thb, Wb, ends) - cum_integral(thb, Wb, starts)) / width


def point_sample(theta, W, starts, ends):
    """消融“去掉平均算子”：用区间中点的瞬时值代替区间平均。"""
    mid = 0.5 * (np.asarray(starts, float) + np.asarray(ends, float))
    th = np.asarray(theta, dtype=float)
    if th.ndim == 1:
        return u_instant(th, W, mid)
    return u_instant(th[..., None, :], np.asarray(W, float)[..., None] if np.ndim(W) else W, mid)


# --------------------------------------------------------------------------
# 派生量
# --------------------------------------------------------------------------
def eta(theta, W):
    """请求窗净交付比例 η = ∫_0^W u dt / W（u 为相对单位）。"""
    return (cum_integral(theta, W, W) - cum_integral(theta, W, 0.0)) / np.asarray(W, float)


def rebound_energy_rel(theta, W, t_end):
    """请求窗结束到 t_end 之间的反弹面积（相对单位 × 分钟）。乘 q/60 得 kWh。"""
    k = _unpack(theta, W)
    lo = np.maximum(k["r0"], W)
    hi = np.minimum(k["r0"] + k["Trb"], t_end)
    return k["b"] * np.clip(hi - lo, 0.0, None)


def curtailed_area(theta, W):
    """连续部分（少充）面积，扣除 M2 掉落段。"""
    k = _unpack(theta, W)
    area = 0.5 * k["L"] * (k["t1c"] - k["t0"]) + k["L"] * (k["tx"] - k["t1c"]) + 0.5 * k["L"] * k["Tdn"]
    if "g0" in k:
        area = area - k["L"] * (k["g1"] - k["g0"])
    return area


def timing(theta, W, target_rel=0.9):
    """时点类派生量（分钟，相对 τ_s）。

    t_start  开始降功率时刻 δ（L=0 时为 nan）
    t90      达到请求目标 target_rel·q 的时刻；未达到时为 nan（原报告口径）
    t90_own  达到自身平台 90% 的时刻
    t_rec    功率恢复到基线的时刻 t_x + T_dn
    t_end    整个过程（含反弹）结束时刻
    """
    k = _unpack(theta, W)
    has = k["L"] > 1e-9
    nan = np.nan
    t_start = np.where(has, k["t0"], nan)
    ramp_len = k["t1c"] - k["t0"]
    frac = np.where(k["L"] > 1e-9, target_rel / np.where(k["L"] > 1e-9, k["L"], 1.0), np.inf)
    t90 = np.where(has & (frac <= 1.0), k["t0"] + np.minimum(frac, 1.0) * ramp_len, nan)
    t90_own = np.where(has, k["t0"] + 0.9 * ramp_len, nan)
    t_rec = np.where(has, k["tx"] + k["Tdn"], nan)
    t_end = np.where(has | (k["b"] * k["Trb"] > 0), k["r0"] + k["Trb"], nan)
    return dict(t_start=t_start, t90=t90, t90_own=t90_own, t_rec=t_rec, t_end=t_end,
                level=k["L"])


def duration_above(theta, W, q, thr_kw=0.15):
    """请求窗内 q·u ≥ thr 的累计时长（秒），对应原报告的累计减载时长 R 的真值。"""
    k = _unpack(theta, W)
    q = np.asarray(q, float)
    thr = thr_kw / q
    L = k["L"]
    ok = L >= thr
    Ls = np.where(L > 1e-12, L, 1.0)
    t_up = k["t0"] + np.clip(thr / Ls, 0, 1) * (k["t1c"] - k["t0"])
    t_dn = k["tx"] + (1.0 - np.clip(thr / Ls, 0, 1)) * k["Tdn"]
    lo = np.clip(t_up, 0.0, W)
    hi = np.clip(t_dn, 0.0, W)
    dur = np.clip(hi - lo, 0.0, None)
    if "g0" in k:
        g_lo = np.clip(k["g0"], lo, hi)
        g_hi = np.clip(k["g1"], lo, hi)
        dur = dur - np.clip(g_hi - g_lo, 0.0, None)
    return np.where(ok, dur * 60.0, 0.0)


def censored(theta, W, obs_end):
    """回补在观测结束前未完成则删失（c=1）。"""
    k = _unpack(theta, W)
    active = (k["L"] > 1e-9) | (k["b"] * k["Trb"] > 0)
    return active & (k["r0"] + k["Trb"] > obs_end + 1e-9)


def pad_m1_to_m2(theta):
    """把 M1 参数补成 M2 形状（掉落段长度为 0）。"""
    theta = np.asarray(theta, float)
    if theta.shape[-1] == 9:
        return theta
    z = np.zeros(theta.shape[:-1] + (2,))
    return np.concatenate([theta, z], axis=-1)
