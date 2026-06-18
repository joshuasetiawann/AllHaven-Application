"""Safe arithmetic evaluator for the Calculator tool.

Evaluates a basic arithmetic expression (``+ - * / %``, parentheses, decimals,
and unary minus) WITHOUT ``eval``: it parses with ``ast`` and walks a strict
whitelist of nodes, so names, calls, attribute access, and exponentiation
(a DoS vector) are never executed.
"""

from __future__ import annotations

import ast
import operator

_BIN = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class CalcError(ValueError):
    """Raised for empty, malformed, or unsupported expressions."""


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        return _BIN[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    raise CalcError("unsupported expression")


def evaluate(expression: str) -> float:
    """Evaluate a basic arithmetic expression and return a float."""
    expr = (expression or "").strip()
    if not expr:
        raise CalcError("empty expression")
    if len(expr) > 200:
        raise CalcError("expression too long")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise CalcError("invalid expression") from exc
    try:
        return float(_eval(tree.body))
    except ZeroDivisionError as exc:
        raise CalcError("division by zero") from exc
