from .tokens import Token, TokenType

class Tokenizer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.current = text[0] if text else None

    def advance(self):
        self.pos += 1
        self.current = self.text[self.pos] if self.pos < len(self.text) else None

    def skip_spaces(self):
        while self.current and self.current.isspace():
            self.advance()

    def number(self):
        start = self.pos
        while self.current and (self.current.isdigit() or self.current == '.'):
            self.advance()
        return Token(TokenType.NUMBER, float(self.text[start:self.pos]))

    def identifier(self):
        start = self.pos
        while self.current and (self.current.isalnum() or self.current == '_'):
            self.advance()
        return Token(TokenType.IDENTIFIER, self.text[start:self.pos])

    def generate_tokens(self):
        tokens = []
        while self.current:
            if self.current.isspace():
                self.skip_spaces()
                continue

            if self.current.isdigit():
                tokens.append(self.number())
                continue

            if self.current.isalpha():
                tokens.append(self.identifier())
                continue

            # Operators and special tokens (check two-char operators first)
            two_char = self.text[self.pos:self.pos+2] if self.pos + 1 < len(self.text) else None
            if two_char == '>=':
                tokens.append(Token(TokenType.GTE)); self.advance(); self.advance(); continue
            if two_char == '<=':
                tokens.append(Token(TokenType.LTE)); self.advance(); self.advance(); continue
            if two_char == '==':
                tokens.append(Token(TokenType.EQ)); self.advance(); self.advance(); continue
            if two_char == '!=':
                tokens.append(Token(TokenType.NE)); self.advance(); self.advance(); continue

            if self.current == '+': tokens.append(Token(TokenType.PLUS))
            elif self.current == '-': tokens.append(Token(TokenType.MINUS))
            elif self.current == '*': tokens.append(Token(TokenType.MUL))
            elif self.current == '/': tokens.append(Token(TokenType.DIV))
            elif self.current == '>': tokens.append(Token(TokenType.GT))
            elif self.current == '<': tokens.append(Token(TokenType.LT))
            elif self.current == '(': tokens.append(Token(TokenType.LPAREN))
            elif self.current == ')': tokens.append(Token(TokenType.RPAREN))
            elif self.current == ',': tokens.append(Token(TokenType.COMMA))
            else:
                raise Exception(f"Unexpected character: {self.current}")

            self.advance()

        tokens.append(Token(TokenType.EOF))
        return tokens
