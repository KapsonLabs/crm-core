from enum import Enum, auto

class TokenType(Enum):
    NUMBER = auto()
    IDENTIFIER = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    PLUS = auto()
    MINUS = auto()
    MUL = auto()
    DIV = auto()
    GT = auto()
    LT = auto()
    GTE = auto()
    LTE = auto()
    EQ = auto()
    NE = auto()
    EOF = auto()

class Token:
    def __init__(self, type_, value=None):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type}, {self.value})"
