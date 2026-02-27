from .ast_nodes import NumberNode, VarNode, BinaryOpNode, FunctionCallNode
from .functions import ALLOWED_FUNCTIONS

class Evaluator:
    def __init__(self, context):
        self.context = context  # {"Actual": 50, "Target": 100, "Inputs": [20,30]}

    def eval(self, node):
        if isinstance(node, NumberNode):
            return node.value

        if isinstance(node, VarNode):
            if node.name not in self.context:
                raise Exception(f"Unknown variable '{node.name}'")
            return self.context[node.name]

        if isinstance(node, FunctionCallNode):
            if node.name not in ALLOWED_FUNCTIONS:
                raise Exception(f"Unknown function '{node.name}'")
            func = ALLOWED_FUNCTIONS[node.name]
            args = [self.eval(a) for a in node.args]
            return func(*args)

        if isinstance(node, BinaryOpNode):
            left = self.eval(node.left)
            right = self.eval(node.right)

            op = node.op.type
            if op.name == "PLUS": return left + right
            if op.name == "MINUS": return left - right
            if op.name == "MUL": return left * right
            if op.name == "DIV": return left / right
            if op.name == "GT": return left > right
            if op.name == "LT": return left < right
            if op.name == "GTE": return left >= right
            if op.name == "LTE": return left <= right
            if op.name == "EQ": return left == right
            if op.name == "NE": return left != right

            raise Exception(f"Unsupported operator {node.op}")

        raise Exception("Invalid AST node")
