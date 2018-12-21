
from rpython.rlib             import jit, unroll, rweakref
from rpython.rlib.objectmodel import specialize

def make_map_type(getter, keyclass):

    class Map(object):
        """ A basic implementation of a map which assigns Racket values to an index
        based on the identity of the Racket value. A Map consists of

        * indexes: a map from objects to indicies for object described by the current map
        * other_maps: sub maps which are extensions the current map
        """

        _attrs_ = _immutable_fields_ = ['indexes', 'other_maps', 'parent']

        def __init__(self, parent):
            self.indexes = {}
            self.other_maps = rweakref.RWeakValueDictionary(keyclass, Map)
            # NB: The parent pointer is needed to prevent the GC from collecting
            # the chain of parent maps which produced this one.
            self.parent = parent

        def __iter__(self):
            return self.indexes.iteritems()

        def iterkeys(self):
            return self.indexes.iterkeys()

        def itervalues(self):
            return self.indexes.itervalues()

        def iteritems(self):
            return self.indexes.iteritems()

        @jit.elidable_promote('all')
        def get_index(self, name):
            return self.indexes.get(name, -1)

        @specialize.argtype(2)
        def lookup(self, name, storage, default=None, offset=0):
            idx = self.get_index(name)
            if idx == -1:
                return default
            assert storage is not None
            return getattr(storage, getter)(idx+offset)

        @jit.elidable_promote('all')
        def add_attribute(self, name):
            newmap = self.other_maps.get(name)
            if newmap is None:
                newmap = Map(self)
                newmap.indexes.update(self.indexes)
                newmap.indexes[name] = len(self.indexes)
                newmap.parent = self
                self.other_maps.set(name, newmap)
            return newmap

        @jit.elidable
        def has_attribute(self, name):
            return name in self.indexes

        @jit.elidable
        def storage_size(self):
            return len(self.indexes)

    Map.EMPTY = Map(None)

    return Map

# TODO Find a beter name for this
def make_caching_map_type(getter, keyclass):

    class CachingMap(object):
        """ A map implementation which partitions its data into two groups, a collection
        of static data stored in the map itself, and a collection of indexes used to
        index into a corresponding data array.

        This partitioning allows structures such as impersonators to share not just
        their layout but common data as well.
        """
        _attrs_ = _immutable_fields_ = [
            'indexes', 'static_data', 'static_submaps',
            'dynamic_submaps', 'parent']

        def __init__(self, parent):
            self.indexes = {}
            self.static_data = {}
            self.dynamic_submaps = rweakref.RWeakValueDictionary(keyclass, CachingMap)
            self.static_submaps  = {}
            self.parent = parent

        def iterkeys(self):
            for key in self.indexes.iterkeys():
                yield key
            for key in self.static_data.iterkeys():
                yield key

        def iteritems(self):
            for item in self.indexes.iteritems():
                yield item
            for item in self.static_data.iteritems():
                yield item

        def itervalues(self):
            for val in self.indexes.itervalues():
                yield val
            for val in self.static_data.itervalues():
                yield val

        @jit.elidable
        def storage_size(self):
            return len(self.indexes)

        @jit.elidable_promote('all')
        def get_dynamic_index(self, name):
            return self.indexes.get(name, -1)

        @jit.elidable_promote('all')
        def get_static_data(self, name, default):
            if name not in self.static_data:
                return default
            return self.static_data[name]

        @specialize.argtype(2)
        def lookup(self, name, storage, default=None, offset=0):
            idx = self.get_dynamic_index(name)
            if idx == -1:
                return self.get_static_data(name, default)
            assert storage is not None
            return getattr(storage, getter)(idx+offset)

        @jit.elidable_promote('all')
        def add_static_attribute(self, name, value):
            assert name not in self.indexes and name not in self.static_data
            key = (name, value)
            newmap = self.static_submaps.get(key, None)
            if newmap is None:
                newmap = CachingMap(self)
                newmap.indexes.update(self.indexes)
                newmap.static_data.update(self.static_data)
                newmap.static_data[name] = value
                self.static_submaps[key] = newmap
            return newmap

        @jit.elidable_promote('all')
        def add_dynamic_attribute(self, name):
            assert name not in self.indexes and name not in self.static_data
            newmap = self.dynamic_submaps.get(name)
            if newmap is None:
                newmap = CachingMap(self)
                newmap.indexes.update(self.indexes)
                newmap.static_data.update(self.static_data)
                newmap.indexes[name] = len(self.indexes)
                self.dynamic_submaps.set(name, newmap)
            return newmap

        @jit.elidable
        def is_dynamic_attribute(self, name):
            return name in seld.indexes

        @jit.elidable
        def is_static_attribute(self, name):
            return name in self.static_data

    CachingMap.EMPTY = CachingMap(None)
    return CachingMap

# These maps are simply unique products of various other map types.
# They are unique based on their component maps.
def make_composite_map_type():

    class CompositeMap(object):
        _attrs_ = _immutable_fields_ = ['handlers', 'properties']

        @staticmethod
        @jit.elidable
        def instantiate(handlers, properties):
            key = (handlers, properties)
            result = CompositeMap.CACHE.get(key, None)
            if result is None:
                result = CompositeMap(handlers, properties)
                CompositeMap.CACHE[key] = result
            return result

        def __init__(self, handlers, properties):
            self.handlers = handlers
            self.properties = properties

        @specialize.argtype(2)
        def lookup_handler(self, key, storage, default=None):
            jit.promote(self)
            return self.handlers.lookup(key, storage, default=default)

        @specialize.argtype(2)
        def lookup_property(self, key, storage, default=None):
            """ We make the assumption that data for the handlers are laid out
            in the form [handler_0, handler_1, ..., property_0, property_1, ...]"""
            jit.promote(self)
            return self.properties.lookup(key, storage, default=default, offset=0)

    # We would really like to use an RWeakValueDictionary here, but tuple keys are
    # not supported, as far as I can tell, and neither are custom hash/equality
    # functions, so we are stuck using a regular dictionary for now.
    #
    # A dictionary of (key1, key2) -> weakref<CompositeMap> may avoid holding onto
    # some bits of memory for too long.
    # Another option is to use two layers of dictionaries
    # key1 -> (key2 -> CompositeMap)
    CompositeMap.CACHE = {} # rweakref.RWeakValueDictionary(tuple, CompositeMap)
    return CompositeMap

