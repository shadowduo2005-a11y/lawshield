"""
tools/calculator.py – Safe mathematical expression evaluator for legal computations.
Supports arithmetic, powers, and common math functions (sqrt, log, etc).
"""
from __future__ import annotations

import ast
import math
import operator
from typing import Union

from langchain_core.tools import tool

# ── Safe operator map ─────────────────────────────────────────────────────────
_SAFE_OPERATORS: dict = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Allowed math functions accessible in expressions (e.g. sqrt(144))
_SAFE_FUNCTIONS: dict = {
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
}


def _eval_node(node: ast.AST) -> Union[int, float]:
    """Recursively evaluate an AST node using only safe operations."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_eval_node(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named functions are allowed.")
        func = _SAFE_FUNCTIONS.get(node.func.id)
        if func is None:
            raise ValueError(f"Unsupported function: '{node.func.id}'. Allowed: {list(_SAFE_FUNCTIONS)}")
        args = [_eval_node(arg) for arg in node.args]
        return func(*args)
    raise TypeError(f"Unsupported expression node: {type(node).__name__}")


def eval_expr(expression: str) -> Union[int, float]:
    """Parse and safely evaluate a mathematical expression string."""
    tree = ast.parse(expression.strip(), mode="eval")
    return _eval_node(tree.body)


@tool
def calculate_math(expression: str) -> str:
    """
    Evaluates a mathematical expression safely without using Python's eval().
    Supports: +, -, *, /, //, %, ** and functions: sqrt, log, log10, abs, round, ceil, floor.
    Use this for capital gains tax, percentages, interest calculations, or basic arithmetic.

    Examples:
      '1000 * 0.15'           → capital gains at 15%
      '(500 + 200) / 2'       → average of two values
      'sqrt(144)'             → square root
      '100000 * (1 + 0.07)**5' → compound interest after 5 years at 7%
    """
    try:
        result = eval_expr(expression)
        # Format as integer when there is no fractional part
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(result)
    except (TypeError, ValueError, KeyError, ZeroDivisionError) as e:
        return f"Calculation error for '{expression}': {e}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"Unexpected error evaluating '{expression}': {e}"
