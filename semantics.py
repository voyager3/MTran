# TODO: ! add support for void functions !
# TODO: override __repr__ everywhere properly instead of node_type => remove 'type'?
# TODO: split into multiple files
# TODO: get rid of 'name' in Variable?

class Node(object):
    def __init__(self, lineno, node_type):
        self.type = node_type
        self.lineno = lineno
        self.parent = None
        self._children = []

    def add_child(self, child):
        self._children.append(child)
        child.parent = self

    def add_children(self, children):
        for child in children:
            self.add_child(child)

    # TODO: incapsulate scopes traversal
    def getvar(self, name):
        node = self
        while node is not None:
            if isinstance(node, ScopeNode) and name in node.scope:
                value = self._getvar(node.scope, name)
                return value
            node = node.parent
        raise UndeclaredVariableError(name, self.lineno)

    def iterchildren(self):
        for child in self._children:
            yield child

    def _getvar(self, scope, name):
        value = scope[name]
        if value is not None:
            return value
        return UndefinedValue()

    def __repr__(self):
        return 'Node({})'.format(self.type)


# Control flow nodes


class LanguageItemNode(Node):
    TYPES = ['boolean', 'number', 'string', 'any']

    def ensure_func_types(self, func):
        self.ensure_type(func.return_type)
        for param in func.params:
            self.ensure_type(param.type)

    def ensure_type(self, type_name):
        if type_name in self.TYPES:
            return
        var = self.getvar(type_name)
        if not isinstance(var.value, ClassValue):
            raise UndeclaredClassError(type_name, self.lineno)

    def run(self):
        raise NotImplementedError()

    def setvar(self, name, value):
        node = self
        while node is not None:
            if isinstance(node, ScopeNode):
                node.scope[name] = value
                return
            node = node.parent


class ScopeNode(LanguageItemNode):
    def __init__(self, lineno, statements):
        super(ScopeNode, self).__init__(lineno, 'block')
        self.scope = {}
        self._this = None
        self.add_children(statements)

    def get_this(self):
        if self._this is not None:
            return self._this
        return UndefinedValue()

    def run(self):
        for child in self._children:
            child.run()

    def set_this(self, this):
        self._this = this

    def update_scope(self, scope):
        self.scope.update(scope)


class ExpressionStatementNode(LanguageItemNode):
    def __init__(self, lineno, expression):
        super(ExpressionStatementNode, self).__init__(lineno, 'expression statement')
        self.add_child(expression)

    def run(self):
        self._children[0].calculate()


class VariableAssignmentNode(LanguageItemNode):
    def __init__(self, lineno, name, expression):
        super(VariableAssignmentNode, self).__init__(lineno, 'variable assignment')
        self._name = name
        self.add_child(expression)

    def run(self):
        value = self._children[0].calculate()
        var = self.getvar(self._name)
        typecheck(self.lineno, self._name, value, var.type)
        var.value = value


class DeclaredVariableAssignmentNode(VariableAssignmentNode):
    def __init__(self, lineno, var_decl, expression):
        name = var_decl.var.name
        super(DeclaredVariableAssignmentNode, self).__init__(lineno, name, expression)
        self.add_child(var_decl)

    def run(self):
        self._children[1].run()
        super(DeclaredVariableAssignmentNode, self).run()


class MemberAssignmentNode(LanguageItemNode):
    def __init__(self, lineno, member_node, expression):
        super(MemberAssignmentNode, self).__init__(lineno, 'member assignment')
        self.add_child(member_node)
        self.add_child(expression)

    def run(self):
        member_node = self._children[0]
        member_node_child = next(iter(member_node.iterchildren()))
        obj = member_node_child.calculate().obj(self.lineno)
        obj.set_member(self.lineno, member_node.name, self._children[1].calculate())


class FunctionDeclarationNode(LanguageItemNode):
    def __init__(self, lineno, func):
        super(FunctionDeclarationNode, self).__init__(lineno, 'function declaration')
        self.func = func

    def run(self):
        name = self.func.name
        func_type = self.func.gettype()
        var = Variable(name, func_type, self.func)
        self.setvar(name, var)


class ReturnNode(LanguageItemNode):
    def __init__(self, lineno, expression):
        super(ReturnNode, self).__init__(lineno, 'return statement')
        self.add_child(expression)

    def run(self):
        # TODO: check if both in function and not in contstructor
        result = self._children[0].calculate()
        raise _Return(result)


class ClassDeclarationNode(LanguageItemNode):
    def __init__(self, lineno, name, members):
        super(ClassDeclarationNode, self).__init__(lineno, 'class declaration')
        self.cls = ClassValue(lineno, name, members)
        self._name = name

    def run(self):
        self._ensure_class_types()
        class_type = self.cls.gettype()
        var = Variable(self._name, class_type, self.cls)
        self.setvar(self._name, var)

    def _ensure_class_types(self):
        for member in self.cls.members:
            if isinstance(member, FunctionValue):
                if not member.name == 'constructor':
                    self.ensure_func_types(member)
            else:
                self.ensure_type(member.type)


class PrintNode(LanguageItemNode):
    def __init__(self, lineno, expression):
        super(PrintNode, self).__init__(lineno, 'print statement')
        self.add_child(expression)

    def run(self):
        print self._children[0].calculate().str()


class IfNode(LanguageItemNode):
    def __init__(self, lineno, condition, block):
        super(IfNode, self).__init__(lineno, 'if statement')
        self.add_child(condition)
        self.add_child(block)

    def add_else(self, block):
        if len(self._children) == 2:
            self.add_child(block)
        else:
            raise Exception("Trying to add 'else' block when it already exists")

    def run(self):
        if self._children[0].calculate().bool():
            self._children[1].run()
        else:
            if len(self._children) == 3:
                self._children[2].run()


class WhileLoopNode(LanguageItemNode):
    def __init__(self, lineno, condition, block):
        super(WhileLoopNode, self).__init__(lineno, 'while loop')
        self.add_child(condition)
        self.add_child(block)

    def run(self):
        while self._children[0].calculate().bool():
            self._children[1].run()


class VariableDeclarationNode(LanguageItemNode):
    def __init__(self, lineno, var):
        super(VariableDeclarationNode, self).__init__(lineno, 'variable declaration')
        self.var = var

    def run(self):
        self.ensure_type(self.var.type)
        self.setvar(self.var.name, self.var)


# Expression nodes


class ExpressionNode(Node):
    def calculate(self):
        raise NotImplementedError()


class PrimitiveValueExpression(ExpressionNode):
    def __init__(self, lineno, value):
        super(PrimitiveValueExpression, self).__init__(lineno, 'primitive value')
        self._value = value

    def calculate(self):
        return self._value


class VariableExpression(ExpressionNode):
    def __init__(self, lineno, name):
        super(VariableExpression, self).__init__(lineno, 'variable')
        self._name = name

    def calculate(self):
        return self.getvar(self._name).value

    # def __repr__(self):
        # return 'variable {}'.format(self._name)


class NegateExpression(ExpressionNode):
    def __init__(self, lineno, expression):
        super(NegateExpression, self).__init__(lineno, 'boolean negation')
        self.add_child(expression)

    def calculate(self):
        value = self._children[0].calculate()
        bool_result = not value.bool()
        return BooleanValue(bool_result)


class BinaryOperationExpression(ExpressionNode):
    # TODO: avoid checking for sign in all operations
    def __init__(self, lineno, op, left, right):
        super(BinaryOperationExpression, self).__init__(lineno, op)
        self._op = op
        self.add_child(left)
        self.add_child(right)

    def _bool_values(self):
        lvalue = self._children[0].calculate().bool()
        rvalue = self._children[1].calculate().bool()
        return lvalue, rvalue

    def _num_values(self):
        lvalue = self._children[0].calculate().num()
        rvalue = self._children[1].calculate().num()
        return lvalue, rvalue


class BooleanOperationExpression(BinaryOperationExpression):
    def calculate(self):
        lvalue, rvalue = self._bool_values()
        if self._op == '&&':
            result = lvalue and rvalue
        elif self._op == '||':
            result = lvalue or rvalue
        return BooleanValue(result)


class ArithmeticOperationExpression(BinaryOperationExpression):
    # TODO: add support for '+' as string concatenation
    def calculate(self):
        lvalue, rvalue = self._num_values()
        if self._op == '+':
            result = lvalue + rvalue
        elif self._op == '-':
            result = lvalue - rvalue
        elif self._op == '*':
            result = lvalue * rvalue
        elif self._op == '/':
            try:
                result = lvalue / rvalue
            except ZeroDivisionError:
                raise DivisionByZeroError(self.lineno)
        return NumberValue(result)


class ComparisonExpression(BinaryOperationExpression):
    def calculate(self):
        # TODO: make equality comparison work not only for numbers
        lvalue, rvalue = self._num_values()
        if self._op == '<':
            result = lvalue < rvalue
        elif self._op == '>':
            result = lvalue > rvalue
        elif self._op == '<=':
            result = lvalue <= rvalue
        elif self._op == '>=':
            result = lvalue >= rvalue
        elif self._op == '===':
            result = lvalue == rvalue
        elif self._op == '!==':
            result = lvalue != rvalue
        return BooleanValue(result)


class NegativeExpression(ExpressionNode):
    def __init__(self, lineno, expression):
        super(NegateExpression, self).__init__(lineno, 'negation')
        self.add_child(expression)

    def calculate(self):
        value = self._children[0].calculate()
        num_result = -value.num()
        return NumberValue(num_result)


class MemberAccessExpression(ExpressionNode):
    def __init__(self, lineno, operand, name):
        super(MemberAccessExpression, self).__init__(lineno, 'member access')
        self.add_child(operand)
        self.name = name
        self.obj = None

    def calculate(self):
        value = self._children[0].calculate()
        self.obj = value.obj(self.lineno)
        return self.obj.get_member(self.name).value


class FunctionCallExpression(ExpressionNode):
    def __init__(self, lineno, operand, params):
        super(FunctionCallExpression, self).__init__(lineno, 'function call')
        self.add_child(operand)
        self.add_children(params)

    def calculate(self):
        func = self._get_func()
        this = self._get_this()
        values = [child.calculate() for child in self._children[1:]]
        return func.call(values, self.lineno, this)

    def _get_func(self):
        func = self._children[0].calculate().obj(self.lineno)
        if not isinstance(func, FunctionValue):
            raise NotAFunctionError(func, self.lineno)
        return func

    def _get_this(self):
        this = None
        if isinstance(self._children[0], MemberAccessExpression):
            this = self._children[0].obj
        return this


class NewInstanceExpression(ExpressionNode):
    # TODO: extract common parts with FunctionCallExpression
    def __init__(self, lineno, name, params):
        super(NewInstanceExpression, self).__init__(lineno, 'new instance')
        self._name = name
        self.add_children(params)

    def calculate(self):
        cls = self.getvar(self._name).value
        if not isinstance(cls, ClassValue):
            raise NotAClassError(self._name, self.lineno)
        params = [child.calculate() for child in self._children]
        return cls.instantiate(params, self.lineno)


class ThisExpression(ExpressionNode):
    def __init__(self, lineno):
        super(ThisExpression, self).__init__(lineno, 'this')

    def calculate(self):
        node = self.parent
        while node is not None:
            if isinstance(node, ScopeNode):
                return node.get_this()
            node = node.parent


# Values


class LanguageValue(object):
    # TODO: supply lineno for all methods
    def bool(self):
        raise NotImplementedError()

    def num(self):
        raise NotImplementedError()

    def obj(self, lineno):
        # TODO: add wrappers for primitives
        raise NotImplementedError()

    def str(self):
        raise NotImplementedError()

    def __repr__(self):
        return self.str()


class LanguageContainerValue(LanguageValue):
    def __init__(self, value):
        self.value = value

    def bool(self):
        return bool(self.value)

    def str(self):
        return str(self.value)


class BooleanValue(LanguageContainerValue):
    def bool(self):
        return self.value

    def num(self):
        if self.value:
            return 1
        return 0

    def str(self):
        if self.value:
            return 'true'
        return 'false'


class NumberValue(LanguageContainerValue):
    def num(self):
        return self.value


class StringValue(LanguageContainerValue):
    def num(self):
        try:
            return float(self.value)
        except ValueError:
            return 0

    def str(self):
        return self.value


class ObjectValue(LanguageContainerValue):
    def __init__(self, lineno, cls, params):
        members = {var.name : var for var in params}
        super(ObjectValue, self).__init__(members)
        self.lineno = lineno
        self.cls = cls

    def bool(self):
        return True

    def gettype(self):
        return 'object'

    def num(self):
        return 0

    def obj(self, lineno):
        return self

    def str(self):
        return str(self.value)

    # TODO: supply lineno
    def get_member(self, name):
        if name in self.value:
            return self.value[name]
        if self.cls is not None and name in self.cls.value:
            return self.cls.get_member(name)
        return UndefinedValue()

    def set_member(self, lineno, name, value):
        var = self.value.get(name)
        if var is None:
            cls_name = self.cls.name if self.cls is not None else 'None'
            # TODO: supply correct line number
            raise NoMemberError(cls_name, name, lineno)
        typecheck(self.lineno, name, value, var.type)
        var.value = value

    def __iter__(self):
        for name, var in self.value.iteritems():
            yield var
        if self.cls is not None:
            for member in self.cls:
                yield member


class FunctionValue(ObjectValue):
    def __init__(self, lineno, name, params, return_type, block):
        super(FunctionValue, self).__init__(lineno, None, [])
        # TODO: support for checking return types
        if not isinstance(block, ScopeNode):
            raise Exception('You must pass a block to a function value')
        self.name = name
        self.params = params
        self.return_type = return_type
        self.block = block

    def call(self, values, lineno, this=None):
        self._check_values(values)
        try:
            self._run(values, this)
        except _Return as r:
            return r.value
        return UndefinedValue()

    def gettype(self):
        # TODO: also specify params and return type
        return 'function'

    def str(self):
        return self.gettype()

    def _check_values(self, values):
        if len(values) != len(self.params):
            raise ParameterNumberError(
                self.name, len(self.params), len(values), self.lineno
            )
        for value, param in zip(values, self.params):
            typecheck(self.lineno, param.name, value, param.type)

    def _run(self, values, this):
        scope = {}
        for value, param in zip(values, self.params):
            var = Variable(param.name, param.type, value)
            scope[param.name] = var
        self.block.update_scope(scope)
        self.block.set_this(this)
        self.block.run()


class ClassValue(ObjectValue):
    def __init__(self, lineno, name, members):
        super(ClassValue, self).__init__(lineno, None, [])
        self.name = name
        self.members = members
        self._fields = [m for m in members if isinstance(m, Variable)]
        self._methods = [m for m in members if isinstance(m, FunctionValue)]
        self._constructor = None
        self._register_methods()

    def gettype(self):
        # TODO: specify
        return 'class'

    def instantiate(self, values, lineno):
        result = self._instantiate(lineno)
        self._constructor.call(values, lineno, result)
        return result

    def _instantiate(self, lineno):
        params = []
        for param in self._fields:
            var = Variable(param.name, param.type)
            params.append(var)
        obj = ObjectValue(lineno, self, params)
        return obj

    def _register_methods(self):
        for method in self._methods:
            # TODO: avoid using the keyword directly
            if method.name == 'constructor':
                self._register_constructor(method)
            else:
                var = Variable(method.name, method.gettype(), method)
                self[method.name] = var
        self._try_add_constructor()

    def _register_constructor(self, method):
        if self._constructor is not None:
            raise MultipleConstructorsError(self.name, self.lineno)
        self._constructor = method

    def _try_add_constructor(self):
        if self._constructor is None:
            block = ScopeNode(self.lineno, [])
            self._constructor = FunctionValue(
                self.lineno, 'constructor', [], None, block
            )


class NullValue(LanguageValue):
    # TODO: make a singleton
    def bool(self):
        return False

    def num(self):
        return 0

    def obj(self, lineno):
        raise CastError(self, 'object', lineno)

    def str(self):
        return 'null'


class UndefinedValue(LanguageValue):
    # TODO: make a singleton
    def bool(self):
        return False

    def num(self):
        return float('nan')

    def obj(self, lineno):
        raise CastError(self, 'object', lineno)

    def str(self):
        return 'undefined'


# Auxiliary objects


_VALUE_TYPE_MAP = {
    NumberValue: 'number',
    StringValue: 'string',
    BooleanValue: 'boolean',
}


def typecheck(lineno, name, value, var_type):
    if isinstance(value, NullValue) or isinstance(value, UndefinedValue):
        return
    cur_type = type(value)
    if cur_type in _VALUE_TYPE_MAP:
        if var_type == _VALUE_TYPE_MAP[cur_type]:
            return
    else:
        cls_name = value.cls.name
        if cls_name == var_type:
            return
    raise TypeMismatchError(name, value, var_type, lineno)


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class Variable(object):
    def __init__(self, name, var_type, value=None):
        self.name = name
        self.type = var_type
        self.value = value if value is not None else UndefinedValue()

    def __repr__(self):
        return 'Variable({}, {}, {})'.format(self.name, self.type, self.value)


# Errors


# TODO: make lineno first parameter


class SemanticError(Exception):
    def __init__(self, msg, lineno):
        msg = 'Semantic error on or before line {}: {}'.format(lineno, msg)
        super(SemanticError, self).__init__(msg)


class NotAFunctionError(SemanticError):
    def __init__(self, value, lineno):
        msg = '{} is not a function'.format(value)
        super(NotAFunctionError, self).__init__(msg, lineno)


class NotAClassError(SemanticError):
    def __init__(self, name, lineno):
        msg = '{} is not a class'.format(name)
        super(NotAClassError, self).__init__(msg, lineno)


class CastError(SemanticError):
    def __init__(self, value, value_type, lineno):
        msg = 'cannot cast {} to {}'.format(value, value_type)
        super(CastError, self).__init__(msg, lineno)


class UndeclaredVariableError(SemanticError):
    def __init__(self, name, lineno):
        msg = 'operation with undeclared variable "{}"'.format(name)
        super(UndeclaredVariableError, self).__init__(msg, lineno)


class MultipleConstructorsError(SemanticError):
    def __init__(self, cls_name, lineno):
        msg = 'multiple constructors in class {}'.format(cls_name)
        super(UndeclaredVariableError, self).__init__(msg, lineno)


class NoMemberError(SemanticError):
    def __init__(self, cls_name, member_name, lineno):
        msg = 'instance of class {} has no member {}'.format(cls_name, member_name)
        super(NoMemberError, self).__init__(msg, lineno)


class UndeclaredClassError(SemanticError):
    def __init__(self, name, lineno):
        msg = 'specifying undeclared class "{}"'.format(name)
        super(UndeclaredVariableError, self).__init__(msg, lineno)


class TypeMismatchError(SemanticError):
    def __init__(self, name, value, var_type, lineno):
        msg = 'variable {} must be of type {}, got {}'.format(name, var_type, value)
        super(TypeMismatchError, self).__init__(msg, lineno)


class ParameterNumberError(SemanticError):
    def __init__(self, func_name, expected, got, lineno):
        msg = 'invalid number of parameters for function {}: expected {}, got {}'.format(
            func_name, expected, got
        )
        super(ParameterNumberError, self).__init__(msg, lineno)


class DivisionByZeroError(SemanticError):
    def __init__(self, lineno):
        msg = 'zero division'
        super(DivisionByZeroError, self).__init__(msg, lineno)
