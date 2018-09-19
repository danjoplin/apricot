# facilityLocation.py
# Author: Jacob Schreiber <jmschreiber91@gmail.com>

"""
This code implements facility location functions.
"""

import numpy

from .base import SubmodularSelection

from tqdm import tqdm

from numba import njit
from numba import prange

dtypes = 'int64(float64[:,:], float64[:], float64[:], int8[:])'

@njit(dtypes, nogil=True, parallel=True)
def select_next(X, gains, current_values, mask):
	for idx in prange(X.shape[0]):
		if mask[idx] == 1:
			continue

		a = numpy.maximum(X[:,idx], current_values)
		gains[idx] = (a - current_values).sum()

	return numpy.argmax(gains)

class FacilityLocationSelection(SubmodularSelection):
	"""A facility location submodular selection algorithm.

	NOTE: All ~pairwise~ values in your data must be positive for this 
	selection to work.

	This function uses a facility location based submodular selection algorithm
	to identify a representative subset of the data. This feature based function
	works on pairwise relationships between each of the samples. This can be
	the correlation, a dot product, or any other such function where a higher
	value corresponds to a higher similarity and a lower value corresponds to
	a lower similarity.

	This implementation allows users to pass in either their own symmetric
	square matrix of similarity values, or a data matrix as normal and a function
	that calculates these pairwise values.

	Parameters
	----------
	n_samples : int
		The number of samples to return.

	pairwise_func : str or callable
		The method for converting a data matrix into a square symmetric matrix
		of pairwise similarities. If a string, can be any of the following:

			'corr' : The squared correlation matrix
			'cosine' : The normalized dot product of the matrix

	Attributes
	----------
	n_samples : int
		The number of samples to select.

	pairwise_func : callable
		A function that takes in a data matrix and converts it to a square
		symmetric matrix.

	ranking : numpy.array int
		The selected samples in the order of their gain.
	"""

	def __init__(self, n_samples=10, pairwise_func='corr', n_greedy_samples=250, verbose=False):
		self.n_greedy_samples = n_greedy_samples
		
		norm = lambda x: numpy.sum(x*x, axis=1).reshape(x.shape[0], 1)

		if pairwise_func == 'corr':
			self.pairwise_func = lambda X: numpy.corrcoef(X, rowvar=True)
		elif pairwise_func == 'cosine':
			self.pairwise_func = lambda X: numpy.dot(X, X.T) / (norm(X).dot(norm(X).T))
		elif pairwise_func == 'euclidean':
			self.pairwise_func = lambda X: -(-2 * numpy.dot(X, X.T) + norm(X)).T + norm(X)
		elif callable(pairwise_func):
			self.pairwise_func = pairwise_func
		else:
			raise KeyError("Must be one of 'corr' or 'cosine' or a custom function.")

		super(FacilityLocationSelection, self).__init__(n_samples, verbose)

	def fit(self, X, y=None):
		"""Perform selection and return the subset of the data set.

		This method will take in a full data set and return the selected subset
		according to the facility location function. The data will be returned in
		the order that it was selected, with the first row corresponding to
		the best first selection, the second row corresponding to the second
		best selection, etc.

		Parameters
		----------
		X : list or numpy.ndarray, shape=(n, d)
			The data set to transform. Must be numeric.

		y : list or numpy.ndarray, shape=(n,), optional
			The labels to transform. If passed in this function will return
			both the data and th corresponding labels for the rows that have
			been selected.

		Returns
		-------
		self : FacilityLocationSelection
			The fit step returns itself.
		"""

		if not isinstance(X, (list, numpy.ndarray)):
			raise ValueError("X must be either a list of lists or a 2D numpy array.")
		if isinstance(X, numpy.ndarray) and len(X.shape) != 2:
			raise ValueError("X must have exactly two dimensions.")

		if self.verbose == True:
			pbar = tqdm(total=self.n_samples)
			pbar.update(1)

		X = numpy.array(X, dtype='float64')
		X_pairwise = self.pairwise_func(X)
		numpy.fill_diagonal(X_pairwise, 0)

		n = X.shape[0]
		mask = numpy.zeros(n, dtype='int8')
		ranking = []
		
		best_score, best_idx = 0., None
		current_values = numpy.zeros(n, dtype='float64')
		
		for i in range(self.n_greedy_samples):
			gains = numpy.zeros(n, dtype='float64')

			best_idx = select_next(X_pairwise, gains, current_values, mask)			

			ranking.append(best_idx)
			mask[best_idx] = 1
			current_values = numpy.maximum(X_pairwise[:, best_idx], current_values)

			if self.verbose == True:
				pbar.update(1)

		for idx, gain in enumerate(gains):
			if mask[idx] != 1:
				self.pq.add(idx, -gain) 


		for i in range(self.n_greedy_samples, self.n_samples):
			best_gain = 0.
			best_idx = None
			
			while True:
				prev_gain, idx = self.pq.pop()
				prev_gain = -prev_gain
				
				if best_gain >= prev_gain:
					self.pq.add(idx, -prev_gain)
					self.pq.remove(best_idx)
					break
				
				a = numpy.maximum(X_pairwise[:, idx], current_values)
				gain = (a - current_values).sum()
				
				self.pq.add(idx, -gain)
				
				if gain > best_gain:
					best_gain = gain
					best_idx = idx

			ranking.append(best_idx)
			mask[best_idx] = True
			current_values = numpy.maximum(X_pairwise[:, best_idx], current_values)

			if self.verbose == True:
				pbar.update(1)

		if self.verbose == True:
			pbar.close()
		
		self.ranking = numpy.array(ranking)
		return self
