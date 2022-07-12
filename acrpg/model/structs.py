from acrpg.model.base import _BaseModel
from acrpg.model.data import *


class RewardBase(_BaseModel):
    _struct = True


class RewardHero(RewardBase):
    hero: DataRef[HeroData]
    amount: int


class RewardWeapon(RewardBase):
    weapon: DataRef[WeaponData]
    amount: int


class RewardArtifact(RewardBase):
    artifact: DataRef[ArtifactData]
    amount: int
