import abc
import inspect
import importlib
from pathlib import Path
from pydantic import BaseModel
from pydantic.fields import ModelField
import sys


from acrpg.model.base import _BaseModel


class CodeGenBase(object):
    __metaclass__ = abc.ABCMeta
    _modules = [
        'acrpg.model.data',
        'acrpg.model.models',
        'acrpg.model.protocol',
        'acrpg.model.structs'
    ]

    def __init__(self, out_dir, game_data):
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

    def generate(self):
        for mod, objs in self._models.items():
            for obj in objs:
                if not obj._abstract:
                    self.emit_code(obj, mod)

    @abc.abstractmethod
    def emit_code(self, cls, mod):
        return
