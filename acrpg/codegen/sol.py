import inflection
from pathlib import Path
from collections import defaultdict
import typing

from acrpg.codegen.base import CodeGenBase, _BaseModel
from acrpg.model.data import DataRef, BaseData
from acrpg.model.models import UpgradeableWithExp, DataModel
from acrpg.utils import *


class Wrapped(object):
    def __init__(self, cls, cgen: 'SolCodeGenGo'):
        self._cls = cls
        self._entity_name = cgen.get_entity_name(cls)
        self._var_name = cgen.get_class_name_us(cls)
        self._var_name_camel = inflection.camelize(self._var_name)
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
    def var_name(self):
        return self._var_name

    @property
    def var_name_camel(self):
        return self._var_name_camel

    @property
    def var_name_plural(self):
        return self._var_name_plural


class SolCodeGenGo(CodeGenBase):
    def __init__(self, *args, **kwargs):
        super(SolCodeGenGo, self).__init__(*args, **kwargs)
        self._contracts = []
        self._data_classes = []
        self._erc721_classes = []
        self._entity_names = {}
        #
        self._arr_id = 0
        self._arrs_to_init = []
        #
        self._erc1155_instances = BaseData._erc1155_instances
        self._erc1155_ids = {}
        for erc1155_id, erc1155_item in enumerate(self._erc1155_instances):
            self._erc1155_ids[erc1155_item.ref_str()] = erc1155_id
        self._upgrade_mats = {}
        #
        self._poly_structs = defaultdict(list)

    def get_upgrade_material(self, cls_):
        _data_cls = self._upgrade_mats.get(cls_.entity_name)
        if _data_cls:
            return _data_cls
        for data_cls in self._data_classes:
            _data_cls = data_cls._cls
            if _data_cls._upgrade_material and _data_cls._upgrade_target == cls_.entity_name:
                self._upgrade_mats[cls_.entity_name] = _data_cls
                return _data_cls
        #
        assert False

    def get_entity_name(self, cls):
        entity_name = self._entity_names.get(cls, None)
        if entity_name:
            return entity_name
        cls_name_us = inflection.underscore(cls.__name__).split('_')
        #assert cls_name_us[-1] in ['data', 'model', 'base']
        entity_name = inflection.camelize('_'.join(cls_name_us[:-1]))
        self._entity_names[cls] = entity_name
        return entity_name

    def get_class_name_us(self, cls):
        cls_name_us_ = inflection.underscore(cls.__name__).split('_')
        #assert cls_name_us_[-1] in ['data', 'model', 'base']
        return '_'.join(cls_name_us_)

    def get_struct_name(self, cls):
        return inflection.underscore(cls.__name__)

    def solize_name(self, name):
        if name in ['type']:
            return '_' + name
        return name

    def get_arr_id(self):
        self._arr_id += 1
        return self._arr_id

    def make_array_initializers(self):
        s = ""
        for arr_args in self._arrs_to_init:
            s += self.emit_make_array(*arr_args)
            s += "\n"
        self._arrs_to_init = []
        return s

    def emit_make_array(self, arr_id, ftype, arr):
        s = f"""
    function get_array_{arr_id}() internal pure returns ({self.get_soltype(ftype)}[] memory _arr) {{
        _arr = new {self.get_soltype(ftype)}[]({len(arr)});
"""
        for jj, arr_el in enumerate(arr):
            s += f"        _arr[{jj}] = {self.get_solval(ftype, arr_el)};\n"
        s += "    }"
        return s

    def get_soltype(self, fdef: type, is_param=False):
        #
        t_origin = typing.get_origin(fdef)
        #
        if fdef == int:
            return "uint"
        elif fdef == str:
            ts = "string"
            if is_param:
                ts += " memory"
            return ts
        elif t_origin:
            t_args = typing.get_args(fdef)
            if t_origin is typing.Optional:
                return self.get_soltype(t_args[0])
            elif t_origin is list:
                ts = f"{self.get_soltype(t_args[0])}[]"
                if is_param:
                    ts += " memory"
                return ts
            elif t_origin is dict:
                return f"mapping({self.get_soltype(t_args[0])} => {self.get_soltype(t_args[1])})"
            elif t_origin == DataRef:
                return "uint" #f"*{self.get_soltype(t_args[0])}"
            else:
                assert False, f"{t_origin} not supported"
        elif issubclass(fdef, DataModel):
            return "uint"
        else:
            ts = f"{self.get_struct_name(fdef)}_t"
            if is_param:
                ts += " memory"
            return ts

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

    def emit_copy_array_from_data(self, ptype, data_ptype, fname, mtype, dtype):
        dtype = self.deref_data_ref(dtype)
        mtype = Wrapped(mtype, self)
        _wrap = Wrapped(dtype, self)
        s = f"""
uint[] memory {fname} = {data_ptype.var_name}.get_{data_ptype.var_name}_{fname}_by_id({data_ptype.var_name}_id);
{ptype.var_name}.{fname} = new uint[]({fname}.length);
for (uint i = 0; i < {fname}.length; i++) {{
    {ptype.var_name}.{fname}[i] = create_{mtype.var_name}({fname}[i]);
}}
"""
        return s

    def emit_model_init(self, cls):
        if isinstance(cls, Wrapped):
            cls = cls._cls
        data_type_for_model = self.get_data_type_for_model(cls)
        _wrap_data_type_for_model = Wrapped(data_type_for_model, self)
        _wrap = Wrapped(cls, self)
        s = f"function create_{_wrap.var_name}(uint {_wrap_data_type_for_model.var_name}_id) internal returns (uint _id) {{\n"
        s += f"    _id = {_wrap.var_name_plural}.length;\n"
        s += f"    {_wrap.var_name}_t memory {_wrap.var_name};\n"
        for fname, fdef in cls.__fields__.items():
            if fdef.default is not None:
                s += f"    {_wrap.var_name}.{fname} = {self.get_solval(fdef.outer_type_, fdef.default)};\n"
            elif fname in data_type_for_model.__fields__:
                data_fdef = data_type_for_model.__fields__[fname]
                data_fdef_type = data_fdef.outer_type_
                inner_t_origin = typing.get_origin(data_fdef_type)
                if inner_t_origin is list:
                    tmp_s = self.emit_copy_array_from_data(_wrap, _wrap_data_type_for_model, fname,
                                                   typing.get_args(fdef.outer_type_)[0],
                                                   typing.get_args(data_fdef_type)[0])
                    s += apply_ident(tmp_s, 4)
            elif fname == 'data':
                s += f"    {_wrap.var_name}.{fname} = {_wrap_data_type_for_model.var_name}_id;\n"
        s += f"    {_wrap.var_name_plural}.push({_wrap.var_name});\n"
        s += "}\n"
        return s

    def get_solval(self, ftype, val, ident=0):
        t_origin = typing.get_origin(ftype)
        #
        if ftype == int:
            s = str(val)
        elif ftype == str:
            s = f"\"{val}\""
        elif t_origin:
            if t_origin == DataRef:
                s = f"uint({val.get_id()})"
            elif t_origin is list:
                inner_type = typing.get_args(ftype)[0]
                arr_id = self.get_arr_id()
                self._arrs_to_init.append((arr_id, inner_type, val))
                return f"get_array_{arr_id}()"
                #vals = [self.get_solval(inner_type, el) for el in val]
                #s = f"[{','.join(vals)}]"
            else:
                assert False
        elif issubclass(ftype, _BaseModel):
            s = f"{self.get_struct_name(ftype)}_t({{\n"
            next_ident = ident + 4
            for fidx, (fname, fval) in enumerate(val):
                el_type = ftype.__fields__[fname].outer_type_
                sep = ',' if fidx != len(ftype.__fields__) - 1 else ''
                s += ' ' * (
                            next_ident + 8) + f"{self.solize_name(fname)}:{self.get_solval(el_type, fval, ident=next_ident)}{sep}\n"
            s += ' ' * (next_ident + 4) + "})"
        else:
            s = str(val)
        return s

    def emit_struct_def(self, cls):
        if isinstance(cls, Wrapped):
            cls = cls._cls
        s = f"""
struct {self.get_struct_name(cls)}_t {{
"""
        for fname, fdef in cls.__fields__.items():
            s += f"    {self.get_soltype(fdef.outer_type_)} {self.solize_name(fname)};\n"
        if cls.is_erc1155():
            s += "    uint _token_id;\n"
        s += "}"
        return s

    def emit_code_nft(self, cls, mode):
        cls_name_us = self.get_class_name_us(cls)
        entity_name = self.get_entity_name(cls)
        plural_entity_name = inflection.pluralize(entity_name.lower())

        _wrap = Wrapped(cls, self)

        data_deps = self.get_model_data_deps(cls)
        model_deps = self.get_all_model_deps(cls)

        model_data_type = Wrapped(self.get_data_type_for_model(cls), self)
        if issubclass(cls, UpgradeableWithExp):
            ladder_type = Wrapped(self.get_ladder_type_for_model(model_data_type), self)
            data_deps.add(ladder_type)

        self.emit_model_init(cls)

        s = f"""// contracts/generated/model/{entity_name}.sol
// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

import "@openzeppelin/contracts/utils/math/SafeMath.sol";

import "../../XDimERC721.sol";
"""
        for dep_cls in data_deps:
            s += f"import \"../data/{dep_cls.entity_name}Data.sol\";\n"

        s += f"""
contract {entity_name} is XDimERC721 {{

    using SafeMath for uint;

"""
        for dep_cls in model_deps:
            s += apply_ident(self.emit_struct_def(dep_cls), 4)
            s += "\n\n"

        for dep_cls in data_deps:
            s += f"    {dep_cls.entity_name}Data public {dep_cls.var_name};\n"

        s += f"""
    event {entity_name}Added(address _receiver);

"""
        for dep_cls in model_deps:
            s += f"    {dep_cls.var_name}_t[] public {dep_cls.var_name_plural};\n"

        for dep_cls in model_deps:
            s += apply_ident(self.emit_model_init(dep_cls), 4) + '\n'

        s += f"\n    function initialize(\n"
        for jj, dep_cls in enumerate(data_deps):
            sep = '' if jj == len(data_deps) - 1 else ','
            s += f"        {dep_cls.entity_name}Data _{dep_cls.var_name}{sep}\n"

        s += f"""
    ) initializer public {{
        __ERC721_init("{entity_name}", "XXX");
"""
        for jj, dep_cls in enumerate(data_deps):
            s += f"        {dep_cls.var_name} = _{dep_cls.var_name};\n"
        s += f"""    }}

    function mint(address to, uint {cls_name_us}_id) public {{
        uint token_id = totalSupply();
        _mint(to, token_id);
        create_{cls_name_us}({cls_name_us}_id);
        //
        emit {entity_name}Added(to);
    }}

    function give(address to, uint {_wrap.data.var_name}_id, uint amount) public {{
        for (uint i = 0; i < amount; i++) {{
            mint(to, {_wrap.data.var_name}_id);
        }}
    }}
"""
        if issubclass(cls, UpgradeableWithExp):
            s += f"""
    function add_exp(uint {_wrap.var_name}_id, uint _exp) public {{
        {_wrap.var_name}_t storage {_wrap.var_name} = {_wrap.var_name_plural}[{_wrap.var_name}_id];
        {_wrap.var_name}.exp = {_wrap.var_name}.exp.add(_exp);
        uint _new_level;
        uint _exp_left;
        uint ladder_id = {model_data_type.var_name}.get_{model_data_type.var_name}_ladder_by_id({_wrap.var_name}.data);
        (_new_level, _exp_left) = {ladder_type.var_name}.get_level(ladder_id, {_wrap.var_name}.level, {_wrap.var_name}.exp);
        {_wrap.var_name}.level = _new_level;
    }}
"""
        s += "}"
        return s, entity_name

    def emit_code_ladder(self, cls, mod):
        cls_name_us = self.get_class_name_us(cls)
        entity_name = self.get_entity_name(cls)
        #
        assert 'levels' in cls.__fields__
        levels_type = cls.__fields__['levels'].outer_type_
        assert typing.get_origin(levels_type) is list
        level_t = typing.get_args(levels_type)[0]
        level_t_name = self.get_struct_name(level_t)
        #
        s = f"""// contracts/generated/data/{entity_name}.sol
// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

contract {entity_name}Data {{

    mapping (uint => mapping (uint => {level_t_name}_t)) _{cls_name_us}_levels;
    mapping (uint => uint) _{cls_name_us}_max_level;

    function get_{level_t_name}(uint _id, uint level) external view returns ({level_t_name}_t memory _{level_t_name}) {{
        _{level_t_name} = _{cls_name_us}_levels[_id][level];
    }}

    function get_level(uint _id, uint curr_level, uint exp) external view returns (uint _level, uint _exp_left) {{
        _level = curr_level;
        while (exp >= _{cls_name_us}_levels[_id][_level].experience) {{
            _level += 1;
        }}
        _exp_left = exp - _{cls_name_us}_levels[_id][_level].experience;
    }}
"""
        klasses = self.get_all_deps(level_t)
        for dep_kls in klasses:
            s += apply_ident(self.emit_struct_def(dep_kls), 4)
            s += "\n"

        for _id, data_inst in enumerate(BaseData.instances(cls)):
            s += f"""
    function initialize_{cls_name_us}_{data_inst.id}() public {{
"""
            for level_id, level_data in enumerate(data_inst.levels):
                s += f"        _{cls_name_us}_levels[{_id}][{level_id}] = {self.get_solval(level_t, level_data)};\n"
            s += f"\n        _{cls_name_us}_max_level[{_id}] = {len(data_inst.levels)};\n"
            s += "    }\n"
        s += "}"

        return s, f"{entity_name}Data"

    def emit_code_data(self, cls, mod):
        cls_name_us = self.get_class_name_us(cls)
        entity_name = self.get_entity_name(cls)
        plural_entity_name = inflection.pluralize(entity_name.lower())
        struct_name = self.get_struct_name(cls)
        s = f"""// contracts/generated/data/{entity_name}Data.sol
// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

contract {entity_name}Data {{

    mapping(uint => {struct_name}_t) _{plural_entity_name};

"""
        klasses = self.get_all_deps(cls)
        for dep_kls in klasses:
            s += apply_ident(self.emit_struct_def(dep_kls), 4)
            s += "\n"

        s += f"""
    function initialize_{entity_name}Data() public {{
"""
        for _id, data_inst in enumerate(BaseData.instances(cls)):
            s += f"        _{plural_entity_name}[{_id}] = {data_inst.id}();\n"

        s += f"""
    }}

    function get_{cls_name_us}_by_id(uint _id) external view returns ({struct_name}_t memory _{struct_name}) {{
        return _{plural_entity_name}[_id];
    }}
"""
        for fname, fdef in cls.__fields__.items():
            s += f"""
    function get_{cls_name_us}_{fname}_by_id(uint _id) external view returns ({self.get_soltype(fdef.outer_type_, is_param=True)}) {{
        return _{plural_entity_name}[_id].{self.solize_name(fname)};
    }}
"""
        if cls.is_erc1155():
            s += f"""
    function get_{cls_name_us}_token_id_by_id(uint _id) external view returns (uint) {{
        return _{plural_entity_name}[_id]._token_id;
    }}
"""

        for _id, data_inst in enumerate(BaseData.instances(cls)):
            s += f"""
    function {data_inst.id}() public pure returns ({struct_name}_t memory _{struct_name}) {{
            // _{struct_name} = new {struct_name}_t;
"""
            for fname, fvalue in data_inst:
                fdef = cls.__fields__[fname]
                s += f"        _{struct_name}.{self.solize_name(fname)} = {self.get_solval(fdef.outer_type_, fvalue)};\n"
            s += "    }\n"

            s += self.make_array_initializers()

        s += "}\n"

        return s, entity_name + 'Data'

    def process_poly_cls(self, cls):
        for p_cls in cls.__mro__:
            if not issubclass(p_cls, _BaseModel):
                break
            if p_cls._struct and p_cls != cls:
                self._poly_structs[p_cls].append(cls)

    def emit_code(self, cls, mod):
        s = ''
        entity_name = ''
        subpath = ''
        #
        if cls._nft:
            subpath = 'model/'
            self._erc721_classes.append(Wrapped(cls, self))
            s, entity_name = self.emit_code_nft(cls, mod)
        elif cls._is_ladder:
            subpath = 'data/'
            self._data_classes.append(Wrapped(cls, self))
            s, entity_name = self.emit_code_ladder(cls, mod)
        elif issubclass(cls, BaseData):
            subpath = 'data/'
            self._data_classes.append(Wrapped(cls, self))
            s, entity_name = self.emit_code_data(cls, mod)
        elif issubclass(cls, _BaseModel):
            self.process_poly_cls(cls)
        if not s:
            return
        assert entity_name
        self._contracts.append(entity_name)
        with open(Path(self._out_dir).joinpath(f'{subpath}{entity_name}.sol'), 'w') as sol_f:
            sol_f.write(s)

    def emit_inventory_contract(self):
        s = f"""// contracts/generated/Inventory.sol
// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

import "@openzeppelin/contracts-upgradeable/token/ERC1155/ERC1155Upgradeable.sol";

"""
        for erc1155_uid, erc1155_item in enumerate(self._erc1155_instances):
            cls_name_us = self.get_class_name_us(type(erc1155_item))
            s += f"uint constant {cls_name_us.upper()}_{erc1155_item.id.upper()} = {erc1155_uid};\n"

        s += f"""
contract Inventory is ERC1155Upgradeable {{
}}
"""

        with open(Path(self._out_dir).joinpath('Inventory.sol'), 'w') as sol_f:
            sol_f.write(s)

#
    def emit_data_contract(self):
        s = f"""// contracts/generated/GameData.sol
// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

"""
        num_data_classes = len(self._data_classes)
        for jj, data_cls in enumerate(self._data_classes):

            s += f"import \"./data/{data_cls.entity_name}Data.sol\";\n"
        s += """

contract GameData {
"""
        for data_cls in self._data_classes:
            if data_cls._cls._is_ladder:
                continue
            s += f"""
    {data_cls.entity_name}Data public _{data_cls.var_name};

    function get_{data_cls.var_name}_by_id(uint _id) external view returns ({data_cls.entity_name}Data.{data_cls.var_name}_t memory) {{
        return _{data_cls.var_name}.get_{data_cls.var_name}_by_id(_id);
    }}
"""
        s += "}"

        with open(Path(self._out_dir).joinpath('GameData.sol'), 'w') as sol_f:
            sol_f.write(s)

    def emit_game_logic_base_contract(self):
        s = f"""// contracts/generated/GameLogicBase.sol
// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";

import "./Inventory.sol";
import "./GameData.sol";
"""
        for erc721_cls in self._erc721_classes:
            s += f"import \"./model/{erc721_cls.entity_name}.sol\";\n"

        s += "\n"
        asset_type_id = 0
        for jj, erc721_cls in enumerate(self._erc721_classes):
            s += f"uint constant ASSET_TYPE_{erc721_cls.entity_name.upper()} = {asset_type_id};\n"
            asset_type_id += 1
        #
        asset_type_id_max = asset_type_id
        #
        s += "\n"
        reward_type_id = 0
        for jj, erc721_cls in enumerate(self._erc721_classes):
            s += f"uint constant REWARD_TYPE_{erc721_cls.entity_name.upper()} = {reward_type_id};\n"
            reward_type_id += 1
        #
        reward_type_id_max = reward_type_id

        s += f"""

contract GameLogicBase is Initializable {{

    using SafeMath for uint;

    GameData public gdata;
    Inventory public inventory;
"""
        for erc721_cls in self._erc721_classes:
            s += f"    {erc721_cls.entity_name} public {erc721_cls.var_name_plural};\n"

        s += f"""
    function initialize(
        GameData _gdata,
        Inventory _inventory,
"""
        for jj, erc721_cls in enumerate(self._erc721_classes):
            sep = ',' if jj != len(self._erc721_classes) - 1 else ''
            s += f"        {erc721_cls.entity_name} _{erc721_cls.var_name_plural}{sep}\n"
        s += "    ) public {\n"
        s += f"""
        gdata = _gdata;
        inventory = _inventory;
"""
        for jj, erc721_cls in enumerate(self._erc721_classes):
            s += f"        {erc721_cls.var_name_plural} = _{erc721_cls.var_name_plural};\n"
        s += "    }\n"

        for erc721_cls in self._erc721_classes:
            if issubclass(erc721_cls._cls, UpgradeableWithExp):
                upgrade_mat_cls = self.get_upgrade_material(erc721_cls)
                _w_upgrade_mat_cls = Wrapped(upgrade_mat_cls, self)
                s += f"""
    function _{erc721_cls.var_name}_use_exp_material (address _user, uint {erc721_cls.var_name}_id, uint mat_id, uint amount) internal {{
        {_w_upgrade_mat_cls.entity_name}Data.{_w_upgrade_mat_cls.var_name}_t memory {_w_upgrade_mat_cls.var_name} = gdata.get_{_w_upgrade_mat_cls.var_name}_by_id(mat_id);
        require(inventory.balanceOf(_user, {_w_upgrade_mat_cls.var_name}._token_id) >= amount);
        uint exp = {_w_upgrade_mat_cls.var_name}.value.mul(amount);
        {erc721_cls.var_name_plural}.add_exp({erc721_cls.var_name}_id, exp);
    }}
"""
        s += f"""
    function _spend_assets(address from, bytes memory assets_data) internal {{
        uint off = 0;
        uint32 assets_num;

        assembly {{
            assets_num := mload(add(assets_data, off))
        }}
        off += 4;
    
        for (uint32 i = 0; i < assets_num; i++) {{
            off = _spend_asset(from, assets_data, off);
        }}    
    }}
    
    function _spend_asset(address from, bytes memory assets_data, uint _off) internal returns (uint off) {{
        off = _off;
        uint16 _asset_type;
        
        assembly {{
            _asset_type := mload(add(assets_data, off))
        }}
        off += 2;    
"""
        asset_type_id = 0
        for erc721_cls in self._erc721_classes:
            if asset_type_id == 0:
                else_if_s = "if"
            # elif reward_type_id == reward_type_id_max - 1:
            #    else_if_s = "else"
            else:
                else_if_s = "else if"
            s += f"""
        {else_if_s} (_asset_type == ASSET_TYPE_{erc721_cls.entity_name.upper()}) {{
            uint _{erc721_cls.data.var_name}_id;
            uint _amount;
            assembly {{
                _{erc721_cls.data.var_name}_id := mload(add(assets_data, off))
            }}
            off += 8;
            assembly {{
                _amount := mload(add(assets_data, off))
            }}
            off += 8;
            //
            _spend_{erc721_cls.entity_name.lower()}(from,  _{erc721_cls.data.var_name}_id, _amount);
        }} 
"""
            asset_type_id += 1
        #
        s += "    }\n"
        #
        for erc721_cls in self._erc721_classes:
            s += f"""
    function _spend_{erc721_cls.entity_name.lower()} (address to, uint {erc721_cls.data.var_name}_id, uint amount) internal {{
        {erc721_cls.var_name_plural}.spend(to, {erc721_cls.data.var_name}_id, amount);
    }}
"""
        ##
        #
        ##
        for erc721_cls in self._erc721_classes:
            s += f"""
    function _give_{erc721_cls.entity_name.lower()} (address to, uint {erc721_cls.data.var_name}_id, uint amount) internal {{
        {erc721_cls.var_name_plural}.give(to, {erc721_cls.data.var_name}_id, amount);
    }}
"""
        s += f"""

    function _give_rewards(address to, bytes memory rewards_data) internal {{
        uint off = 0;
        uint32 rewards_num;

        assembly {{
            rewards_num := mload(add(rewards_data, off))
        }}
        off += 4;
    
        for (uint32 i = 0; i < rewards_num; i++) {{
            off = _give_reward(to, rewards_data, off);
        }}
    }}

    function _give_reward(address to, bytes memory reward_data, uint _off) internal returns (uint off) {{
        off = _off;
        uint16 _reward_type;
        
        assembly {{
            _reward_type := mload(add(reward_data, off))
        }}
        off += 2;
"""
        reward_type_id = 0
        for erc721_cls in self._erc721_classes:
            if reward_type_id == 0:
                else_if_s = "if"
            #elif reward_type_id == reward_type_id_max - 1:
            #    else_if_s = "else"
            else:
                else_if_s = "else if"
            s += f"""
        {else_if_s} (_reward_type == REWARD_TYPE_{erc721_cls.entity_name.upper()}) {{
            uint _{erc721_cls.data.var_name}_id;
            uint _amount;
            assembly {{
                _{erc721_cls.data.var_name}_id := mload(add(reward_data, off))
            }}
            off += 8;
            assembly {{
                _amount := mload(add(reward_data, off))
            }}
            off += 8;
            //
            _give_{erc721_cls.entity_name.lower()}(to,  _{erc721_cls.data.var_name}_id, _amount);
        }} 
"""
            reward_type_id += 1
        s += "    }\n"

        s += "}"
        with open(Path(self._out_dir).joinpath('GameLogicBase.sol'), 'w') as sol_f:
            sol_f.write(s)

    def emit_deser_func(self, tname, bsz):
        return f"""
function load_{tname}(bytes memory _data, uint _off) internal pure returns ({tname} out, uint off) {{
    assembly {{
        out := mload(add(_data, _off))
    }}
    off = _off + {bsz};
}}

function load_{tname}(bytes memory _data) internal pure returns ({tname} out) {{
    assembly {{
        out := mload(_data)
    }}
}}
"""

    def emit_ser_func(self, tname, bsz):
        return f"""
function dump_{tname}({tname} _value, bytes memory _data, uint _off) internal pure returns (uint off) {{
    assembly {{
        mstore(add(_data, _off), _value)
    }}
    off = _off + {bsz};
}}

function dump_{tname}({tname} _value, bytes memory _data) internal pure {{
    assembly {{
        mstore(_data, _value)
    }}
}}
"""

    def emit_serdes_library(self):
        s = f"""// contracts/SerDes.sol
// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

library SerDes {{
    
"""
        for sz in range(8, 264, 8):
            bsz = sz // 8
            s += apply_ident(self.emit_deser_func(f'int{sz}', bsz), 4)
            s += apply_ident(self.emit_deser_func(f'uint{sz}', bsz), 4)
            s += apply_ident(self.emit_ser_func(f'int{sz}', bsz), 4)
            s += apply_ident(self.emit_ser_func(f'uint{sz}', bsz), 4)
        #
        s += apply_ident(self.emit_deser_func('int', 32), 4)
        s += apply_ident(self.emit_deser_func('uint', 32), 4)
        s += apply_ident(self.emit_ser_func('int', 32), 4)
        s += apply_ident(self.emit_ser_func('uint', 32), 4)
        #
        s += apply_ident(self.emit_deser_func('address', 20), 4)
        s += apply_ident(self.emit_ser_func('address', 20), 4)
        #
        s += f"""
    function load_bool(bytes memory _data, uint _off) internal pure returns (bool out, uint off) {{
        uint8 tmp;
        assembly {{
            tmp := mload(add(_data, _off))
        }}
        off = _off + 1;
        out = tmp == 0 ? false : true;
    }}
    
    function load_bool(bytes memory _data) internal pure returns (bool out) {{
        uint8 tmp;
        assembly {{
            out := mload(_data)
        }}
        out = tmp == 0 ? false : true;
    }}

    function dump_bool(bool _value, bytes memory _data, uint _off) internal pure returns (uint off) {{
        uint8 _tmp = _value ? 1 : 0;
        assembly {{
            mstore(add(_data, _off), _tmp)
        }}
        off = _off + 1;
    }}
    
    function dump_bool(bool _value, bytes memory _data) internal pure {{
        uint8 _tmp = _value ? 1 : 0;
        assembly {{
            mstore(_data, _tmp)
        }}
    }}
"""
        s += "}"
        with open(Path(self._out_dir).joinpath('../SerDes.sol'), 'w') as sol_f:
            sol_f.write(s)

    def emit_visitor(self, p_cls):
        ch_classes = self._poly_structs[p_cls]
        _wrap_chs = [Wrapped(ch_class, self) for ch_class in ch_classes]
        _wrap = Wrapped(p_cls, self)
        #
        s = f"""// contracts/visitors/{_wrap.entity_name}Visitor.sol
// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

import "../../SerDes.sol";

"""
        for jj, ch_class in enumerate(_wrap_chs):
            s += f"uint constant {_wrap.entity_name.upper()}_TYPE_{ch_class.var_name.upper()} = {jj};\n"

        s += f"""

library {_wrap.entity_name}Lib {{
    
    using SerDes for bytes;

"""
        #
        for ch_class in _wrap_chs:
            s += apply_ident(self.emit_struct_def(ch_class), 4)
        #
        for ch_class in _wrap_chs:
            s += f"    function load_{ch_class.var_name} (bytes memory _data, uint _off) internal pure returns ({ch_class.var_name}_t memory _{ch_class.var_name}, uint off) {{\n"
            s += apply_ident("off = _off;", 8)
            for fname, fdef in ch_class._cls.__fields__.items():
                s += apply_ident(f"(_{ch_class.var_name}.{self.solize_name(fname)}, off) = _data.load_{self.get_soltype(fdef.outer_type_)}(off);", 8)
            s += apply_ident("}\n", 4)
        s += "}"
        #
        s += f"""

contract {_wrap.entity_name}Visitor {{

    using SerDes for bytes;
    using {_wrap.entity_name}Lib for bytes;

    function visit(bytes memory _{_wrap.entity_name.lower()}_bytes) public {{
        uint off = 0;
        uint _type;
        (_type, off) = _{_wrap.entity_name.lower()}_bytes.load_uint(off);
"""
        for jj, ch_class in enumerate(_wrap_chs):
            else_if_s = "if" if jj == 0 else "else if"
            s += f"""
        {else_if_s} (_type == {_wrap.entity_name.upper()}_TYPE_{ch_class.var_name.upper()}) {{
            {_wrap.entity_name}Lib.{ch_class.var_name}_t memory _{ch_class.var_name};
            (_{ch_class.var_name}, off) = _{_wrap.entity_name.lower()}_bytes.load_{ch_class.var_name}(off);
            visit_{ch_class.var_name}(_{ch_class.var_name});
        }}
"""
        s += "    }"
        #
        for _ch_wrap in _wrap_chs:
            s += f"""
    function visit_{_ch_wrap.var_name}({_wrap.entity_name}Lib.{_ch_wrap.var_name}_t memory _{_ch_wrap.var_name}) internal {{
    }}
"""
        #
        s += "}"
        with open(Path(self._out_dir).joinpath('visitors').joinpath(f'{_wrap.entity_name}Visitor.sol'), 'w') as sol_f:
            sol_f.write(s)

    def emit_visitors(self):
        for p_cls in self._poly_structs:
            self.emit_visitor(p_cls)

    def generate(self):
        super().generate()
        self.emit_inventory_contract()
        self.emit_data_contract()
        self.emit_visitors()
        self.emit_game_logic_base_contract()
        #self.emit_serdes_library()
