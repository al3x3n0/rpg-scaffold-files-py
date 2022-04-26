from collections import defaultdict
import inflection
from pydantic import Field, validator, ValidationError
from pydantic.fields import ModelField
import typing

from acrpg.model.base import _BaseModel


class BaseData(_BaseModel):
    _abstract = True

    _registry = {}
    _instances = defaultdict(list)
    _ids = defaultdict(dict)
    _erc1155_instances = []
    _erc721_instances = []

    id: str = Field(...)

    def __init__(self, **data):
        super().__init__(**data)
        ref_str = self.ref_str()
        BaseData._registry[ref_str] = self
        #
        cls = type(self)
        #
        _ids = BaseData._ids[cls]
        _instances = BaseData._instances[cls]
        _ids[self.id] = len(_instances)
        _instances.append(self)
        #
        if cls.is_erc721():
            BaseData._erc721_instances.append(self)
        #
        if cls.is_erc1155():
            BaseData._erc1155_instances.append(self)

    def ref_str(self):
        klass_name = inflection.underscore(type(self).__name__)
        return f"{klass_name}/{self.id}"

    def get_id(self):
        return BaseData._ids[type(self)][self.id]

    @validator('id')
    def process_id(cls, value: str, field: ModelField):
        #assert value.isalnum(), 'must be alphanumeric'
        return value

    @staticmethod
    def data_classes():
        return BaseData._instances.keys()

    @staticmethod
    def instances(cls):
        return BaseData._instances[cls]

    @staticmethod
    def get(klass_name, id):
        print(klass_name, id)
        return BaseData._registry.get(f"{klass_name}/{id}").get_id()


ReferencedType = typing.TypeVar('ReferencedType')


class DataRef(typing.Generic[ReferencedType]):

    def __init__(self, data_type: ReferencedType, id_: str):
        self.data_type = data_type
        self.id = id_

    def get_id(self):
        return BaseData.get(self.data_type, self.id)

    def ref_str(self):
        return f"{self.data_type}/{self.id}"

    @classmethod
    def __get_validators__(cls):
        yield cls.validate_ref

    @classmethod
    def validate_ref(cls, v):
        if not isinstance(v, str):
            raise ValidationError("Data reference should be string")
        try:
            kls, id_ = v.split('/')
        except:
            raise ValidationError(f"Invalid data reference: {v}")
        return DataRef(kls, id_)

    def __repr__(self):
        return f"'{self.data_type}/{self.id}'"


class CurrencyData(BaseData):
    _tokenized = True

    name: str
    ticker: str


class AchievementData(BaseData):
    name: str = Field(...)
    description: str


class AffinityData(BaseData):
    name: str = Field(...)
    description: str


class QualityData(BaseData):
    name: str = Field(...)


class FactionData(BaseData):
    name: str = Field(...)
    description: str


class BuildingData(BaseData):
    name: str
    description: str


class HeroSkinData(BaseData):
    name: str = Field(...)
    description: str


class HeroClassData(BaseData):
    name: str
    description: str


class HeroLevelLadderData(_BaseModel):
    experience: int


class HeroLadderData(BaseData):
    _is_ladder = True

    levels: typing.List[HeroLevelLadderData]


class HeroWeaponSlotData(BaseData):
    name: str


class SkillData(BaseData):
    name: str


class HeroData(BaseData):
    name: str
    description: str
    ladder: DataRef[HeroLadderData]
    affinity: DataRef[AffinityData]
    klass: DataRef[HeroClassData]
    slots: typing.List[DataRef[HeroWeaponSlotData]]
    skills: typing.List[DataRef[SkillData]]
    quality: DataRef[QualityData]


class WeaponLevelLadderData(_BaseModel):
    experience: int


class WeaponLadderData(BaseData):
    _is_ladder = True

    levels: typing.List[WeaponLevelLadderData]


class WeaponData(BaseData):
    name: str
    description: str
    ladder: DataRef[WeaponLadderData]


class ArtifactLevelLadderData(_BaseModel):
    experience: int


class ArtifactLadderData(BaseData):
    _is_ladder = True

    levels: typing.List[ArtifactLevelLadderData]


class ArtifactData(BaseData):
    name: str = Field(...)
    description: str
    ladder: DataRef[ArtifactLadderData]


class ExpeditionData(BaseData):
    name: str = Field(...)
    description: str


class HeroUpgradeMaterialData(BaseData):
    _upgrade_material = True
    _upgrade_target = 'Hero'

    type: str = Field("hero_upgrade_material", const=True)
    name: str = Field(...)
    value: int
    description: str


class WeaponUpgradeMaterialData(BaseData):
    _upgrade_material = True
    _upgrade_target = 'Weapon'

    type: str = Field("weapon_upgrade_material", const=True)
    name: str = Field(...)
    value: int
    description: str


class ArtifactUpgradeMaterialData(BaseData):
    _upgrade_material = True
    _upgrade_target = 'Artifact'

    type: str = Field("artifact_upgrade_material", const=True)
    name: str = Field(...)
    value: int
    description: str


class GameData(_BaseModel):
    upgrade_materials: typing.Optional[typing.List[
        typing.Union[HeroUpgradeMaterialData,
                     WeaponUpgradeMaterialData,
                     ArtifactUpgradeMaterialData]
    ]] = []
    currencies: typing.Optional[typing.List[CurrencyData]] = []
    buldings: typing.Optional[typing.List[BuildingData]] = []
    quality: typing.Optional[typing.List[QualityData]] = []
    affinity: typing.Optional[typing.List[AffinityData]] = []
    factions: typing.Optional[typing.List[FactionData]] = []
    hero_class: typing.Optional[typing.List[HeroClassData]] = []
    hero_slots: typing.Optional[typing.List[HeroWeaponSlotData]] = []
    artifacts: typing.Optional[typing.List[ArtifactData]] = []
    artifact_ladder: typing.Optional[typing.List[ArtifactLadderData]] = []
    heroes: typing.Optional[typing.List[HeroData]] = []
    hero_ladder: typing.Optional[typing.List[HeroLadderData]] = []
    weapons: typing.Optional[typing.List[WeaponData]] = []
    weapon_ladder: typing.Optional[typing.List[WeaponLadderData]] = []
    achievements: typing.Optional[typing.List[AchievementData]] = []
    expeditions: typing.Optional[typing.List[ExpeditionData]] = []
    skills: typing.Optional[typing.List[SkillData]] = []

    def resolve_refs(self):
        pass

    def merge(self, other: 'GameData'):
        for key, value in self:
            if isinstance(value, typing.List):
                value.extend(getattr(other, key))
