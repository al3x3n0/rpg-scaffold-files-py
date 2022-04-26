import inflection
from pathlib import Path
from pydantic.fields import ModelField
import typing

from acrpg.codegen.base import CodeGenBase
from acrpg.model.data import DataRef


class CodeGenCSharp(CodeGenBase):

    def get_cs_type(self, fdef: type):
        #
        t_origin = typing.get_origin(fdef)
        #
        if fdef == int:
            return "int64_t"
        elif fdef == str:
            return "string"
        elif t_origin:
            t_args = typing.get_args(fdef)
            if t_origin is typing.Optional:
                return self.get_cs_type(t_args[0])
            elif t_origin is list:
                return f"List<{self.get_cs_type(t_args[0])}>"
            elif t_origin is dict:
                return f"Dict<{self.get_cs_type(t_args[0])}, {self.get_gotype(t_args[1])}>"
            elif t_origin == DataRef:
                return f"{self.get_cs_type(t_args[0])}"
            else:
                assert False, f"{t_origin} not supported"
        else:
            return fdef.__name__

    def emit_code(self, cls, mod):
        s = ""
        s += "[System.Serializable]\n"
        s += f"public class {cls.__name__}\n{{\n"
        for fname, fdef in cls.__fields__.items():
            s += f"    public {self.get_cs_type(fdef)} {inflection.camelize(fname)};\n"
        s += f"""
    public string ToJson() {{
        return JsonUtility.ToJson(this);
    }}

    public static {cls.__name__} FromJSON (string json) {{
        return JsonUtility.FromJson<{cls.__name__}>(json);
    }}
"""
        s += "}\n"
        #
        with open(Path(self._out_dir).joinpath(f"{cls.__name__}.cs"), 'w') as cs_f:
            cs_f.write(s)
