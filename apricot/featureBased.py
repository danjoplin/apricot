# featureBased.py
# Author: Jacob Schreiber <jmschreiber91@gmail.com> 

"""
This file contains code that implements feature based submodular selection
algorithms.
"""

import numpy

from .base import SubmodularSelection

from tqdm import tqdm

from numba import njit
from numba import prange

dtypes = 'int64(float64[:,:], float64[:], float64[:], float64[:], int8[:])'

@njit(dtypes, nogil=True, parallel=True)
def select_sqrt_next(X, gains, current_values, current_concave_values, mask):
	for idx in prange(X.shape[0]):
		if mask[idx] == 1:
			continue

		a = numpy.sqrt(current_values + X[idx])
		gains[idx] = (a - current_concave_values).sum()

	return numpy.argmax(gains)

@njit(dtypes, nogil=True, parallel=True)
def select_log_next(X, gains, current_values, current_concave_values, mask):
	for idx in prange(X.shape[0]):
		if mask[idx] == 1:
			continue

		a = numpy.log(current_values + X[idx] + 1)
		gains[idx] = (a - current_concave_values).sum()

	return numpy.argmax(gains)

@njit(dtypes, nogil=True, parallel=True)
def select_inv_next(X, gains, current_values, current_concave_values, mask):
	for idx in prange(X.shape[0]):
		if mask[idx] == 1:
			continue

		a = 1. / (1. + current_values + X[idx])
		gains[idx] = (a - current_concave_values).sum()

	return numpy.argmax(gains)

@njit(dtypes, nogil=True, parallel=True)
def select_min_next(X, gains, current_values, current_concave_values, mask):
	for idx in prange(X.shape[0]):
		if mask[idx] == 1:
			continue

		a = numpy.fmin(current_values, X[idx])
		gains[idx] = (a - current_concave_values).sum()

	return numpy.argmax(gains)

def select_custom_next(X, gains, current_values, current_concave_values, mask, 
	concave_func):
	best_gain = 0.
	best_idx = -1

	for idx in range(X.shape[0]):
		if mask[idx] == 1:
			continue

		a = concave_func(current_values + X[idx])
		gains[idx] = (a - current_concave_values).sum()

		if gains[idx] > best_gain:
			best_gain = gain
			best_idx = idx

	return best_idx

class FeatureBasedSelection(SubmodularSelection):
	"""A feature based submodular selection algorithm.

	NOTE: All values in your data must be positive for this selection to work.

	This function will use a feature based submodular selection algorithm to
	identify a representative subset of the data. The feature based functions
	use the values of the features themselves, rather than a transformation of
	the values, in order to select a diverse subset. The goal of this approach
	is to find a representative subset that sees each ~feature~ at a certain
	saturation across the selected points, rather than trying to uniformly
	sample the space.

	This implementation uses the lazy greedy algorithm so that multiple passes
	over the whole data set are not required each time a sample is selected. The
	benefit of this effect is not typically seen until many (over 100) passes are
	seen of the data set.

	Parameters
	----------
	n_samples : int
		The number of samples to return.

	concave_func : str or callable
		The type of concave function to apply to the feature values. You can
		pass in your own function to apply. Otherwise must be one of the
		following:

			'log' : log(1 + X)
			'sqrt' : sqrt(X)
			'min' : min(X, 1)
			'inverse' : 1 / (1 + X)

	verbose : bool
		Whether to print output during the selection process.

	Attributes
	----------
	pq : PriorityQueue
		The priority queue used to implement the lazy greedy algorithm.

	n_samples : int
		The number of samples to select.

	concave_func : callable
		A concave function for transforming feature values, often referred to as
		phi in the literature.

	ranking : numpy.array int
		The selected samples in the order of their gain with the first number in
		the ranking corresponding to the index of the first sample that was
		selected by the greedy procedure.
	"""

	def __init__(self, n_samples, concave_func='sqrt', n_greedy_samples=3, 
		verbose=False):
		self.concave_func_name = concave_func
		self.n_greedy_samples = n_greedy_samples

		if concave_func == 'log':
			self.concave_func = lambda X: numpy.log(X + 1)
		elif concave_func == 'sqrt':
			self.concave_func = lambda X: numpy.sqrt(X)
		elif concave_func == 'min':
			self.concave_func = lambda X: numpy.fmin(X, numpy.ones_like(X))
		elif concave_func == 'inverse':
			self.concave_func = lambda X: 1. / (1. + X)
		elif callable(concave_func):
			self.concave_func = concave_func
		else:
			raise KeyError("Must be one of 'log', 'sqrt', 'min', 'inverse', or a custom function.")

		super(FeatureBasedSelection, self).__init__(n_samples, verbose)

	def fit(self, X, y=None):
		"""Perform selection and return the subset of the data set.

		This method will take in a full data set and return the selected subset
		according to the feature based function. The data will be returned in
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
		self : FeatureBasedSelection
			The fit step returns itself.
		"""

		if not isinstance(X, (list, numpy.ndarray)):
			raise ValueError("X must be either a list of lists or a 2D numpy array.")
		if isinstance(X, numpy.ndarray) and len(X.shape) != 2:
			raise ValueError("X must have exactly two dimensions.")
 		if numpy.min(X) < 0.0:
			raise ValueError("X cannot contain negative values.")

		if self.verbose == True:
			pbar = tqdm(total=self.n_samples)

		X = numpy.array(X, dtype='float64')
		n, d = X.shape

		mask = numpy.zeros(X.shape[0], dtype='int8')
		ranking = []

		current_values = numpy.zeros(d, dtype='float64')
		current_concave_values = numpy.zeros(d, dtype='float64')
		
		for i in range(self.n_greedy_samples):
			gains = numpy.zeros(n, dtype='float64')

			if self.concave_func_name == 'sqrt':
				best_idx = select_sqrt_next(X, gains, current_values, 
					current_concave_values, mask)
			elif self.concave_func_name == 'log':
				best_idx = select_log_next(X, gains, current_values, 
					current_concave_values, mask)
			elif self.concave_func_name == 'inverse':
				best_idx = select_inv_next(X, gains, current_values, 
					current_concave_values, mask)
			elif self.concave_func_name == 'min':
				best_idx = select_min_next(X, gains, current_values, 
					current_concave_values, mask)
			else:
				best_idx = select_custom_next(X, gains, current_values, 
					current_concave_values, mask, self.concave_func)			

			ranking.append(best_idx)
			mask[best_idx] = True
			current_values += X[best_idx]
			current_concave_values = self.concave_func(current_values)

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
				
				a = self.concave_func(current_values + X[idx])
				gain = (a - current_concave_values).sum()
				
				self.pq.add(idx, -gain)
				
				if gain > best_gain:
					best_gain = gain
					best_idx = idx

			ranking.append(best_idx)
			mask[best_idx] = True
			current_values += X[best_idx]
			current_concave_values = self.concave_func(current_values)

			if self.verbose == True:
				pbar.update(1)

		if self.verbose == True:
			pbar.close()

		self.ranking = numpy.array(ranking, dtype='int32')
		return self
