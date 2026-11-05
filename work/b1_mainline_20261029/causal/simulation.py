"""Purpose-built seven-dose benchmark with pre-treatment confounding only."""
import numpy as np
from scipy.special import softmax
from api import LEVELS


def generate(seed, scenario, n_users=600, events_per_user=6):
    rng = np.random.default_rng(seed)
    users = np.repeat(np.arange(n_users), events_per_user)
    n = len(users)
    user_x = rng.uniform(-1, 1, (n_users, 2))
    X = np.column_stack([np.clip(user_x[users, 0]+rng.normal(0,.2,n), -1.4,1.4),
                         np.clip(user_x[users, 1]+rng.normal(0,.2,n), -1.4,1.4),
                         rng.integers(0,2,n).astype(float)])
    user_effect = rng.normal(0, .08, n_users)[users]
    noise = rng.normal(0, .08, n)
    base = .3+.12*X[:,0]+.08*X[:,1]+.08*X[:,0]*X[:,1]+.05*X[:,0]**2+.04*X[:,2]+user_effect
    delta = np.array([0., .04, .08, .12, .16, .20, .24])
    if scenario == 'observational_zero': delta = np.zeros(7)
    if scenario == 'observational_nonmonotone': delta = np.array([0., .05, .12, .07, .18, .14, .22])
    factor = 1+.15*X[:,0]-.1*X[:,1]
    potential = base[:,None]+factor[:,None]*delta[None,:]
    z = (LEVELS-LEVELS.mean())/1.2
    logits = (.9*X[:,0]+.6*X[:,1]+.2*X[:,2])[:,None]*z
    pi = softmax(logits, axis=1)
    if scenario == 'rct_positive': pi = np.full((n,7), 1/7)
    uniforms = rng.random(n)
    idx = np.minimum((uniforms[:,None] > pi.cumsum(1)).sum(1), 6)
    if scenario == 'deterministic_no_overlap':
        idx = np.minimum(((X[:,0]+1.4)/2.8*7).astype(int), 6)
        pi = np.eye(7)[idx]
    y = potential[np.arange(n), idx]+noise
    tau = (potential-potential[:,[0]]).mean(0)
    return dict(X=X, d=LEVELS[idx], y=y, groups=users, truth_tau=tau, assignment_pi=pi,
                potential=potential, true_first=next((j for j in range(1,7) if tau[j]>=.1), -1))
