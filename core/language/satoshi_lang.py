#!/usr/bin/env python3
"""
SatoshiLang Interpreter

A blockchain-native programming language interpreter with AI security integration.
"""

import re
import hashlib
from typing import Any, Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod


class TokenType(Enum):
    """Token types for SatoshiLang lexer"""
    # Literals
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    STRING = "STRING"
    TRUE = "TRUE"
    FALSE = "FALSE"
    
    # Keywords
    FN = "fn"
    LET = "let"
    MUT = "mut"
    IF = "if"
    ELSE = "else"
    MATCH = "match"
    FOR = "for"
    WHILE = "while"
    RETURN = "return"
    ASYNC = "async"
    AWAIT = "await"
    CONCURRENT = "concurrent"
    CONTRACT = "contract"
    BLOCK = "block"
    
    # Symbols
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    LBRACKET = "["
    RBRACKET = "]"
    SEMICOLON = ";"
    COLON = ":"
    ARROW = "->"
    FAT_ARROW = "=>"
    COMMA = ","
    DOT = "."
    
    # Operators
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    EQUAL = "="
    DOUBLE_EQUAL = "=="
    NOT_EQUAL = "!="
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="
    AND = "&&"
    OR = "||"
    NOT = "!"
    
    # Special
    IDENTIFIER = "IDENTIFIER"
    EOF = "EOF"
    DECORATOR = "@"


@dataclass
class Token:
    """Represents a lexical token"""
    type: TokenType
    value: str
    line: int
    column: int


class Lexer:
    """Tokenizes SatoshiLang source code"""
    
    KEYWORDS = {
        'fn', 'let', 'mut', 'if', 'else', 'match', 'for', 'while',
        'return', 'async', 'await', 'concurrent', 'contract', 'block',
        'true', 'false', 'struct', 'enum', 'impl', 'type'
    }
    
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.line = 1
        self.column = 1
        self.tokens = []
    
    def tokenize(self) -> List[Token]:
        """Convert source code to tokens"""
        while self.position < len(self.source):
            self._skip_whitespace()
            
            if self.position >= len(self.source):
                break
            
            if self._read_comment():
                continue
            
            if not self._read_token():
                raise SyntaxError(
                    f"Invalid character at {self.line}:{self.column}: "
                    f"{self.source[self.position]}"
                )
        
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens
    
    def _current_char(self) -> Optional[str]:
        """Get current character"""
        if self.position < len(self.source):
            return self.source[self.position]
        return None
    
    def _peek_char(self, offset: int = 1) -> Optional[str]:
        """Peek ahead at character"""
        pos = self.position + offset
        if pos < len(self.source):
            return self.source[pos]
        return None
    
    def _advance(self):
        """Move to next character"""
        if self.position < len(self.source):
            if self.source[self.position] == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.position += 1
    
    def _skip_whitespace(self):
        """Skip whitespace characters"""
        while self._current_char() and self._current_char() in ' \t\n\r':
            self._advance()
    
    def _read_comment(self) -> bool:
        """Read comments"""
        if self._current_char() == '/' and self._peek_char() == '/':
            while self._current_char() and self._current_char() != '\n':
                self._advance()
            return True
        
        if self._current_char() == '/' and self._peek_char() == '*':
            self._advance()  # /
            self._advance()  # *
            while self.position < len(self.source) - 1:
                if self._current_char() == '*' and self._peek_char() == '/':
                    self._advance()  # *
                    self._advance()  # /
                    return True
                self._advance()
            return True
        
        return False
    
    def _read_token(self) -> bool:
        """Read next token"""
        char = self._current_char()
        
        # Decorators
        if char == '@':
            self._add_token(TokenType.DECORATOR, '@')
            self._advance()
            return True
        
        # Numbers
        if char.isdigit():
            return self._read_number()
        
        # Strings
        if char in '"\'':
            return self._read_string()
        
        # Identifiers and keywords
        if char.isalpha() or char == '_':
            return self._read_identifier()
        
        # Operators and symbols
        return self._read_operator()
    
    def _read_number(self) -> bool:
        """Read number token"""
        start = self.position
        
        while self._current_char() and self._current_char().isdigit():
            self._advance()
        
        # Float
        if self._current_char() == '.' and self._peek_char().isdigit():
            self._advance()
            while self._current_char() and self._current_char().isdigit():
                self._advance()
            token_type = TokenType.FLOAT
        else:
            token_type = TokenType.INTEGER
        
        value = self.source[start:self.position]
        self._add_token(token_type, value)
        return True
    
    def _read_string(self) -> bool:
        """Read string token"""
        quote = self._current_char()
        self._advance()  # Skip opening quote
        
        start = self.position
        while self._current_char() and self._current_char() != quote:
            if self._current_char() == '\\':
                self._advance()
            self._advance()
        
        if not self._current_char():
            raise SyntaxError(f"Unterminated string at {self.line}:{self.column}")
        
        value = self.source[start:self.position]
        self._advance()  # Skip closing quote
        
        self._add_token(TokenType.STRING, value)
        return True
    
    def _read_identifier(self) -> bool:
        """Read identifier or keyword token"""
        start = self.position
        
        while self._current_char() and (self._current_char().isalnum() or self._current_char() == '_'):
            self._advance()
        
        value = self.source[start:self.position]
        
        if value in self.KEYWORDS:
            if value == 'true':
                self._add_token(TokenType.TRUE, value)
            elif value == 'false':
                self._add_token(TokenType.FALSE, value)
            else:
                self._add_token(TokenType[value.upper()], value)
        else:
            self._add_token(TokenType.IDENTIFIER, value)
        
        return True
    
    def _read_operator(self) -> bool:
        """Read operator tokens"""
        char = self._current_char()
        
        two_char_ops = {
            '->': TokenType.ARROW,
            '=>': TokenType.FAT_ARROW,
            '==': TokenType.DOUBLE_EQUAL,
            '!=': TokenType.NOT_EQUAL,
            '<=': TokenType.LE,
            '>=': TokenType.GE,
            '&&': TokenType.AND,
            '||': TokenType.OR,
        }
        
        # Check two-character operators
        two_char = char + (self._peek_char() or '')
        if two_char in two_char_ops:
            self._add_token(two_char_ops[two_char], two_char)
            self._advance()
            self._advance()
            return True
        
        # Single character operators
        single_char_ops = {
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
            ';': TokenType.SEMICOLON,
            ':': TokenType.COLON,
            ',': TokenType.COMMA,
            '.': TokenType.DOT,
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.STAR,
            '/': TokenType.SLASH,
            '%': TokenType.PERCENT,
            '=': TokenType.EQUAL,
            '<': TokenType.LT,
            '>': TokenType.GT,
            '!': TokenType.NOT,
        }
        
        if char in single_char_ops:
            self._add_token(single_char_ops[char], char)
            self._advance()
            return True
        
        return False
    
    def _add_token(self, token_type: TokenType, value: str):
        """Add token to list"""
        self.tokens.append(Token(token_type, value, self.line, self.column))


class Parser:
    """Parses tokens into an Abstract Syntax Tree (AST)"""
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.position = 0
    
    def parse(self) -> Dict[str, Any]:
        """Parse tokens into AST"""
        program = {"type": "program", "items": []}
        
        while not self._is_at_end():
            item = self._parse_item()
            if item:
                program["items"].append(item)
        
        return program
    
    def _current_token(self) -> Token:
        """Get current token"""
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return self.tokens[-1]
    
    def _peek_token(self, offset: int = 1) -> Token:
        """Peek ahead at token"""
        pos = self.position + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return self.tokens[-1]
    
    def _advance(self):
        """Move to next token"""
        if not self._is_at_end():
            self.position += 1
    
    def _is_at_end(self) -> bool:
        """Check if at end of tokens"""
        return self._current_token().type == TokenType.EOF
    
    def _parse_item(self) -> Optional[Dict[str, Any]]:
        """Parse top-level item (function, contract, etc.)"""
        # Check for decorators
        decorators = []
        while self._current_token().type == TokenType.DECORATOR:
            self._advance()
            name = self._current_token().value
            self._advance()
            decorators.append(name)
        
        # Parse function
        if self._current_token().type == TokenType.FN:
            return self._parse_function(decorators)
        
        # Parse contract
        if self._current_token().type == TokenType.CONTRACT:
            return self._parse_contract(decorators)
        
        return None
    
    def _parse_function(self, decorators: List[str]) -> Dict[str, Any]:
        """Parse function definition"""
        self._advance()  # Skip 'fn'
        
        name = self._current_token().value
        self._advance()
        
        self._advance()  # Skip '('
        params = []
        while self._current_token().type != TokenType.RPAREN:
            param = self._parse_parameter()
            params.append(param)
            if self._current_token().type == TokenType.COMMA:
                self._advance()
        self._advance()  # Skip ')'
        
        return_type = None
        if self._current_token().type == TokenType.ARROW:
            self._advance()
            return_type = self._current_token().value
            self._advance()
        
        body = self._parse_block()
        
        return {
            "type": "function",
            "name": name,
            "params": params,
            "return_type": return_type,
            "body": body,
            "decorators": decorators
        }
    
    def _parse_parameter(self) -> Dict[str, str]:
        """Parse function parameter"""
        name = self._current_token().value
        self._advance()
        
        self._advance()  # Skip ':'
        param_type = self._current_token().value
        self._advance()
        
        return {"name": name, "type": param_type}
    
    def _parse_block(self) -> List[Dict[str, Any]]:
        """Parse code block"""
        self._advance()  # Skip '{'
        statements = []
        
        while self._current_token().type != TokenType.RBRACE and not self._is_at_end():
            stmt = self._parse_statement()
            if stmt:
                statements.append(stmt)
        
        self._advance()  # Skip '}'
        return statements
    
    def _parse_statement(self) -> Optional[Dict[str, Any]]:
        """Parse statement"""
        if self._current_token().type == TokenType.LET:
            return self._parse_let_statement()
        elif self._current_token().type == TokenType.IF:
            return self._parse_if_statement()
        elif self._current_token().type == TokenType.WHILE:
            return self._parse_while_statement()
        elif self._current_token().type == TokenType.RETURN:
            return self._parse_return_statement()
        else:
            return self._parse_expression_statement()
    
    def _parse_let_statement(self) -> Dict[str, Any]:
        """Parse let statement"""
        self._advance()  # Skip 'let'
        
        name = self._current_token().value
        self._advance()
        
        self._advance()  # Skip '='
        value = self._parse_expression()
        
        if self._current_token().type == TokenType.SEMICOLON:
            self._advance()
        
        return {
            "type": "let",
            "name": name,
            "value": value
        }
    
    def _parse_expression(self) -> Dict[str, Any]:
        """Parse a full expression with binary operator precedence."""
        return self._parse_or()

    def _parse_or(self) -> Dict[str, Any]:
        left = self._parse_and()
        while self._current_token().type == TokenType.OR:
            self._advance()
            right = self._parse_and()
            left = {"type": "binary", "op": "||", "left": left, "right": right}
        return left

    def _parse_and(self) -> Dict[str, Any]:
        left = self._parse_equality()
        while self._current_token().type == TokenType.AND:
            self._advance()
            right = self._parse_equality()
            left = {"type": "binary", "op": "&&", "left": left, "right": right}
        return left

    def _parse_equality(self) -> Dict[str, Any]:
        left = self._parse_comparison()
        while self._current_token().type in (TokenType.DOUBLE_EQUAL, TokenType.NOT_EQUAL):
            op = self._current_token().value
            self._advance()
            right = self._parse_comparison()
            left = {"type": "binary", "op": op, "left": left, "right": right}
        return left

    def _parse_comparison(self) -> Dict[str, Any]:
        left = self._parse_addition()
        while self._current_token().type in (TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE):
            op = self._current_token().value
            self._advance()
            right = self._parse_addition()
            left = {"type": "binary", "op": op, "left": left, "right": right}
        return left

    def _parse_addition(self) -> Dict[str, Any]:
        left = self._parse_multiplication()
        while self._current_token().type in (TokenType.PLUS, TokenType.MINUS):
            op = self._current_token().value
            self._advance()
            right = self._parse_multiplication()
            left = {"type": "binary", "op": op, "left": left, "right": right}
        return left

    def _parse_multiplication(self) -> Dict[str, Any]:
        left = self._parse_unary()
        while self._current_token().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self._current_token().value
            self._advance()
            right = self._parse_unary()
            left = {"type": "binary", "op": op, "left": left, "right": right}
        return left

    def _parse_unary(self) -> Dict[str, Any]:
        if self._current_token().type == TokenType.NOT:
            self._advance()
            operand = self._parse_unary()
            return {"type": "unary", "op": "!", "operand": operand}
        if self._current_token().type == TokenType.MINUS:
            self._advance()
            operand = self._parse_unary()
            return {"type": "unary", "op": "-", "operand": operand}
        return self._parse_primary()

    def _parse_primary(self) -> Dict[str, Any]:
        """Parse primary expressions (literals, identifiers, calls, parens)."""
        token = self._current_token()

        if token.type == TokenType.INTEGER:
            self._advance()
            return {"type": "integer", "value": int(token.value)}

        if token.type == TokenType.FLOAT:
            self._advance()
            return {"type": "float", "value": float(token.value)}

        if token.type == TokenType.STRING:
            self._advance()
            return {"type": "string", "value": token.value}

        if token.type == TokenType.TRUE:
            self._advance()
            return {"type": "boolean", "value": True}

        if token.type == TokenType.FALSE:
            self._advance()
            return {"type": "boolean", "value": False}

        if token.type == TokenType.IDENTIFIER:
            name = token.value
            self._advance()
            # Function call: name(args...)
            if self._current_token().type == TokenType.LPAREN:
                return self._parse_call(name)
            # Field access: name.field (only when followed by an identifier)
            if (self._current_token().type == TokenType.DOT and
                    self._peek_token().type == TokenType.IDENTIFIER):
                self._advance()  # skip '.'
                field = self._current_token().value
                self._advance()
                return {"type": "field_access", "object": name, "field": field}
            return {"type": "identifier", "name": name}

        if token.type == TokenType.LPAREN:
            self._advance()  # skip '('
            expr = self._parse_expression()
            if self._current_token().type == TokenType.RPAREN:
                self._advance()  # skip ')'
            return expr

        # Fallback
        self._advance()
        return {"type": "unknown"}

    def _parse_call(self, name: str) -> Dict[str, Any]:
        """Parse function call: name(arg1, arg2, ...)"""
        self._advance()  # skip '('
        args = []
        while self._current_token().type != TokenType.RPAREN and not self._is_at_end():
            args.append(self._parse_expression())
            if self._current_token().type == TokenType.COMMA:
                self._advance()
        if self._current_token().type == TokenType.RPAREN:
            self._advance()  # skip ')'
        return {"type": "call", "name": name, "args": args}

    def _parse_if_statement(self) -> Dict[str, Any]:
        """Parse if statement"""
        self._advance()  # Skip 'if'
        
        condition = self._parse_expression()
        then_block = self._parse_block()
        else_block = None
        
        if self._current_token().type == TokenType.ELSE:
            self._advance()
            else_block = self._parse_block()
        
        return {
            "type": "if",
            "condition": condition,
            "then": then_block,
            "else": else_block
        }
    
    def _parse_while_statement(self) -> Dict[str, Any]:
        """Parse while loop"""
        self._advance()  # Skip 'while'
        condition = self._parse_expression()
        body = self._parse_block()
        return {"type": "while", "condition": condition, "body": body}

    def _parse_return_statement(self) -> Dict[str, Any]:
        """Parse return statement"""
        self._advance()  # Skip 'return'
        value = None
        
        if self._current_token().type != TokenType.SEMICOLON:
            value = self._parse_expression()
        
        if self._current_token().type == TokenType.SEMICOLON:
            self._advance()
        
        return {"type": "return", "value": value}
    
    def _parse_expression_statement(self) -> Optional[Dict[str, Any]]:
        """Parse expression statement"""
        expr = self._parse_expression()
        
        if self._current_token().type == TokenType.SEMICOLON:
            self._advance()
        
        return expr
    
    def _parse_contract(self, decorators: List[str]) -> Dict[str, Any]:
        """Parse contract definition (simplified)"""
        self._advance()  # Skip 'contract'
        
        name = self._current_token().value
        self._advance()
        
        body = self._parse_block()
        
        return {
            "type": "contract",
            "name": name,
            "body": body,
            "decorators": decorators
        }


class SatoshiLangInterpreter:
    """Interprets SatoshiLang programs"""
    
    def __init__(self):
        self.functions = {}
        self.variables = {}
        self.contracts = {}
    
    def execute(self, source: str) -> Any:
        """Execute SatoshiLang program"""
        # Lexical analysis
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        # Parsing
        parser = Parser(tokens)
        ast = parser.parse()
        
        # Execution
        return self._execute_program(ast)
    
    def _execute_program(self, program: Dict[str, Any]) -> Any:
        """Execute program AST"""
        result = None
        
        for item in program.get("items", []):
            if item["type"] == "function":
                self.functions[item["name"]] = item
            elif item["type"] == "contract":
                self.contracts[item["name"]] = item
        
        return result
    
    def call_function(self, name: str, args: List[Any]) -> Any:
        """Call a function"""
        if name not in self.functions:
            raise RuntimeError(f"Function '{name}' not found")
        
        func = self.functions[name]
        
        # Check for AI monitoring
        if "ai_monitored" in func.get("decorators", []):
            print(f"[AI] Monitoring function call: {name}")
        
        # Check for threat detection
        if "threat_detection" in func.get("decorators", []):
            print(f"[Security] Running threat detection for: {name}")
        
        # Execute function (simplified)
        print(f"Executing function: {name}")
        return None


if __name__ == "__main__":
    # Example program
    program = """
    fn add(a: u32, b: u32) -> u32 {
        let result = a + b;
        result
    }
    
    @ai_monitored
    @threat_detection
    fn transfer(from: Address, to: Address, amount: u64) {
        validate_signature(from);
        update_ledger(from, to, amount);
    }
    """
    
    interpreter = SatoshiLangInterpreter()
    result = interpreter.execute(program)
    print("Program executed successfully!")
