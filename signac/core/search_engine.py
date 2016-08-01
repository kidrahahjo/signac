from collections import defaultdict
import logging

from ..common import six
if six.PY2:
    from collections import Mapping
else:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


def _flatten(container):
    for i in container:
        if isinstance(i, (list, tuple)):
            for j in _flatten(i):
                yield j
        else:
            yield i


def _traverse_tree(t, include=None):
    if include is False:
        return
    if isinstance(t, list):
        for i in t:
            for b in _traverse_tree(i, include):
                yield b
    elif isinstance(t, Mapping):
        for k in t:
            if include is None or include is True:
                for i in _traverse_tree(t[k]):
                    yield k, i
            else:
                if not include.get(k, False):
                    continue
                for i in _traverse_tree(t[k], include.get(k)):
                    yield k, i
    else:
        yield t


def _valid_filter(f):
    if isinstance(f, Mapping):
        return all(_valid_filter(v) for v in f.values())
    else:
        return not isinstance(f, list)


class DocumentSearchEngine(object):
    """Search for documents as part of an index.

    Use the DocumentSearchEngine to search for specific
    key-value pairs within a list of documents.
    Each document must have a unique identifier.

    Use the include argument to control what keys
    are indexed and which are not. This may increase
    indexing speed and reduce memory usage. See
    :meth:`~.check_filter` for more information.

    :param docs: A set of documents to index.
    :type docs: list
    :param include: A mapping of keys that shall be
        included (True) or excluded (False).
    :type include: Mapping
    :param hash_: The hash function to use, defaults to :func:`hash`.
    :type hash_: callable
    """
    def __init__(self, docs=None, include=None, hash_=None):
        self._hash = hash if hash_ is None else hash_
        logger.debug("Building index...")
        self.ids, self.index, self.included = self._build_index(docs, include)
        logger.debug("Built index with {} entries.".format(len(self.index)))

    def _build_index(self, docs, include=None):
        index = defaultdict(set)
        ids = set()
        if include is None:
            included = None
        else:
            included = dict()
            for branch in _traverse_tree(include):
                f = tuple(_flatten(branch))
                included[self._hash(f[:-1])] = f[-1]
        if docs is not None:
            for doc in docs:
                ids.add(doc['_id'])
                for branch in _traverse_tree(doc, include=include):
                    f = tuple(_flatten(branch))
                    index[self._hash(f)].add(doc['_id'])
        return ids, index, included

    def _filter_supported(self, filter):
        if self.included is None:
            return True
        else:
            for branch in _traverse_tree(filter):
                f = tuple(_flatten(branch))
                for i in range(len(f)):
                    h = self._hash(f[:-i])
                    if self.included.get(h, False):
                        break
                else:
                    return False
            else:
                return True

    def check_filter(self, filter):
        """Check whether the filter is valid and supported.

        Not all filters are supported when the search engine
        is build with specific keys to be included or excluded.

        Example:

        .. code::
            incl = {'a': True, 'b': {'c': False, 'd': True}}
            engine = DocumentSearchEngine(docs, incl)
            # Examples for supported filters:
            engine.find({'a': x})
            engine.find({'a': x, 'b': y})
            engine.find({'b': {'d': z}})
            # Examples for filters that are not supported:
            engine.find({'b': {'c': x}})
            engine.find({'b': {'e': y}}) # *)
            engine.find({'c': z})        # *)

        *) Once one key within one hierarchy level is specified
        to be either included or excluded, all other keys within
        the same level are automatically excluded.

        :param filter: The filter to be checked.
        :type filter: Mapping
        :raises ValueError: If the filter is invalid.
        :raises RuntimeError: If the filter is not supported
            by the index.
        """
        if filter is None:
            return True
        if not _valid_filter(filter):
            raise ValueError(filter)
        elif not self._filter_supported(filter):
            msg = "{} not indexed for filter: '{}'."
            raise RuntimeError(msg.format(type(self).__name__, filter))

    def find(self, filter=None):
        """Find all documents matching filter.

        :param filter: A mapping of key-value pairs that
            all indexed documents are compared against.
        :type filter: Mapping
        :yields: The ids of all indexed documents matching the
            filter.
        :raises ValueError: If the filter is invalid.
        :raises RuntimeError: If the filter is not supported
            by the index.
        """
        self.check_filter(filter)
        if filter is None or not len(filter):
            for _id in self.ids:
                yield _id
        else:
            result = None
            for branch in _traverse_tree(filter):
                h = self._hash(tuple(_flatten(branch)))
                m = self.index.get(h, set())
                if result is None:
                    result = m
                    continue
                if m is None:
                    return
                else:
                    result = result.intersection(m)
            if result is None:
                return
            else:
                for _id in result:
                    yield _id

    def __len__(self):
        """Return the number of indexed documents."""
        return len(self.ids)