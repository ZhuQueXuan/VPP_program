# -*- coding: utf-8 -*-

# Author: Yikun Zhang
# Last Editing: January 15, 2025

# Description: This script contains the utility functions for the main functions 
# in our package.

import numpy as np
from .rbf import KernelRetrieval
import scipy.integrate as integrate
from sklearn.preprocessing import PolynomialFeatures

#=======================================================================================#


def RoTBWLocalPoly(Y, X, kernT="epanechnikov", kernS="epanechnikov", C_h=10, C_b=15):
    '''
    Compute the rule-of-thumb bandwidth selector in Eq.(A1) of 
    Yang and Tschernig (1999).
    
    Parameters
    ----------
        Y: (n,)-array
            The outcomes of n observations.
        
        X: (n,d+1)-array
            The first column of X is the treatment/exposure variable, while 
            the other d columns are confounding variables of n observations.
            
        kernT, kernS: str
            The names of kernel functions for the treatment/exposure variable 
            and confounding variables. (Default: "epanechnikov".)
            
        C_h,C_b: float
            The scaling factors for the rule-of-thumb bandwidth parameters. 
            (Default: C_h=7, C_b=3.)
    
    Return
    ----------
        h: float
            The rule-of-thumb bandwidth parameter for the treatment/exposure variable.
            
        b: (d,)-array
            The rule-of-thumb bandwidth vector for the confounding variables.
    '''
    n = X.shape[0]  ## Number of data points
    d = X.shape[1] - 1
    
    kernT, sigmaK_sq, K_sq = KernelRetrieval(kernT)
    # Apply the rule-of-thumb bandwidth selector in Eq.(A1) of Yang and Tschernig (1999)
    p_coeff = np.polyfit(X[:,0], Y, 4)
    sec_deriv = 12*p_coeff[0]*X[:,0] + 6*p_coeff[1]*X[:,0] + 2*X[:,0]
    C_fun = np.mean(sec_deriv**2)
    T = X[:,0].reshape(-1,1)
    lhs = np.concatenate([np.ones((n,1)), X, T**2, T**3, T**4], axis=1)
    rcond = np.finfo(lhs.dtype).eps * max(*lhs.shape)
    beta = np.linalg.lstsq(lhs, Y, rcond=rcond)[0]
    # Compute the residual sum of squares
    resid = np.sum((Y - np.dot(lhs, beta))**2) * (np.max(X[:,0]) - np.min(X[:,0]))/ (n-5)
    sigmaK_sq = sigmaK_sq**2
    # ROT
    # h = ((K_sq*resid)/(4*n*sigmaK_sq*C_fun))**(1/5) * (n**(d/(5*(d+5)))) * C_h
    h = ((K_sq*resid)/(4*n*sigmaK_sq*C_fun))**(1/5) * C_h
    
    kernS, sigmaK_sq, K_sq = KernelRetrieval(kernS)
    sec_deriv = np.zeros((n, d))
    for i in range(1, d+1):
        # Fit a fourth-order polynomial to each confounding variable
        p_coeff = np.polyfit(X[:,i], Y, 4)
        sec_deriv[:,i-1] = 12*p_coeff[0]*X[:,i] + 6*p_coeff[1]*X[:,i] + 2*X[:,i]
    C_fun = np.sum(np.diag(np.dot(sec_deriv.T, sec_deriv))/n)
    lhs = np.concatenate([np.ones((n,1)), X, T**2, T**3, T**4], axis=1)
    # lhs = np.concatenate([np.ones((n,1)), X[:,1:]], axis=1)
    rcond = np.finfo(lhs.dtype).eps * max(*lhs.shape)
    beta = np.linalg.lstsq(lhs, Y, rcond=rcond)[0]
    resid = np.sum((Y - np.dot(lhs, beta))**2) * (np.max(X[:,1:], axis=0) - np.min(X[:,1:], axis=0)) / (n-5)
    sigmaK_sq = sigmaK_sq**2
    K_sq = K_sq**d
    # b = ((K_sq*d*resid)/(4*n*sigmaK_sq*C_fun))**(1/(d+5)) * C_b
    b = ((K_sq*d*resid)/(4*sigmaK_sq*C_fun))**(1/(d+5)) * n**(-1/(d+1)) * C_b
    
    return h, b


def HatMatrix(X, degree=2, deriv_ord=1, h=None, b=None, print_bw=True, 
              kernT="epanechnikov", kernS="epanechnikov"):
    '''
    Compute the hat matrix of the local polynomial regression when it is viewed 
    as a linear smoother.
    
    Parameters
    ----------
        X: (n,d+1)-array
            The first column of X is the treatment/exposure variable, while 
            the other d columns are confounding variables of n observations.
            
        degree: int
            Degree of local polynomials. (Default: degree=2.)
            
        deriv_ord: int
            The order of the estimated derivative the conditional mean outcome function. 
            (Default: deriv_ord=1. Then, it estimates the partial derivative of the 
            conditional mean outcome function with respect to the treatment variable.)
            
        h,b: float
            The bandwidth parameters for the treatment/exposure variable and 
            confounding variables. 
            
        print_bw: boolean
            The indicator of whether the current bandwidth parameters should be
            printed to the console. (Default: print_bw=True.)
            
        kernT, kernS: str
            The names of kernel functions for the treatment/exposure variable 
            and confounding variables. (Default: "epanechnikov".)
            
    Return
    ----------
        hat_mat: (n,n)-array
            The hat matrix.
    '''
    n = X.shape[0]  ## Number of data points
    d = X.shape[1] - 1
    x_eval = X.copy()
    
    if print_bw:
        print("The current bandwidth for treament variable in the local polynomial regression is "+ str(h) + ".\n")
        print("The current bandwidth for confounding variables in the local polynomial regression is "+ str(b) + ".\n")
    
    kernT, sigmaK_sq, K_sq = KernelRetrieval(kernT)
    kernS, sigmaK_sq, K_sq = KernelRetrieval(kernS)
    hat_mat = np.zeros((n, n))
    for i in range(x_eval.shape[0]):
        weights = kernT((X[:,0] - x_eval[i,0])/h) * np.prod(kernS((X[:,1:] - x_eval[i,1:])/b), axis=1)
        # Filter out the data points with zero weights to speed up regressions with kernels of compact support
        inds = np.where(np.abs(weights) > 1e-26)[0]
        X_dat = np.zeros((n, degree+1+d))
        # X_dat[:,:(degree+1)] = (((X[:,0] - x_eval[i,0])/h).reshape(-1,1))**(np.arange(degree+1))
        for p in range(degree + 1):
            X_dat[:,p] = ((X[:,0] - x_eval[i,0])/h)**p
        X_dat[:,(degree+1):] = (X[:,1:] - x_eval[i,1:])/b
        X_dat = X_dat[inds,:]
        W = np.diag(weights[inds])
        design_mat = np.dot(np.dot(X_dat.T, W), X_dat)
        try:
            hat_mat_samp = np.dot(np.linalg.inv(design_mat), np.dot(X_dat.T, W))
        except:
            # Add some small quantities to the diagonal matrix to prevent the singularity of the matrix
            design_mat = design_mat + 1e-16*np.eye(design_mat.shape[0])
            hat_mat_samp = np.dot(np.linalg.inv(design_mat), np.dot(X_dat.T, W))
        hat_mat[i,inds] = hat_mat_samp[deriv_ord,:]
    return hat_mat
    
    
    

def BndKern(x_qry, kern, deriv_ord=0, alpha=1, bnd='left'):
    '''
    Generalized jackknife boundary kernel.
    
    Parameters
    ----------
        x_qry: (m,)-array
            The coordinates of m query points in the 1-dimensional Euclidean space.
       
        kern: python function
            The kernel function.
            
        deriv_ord: int
            The order of the derivative estimator. (Default: deriv_ord=0, which
            is for nonparametric density or curve estimation.)
        
        alpha: float
            The truncated proportion of the kernel support (0 <= alpha <= 1). 
            (Default: alpha=1, which recovers the original kernel function for 
             the interior points.)
        
        bnd: str
            Indicator of whether the input point is within the left or right 
            boundary of the support. (Default: bnd='left'.)
    
    Return
    ----------
        res: (m,)-array
            The boundary kernel function evaluated at m query points.
    '''
    kappa_lst = np.zeros((2*deriv_ord+3,))
    if bnd == 'left':
        sign = -1
    else:
        sign = 1
    for i in range(deriv_ord, 3*deriv_ord + 3):
        kappa_lst[i-deriv_ord] = integrate.quad(lambda x: ((sign*x)**i)*kern(x), 
                                                -np.inf, alpha)[0]
    mat = np.zeros((deriv_ord + 2, deriv_ord + 2))
    for i in range(deriv_ord + 2):
        mat[i,:] = kappa_lst[i:(i+deriv_ord+2)]
    B = np.zeros((deriv_ord + 2, ))
    B[deriv_ord] = 1
    coef = np.linalg.solve(mat, B)
    res = 0
    for j in range(deriv_ord+2):
        res += coef[j]*(x_qry**j)*kern(x_qry)
    return res


def KDE1D(x, data, kern='epanechnikov', h=None):
    '''
    One-dimensional kernel density estimation with generalized jackknife boundary
    corrections (Jones 1993).
    
    Parameters
    ----------
        x: (m,)-array
            The coordinates of m query points in the 1-dim Euclidean space.
    
        data: (n,)-array
            The coordinates of n random sample points in the d-dimensional 
            Euclidean space.
       
        kern: str
            The name of the kernel function. (Default: "epanechnikov".)
            
        h: float
            The bandwidth parameter. (Default: h=None. Then the Silverman's 
            rule of thumb is applied; see Chen et al.(2016) for details.)
    
    Return
    ----------
        f_hat: (m,)-array
            The corresponding kernel density estimates at m query points.
    '''
    n = data.shape[0]  ## Number of data points
    d = 1  ## Dimension of the data
    kern, sigmaK_sq, K_sq = KernelRetrieval(kern)
    
    if h is None:
        # Apply Silverman's rule of thumb to select the bandwidth parameter 
        h = (4/(d+2))**(1/(d+4))*(n**(-1/(d+4)))*np.std(data)
        print("The current bandwidth for KDE is "+ str(h) + ".\n")
    
    f_hat = np.zeros((x.shape[0], ))
    for i in range(x.shape[0]):
        if x[i] < np.min(data) or x[i] > np.max(data):
            f_hat[i] = 0
        elif x[i] < np.min(data) + h:
            alpha = (x[i] - np.min(data))/h
            f_hat[i] = np.mean(BndKern((data - x[i])/h, kern=kern, deriv_ord=0, 
                                       alpha=alpha, bnd='left') / h)
        elif x[i] > np.max(data) - h:
            alpha = (np.max(data) - x[i])/h
            f_hat[i] = np.mean(BndKern((data - x[i])/h, kern=kern, deriv_ord=0, 
                                       alpha=alpha, bnd='right') / h)
        else:
            f_hat[i] = np.mean(kern((data - x[i])/h) / h)
    return f_hat


def KDE(x, data, kern='gaussian', h=None):
    '''
    The d-dimensional Euclidean kernel density estimator.
    
    Parameters
    ----------
        x: (m,d)-array
            The coordinates of m query points in the d-dim Euclidean space.
    
        data: (n,d)-array
            The coordinates of n random sample points in the d-dimensional 
            Euclidean space.
            
        kern: str
            The name of the kernel function. (Default: "gaussian".)
       
        h: float
            The bandwidth parameter. (Default: h=None. Then the Silverman's 
            rule of thumb is applied. See Chen et al.(2016) for details.)
    
    Return
    ----------
        f_hat: (m,)-array
            The corresponding kernel density estimates at m query points.
    '''
    n = data.shape[0]  ## Number of data points
    if len(data.shape) == 1:
        d = 1
        data = data.reshape(-1,1)
        x = x.reshape(-1,1)
    else:
        d = data.shape[1]  ## Dimension of the data
    kern, sigmaK_sq, K_sq = KernelRetrieval(kern)
    
    if h is None:
        # Apply Silverman's rule of thumb to select the bandwidth parameter 
        h = (4/(d+2))**(1/(d+4))*(n**(-1/(d+4)))*np.std(data, axis=0)
        print("The current bandwidth is "+ str(h) + ".\n")
    
    f_hat = np.zeros((x.shape[0], ))
    for i in range(x.shape[0]):
        f_hat[i] = np.mean(np.exp(np.sum(-((x[i,:] - data)/h)**2, axis=1)/2))/ ((2*np.pi)**(d/2)*np.prod(h))
    return f_hat


def CondDenEstKDE(Y, X, reg_mod, y_eval=None, x_eval=None, kern='epanechnikov', b=None):
    '''
    Conditional density estimation by applying the kernel density estimator (KDE) 
    on the regression residuals.
    
    Parameters
    ----------
        Y: (n,)-array
            The outcome variables of n observations.
            
        X: (n,d)-array
            The d-dimensional covariates of n observations.
            
        reg_mod: scikit-learn model or any python model that can use ".fit()" and ".predict()"
            The conditional mean outcome (or regression) model of Y given X.
            
        y_eval: (m,)-array
            The outcome variables at which we evaluate the estimated conditional
            densities.
            
        x_eval: (m,d)-array
            The covariates at which we evaluate the estimated conditional
            densities.
            
        kern: str
            The name of the kernel function. (Default: kern="epanechnikov".)
            
        b: float
            The bandwidth parameter for KDE. (Default: b=None.)
    
    Return
    ----------
        cond_est: (m,)-array
            The estimated conditional densities at the m query points.
    '''
    if y_eval is None:
        y_eval = Y
    if x_eval is None:
        x_eval = X
    
    reg_hat = reg_mod.fit(X, Y)
    y_pred = reg_hat.predict(x_eval)
    
    cond_est = KDE1D(x=y_eval-y_pred, data=y_eval-y_pred, kern=kern, h=b)
    return cond_est


def CondDenEst(Y, X, reg_mod, y_eval=None, x_eval=None, kern='gaussian', b=None, 
               poly_ext=False):
    '''
    Conditional density estimation via nonparametric regression on the kernel-smoothed 
    outcome variables.
    
    Parameters
    ----------
        Y: (n,)-array
            The outcome variables of n observations.
            
        X: (n,d)-array
            The d-dimensional covariates of n observations.
            
        reg_mod: scikit-learn model or any python model that can use ".fit()" and ".predict()"
            The conditional mean outcome (or regression) model of Y given X.
            
        y_eval: (m,)-array
            The outcome variables on which we evaluate the estimated conditional
            densities.
            
        x_eval: (m,d)-array
            The covariates on which we evaluate the estimated conditional
            densities.
            
        kern: str
            The name of the kernel function. (Default: kern="gaussian".)
            
        b: float
            The bandwidth parameter for KDE. (Default: b=None.)
        
        poly_ext: boolean
            The indicator of whether polynomial features are generated from the 
            current covariates. (Default: poly_ext=False.)
    
    Return
    ----------
        cond_est: (m,)-array
            The estimated conditional densities at the m query points.
    '''
    n = X.shape[0]
    
    if b is None:
        # Apply Silverman's rule of thumb to select the bandwidth parameter 
        b = (4/3)**(1/5)*(n**(-1/5))*np.std(Y)
        print("The current bandwidth for the conditional density estimator is "+ str(b) + ".\n")
    
    if y_eval is None:
        y_eval = Y
    if x_eval is None:
        x_eval = X
    
    kern, sigmaK_sq, K_sq = KernelRetrieval(kern)
    cond_est = np.zeros((y_eval.shape[0],))
    if poly_ext:
        X_inter = PolynomialFeatures(degree=3, interaction_only=False, 
                                     include_bias=True).fit_transform(X)
        x_eval_inter = PolynomialFeatures(degree=3, interaction_only=False, 
                                          include_bias=True).fit_transform(x_eval)
    else:
        X_inter = X
        x_eval_inter = x_eval
    
    # Estimate the conditional density by fitting the kernelized outcomes
    for i in range(y_eval.shape[0]):
        Y_kern = kern((Y - y_eval[i])/b)/b
        reg_hat = reg_mod.fit(X_inter, Y_kern)
        y_pred = reg_hat.predict(x_eval_inter[i,:].reshape(1,-1))
        cond_est[i] = y_pred[0]
    
    return cond_est

