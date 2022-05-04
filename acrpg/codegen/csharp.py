import inflection
from pathlib import Path
import typing

from acrpg.codegen.base import CodeGenBase, Wrapped
from acrpg.model.base import _BaseModel
from acrpg.model.data import DataRef, BaseData
from acrpg.model.models import UpgradeableWithExp


class CodeGenCSharp(CodeGenBase):

    def __init__(self, *args, **kwargs):
        super(CodeGenCSharp, self).__init__(*args, **kwargs)
        self._server_out_dir = kwargs.get('server_out_dir')

    def get_sql_type(self, fdef: type):
        #
        t_origin = typing.get_origin(fdef)
        #
        if fdef == int:
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

    def get_cs_type(self, fdef: type):
        #
        t_origin = typing.get_origin(fdef)
        #
        if fdef == int:
            return "long"
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
        s = ''
        entity_name = ''
        subpath = ''
        #
        if cls._nft:
            subpath = 'Model/'
            s, entity_name = self.emit_code_model(cls, mod)
        elif cls._is_ladder:
            subpath = 'Data/'
            s, entity_name = self.emit_code_ladder(cls, mod)
        elif issubclass(cls, BaseData):
            subpath = 'Data/'
            s, entity_name = self.emit_code_data(cls, mod)
        elif issubclass(cls, _BaseModel):
            subpath = 'Model/'
            s, entity_name = self.emit_code_model(cls, mod)
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

    def emit_code_ladder(self, cls, mod):
        _wrp_cls = Wrapped(cls, self)
        s = f"""/* Generated/Data/{cls.__name__}.cs */

namespace {self.namespace}.Generated
{{

public class {cls.__name__}
{{
"""
        s += "}\n\n}"
        return s, cls.__name__

    def emit_code_model(self, cls, mod):
        _wrp_cls = Wrapped(cls, self)
        s = f"""/* Generated/Model/{cls.__name__}.cs */

namespace {self.namespace}.Generated
{{

public class {cls.__name__}
{{
"""
        for fname, fdef in cls.__fields__.items():
            s += f"    public {self.get_cs_type(fdef.outer_type_)} {inflection.camelize(fname)} {{ get; set; }}\n"
        s += "}\n\n}"
        return s, cls.__name__

    def emit_code_data(self, cls, mod):
        _wrp_cls = Wrapped(cls, self)
        s = f"""/* Generated/Data/{cls.__name__}.cs */
using MasterMemory;
using MessagePack;

namespace {self.namespace}.Generated
{{

[MemoryTable("{_wrp_cls.var_name}"), MessagePackObject(true)]  
public class {cls.__name__}
{{
"""
        for fname, fdef in cls.__fields__.items():
            if fname == 'id':
                s += "    [PrimaryKey]\n"
                s += f"    public int Id {{ get; set; }}\n"
            else:
                s += f"    public {self.get_cs_type(fdef.outer_type_)} {inflection.camelize(fname)} {{ get; }}\n"
        s += self.emit_constructor(cls)
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
        s = f"""
namespace {self.namespace}.Generated
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

    def _emit_user_repo(self):
        models_s = ','.join([wrp_cls.var_name_camel for wrp_cls in self._erc721_classes])
        models_x_s = ','.join([f'q => q.{wrp_cls.entity_name_plural}' for wrp_cls in self._erc721_classes])

        s = f"""//
using System;
using System.Data;
using MagicOnion.Server;

using {self.namespace}.Server.DB;
using {self.namespace}.Server.DB.Generated.Models;

namespace {self.namespace}.Server.Repositories
{{

public partial class User
{{
"""
        for wrp_cls in self._erc721_classes:
            s += f"    public List<{wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} {{ get => Model.{wrp_cls.entity_name_plural}; }}\n"
        s += "\n"
        for wrp_cls in self._erc721_classes:
            s += f"""
    public async Task<{wrp_cls.var_name_camel}> AddAsync({wrp_cls.var_name_camel} {wrp_cls.entity_name_us})
    {{
        var tx = ServiceContext.Current.Items["tx"] as IDbTransaction;
        var changes = ServiceContext.Current.Items[nameof(DbChangeSet)] as DbChangeSet;
        //
        {wrp_cls.entity_name_us}.UserId = this.Id;        
        Console.WriteLine($"current tx is {{tx}}");
        await this._db.{wrp_cls.entity_name_plural}.InsertAsync({wrp_cls.entity_name_us}, tx);
        this._model.{wrp_cls.entity_name_plural}.Add({wrp_cls.entity_name_us});
        changes?.Add(this._model);
        return {wrp_cls.entity_name_us};
    }}
"""
        s += f"""
}}

public partial class UserRepository
{{
    private async Task<UserModel> FindByIdAsync(int id)
    {{
        return await _db.Users.FindAsync<{models_s}>(x => x.Id == id, {models_x_s});
    }}
"""
        s += "}\n\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath("Repositories") \
            .joinpath('User.cs')
        self.write_file(out_path, s)

    def _emit_user_model(self):
        s = f"""//
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using MicroOrm.Dapper.Repositories.Attributes;
using MicroOrm.Dapper.Repositories.Attributes.Joins;

namespace {self.namespace}.Server.DB.Generated.Models
{{

[MessagePack.MessagePackObject(true)]
[Table("user_models")]
public class UserModel
{{
    [Key]
    [Identity]
    public int Id {{ get; set; }}

    [Key]
    public byte[] Address {{ get; set; }}

"""
        for wrp_cls in self._erc721_classes:
            s += f'    [LeftJoin("{wrp_cls.var_name_plural}", "Id", "UserId")]\n'
            s += f"    public List<{wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} {{ get; set; }}\n\n"
        s += "}\n\n}"
        out_path = Path(self._server_out_dir)\
            .joinpath("DB") \
            .joinpath('Models') \
            .joinpath('User.cs')
        self.write_file(out_path, s)

    def _emit_db_change_set(self):
        s = f"""//
using System.Data;
using System.Collections.Generic;
using MagicOnion.Server;

using {self.namespace}.Server.Cache;
using {self.namespace}.Server.DB.Generated.Models;

namespace {self.namespace}.Server.DB
{{

public partial class DbChangeSet
{{
    private Dictionary<int, UserModel> _user_models; 
"""
        for wrp_cls in self._erc721_classes:
            s += f"    private Dictionary<int, {wrp_cls.var_name_camel}> _{wrp_cls.var_name_plural};\n"
        s += "\n"
        s += """
    public Dictionary<int, UserModel> Users => _user_models ??
        (_user_models = new Dictionary<int, UserModel>());
"""
        for wrp_cls in self._erc721_classes:
            s += f"""
    public Dictionary<int, {wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} => _{wrp_cls.var_name_plural} ??
        (_{wrp_cls.var_name_plural} = new Dictionary<int, {wrp_cls.var_name_camel}>());
"""
        s += "\n"
        s += f"""
    public void Add(UserModel user_model)
    {{
        Users[user_model.Id] = user_model;
    }}
"""
        #
        for wrp_cls in self._erc721_classes:
            s += f"""
    public void Add({wrp_cls.var_name_camel} {wrp_cls.var_name})
    {{
        {wrp_cls.entity_name_plural}[{wrp_cls.var_name}.Id] = {wrp_cls.var_name};
    }}
"""
        s += f"""
    public async Task FlushCache(UserCache cache)
    {{
        foreach(var u in Users)
        {{
            Console.WriteLine($"flushing user, Id={{u.Value.Id}}");
            await cache.SetAsync(u.Value);
        }}
    }}
"""
        s += f"""
    public async Task FlushDbChanges(DbContext db)
    {{
        var tx = ServiceContext.Current.Items["tx"] as IDbTransaction;
"""
        for wrp_cls in self._erc721_classes:

            s += f"""
        if (_{wrp_cls.var_name_plural} is not null)
        {{
            await db.{wrp_cls.entity_name_plural}.BulkUpdateAsync(_{wrp_cls.var_name_plural}.Values.ToList(), tx);
        }}
"""
        s += f"""
    }}
"""
        s += "}\n\n}"
        out_path = Path(self._server_out_dir)\
            .joinpath("DB") \
            .joinpath('DbChangeSet.cs')
        self.write_file(out_path, s)

    def emit_db_models(self):
        for wrp_cls in self._erc721_classes:
            self._emit_db_model(wrp_cls)

    def _emit_db_model(self, wrp_cls):
        s = f"""//
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using MicroOrm.Dapper.Repositories.Attributes;

namespace {self.namespace}.Server.DB.Generated.Models
{{

[MessagePack.MessagePackObject(true)]
[Table("{wrp_cls.var_name_plural}")]
public class {wrp_cls.var_name_camel}
{{
    [Key]
    [Identity]
    public int Id {{ get; set; }}

    public int UserId {{ get; set; }}

"""
        for fname, fdef in wrp_cls._cls.__fields__.items():
            if fname == 'id':
                continue
            t_origin = typing.get_origin(fdef.outer_type_)
            if t_origin == DataRef:
                s += f"    public long {inflection.camelize(fname)} {{ get; set; }}\n"
            else:
                s += f"    public {self.get_cs_type(fdef.outer_type_)} {inflection.camelize(fname)} {{ get; set; }}\n"
        #
        s += "}\n\n}"
        out_path = Path(self._server_out_dir)\
            .joinpath("DB") \
            .joinpath('Models') \
            .joinpath(f'{wrp_cls.entity_name}.cs')
        self.write_file(out_path, s)

    def _emit_idb_context(self):
        s = f"""//
using MicroOrm.Dapper.Repositories;
using MicroOrm.Dapper.Repositories.DbContext;

using {self.namespace}.Server.DB.Generated.Models;

namespace {self.namespace}.Server.DB
{{

public interface IDbContext : IDapperDbContext
{{
    IDapperRepository<UserModel> Users {{ get; }}
"""
        for wrp_cls in self._erc721_classes:
            s += f"    IDapperRepository<{wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} {{ get; }}\n"
        s += "}\n\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath('DB') \
            .joinpath(f'IDbContext.cs')
        self.write_file(out_path, s)

    def _emit_users_table_create_sql(self):
        s = f"CREATE TABLE IF NOT EXISTS `user_models` (`Id` int not null auto_increment,"
        s += " `Address` varbinary(32) not null,"
        s += " INDEX `Address_Idx` (`Address`),"
        s += " PRIMARY KEY (`Id`));"
        return s

    def _emit_table_create_sql(self, wrp_cls):
        s = f"CREATE TABLE IF NOT EXISTS `{wrp_cls.var_name_plural}` (`Id` int not null auto_increment,"
        s += " `UserId` int not null,"
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

using {self.namespace}.Server.DB.Generated.Models;

namespace {self.namespace}.Server.DB
{{

public partial class DbContext : DapperDbContext, IDbContext
{{

    private void InitDB()
    {{
        Connection.Execute(\"{self._emit_users_table_create_sql()}\");
"""
        for wrp_cls in self._erc721_classes:
            s += f"        Connection.Execute(\"{self._emit_table_create_sql(wrp_cls)}\");\n"
        s += "    }\n\n"
        #
        s += f"    private IDapperRepository<UserModel> _user_models;\n"
        for wrp_cls in self._erc721_classes:
            s += f"    private IDapperRepository<{wrp_cls.var_name_camel}> _{wrp_cls.var_name_plural};\n"
        #
        s += f"""
    public IDapperRepository<UserModel> Users => _user_models ??
        (_user_models = new DapperRepository<UserModel>(Connection, new SqlGenerator<UserModel>(SqlProvider.MySQL)));"""
        #
        for wrp_cls in self._erc721_classes:
            s += f"""
    public IDapperRepository<{wrp_cls.var_name_camel}> {wrp_cls.entity_name_plural} => _{wrp_cls.var_name_plural} ??
        (_{wrp_cls.var_name_plural} = new DapperRepository<{wrp_cls.var_name_camel}>(Connection, new SqlGenerator<{wrp_cls.var_name_camel}>(SqlProvider.MySQL)));"""
        #
        s += "}\n\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath('DB') \
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

namespace {self.namespace}.Server.Services
{{

public partial class GameService
{{
    public async UnaryResult<int> Retire{wrp_cls.entity_name}(long id)
    {{
        return 0;
    }}
"""
        s += "}\n"
        # namespace end
        s += "\n}"
        out_path = Path(self._server_out_dir) \
            .joinpath("Services") \
            .joinpath(f'{wrp_cls.entity_name}Service.cs')
        self.write_file(out_path, s)

    def _emit_model_cheat_services(self):
        for wrp_cls in self._erc721_classes:
            self._emit_model_cheat_service(wrp_cls)

    def _emit_model_cheat_service(self, wrp_cls):
        s = f"""//
using MagicOnion;

using {self.namespace}.Server.Repositories;
using {self.namespace}.Server.DB.Generated.Models;

namespace {self.namespace}.Server.Services
{{

public partial class CheatService
{{
    public async UnaryResult<int> Add{wrp_cls.entity_name}(int userId, int dataId)
    {{
        var {wrp_cls.var_name} = new {wrp_cls.var_name_camel}() 
            {{
                UserId = userId,
                Data = dataId
            }};
        var user = await _userRepo.GetAsync(userId);
        Console.WriteLine($"User cheat: {{user?.Id}}");
        await user.AddAsync({wrp_cls.var_name});
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
using MagicOnion;

namespace {self.namespace}.Shared.Services
{{

public partial interface ICheatService
{{
    public UnaryResult<int> Add{wrp_cls.entity_name}(int userId, int dataId);
"""
        s += "}\n"
        # namespace end
        s += "\n}"
        out_path = Path(self._out_dir) \
            .joinpath("Services") \
            .joinpath("Cheats") \
            .joinpath(f'I{wrp_cls.entity_name}CheatService.cs')
        self.write_file(out_path, s)

    def generate(self):
        super().generate()
        self.emit_visitors()
        self.emit_db_models()
        self._emit_db_change_set()
        self._emit_user_model()
        self._emit_user_repo()
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


