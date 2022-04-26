from acrpg.model.expr import *

import pyparsing as pp


def operator_operands(tokens):
    it = iter(tokens)
    while 1:
        try:
            yield (next(it), next(it))
        except StopIteration:
            break


class OpBuilder(object):
    _ops = {}

    def __init__(self, tokens):
        self.value = tokens[0]

    def _eval(self, v):
        if isinstance(v, OpBuilder):
            return v.eval()
        return v

    def eval(self):
        val1 = self._eval(self.value[0])
        for op, val in operator_operands(self.value[1:]):
            op_cls = type(self)._ops[op]
            val2 = self._eval(val)
            val1 = op_cls(val1, val2)
        return val1


class FCallBuilder(object):
    def __init__(self, tokens):
        print(tokens)
        self.value = tokens[0]

    def eval(self):
        print("zzz", self.value)


class NegOpBuilder(OpBuilder):
    def eval(self):
        pass


class LogicalAndOpBuilder(OpBuilder):
    _ops = {
        '&&': LogicalAndExpr
    }


class LogicalOrOpBuilder(OpBuilder):
    _ops = {
        '||': LogicalOrExpr
    }


class BitwiseOrOpBuilder(OpBuilder):
    _ops = {
        '|': OrExpr
    }


class BitwiseAndOpBuilder(OpBuilder):
    _ops = {
        '&': AndExpr
    }


class BitwiseXorOpBuilder(OpBuilder):
    _ops = {
        '^': XorExpr
    }


class AddSubOpBuilder(OpBuilder):
    _ops = {
        "+": AddExpr,
        "-": SubExpr,
    }


class MulOpBuilder(OpBuilder):
    _ops = {
        "*": MulExpr,
        "/": DivExpr,
    }


class ShiftOpBuilder(OpBuilder):
    _ops = {
        ">>": LSRExpr,
        "<<": LSLExpr,
    }


class CompOpBuilder(OpBuilder):
    _ops = {
        "<": LTExpr,
        "<=": LTEExpr,
        ">": GTExpr,
        ">=": GTEExpr,
        "!=": NEExpr,
        "==": EQExpr,
    }


ppc = pp.pyparsing_common
pp.ParserElement.enablePackrat()

LBRACK, RBRACK, LBRACE, RBRACE, LPAR, RPAR, EQ, COMMA, SEMI, COLON = map(
    pp.Suppress, "[]{}()=,;:"
)

keywords = {
    k.upper(): pp.Keyword(k)
    for k in """\
    false true
    """.split()
}

vars().update(keywords)
any_keyword = pp.MatchFirst(keywords.values()).setName("<keyword>")

FALSE.setParseAction(lambda ts: BoolConstExpr(False))
TRUE.setParseAction(lambda ts: BoolConstExpr(True))

comment_intro = pp.Literal("//")
short_comment = comment_intro + pp.restOfLine

ident = ~any_keyword + ppc.identifier

name = pp.delimitedList(ident, delim=".", combine=True)
name.setParseAction(lambda ts: RefExpr(ts[0]))

number = ppc.number
number.setParseAction(lambda ts: IntConstExpr(ts[0]))

string = pp.QuotedString('"')
string.setParseAction(lambda ts: StrConstExpr(ts[0]))

exp = pp.Forward()

explist1 = pp.delimitedList(exp)

args = LPAR + pp.Optional(explist1) + RPAR

functioncall = name + args
functioncall.setParseAction(FCallBuilder)

var = pp.Forward()
var_atom = functioncall | name | LPAR + exp + RPAR
index_ref = pp.Group(LBRACK + exp + RBRACK)
var <<= pp.delimitedList(pp.Group(var_atom + index_ref) | var_atom, delim=".")

exp_atom = (
    FALSE
    | TRUE
    | number
    | string
    | functioncall
    | var  # prefixexp
)

exp <<= pp.infixNotation(
    exp_atom,
    [
        (pp.oneOf("! - ~"), 1, pp.opAssoc.RIGHT),
        (pp.oneOf("* /"), 2, pp.opAssoc.LEFT, MulOpBuilder),
        (pp.oneOf("+ -"), 2, pp.opAssoc.LEFT, AddSubOpBuilder),
        (pp.oneOf("<< >>"), 2, pp.opAssoc.LEFT, ShiftOpBuilder),
        ("&", 2, pp.opAssoc.LEFT, BitwiseAndOpBuilder),
        ("^", 2, pp.opAssoc.LEFT, BitwiseXorOpBuilder),
        ("|", 2, pp.opAssoc.LEFT, BitwiseOrOpBuilder),
        (pp.oneOf("< > <= >= != =="), 2, pp.opAssoc.LEFT, CompOpBuilder),
        ("&&", 2, pp.opAssoc.LEFT, LogicalAndOpBuilder),
        ("||", 2, pp.opAssoc.LEFT, LogicalOrOpBuilder),
    ],
)
