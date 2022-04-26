
class Expr(object):
    pass


class RefExpr(Expr):
    def __init__(self, name):
        super(RefExpr, self).__init__()
        self.name = name


class ConstExpr(Expr):
    def __init__(self, val):
        super(ConstExpr, self).__init__()
        self.val = val


class StrConstExpr(ConstExpr):
    def __init__(self, *args):
        super(StrConstExpr, self).__init__(*args)


class IntConstExpr(ConstExpr):
    def __init__(self, *args):
        super(IntConstExpr, self).__init__(*args)


class BoolConstExpr(ConstExpr):
    def __init__(self, *args):
        super(BoolConstExpr, self).__init__(*args)


class BinOpExpr(Expr):
    def __init__(self, *args):
        super(Expr, self).__init__()
        self.a = args[0]
        self.b = args[1]


class EQExpr(BinOpExpr):
    pass


class NEExpr(BinOpExpr):
    pass


class LTExpr(BinOpExpr):
    pass


class GTExpr(BinOpExpr):
    pass


class LTEExpr(BinOpExpr):
    pass


class GTEExpr(BinOpExpr):
    pass


class AddExpr(BinOpExpr):
    pass


class SubExpr(BinOpExpr):
    pass


class MulExpr(BinOpExpr):
    pass


class DivExpr(BinOpExpr):
    pass


class LogicalAndExpr(BinOpExpr):
    pass


class LogicalOrExpr(BinOpExpr):
    pass


class OrExpr(BinOpExpr):
    pass


class XorExpr(BinOpExpr):
    pass


class AndExpr(BinOpExpr):
    pass


class LSRExpr(BinOpExpr):
    pass


class LSLExpr(BinOpExpr):
    pass
