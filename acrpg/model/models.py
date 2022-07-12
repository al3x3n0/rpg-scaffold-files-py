from collections import defaultdict
import inflection
import typing

from acrpg.model.base import _BaseModel
from acrpg.model.data import *


class DataModel(_BaseModel):
    _abstract = True


class Upgradeable(DataModel):
    _abstract = True
    level: int


class UpgradeableWithExp(DataModel):
    _abstract = True
    exp: cs_ulong = 0
    level: cs_int = 0


class SkillModel(Upgradeable):
    data: DataRef[SkillData]


class HeroModel(UpgradeableWithExp):
    _nft = True

    data: DataRef[HeroData]
    #skills: typing.List[SkillModel]


class WeaponModel(UpgradeableWithExp):
    _nft = True

    data: DataRef[WeaponData]


class ArtifactModel(UpgradeableWithExp):
    _nft = True

    data: DataRef[ArtifactData]


class BuildingModel(Upgradeable):
    _nft = True

    data: DataRef[BuildingData]


class UserModel(_BaseModel):
    _dto = True

    exp: int
    level: int
    buildings: typing.List[BuildingModel]
    heroes: typing.List[HeroModel]
    weapons: typing.List[WeaponModel]
    artifacts: typing.List[ArtifactModel]
