import abc
import inspect
import importlib
from collections import defaultdict
import inflection
import os
import pathlib
import typing

from acrpg.model.base import _BaseModel
from acrpg.model.data import DataRef, BaseData, GameData
from acrpg.model.models import DataModel


class Wrapped(object):
    def __init__(self, cls, cgen: 'CodeGenBase'):
        self._cls = cls
        self._entity_name = cgen.get_entity_name(cls)
        self._entity_name_plural = inflection.pluralize(self._entity_name)
        self._entity_name_us = inflection.underscore(self._entity_name)
        self._var_name = cgen.get_class_name_us(cls)
        self._var_name_camel = inflection.camelize(self._var_name)
        self._var_name_camel_plural = inflection.pluralize(self._var_name_camel)
        self._var_name_plural = inflection.pluralize(self._var_name)
        self._data = None
        if self._cls.is_erc721():
            self._data = Wrapped(cgen.get_data_type_for_model(cls), cgen)

    @property
    def data(self):
        return self._data

    @property
    def entity_name(self):
        return self._entity_name

    @property
    def entity_name_plural(self):
        return self._entity_name_plural

    @property
    def entity_name_us(self):
        return self._entity_name_us

    @property
    def var_name(self):
        return self._var_name

    @property
    def var_name_camel(self):
        return self._var_name_camel

    @property
    def var_name_camel_plural(self):
        return self._var_name_camel_plural

    @property
    def var_name_plural(self):
        return self._var_name_plural


class CodeGenBase(object):
    __metaclass__ = abc.ABCMeta
    _modules = [
        'acrpg.model.data',
        'acrpg.model.models',
        'acrpg.model.protocol',
        'acrpg.model.structs'
    ]

    def __init__(self, namespace, out_dir, game_data, **kwargs):
        self._namespace = namespace
        self._out_dir = out_dir
        self._game_data = game_data
        self._models = {}
        for _mod in self._modules:
            self._models[_mod] = [
                obj for (name, obj) in
                inspect.getmembers(importlib.import_module(_mod))
                if inspect.isclass(obj) and issubclass(obj, _BaseModel) and obj.__module__ == _mod and obj is not _BaseModel
            ]
            #print(self._models)
        #
        self._data_classes = []
        self._erc721_classes = []
        self._poly_structs = defaultdict(list)

    @property
    def namespace(self):
        return self._namespace

    def generate(self):
        for mod, objs in self._models.items():
            for obj in objs:
                if obj._abstract:
                    continue
                if issubclass(obj, GameData):
                    continue
                if obj._nft:
                    self._erc721_classes.append(Wrapped(obj, self))
                elif obj._is_ladder:
                    self._data_classes.append(Wrapped(obj, self))
                elif issubclass(obj, BaseData):
                    self._data_classes.append(Wrapped(obj, self))
                elif issubclass(obj, _BaseModel):
                    self.process_poly_cls(obj)
                #
                self.emit_code(obj, mod)

    @abc.abstractmethod
    def emit_code(self, cls, mod):
        return

    def get_entity_name(self, cls):
        cls_name_us = inflection.underscore(cls.__name__).split('_')
        #assert cls_name_us[-1] in ['data', 'model', 'base']
        entity_name = inflection.camelize('_'.join(cls_name_us[:-1]))
        return entity_name

    def get_class_name_us(self, cls):
        cls_name_us_ = inflection.underscore(cls.__name__).split('_')
        #assert cls_name_us_[-1] in ['data', 'model', 'base']
        return '_'.join(cls_name_us_)

    def get_model_data_deps(self, cls):
        deps = set()
        for fname, fdef in cls.__fields__.items():
            ftype = fdef.outer_type_
            t_origin = typing.get_origin(ftype)
            if t_origin == DataRef:
                deps.add(Wrapped(typing.get_args(ftype)[0], self))
        return deps

    def get_all_model_deps(self, cls):
        deps = set()
        t_origin = typing.get_origin(cls)
        if t_origin:
            if t_origin is list:
                inner_type = typing.get_args(cls)[0]
                inner_deps = self.get_all_model_deps(inner_type)
                deps = deps.union(inner_deps)
        elif issubclass(cls, DataModel):
            deps.add(Wrapped(cls, self))
            for fname, fdef in cls.__fields__.items():
                ftype = fdef.outer_type_
                deps = deps.union(self.get_all_model_deps(ftype))
        #
        return deps

    def get_all_deps(self, cls):
        deps = set()
        t_origin = typing.get_origin(cls)
        if t_origin:
            if t_origin == DataRef:
                pass
            elif t_origin is list:
                inner_type = typing.get_args(cls)[0]
                inner_deps = self.get_all_deps(inner_type)
                deps = deps.union(inner_deps)
        elif issubclass(cls, _BaseModel):
            deps.add(cls)
            for fname, fdef in cls.__fields__.items():
                ftype = fdef.outer_type_
                deps = deps.union(self.get_all_deps(ftype))
        #
        return deps

    def deref_data_ref(self, ftype):
        t_origin = typing.get_origin(ftype)
        assert (t_origin == DataRef)
        return typing.get_args(ftype)[0]

    def get_ladder_type_for_model(self, cls):
        if isinstance(cls, Wrapped):
            cls = cls._cls
        assert 'ladder' in cls.__fields__
        data_ftype = cls.__fields__['ladder'].outer_type_
        return self.deref_data_ref(data_ftype)

    def get_data_type_for_model(self, cls):
        if isinstance(cls, Wrapped):
            cls = cls._cls
        assert 'data' in cls.__fields__
        data_ftype = cls.__fields__['data'].outer_type_
        return self.deref_data_ref(data_ftype)

    def process_poly_cls(self, cls):
        for p_cls in cls.__mro__:
            if not issubclass(p_cls, _BaseModel):
                break
            if p_cls._struct and p_cls != cls:
                self._poly_structs[p_cls].append(cls)

    def write_file(self, p: pathlib.Path, s: str):
        os.makedirs(str(p.parents[0]), exist_ok=True)
        with open(str(p), 'w') as f:
            print(s, file=f)
