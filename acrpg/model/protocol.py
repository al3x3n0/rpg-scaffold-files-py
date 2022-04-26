import inflection
from pydantic import Field, validator, root_validator, ValidationError
from pydantic.fields import ModelField
import typing

from acrpg.model.base import _BaseModel


class Protocol(_BaseModel):
    _abstract = True

