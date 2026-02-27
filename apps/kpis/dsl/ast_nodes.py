class NumberNode:
    def __init__(self, value): self.value = value

class VarNode:
    def __init__(self, name): self.name = name

class BinaryOpNode:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

class FunctionCallNode:
    def __init__(self, name, args):
        self.name = name
        self.args = args
