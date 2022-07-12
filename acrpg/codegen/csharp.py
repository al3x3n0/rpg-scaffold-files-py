import inflection
from pathlib import Path
import typing

from acrpg.codegen.base import CodeGenBase, Wrapped
from acrpg.model.types import *
from acrpg.model.base import _BaseModel
from acrpg.model.data import DataRef, BaseData
from acrpg.model.models import UpgradeableWithExp


class CodeGenCSharp(CodeGenBase):

    def __init__(self, *args, **kwargs):
        super(CodeGenCSharp, self).__init__(*args, **kwargs)
        self._server_out_dir = kwargs.get('server_out_dir')
        self._console_app_out_dir = kwargs.get('console_app_out_dir')

    def get_sql_type(self, fdef: type):
        #
        t_origin = typing.get_origin(fdef)
        #
        if fdef == cs_ulong:
            return "bigint" #FIXME
        elif fdef == cs_int:
            return "int"
        elif fdef == int:
            return "int"
        elif fdef == str:
            return "varchar(256)"
        elif t_origin:
            t_args = typing.get_args(fdef)
            if t_origin is typing.Optional:
                return self.get_sql_type(t_args[0])
            elif t_origin == DataRef:
                return f"int"
            else:
                assert False, f"{t_origin} not supported"
        else:
            return fdef.__name__

    def get_cs_val(self, ftype, val, ident=0):
        t_origin = typing.get_origin(ftype)
        #
        if ftype in [int, cs_ulong, cs_long, cs_int, cs_uint]:
            s = str(val)
        elif ftype == str:
            s = f"\"{val}\""
        elif t_origin:
            if t_origin == DataRef:
                s = f"{inflection.camelize(val.data_type)}.Types.{val.id.upper()}"
            elif t_origin is list:
                s = f"new List<{self.get_cs_type(typing.get_args(ftype)[0])}> {{\n"
                for el in val:
                    s += ' ' * (ident + 4) + f"{self.get_cs_val(typing.get_args(ftype)[0], el, ident=(ident+4))},\n"
                s += ' ' * ident + "}"
            else:
                assert False
        elif issubclass(ftype, _BaseModel):
            s = f"new {ftype.__name__}{{\n"
            for fname, fval in val:
                el_type = ftype.__fields__[fname].outer_type_
                s += ' ' * (ident + 4) + f"{inflection.camelize(fname)} = {self.get_cs_val(el_type, fval, ident=(ident+4))},\n"
            s += ' ' * ident + "}"
        else:
            s = str(val)
        return s

    def get_cs_type(self, fdef: type, dto=False):
        #
        t_origin = typing.get_origin(fdef)
        #
        if fdef == cs_ulong:
            return "ulong"
        elif fdef == cs_long:
            return "long"
        elif fdef == cs_uint:
            return "uint"
        elif fdef == cs_int:
            return "int"
        elif fdef == int:
            return "int"
        elif fdef == str:
            return "string"
        elif t_origin:
            t_args = typing.get_args(fdef)
            if t_origin is typing.Optional:
                return self.get_cs_type(t_args[0])
            elif t_origin is list:
                return f"List<{self.get_cs_type(t_args[0], dto=dto)}>"
            elif t_origin is dict:
                return f"Dict<{self.get_cs_type(t_args[0], dto=dto)}, {self.get_cs_type(t_args[1], dto=dto)}>"
            elif t_origin == DataRef:
                return f"{self.get_cs_type(t_args[0], dto=dto)}.Types"
            else:
                assert False, f"{t_origin} not supported"
        else:
            if issubclass(fdef, _BaseModel) and dto:
                wrp_cls = Wrapped(fdef, self)
                return f'{wrp_cls.var_name_camel}DTO'
            return fdef.__name__

    def emit_code(self, cls, mod):
        s = ''
        entity_name = ''
        subpath = ''
        #
        if cls._nft or cls._dto:
            subpath = 'Model/'
            s, entity_name = self.emit_code_model(cls, mod)
        elif issubclass(cls, BaseData):
            subpath = 'Data/'
            s, entity_name = self.emit_code_data(cls, mod)
            self.emit_init_game_data(cls)
            self._emit_game_data_helper(cls)
        elif issubclass(cls, _BaseModel):
            subpath = 'Structs/'
            s, entity_name = self.emit_code_struct(cls, mod)
        if not s:
            return
        assert entity_name
        path = Path(self._out_dir).joinpath(f'{subpath}{entity_name}.cs')
        self.write_file(path, s)

    def emit_constructor(self, cls):
        s = f"    public {cls.__name__} ("
        params = []
        for fname, fdef in cls.__fields__.items():
            if fname == 'id':
                params.append("int Id")
            else:
                params.append(f"{self.get_cs_type(fdef.outer_type_)} {inflection.camelize(fname)}")
        s += ", ".join(params)
        s += ")\n    {\n"
        for fname, fdef in cls.__fields__.items():
            s += f"        this.{inflection.camelize(fname)} = {inflection.camelize(fname)};\n"
        s += "    }\n"
        return s

    def _emit_cost_base_struct(self):
        s = f"""/* Generated/Structs/CostBase.cs */
using System;
using System.Collections.Generic;
using MessagePack;

using {self.namespace}.Shared.Data;


namespace {self.namespace}.Shared.Structs
{{

    public abstract class CostBase
    {{
        public abstract void Accept(ICostVisitor visitor);
    }}
}}
"""
        out_path = Path(self._out_dir) \
            .joinpath('Structs') \
            .joinpath(f'CostBase.cs')
        self.write_file(out_path, s)

    def _emit_cost_visitor(self):
        s = f"""/* Generated/Visitors/ICostVisitor.cs */

namespace {self.namespace}.Shared.Structs
{{
    public interface ICostVisitor
    {{
"""
        for wrp_cls in self._erc721_classes:
            s += 8*' ' + f"void Visit(Cost{wrp_cls.entity_name} cost);\n"
        s += """
    }
}
"""
        out_path = Path(self._out_dir) \
            .joinpath('Visitors') \
            .joinpath(f'ICostVisitor.cs')
        self.write_file(out_path, s)

    def _emit_cost_processor(self):
        s = f"""/* Generated/Costs/CostProcessor.cs */

namespace {self.namespace}.Server.Services
{{
    public partial class CostProcessor
    {{
"""
        s += """
    }
}
"""
        out_path = Path(self._server_out_dir) \
            .joinpath('Costs') \
            .joinpath('CostProcessor.cs')
        self.write_file(out_path, s)

    def _emit_cost_structs(self):
        self._emit_cost_base_struct()
        self._emit_cost_processor()
        self._emit_cost_visitor()
        for wrp_cls in self._erc721_classes:
            s = f"""/* Generated/Structs/Cost{wrp_cls.entity_name}.cs */
using System;
using System.Collections.Generic;
using MessagePack;

using {self.namespace}.Shared.Data;


namespace {self.namespace}.Shared.Structs
{{

    [MessagePackObject(true)]
    public class Cost{wrp_cls.entity_name} : CostBase
    {{
        public List<string> Conditions {{ get; set; }}
        
        public override void Accept(ICostVisitor visitor)
        {{
            visitor.Visit(this);
        }}
    }}
}}
"""
            out_path = Path(self._out_dir) \
                .joinpath('Structs') \
                .joinpath(f'Cost{wrp_cls.entity_name}.cs')
            self.write_file(out_path, s)

    def emit_abstrct_code_struct(self, cls):
        _wrp_cls = Wrapped(cls, self)
        s = f"""/* Generated/Structs/{cls.__name__}.cs */
using System;
using MessagePack;

using {self.namespace}.Shared.Data;


namespace {self.namespace}.Shared.Structs
{{

public abstract class {_wrp_cls.var_name_camel}
{{
"""
        for fname, fdef in cls.__fields__.items():
            s += f"    public {self.get_cs_type(fdef.outer_type_)} {inflection.camelize(fname)} {{ get; set; }}\n"
        s += f"""
    public abstract void Accept(I{_wrp_cls.entity_name}Visitor visitor);
}}

}}
"""
        return s, f"{_wrp_cls.var_name_camel}"

    def emit_code_struct(self, cls, mod):
        #
        if cls in self._poly_structs:
            return self.emit_abstrct_code_struct(cls)
        #
        _wrp_cls = Wrapped(cls, self)
        inherit_str = ''
        poly_base = self._poly_bases.get(cls)
        if poly_base:
            poly_base = Wrapped(poly_base, self)
            inherit_str = f' : {poly_base.var_name_camel}'
        s = f"""/* Generated/Structs/{cls.__name__}.cs */
using System;
using MessagePack;

using {self.namespace}.Shared.Data;


namespace {self.namespace}.Shared.Structs
{{

[MessagePackObject(true)]
public class {_wrp_cls.var_name_camel}{inherit_str}
{{
"""
        for fname, fdef in cls.__fields__.items():
            s += f"    public {self.get_cs_type(fdef.outer_type_)} {inflection.camelize(fname)} {{ get; set; }}\n"
        if poly_base:
            s += f"""
    public override void Accept(I{_wrp_cls.entity_name}Visitor visitor)
    {{
        visitor.Visit(this);
    }}
"""
        s += "}\n\n}"
        return s, f"{_wrp_cls.var_name_camel}"

    def emit_code_model(self, cls, mod):
        _wrp_cls = Wrapped(cls, self)
        s = f"""/* Generated/Model/{cls.__name__}.cs */
using System;
using System.Collections.Generic;
using MessagePack;

using {self.namespace}.Shared.Structs;


namespace {self.namespace}.Shared.Protocol.Models
{{

[MessagePackObject(true)]
public class {_wrp_cls.var_name_camel}DTO
{{
"""
        for fname, fdef in cls.__fields__.items():
            t_origin = typing.get_origin(fdef.outer_type_)
            if t_origin == DataRef:
                s += f"    public int {inflection.camelize(fname)} {{ get; set; }}\n"
            else:
                s += f"    public {self.get_cs_type(fdef.outer_type_, dto=True)} {inflection.camelize(fname)} {{ get; set; }}\n"
        s += "}\n\n}"
        return s, f"{_wrp_cls.var_name_camel}DTO"

    def _emit_game_data_helper(self, cls):
        _wrp_cls = Wrapped(cls, self)
        s = f"""

using {self.namespace}.Shared.Data;


namespace {self.namespace}.Server.GameData
{{
    public partial class GameDataService
    {{
        public {_wrp_cls.var_name_camel} Get{_wrp_cls.var_name_camel}(int id)
        {{
            return this._db.{_wrp_cls.var_name_camel}Table.FindById(id);
        }}
"""
        s += """
    }
}
"""
        out_path = Path(self._server_out_dir)\
            .joinpath('GameData')\
            .joinpath(f'{_wrp_cls.var_name_camel}.cs')
        self.write_file(out_path, s)

    def _emit_init_game_data_all(self):
        s = f"""/* Generated/Data/InitGenerated.cs */

namespace {self.namespace}.ConsoleApp.Data
{{

public partial class GameDataBuilder
{{
    public void InitGenerated()
    {{
"""
        for _wrp_cls in self._data_classes:
            s += 8*' '+f"Init{_wrp_cls.var_name_camel}();\n"
        s += """
    }
}

}
"""
        out_path = Path(self._console_app_out_dir)\
            .joinpath('Data')\
            .joinpath(f'InitGenerated.cs')
        self.write_file(out_path, s)

    def emit_init_game_data(self, cls):
        _wrp_cls = Wrapped(cls, self)
        s = f"""/* Generated/Data/{cls.__name__}.cs */
using MasterMemory;

using {self.namespace}.Shared.Data;
using {self.namespace}.Shared.Structs;


namespace {self.namespace}.ConsoleApp.Data
{{

public partial class GameDataBuilder
{{
    private void Init{_wrp_cls.var_name_camel}()
    {{
        _builder.Append(new {_wrp_cls.var_name_camel}[]
        {{
"""
        for data_inst in BaseData.instances(cls):
            s += 12*' ' + f"new {_wrp_cls.var_name_camel}("
            jj = 0
            for fname, fvalue in data_inst:
                fdef = cls.__fields__[fname]
                comma_s = ',' if jj < len(cls.__fields__)-1 else ''
                if fname == 'id':
                    s += f"Id: (int){_wrp_cls.var_name_camel}.Types.{data_inst.id.upper()}{comma_s} "
                else:
                    s += f"{inflection.camelize(fname)}: {self.get_cs_val(fdef.outer_type_, fvalue, ident=12)}{comma_s} "
                jj += 1
            s += "),\n"
        s += """
        });
    }
"""
        s += "}\n\n}"
        out_path = Path(self._console_app_out_dir)\
            .joinpath('Data')\
            .joinpath(f'{_wrp_cls.var_name_camel}.cs')
        self.write_file(out_path, s)

    def emit_code_data(self, cls, mod):
        _wrp_cls = Wrapped(cls, self)
        s = f"""/* Generated/Data/{cls.__name__}.cs */
using System.Collections.Generic;
using MasterMemory;

using {self.namespace}.Shared.Structs;


namespace {self.namespace}.Shared.Data
{{

[MemoryTable("{_wrp_cls.var_name}"), MessagePack.MessagePackObject(true)]  
public class {cls.__name__}
{{
    public enum Types : int
    {{
"""
        for _id, data_inst in enumerate(BaseData.instances(cls)):
            s += 8*' ' + f"{data_inst.id.upper()} = {_id},\n"
        s += "    }\n\n"
        for fname, fdef in cls.__fields__.items():
            if fname == 'id':
                s += "    [PrimaryKey]\n"
                s += f"    public int Id {{ get; }}\n"
            else:
                s += f"    public {self.get_cs_type(fdef.outer_type_)} {inflection.camelize(fname)} {{ get; }}\n"
        s += self.emit_constructor(cls)
        if cls._is_ladder:
            s += f"""
    public (int, ulong) GetLevel(int currLevel, ulong exp)
    {{
        var level = currLevel;
        while (exp >= this.Levels[level].Experience) {{
            level += 1;
        }}
        var expLeft = this.Levels[level].Experience - exp;
        return (level, expLeft);
    }}
    
    public ulong GetLevelExp(int level)
    {{
        if (level >=  this.Levels.Count)
        {{
            return 0;
        }}
        
        ulong totExp = 0;
        for (int i = 0; i < level; i++)
        {{
            totExp += this.Levels[i].Experience;
        }}
        return totExp;
    }}
"""
        s += "}\n\n}"
        #
        return s, cls.__name__

    def emit_visitors(self):
        for p_cls in self._poly_structs:
            self.emit_visitor(p_cls)

    def emit_visitor(self, p_cls):
        ch_classes = self._poly_structs[p_cls]
        _wrp_chs = [Wrapped(ch_class, self) for ch_class in ch_classes]
        _wrp_cls = Wrapped(p_cls, self)
        #
        s = f"""/* Generated/Structs/I{_wrp_cls.entity_name}Visitor.cs */

namespace {self.namespace}.Shared.Structs
{{

public interface I{_wrp_cls.entity_name}Visitor
{{
"""
        for _wrp_ch_cls in _wrp_chs:
            s += f"    void Visit({_wrp_ch_cls.var_name_camel} {_wrp_ch_cls.entity_name_us});\n"
        s += "}\n\n}"
        #
        out_path = Path(self._out_dir)\
            .joinpath('Visitors')\
            .joinpath(f'I{_wrp_cls.entity_name}Visitor.cs')
        self.write_file(out_path, s)

    def _emit_i_user_repo(self):
        s = f"""
using System;

using {self.namespace}.Server.Db;
using {self.namespace}.Server.Db.Models;

namespace {self.namespace}.Server.Repositories
{{

public partial interface IUserRepository
{{
"""
        for wrp_cls in self._erc721_classes:
            s += f"    public {wrp_cls.var_name_camel} AddToUser(UserModel user, {wrp_cls.var_name_camel} {wrp_cls.entity_name_us});\n"
            s += f"    public bool RemoveFromUser(UserModel user, {wrp_cls.var_name_camel} {wrp_cls.entity_name_us});\n"

        s += "}\n\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath("Repositories") \
            .joinpath('IUserRepository.cs')
        self.write_file(out_path, s)

    def _emit_user_repo(self):
        s = f"""//
using System;
using System.Collections.Generic;
using System.Linq;
using System.Data;
using MagicOnion.Server;

using {self.namespace}.Server.Db;
using {self.namespace}.Server.Db.Models;

namespace {self.namespace}.Server.Repositories
{{

public partial class UserRepository 
{{
    private async Task<UserModel> GetFromDbAsync(Ulid id)
    {{
        var user = await _db.Users.FindAsync(x => x.Id == id);
        if (user is null)
        {{
            return null;
        }}
        var user_inventory = await _db.UserInventory.FindAllAsync(x => x.UserId == id);
"""
        for wrp_cls in self._erc721_classes:
            s += f"        var {wrp_cls.var_name_plural} = await _db.{wrp_cls.entity_name_plural}.FindAllAsync(x => x.UserId == id);\n"
            s += f"        user.{wrp_cls.entity_name_plural} = {wrp_cls.var_name_plural}.ToDictionary(x => x.Id, x => x);\n"
        s += "        return user;\n"
        s += "    }\n"

        for wrp_cls in self._erc721_classes:
            s += f"""
    public {wrp_cls.var_name_camel} AddToUser(UserModel user, {wrp_cls.var_name_camel} {wrp_cls.entity_name_us})
    {{
        {wrp_cls.entity_name_us}.UserId = user.Id;
        user.{wrp_cls.entity_name_plural}[{wrp_cls.entity_name_us}.Id] = {wrp_cls.entity_name_us};           
        this._changes.{wrp_cls.entity_name_plural}.Add({wrp_cls.entity_name_us});
        return {wrp_cls.entity_name_us};
    }}

    public bool RemoveFromUser(UserModel user, {wrp_cls.var_name_camel} {wrp_cls.entity_name_us})
    {{
        var success = user.{wrp_cls.entity_name_plural}.Remove({wrp_cls.entity_name_us}.Id);           
        this._changes.{wrp_cls.entity_name_plural}.Remove({wrp_cls.entity_name_us});
        return success;
    }}
"""
        s += f"""
    public async Task CommitChanges()
    {{
        using (var tx = this._db.BeginTransaction())
        {{
            if (this._changes.UserInventory is not null)
            {{
                await this._db.UserInventory.BulkInsertAsync(this._changes.UserInventory.Added.Values.ToList(), tx);
                await this._db.UserInventory.BulkUpdateAsync(this._changes.UserInventory.Updated.Values.ToList(), tx);
            }}
"""
        for wrp_cls in self._erc721_classes:
            s += f"""
            if (this._changes.{wrp_cls.entity_name_plural} is not null)
            {{
                foreach(var model in this._changes.{wrp_cls.entity_name_plural}.Removed.Values)
                {{
                    await this._db.{wrp_cls.entity_name_plural}.DeleteAsync(model, tx);
                }}
                await this._db.{wrp_cls.entity_name_plural}.BulkInsertAsync(this._changes.{wrp_cls.entity_name_plural}.Added.Values.ToList(), tx);
                await this._db.{wrp_cls.entity_name_plural}.BulkUpdateAsync(this._changes.{wrp_cls.entity_name_plural}.Updated.Values.ToList(), tx);
            }}
"""
        s += """
            tx.Commit();
        }
    }
"""
        s += "}\n\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath("Repositories") \
            .joinpath('UserRepository.cs')
        self.write_file(out_path, s)

    def _emit_user_model(self):
        s = f"""//
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using MicroOrm.Dapper.Repositories.Attributes;
using MicroOrm.Dapper.Repositories.Attributes.Joins;

using AlienCell.Server.Db;


namespace {self.namespace}.Server.Db.Models
{{

public partial class UserModel
{{
"""
        for wrp_cls in self._erc721_classes:
            s += "    [NotMapped]\n"
            s += f"    public Dictionary<Ulid, {wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} {{ get; set; }} = new Dictionary<Ulid, {wrp_cls.var_name_camel}>();\n"
        s += "}\n\n}"
        out_path = Path(self._server_out_dir)\
            .joinpath("Db") \
            .joinpath('Models') \
            .joinpath('User.cs')
        self.write_file(out_path, s)

    def _emit_i_db_change_set(self):
        s = f"""
using System;

using {self.namespace}.Server.Cache;
using {self.namespace}.Server.Db.Models;

namespace {self.namespace}.Server.Db
{{

public partial interface IDbChangeSet
{{
    public ChangeSet<(Ulid, string, long), UserInventoryModel> UserInventory {{ get; }}
"""
        for wrp_cls in self._erc721_classes:
            s += f"    public ChangeSet<Ulid, {wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} {{ get; }}\n"
        s += "}\n\n}"
        out_path = Path(self._server_out_dir)\
            .joinpath("Db") \
            .joinpath('IDbChangeSet.cs')
        self.write_file(out_path, s)

    def _emit_db_change_set(self):
        s = f"""//
using System;
using System.Data;
using System.Collections.Generic;
using MagicOnion.Server;

using {self.namespace}.Server.Cache;
using {self.namespace}.Server.Db.Models;

namespace {self.namespace}.Server.Db
{{

public partial class DbChangeSet
{{
    private ChangeSet<Ulid, UserModel> _user_models;
    private ChangeSet<(Ulid, string, long), UserInventoryModel> _user_inventory_models;
"""
        for wrp_cls in self._erc721_classes:
            s += f"    private ChangeSet<Ulid, {wrp_cls.var_name_camel}> _{wrp_cls.var_name_plural};\n"
        s += "\n"
        s += """
    public ChangeSet<Ulid, UserModel> Users => _user_models ??
        (_user_models = new ChangeSet<Ulid, UserModel>());
        
    public ChangeSet<(Ulid, string, long), UserInventoryModel> UserInventory => _user_inventory_models ??
        (_user_inventory_models = new ChangeSet<(Ulid, string, long), UserInventoryModel>());
"""
        for wrp_cls in self._erc721_classes:
            s += f"""
    public ChangeSet<Ulid, {wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} => _{wrp_cls.var_name_plural} ??
        (_{wrp_cls.var_name_plural} = new ChangeSet<Ulid, {wrp_cls.var_name_camel}>());
"""
        s += "\n"
        s += f"""
    public async Task InvalidateUsers(UserCache cache)
    {{
        foreach(var u in Users.Updated)
        {{
            await cache.RemoveAsync(u.Value);
        }}
    }}

    public async Task FlushCache(UserCache cache)
    {{
        //foreach(var u in Users)
        //{{
        //    Console.WriteLine($"flushing user, Id={{u.Value.Id}}");
        //    await cache.SetAsync(u.Value);
        //}}
    }}
"""
        s += "}\n\n}"
        out_path = Path(self._server_out_dir)\
            .joinpath("Db") \
            .joinpath('DbChangeSet.cs')
        self.write_file(out_path, s)

    def emit_db_models(self):
        for wrp_cls in self._erc721_classes:
            self._emit_db_model(wrp_cls)

    def _emit_db_model(self, wrp_cls):
        s = f"""//
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using MicroOrm.Dapper.Repositories.Attributes;

using AlienCell.Server.Db;


namespace {self.namespace}.Server.Db.Models
{{

[MessagePack.MessagePackObject(true)]
[Table("{wrp_cls.var_name_plural}")]
public class {wrp_cls.var_name_camel} : IModel<Ulid>
{{
    [Key]
    public Ulid Id {{ get; set; }} = Ulid.NewUlid();

    public Ulid UserId {{ get; set; }}

"""
        for fname, fdef in wrp_cls._cls.__fields__.items():
            if fname == 'id':
                continue
            t_origin = typing.get_origin(fdef.outer_type_)
            if t_origin == DataRef:
                s += f"    public int {inflection.camelize(fname)} {{ get; set; }}\n"
            else:
                s += f"    public {self.get_cs_type(fdef.outer_type_)} {inflection.camelize(fname)} {{ get; set; }}\n"
        #
        s += "}\n\n}"
        out_path = Path(self._server_out_dir)\
            .joinpath("Db") \
            .joinpath('Models') \
            .joinpath(f'{wrp_cls.entity_name}.cs')
        self.write_file(out_path, s)

    def _emit_idb_context(self):
        s = f"""//
using MicroOrm.Dapper.Repositories;
using MicroOrm.Dapper.Repositories.DbContext;

using {self.namespace}.Server.Db.Models;

namespace {self.namespace}.Server.Db
{{

public partial interface IDbContext
{{
    IDapperRepository<UserModel> Users {{ get; }}
    IDapperRepository<UserInventoryModel> UserInventory {{ get; }}
"""
        for wrp_cls in self._erc721_classes:
            s += f"    IDapperRepository<{wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} {{ get; }}\n"
        s += "}\n\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath('Db') \
            .joinpath(f'IDbContext.cs')
        self.write_file(out_path, s)

    def _emit_accounts_table_create_sql(self):
        s = f"CREATE TABLE IF NOT EXISTS `accounts` ("
        s += " `Id` varbinary(16) not null,"
        s += " `Address` varchar(40) not null default '',"
        s += " `DeviceUId` varchar(255) not null default '',"
        #
        s += " `Name` varchar(127) not null default '',"
        s += " `Email` varchar(255) not null default '',"
        s += " `Phone` varchar(15) not null default '',"
        #
        s += " `PasswordHash` varbinary(32) default null,"
        #
        s += " `EKS` text not null default '',"
        s += " `EKSHash` varbinary(32) default null,"
        #
        s += " `CreatedAt` timestamp not null default CURRENT_TIMESTAMP,"
        s += " `UpdatedAt` timestamp not null default CURRENT_TIMESTAMP,"
        #
        s += " INDEX `Address_Idx` (`Address`),"
        s += " PRIMARY KEY (`Id`));"
        return s

    def _emit_users_table_create_sql(self):
        s = f"CREATE TABLE IF NOT EXISTS `user_models` ("
        s += " `Id` varbinary(16) not null,"
        s += " `AccountId` varbinary(16) not null,"
        s += " `Exp` BIGINT not null default 0,"
        s += " `Level` INT not null default 0,"
        s += " PRIMARY KEY (`Id`));"
        return s

    def _emit_user_inventory_table_create_sql(self):
        s = f"CREATE TABLE IF NOT EXISTS `user_inventory` ("
        s += " `UserId` varbinary(16) not null,"
        s += " `Type` varchar(255) not null,"
        s += " `ItemId` INT not null default 0,"
        s += " `Amount` INT not null default 0,"
        s += " PRIMARY KEY `Pk_UserId_Type_ItemId` (`UserId`, `Type`, `ItemId`),"
        s += " INDEX `UserId_Idx` (`UserId`)"
        s += ");"
        return s

    def _emit_table_create_sql(self, wrp_cls):
        s = f"CREATE TABLE IF NOT EXISTS `{wrp_cls.var_name_plural}` (`Id` varbinary(16) not null,"
        s += " `UserId` varbinary(16) not null,"
        for fname, fdef in wrp_cls._cls.__fields__.items():
            if fname == 'id':
                continue
            s += f" `{inflection.camelize(fname)}` {self.get_sql_type(fdef.outer_type_)} not null,"
        s += " PRIMARY KEY (`Id`));"
        return s

    def _emit_db_context(self):
        s = f"""//
using Dapper;
using MicroOrm.Dapper.Repositories;
using MicroOrm.Dapper.Repositories.DbContext;
using MicroOrm.Dapper.Repositories.SqlGenerator;

using {self.namespace}.Server.Db.Models;

namespace {self.namespace}.Server.Db
{{

public partial class DbContext
{{

    private void InitDb()
    {{
        Connection.Execute(\"{self._emit_accounts_table_create_sql()}\");
        Connection.Execute(\"{self._emit_users_table_create_sql()}\");
        Connection.Execute(\"{self._emit_user_inventory_table_create_sql()}\");
"""
        for wrp_cls in self._erc721_classes:
            s += f"        Connection.Execute(\"{self._emit_table_create_sql(wrp_cls)}\");\n"
        s += "    }\n\n"
        #
        s += f"    private IDapperRepository<UserModel> _user_models;\n"
        s += f"    private IDapperRepository<UserInventoryModel> _user_inventory_models;\n"
        for wrp_cls in self._erc721_classes:
            s += f"    private IDapperRepository<{wrp_cls.var_name_camel}> _{wrp_cls.var_name_plural};\n"
        #
        s += f"""
    public IDapperRepository<UserModel> Users => _user_models ??
        (_user_models = new DapperRepository<UserModel>(Connection, new SqlGenerator<UserModel>(SqlProvider.MySQL)));

    public IDapperRepository<UserInventoryModel> UserInventory => _user_inventory_models ??
        (_user_inventory_models = new DapperRepository<UserInventoryModel>(Connection, new SqlGenerator<UserInventoryModel>(SqlProvider.MySQL)));
"""
        #
        for wrp_cls in self._erc721_classes:
            s += f"""
    public IDapperRepository<{wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} => _{wrp_cls.var_name_plural} ??
        (_{wrp_cls.var_name_plural} = new DapperRepository<{wrp_cls.var_name_camel}>(Connection, new SqlGenerator<{wrp_cls.var_name_camel}>(SqlProvider.MySQL)));"""
        #
        s += "}\n\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath('Db') \
            .joinpath(f'DbContext.cs')
        self.write_file(out_path, s)

    def _emit_events(self):
        for wrp_cls in self._erc721_classes:
            self._emit_model_event(wrp_cls)

    def _emit_model_event(self, wrp_cls):
        s = f"""
namespace {self.namespace}.Generated.Events
{{

public class {wrp_cls.entity_name}AddedEvent
{{
}}

public class {wrp_cls.entity_name}RetiredEvent
{{
}}
"""
        if issubclass(wrp_cls._cls, UpgradeableWithExp):
            s += f"""
public class {wrp_cls.entity_name}LevelUpEvent
{{
"""
            s += "}\n"
            #
            s += f"""
public class {wrp_cls.entity_name}ExpChangeEvent
{{
"""
            s += "}\n"
        s += "\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath('Events') \
            .joinpath(f'{wrp_cls.entity_name}Events.cs')
        self.write_file(out_path, s)

    def _emit_ievent_hub(self):
        s = f"""//
using MessagePipe;

namespace {self.namespace}.Generated.Events
{{

public interface IEventHubSub
{{
"""
        for wrp_cls in self._erc721_classes:
            s += f"    ISubscriber<{wrp_cls.entity_name}AddedEvent> {wrp_cls.entity_name}AddedSub {{ get; }}\n"
            s += f"    ISubscriber<{wrp_cls.entity_name}RetiredEvent> {wrp_cls.entity_name}RetiredSub {{ get; }}\n"
            #
            if issubclass(wrp_cls._cls, UpgradeableWithExp):
                s += f"    ISubscriber<{wrp_cls.entity_name}LevelUpEvent> {wrp_cls.entity_name}LevelUpSub {{ get; }}\n"
                s += f"    ISubscriber<{wrp_cls.entity_name}ExpChangeEvent> {wrp_cls.entity_name}ExpChangeSub {{ get; }}\n"
            #
            s += "\n"
        s += "}\n"

        s += """
public interface IEventHubPub
{
"""
        for wrp_cls in self._erc721_classes:
            s += f"    IPublisher<{wrp_cls.entity_name}AddedEvent> {wrp_cls.entity_name}AddedPub {{ get; }}\n"
            s += f"    IPublisher<{wrp_cls.entity_name}RetiredEvent> {wrp_cls.entity_name}RetiredPub {{ get; }}\n"
            #
            if issubclass(wrp_cls._cls, UpgradeableWithExp):
                s += f"    IPublisher<{wrp_cls.entity_name}LevelUpEvent> {wrp_cls.entity_name}LevelUpPub {{ get; }}\n"
                s += f"    IPublisher<{wrp_cls.entity_name}ExpChangeEvent> {wrp_cls.entity_name}ExpChangePub {{ get; }}\n"
                s += "\n"
        s += "}\n"
        # namespace end
        s += "\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath(f'IEventHub.cs')
        self.write_file(out_path, s)

    def _emit_event_hub(self):
        s = f"""//
using MessagePipe;

namespace {self.namespace}.Generated.Events
{{

public class EventHub : IEventHubPub, IEventHubSub
{{

    public EventHub (EventFactory eventFactory)
    {{
"""
        for wrp_cls in self._erc721_classes:
            s += f"        (_{wrp_cls.entity_name_us}_added_pub, _{wrp_cls.entity_name_us}_added_sub) = eventFactory.CreateEvent<{wrp_cls.entity_name}AddedEvent>();\n"
            s += f"        (_{wrp_cls.entity_name_us}_retired_pub, _{wrp_cls.entity_name_us}_retired_sub) = eventFactory.CreateEvent<{wrp_cls.entity_name}RetiredEvent>();\n"
            if issubclass(wrp_cls._cls, UpgradeableWithExp):
                s += f"        (_{wrp_cls.entity_name_us}_level_up_pub, _{wrp_cls.entity_name_us}_level_up_sub) = eventFactory.CreateEvent<{wrp_cls.entity_name}LevelUpEvent>();\n"
                s += f"        (_{wrp_cls.entity_name_us}_exp_change_pub, _{wrp_cls.entity_name_us}_exp_change_sub) = eventFactory.CreateEvent<{wrp_cls.entity_name}ExpChangeEvent>();\n"
        s += "    }\n\n"
        for wrp_cls in self._erc721_classes:
            s += f"    private ISubscriber<{wrp_cls.entity_name}AddedEvent> _{wrp_cls.entity_name_us}_added_sub;\n"
            s += f"    private IDisposablePublisher<{wrp_cls.entity_name}AddedEvent> _{wrp_cls.entity_name_us}_added_pub;\n"
            s += f"    private ISubscriber<{wrp_cls.entity_name}RetiredEvent> _{wrp_cls.entity_name_us}_retired_sub;\n"
            s += f"    private IDisposablePublisher<{wrp_cls.entity_name}RetiredEvent> _{wrp_cls.entity_name_us}_retired_pub;\n"
            #
            if issubclass(wrp_cls._cls, UpgradeableWithExp):
                s += f"    private ISubscriber<{wrp_cls.entity_name}LevelUpEvent> _{wrp_cls.entity_name_us}_level_up_sub;\n"
                s += f"    private IDisposablePublisher<{wrp_cls.entity_name}LevelUpEvent> _{wrp_cls.entity_name_us}_level_up_pub;\n"
                s += f"    private ISubscriber<{wrp_cls.entity_name}ExpChangeEvent> _{wrp_cls.entity_name_us}_exp_change_sub;\n"
                s += f"    private IDisposablePublisher<{wrp_cls.entity_name}ExpChangeEvent> _{wrp_cls.entity_name_us}_exp_change_pub;\n"
            s += "\n"
        #
        for wrp_cls in self._erc721_classes:
            s += f"    public IPublisher<{wrp_cls.entity_name}AddedEvent> {wrp_cls.entity_name}AddedPub {{ get => _{wrp_cls.entity_name_us}_added_pub; }}\n"
            s += f"    public IPublisher<{wrp_cls.entity_name}RetiredEvent> {wrp_cls.entity_name}RetiredPub {{ get => _{wrp_cls.entity_name_us}_retired_pub; }}\n"
            #
            if issubclass(wrp_cls._cls, UpgradeableWithExp):
                s += f"    public IPublisher<{wrp_cls.entity_name}LevelUpEvent> {wrp_cls.entity_name}LevelUpPub {{ get => _{wrp_cls.entity_name_us}_level_up_pub; }}\n"
                s += f"    public IPublisher<{wrp_cls.entity_name}ExpChangeEvent> {wrp_cls.entity_name}ExpChangePub {{ get => _{wrp_cls.entity_name_us}_exp_change_pub; }}\n"
                s += "\n"
            s += "\n"
        #
        for wrp_cls in self._erc721_classes:
            s += f"    public ISubscriber<{wrp_cls.entity_name}AddedEvent> {wrp_cls.entity_name}AddedSub {{ get => _{wrp_cls.entity_name_us}_added_sub; }}\n"
            s += f"    public ISubscriber<{wrp_cls.entity_name}RetiredEvent> {wrp_cls.entity_name}RetiredSub {{ get => _{wrp_cls.entity_name_us}_retired_sub; }}\n"
            #
            if issubclass(wrp_cls._cls, UpgradeableWithExp):
                s += f"    public ISubscriber<{wrp_cls.entity_name}LevelUpEvent> {wrp_cls.entity_name}LevelUpSub {{ get => _{wrp_cls.entity_name_us}_level_up_sub; }}\n"
                s += f"    public ISubscriber<{wrp_cls.entity_name}ExpChangeEvent> {wrp_cls.entity_name}ExpChangeSub {{ get => _{wrp_cls.entity_name_us}_exp_change_sub; }}\n"
        s += "}\n"
        # namespace end
        s += "\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath(f'EventHub.cs')
        self.write_file(out_path, s)

    def _emit_iservices(self):
        for wrp_cls in self._erc721_classes:
            self._emit_model_iservice(wrp_cls)

    def _emit_model_iservice(self, wrp_cls):
        s = f"""//
using MagicOnion;

namespace {self.namespace}.Shared.Services
{{

public partial interface IGameService
{{
    public UnaryResult<int> Retire{wrp_cls.entity_name}(long id);
"""
        s += "}\n"
        # namespace end
        s += "\n}"
        out_path = Path(self._out_dir) \
            .joinpath("Services") \
            .joinpath(f'I{wrp_cls.entity_name}Service.cs')
        self.write_file(out_path, s)

    def _emit_model_services(self):
        for wrp_cls in self._erc721_classes:
            self._emit_model_service(wrp_cls)

    def _emit_model_service(self, wrp_cls):
        s = f"""//
using MagicOnion;

using {self.namespace}.Shared.Services;
using {self.namespace}.Server.Db.Models;


namespace {self.namespace}.Server.Services
{{

public partial class GameService
{{
    public async UnaryResult<int> Retire{wrp_cls.entity_name}(long id)
    {{
        await Task.Delay(0);
        return 0;
    }}
"""
        if issubclass(wrp_cls._cls, UpgradeableWithExp):
            item_type_s = f"{wrp_cls.entity_name_us}_upgrade_material"

            s += f"""
    private bool UpgradeWithMaterial(UserModel user, {wrp_cls.entity_name}Model {wrp_cls.var_name}, List<int> matIds, List<ulong> amounts)
    {{
        for (int i = 0; i < matIds.Count; i++)
        {{
            if (!this.Users.HasItems(user, \"{item_type_s}\", matIds[i], amounts[i]))
            {{
                return false;
            }}
        }}

        for (int i = 0; i < matIds.Count; i++)
        {{
            var (success, itemsLeft) = this.Users.UseItems(user, \"{item_type_s}\", matIds[i], amounts[i]);
            if (!success)
            {{
                return false;
            }}
        }}

        ulong addExp = 0;
        for (int i = 0; i < matIds.Count; i++)
        {{
            var matData = _gd.Db.{wrp_cls.entity_name}UpgradeMaterialDataTable.FindById(matIds[i]);
            addExp += matData.Value * amounts[i];
        }}

        var {wrp_cls.entity_name_us}_data = _gd.Get{wrp_cls.entity_name}Data({wrp_cls.var_name}.Data);
        var {wrp_cls.entity_name_us}_ladder_data = _gd.Get{wrp_cls.entity_name}LadderData((int){wrp_cls.entity_name_us}_data.Ladder);
    
        {wrp_cls.var_name}.Exp += addExp;
        var (newLevel, newExp) = {wrp_cls.entity_name_us}_ladder_data.GetLevel({wrp_cls.var_name}.Level, {wrp_cls.var_name}.Exp);
        {wrp_cls.var_name}.Level = newLevel;
        {wrp_cls.var_name}.Exp = newExp;

        return true;
    }}
"""
        s += "}\n\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath("Services") \
            .joinpath(f'{wrp_cls.entity_name}Service.cs')
        self.write_file(out_path, s)

    def _emit_model_cheat_services(self):
        for wrp_cls in self._erc721_classes:
            self._emit_model_cheat_service(wrp_cls)

    def _emit_model_cheat_service(self, wrp_cls):
        s = f"""//
using System;
using MagicOnion;

using {self.namespace}.Server.Repositories;
using {self.namespace}.Server.Db.Models;

namespace {self.namespace}.Server.Services
{{

public partial class CheatService
{{
    public async UnaryResult<Ulid> Add{wrp_cls.entity_name}(Ulid userId, int dataId)
    {{
        var {wrp_cls.var_name} = new {wrp_cls.var_name_camel}() 
            {{
                Data = dataId
            }};
        var user = await _userRepo.GetAsync(userId);
        _userRepo.AddToUser(user, {wrp_cls.var_name});
        return {wrp_cls.var_name}.Id;
    }}
"""
        s += "}\n"
        # namespace end
        s += "\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath("Services") \
            .joinpath("Cheats") \
            .joinpath(f'{wrp_cls.entity_name}CheatService.cs')
        self.write_file(out_path, s)

    def _emit_icheat_services(self):
        for wrp_cls in self._erc721_classes:
            self._emit_model_icheat_service(wrp_cls)

    def _emit_model_icheat_service(self, wrp_cls):
        s = f"""//
using System;
using MagicOnion;

namespace {self.namespace}.Shared.Services
{{

public partial interface ICheatService
{{
    public UnaryResult<Ulid> Add{wrp_cls.entity_name}(Ulid userId, int dataId);
"""
        s += "}\n"
        # namespace end
        s += "\n}"
        out_path = Path(self._out_dir) \
            .joinpath("Services") \
            .joinpath("Cheats") \
            .joinpath(f'I{wrp_cls.entity_name}CheatService.cs')
        self.write_file(out_path, s)


    def _emit_cost_processor(self):
        s = f"""// Generated/Costs/CostProcessor.cs
using {self.namespace}.Shared.Structs;


namespace {self.namespace}.Server.Services
{{
    public partial class CostProcessor
    {{
"""
        for wrp_cls in self._erc721_classes:
            s += f"""
        public void Visit(Cost{wrp_cls.entity_name} cost)
        {{
        }}
"""
        s += """
    }
}
"""
        out_path = Path(self._server_out_dir) \
            .joinpath("Costs") \
            .joinpath("CostProcessor.cs")
        self.write_file(out_path, s)

    def _emit_reward_giver(self):
        s = f"""// Generated/Rewards/RewardGiver.cs
using {self.namespace}.Shared.Structs;
using {self.namespace}.Server.Db.Models;


namespace {self.namespace}.Server.Services
{{
    public partial class RewardGiver
    {{
"""
        for wrp_cls in self._erc721_classes:
            if wrp_cls.entity_name == 'Building':
                continue #FIXME
            s += f"""
        public void Visit(Reward{wrp_cls.entity_name} reward)
        {{
            for (int i = 0; i < reward.Amount; i++)
            {{
                var {wrp_cls.var_name} = new {wrp_cls.var_name_camel}() 
                {{
                    Data = (int)reward.{wrp_cls.entity_name}
                }};
                this._userRepo.AddToUser(this._user, {wrp_cls.var_name});
            }}
        }}
"""
        s += """
    }
}
"""
        out_path = Path(self._server_out_dir) \
            .joinpath("Rewards") \
            .joinpath("RewardGiver.cs")
        self.write_file(out_path, s)

    def _emit_dto_auto_map(self):
        s = f"""
using AutoMapper;

using {self.namespace}.Server.Db.Models;
using {self.namespace}.Shared.Protocol.Models;


namespace {self.namespace}.Server.Mappings
{{
public partial class AutoMapping
{{
    private void CreateGeneratedMappings()
    {{
        CreateMap<UserModel, UserModelDTO>().ReverseMap();
"""
        for wrp_cls in self._erc721_classes:
            s += f"        CreateMap<{wrp_cls.entity_name}Model, {wrp_cls.var_name_camel}DTO>().ReverseMap();\n"
        s += """
    }
"""
        s += "}\n\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath("AutoMappings.cs")
        self.write_file(out_path, s)

    def generate(self):
        super().generate()
        self.emit_visitors()
        self.emit_db_models()
        #
        self._emit_i_db_change_set()
        self._emit_db_change_set()
        #
        self._emit_user_model()
        self._emit_i_user_repo()
        self._emit_user_repo()
        #
        self._emit_idb_context()
        self._emit_db_context()
        self._emit_events()
        self._emit_ievent_hub()
        self._emit_event_hub()
        self._emit_iservices()
        self._emit_model_services()
        #
        self._emit_icheat_services()
        self._emit_model_cheat_services()
        #
        self._emit_dto_auto_map()
        #
        self._emit_init_game_data_all()
        self._emit_reward_giver()
        #
        self._emit_cost_structs()
