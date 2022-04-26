from pydantic import BaseModel
import six


class _BaseModelMeta(type(BaseModel)):
    _ATTRS = (
        '_abstract',
        '_tokenized',
        '_nft',
        '_upgrade_material',
        '_upgrade_target',
        '_is_ladder',
        '_struct'
    )

    def __new__(mcs, cls_name, bases, namespace):
        new_cls = super().__new__(mcs, cls_name, bases, namespace)
        for key in mcs._ATTRS:
            if key.startswith('_'):
                setattr(new_cls, key, namespace.get(key, False))
        return new_cls


class _BaseModel(six.with_metaclass(_BaseModelMeta, BaseModel)):
    _abstract = True

    @classmethod
    def is_nft(cls):
        return cls._nft

    @classmethod
    def is_erc1155(cls):
        return cls._tokenized or\
               cls._upgrade_material

    @classmethod
    def is_erc721(cls):
        return cls._nft
