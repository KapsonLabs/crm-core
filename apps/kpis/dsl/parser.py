from .tokens import TokenType
from .ast_nodes import NumberNode, VarNode, BinaryOpNode, FunctionCallNode

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0
        self.current = tokens[0]

    def eat(self, type_):
        if self.current.type == type_:
            self.index += 1
            self.current = self.tokens[self.index]
        else:
            raise Exception(f"Unexpected token {self.current}, expected {type_}")

    def parse(self):
        result = self.expression()
        if self.current.type != TokenType.EOF:
            raise Exception("Extra tokens after expression")
        return result

    def expression(self):
        node = self.term()

        while self.current.type in (
                TokenType.PLUS, TokenType.MINUS,
                TokenType.GT, TokenType.LT,
                TokenType.GTE, TokenType.LTE,
                TokenType.EQ, TokenType.NE
        ):
            op = self.current
            self.eat(op.type)
            node = BinaryOpNode(node, op, self.term())

        return node

    def term(self):
        node = self.factor()

        while self.current.type in (TokenType.MUL, TokenType.DIV):
            op = self.current
            self.eat(op.type)
            node = BinaryOpNode(node, op, self.factor())

        return node

    def factor(self):
        token = self.current

        if token.type == TokenType.NUMBER:
            self.eat(TokenType.NUMBER)
            return NumberNode(token.value)

        if token.type == TokenType.IDENTIFIER:
            name = token.value
            self.eat(TokenType.IDENTIFIER)

            # Function call?
            if self.current.type == TokenType.LPAREN:
                self.eat(TokenType.LPAREN)
                args = []
                if self.current.type != TokenType.RPAREN:
                    args.append(self.expression())
                    while self.current.type == TokenType.COMMA:
                        self.eat(TokenType.COMMA)
                        args.append(self.expression())
                self.eat(TokenType.RPAREN)
                return FunctionCallNode(name, args)

            return VarNode(name)

        if token.type == TokenType.LPAREN:
            self.eat(TokenType.LPAREN)
            expr = self.expression()
            self.eat(TokenType.RPAREN)
            return expr

        raise Exception(f"Unexpected token: {token}")
