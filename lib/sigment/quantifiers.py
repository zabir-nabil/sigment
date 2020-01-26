# -*- coding: utf-8 -*-

from copy import copy
from random import sample
from .internals import _Validator, choice
from .base import _Base

__all__ = ['Pipeline', 'Sometimes', 'SomeOf', 'OneOf']

class Quantifier(_Base):
    """Specifies how to execute transformation or quantifier steps.

    .. note::
        As this is a base class, it should **not** be directly instantiated.

    Parameters
    ----------
    steps: List[Transform, Quantifier]
        A collection of transformation or quantifier steps to apply.

    random_order: bool
        Whether or not to randomize the order of execution of `steps`.

    random_state: numpy.RandomState, int, optional
        A random state object or seed for reproducible randomness.
    """

    def __init__(self, steps, random_order=False, random_state=None):
        if self.__class__ == Quantifier:
            raise NotImplementedError('Quantifier is a base class and cannot be instantiated')
        from .transforms import Transform

        if isinstance(steps, dict):
            steps = steps.values()
        else:
            try:
                (step for step in steps)
            except TypeError as e:
                raise TypeError('Expected steps to be an iterable') from e
        if not all(isinstance(step, (Quantifier, Transform)) for step in steps):
            raise TypeError('Expected each step to be a subclass of Quantifier (Sometimes, SomeOf or OneOf) or Transform')

        self.steps = steps
        self._val = _Validator()
        self.random_order = self._val.boolean(random_order, 'random_order')
        self.random_state = self._val.random_state(random_state)

    """Runs the transformations or quantifiers on a provided input signal.

    Parameters
    ----------
    X: numpy.ndarray [shape (T,) or (Tx1) for mono, (Tx2) for stereo]
        The input signal to transform.

    sr: int, optional
        The sample rate for the input signal.

        .. note::
            Not required if not using transformations that require a sample rate.

    Returns
    -------
    augmented: numpy.ndarray
        The augmented copy of the signal `X`.

        .. note::
            If a mono signal `X` of shape `(Tx1)` was used, the output is reshaped to `(T,)`.
    """
    def __call__(self, X, sr=None):
        X = self._val.signal(X)
        sr = sr if sr is None else self._val.restricted_integer(
            sr, 'sr (sample rate)',
            lambda x: x > 0, 'positive')

        steps = copy(self._generate_steps())

        if self.random_order:
            self.random_state.shuffle(steps)

        for step in steps:
            step.random_state = self.random_state
            X = step(X, sr)

        return X

    """Runs the transformations or quantifiers on a provided input signal,
    producing multiple augmented copies of the input signal.

    Parameters
    ----------
    X: numpy.ndarray [shape (T,) or (Tx1) for mono, (Tx2) for stereo]
        The input signal to transform.

    n: int [n > 0]
        Number of augmented copies of `X` to generate.

    sr: int, optional
        The sample rate for the input signal.

        .. note::
            Not required if not using transformations that require a sample rate.

    Returns
    -------
    augmented: List[numpy.ndarray] or numpy.ndarray
        The augmented copies (or copy if `n=1`) of the signal `X`.

        .. note::
            If a mono signal `X` of shape `(Tx1)` was used, the output is reshaped to `(T,)`.
    """
    def generate(self, X, n, sr=None):
        X = self._val.signal(X)
        n = self._val.restricted_integer(
            n, 'n (number of augmented copies)',
            lambda x: x > 0, 'positive')
        sr = sr if sr is None else self._val.restricted_integer(
            sr, 'sr (sample rate)',
            lambda x: x > 0, 'positive')
        X = [self.__call__(X, sr) for _ in range(n)]
        return X[0] if n == 1 else X

    def _generate_steps(self):
        raise NotImplementedError

    def __repr__(self, indent=4, level=0):
        attrs = [(k, v) for k, v in self.__dict__.items() if
            k not in ['steps', 'random_order', 'random_state'] and not k.startswith('_')]
        padding = ' ' * (indent * level)
        return padding + '{}.{}([\n'.format(
                self.__class__.__module__, self.__class__.__name__
            ) + '{}\n'.format(
                (', \n').join(step.__repr__(indent=indent, level=level+1) for step in self.steps)
            ) + padding + ('], {}, random_order={})'.format(
                ', '.join('{}={}'.format(k, v) for k, v in attrs),
                self.random_order
            ) if len(attrs) > 0 else '], random_order={})'.format(
                self.random_order)
        ) if len(self.steps) > 0 else '{}.{}([]{}, random_order={})'.format(
            self.__class__.__module__, self.__class__.__name__,
            (', ' if len(attrs) > 0 else '') +
            ', '.join('{}={}'.format(k, v) for k, v in attrs),
            self.random_order
        )

    def __str__(self):
        attrs = [(k, v) for k, v in self.__dict__.items() if
            k not in ['steps', 'random_order', 'random_state'] and not k.startswith('_')]
        return self.__repr__() if len(self.steps) == 0 else '{}.{}([...], {}random_order={})'.format(
            self.__class__.__module__, self.__class__.__name__,
            (', ' if len(attrs) > 0 else '') +
            ', '.join('{}={}'.format(k, v) for k, v in attrs),
            self.random_order
        )

    def __len__(self):
        return len(self.steps)

    def __getitem__(self, idx):
        return self.steps.__getitem__(idx)

class Pipeline(Quantifier):
    """TODO"""

    def _generate_steps(self):
        return self.steps

class Sometimes(Quantifier):
    """Probabilistically applies the provided transformation or quantifier steps.

    Parameters
    ----------
    steps: List[Transform, Quantifier]
        A collection of transformation or quantifier steps to apply.

    p: float [0 <= p <= 1]
        The probability of executing the transformations or quantifiers.

    random_order: bool
        Whether or not to randomize the order of execution of `steps`.

    random_state: numpy.RandomState, int, optional
        A random state object or seed for reproducible randomness.
    """

    def __init__(self, steps, p=0.5, random_order=False, random_state=None):
        super().__init__(steps, random_order, random_state)
        self.p = self._val.restricted_float(
            p, 'p (probability)',
            lambda x: 0. <= x <= 1., 'between zero and one')

    def _generate_steps(self):
        return self.steps if choice(self.random_state, self.p) else []

class SomeOf(Quantifier):
    """TODO"""

    def __init__(self, steps, n, random_order=False, random_state=None):
        super().__init__(steps, random_order, random_state)
        self._val.integer_value(
            n, 'n (number of steps to run)',
            lambda x1, x2: x2 >= x1 > 0, 'positive')
        if n[1] > len(steps):
            raise ValueError('Quantifier upper limit for n (number of steps) cannot exceed the number of available augmentations')
        self.n = n

    def _generate_steps(self):
        n = self.random_state.choice(range(self.n[0], self.n[1] + 1))
        idxs = range(len(self.steps))
        return [self.steps[idx] for idx in sorted(sample(idxs, k=n))]

class OneOf(SomeOf):
    """TODO"""

    def __init__(self, steps, random_order=False, random_state=None):
        super().__init__(steps, (1, 1), random_order, random_state)