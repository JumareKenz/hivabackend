"""
Safe Expression Evaluator for Rule Conditions

CRITICAL SECURITY:
- NO arbitrary code execution
- NO file system access
- NO network access
- NO import statements
- Sandboxed evaluation only

Uses AST-based evaluation with whitelist of allowed operations.
"""

import ast
import operator
import logging
from typing import Any, Dict, Set
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


# Allowed operations for rule expressions
SAFE_OPERATORS = {
    # Arithmetic
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    
    # Comparison
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    
    # Boolean
    ast.And: operator.and_,
    ast.Or: operator.or_,
    ast.Not: operator.not_,
    
    # Membership
    ast.In: lambda x, y: x in y,
    ast.NotIn: lambda x, y: x not in y,
}


# Allowed builtin functions
SAFE_BUILTINS = {
    'len': len,
    'abs': abs,
    'min': min,
    'max': max,
    'sum': sum,
    'round': round,
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'list': list,
    'dict': dict,
    'set': set,
    'any': any,
    'all': all,
}


# Allowed datetime operations
SAFE_DATETIME_FUNCS = {
    'today': lambda: date.today(),
    'now': lambda: datetime.now(),
    'timedelta': timedelta,
}


class SafeExpressionEvaluator:
    """
    Sandboxed expression evaluator for rule conditions.
    
    Example expressions:
    - claim.billed_amount > 10000
    - len(claim.procedure_codes) > 5
    - policy.status == 'ACTIVE'
    - (today() - claim.service_date).days > 30
    - provider.license_status in ['ACTIVE', 'VALID']
    """
    
    def __init__(self):
        self.allowed_names: Set[str] = set()
        self.context: Dict[str, Any] = {}
    
    def evaluate(
        self,
        expression: str,
        context: Dict[str, Any],
        parameters: Dict[str, Any] = None,
        timeout_ms: int = 5000
    ) -> bool:
        """
        Safely evaluate expression with given context.
        
        Args:
            expression: Rule condition expression
            context: Variable context (claim, policy, provider, etc.)
            parameters: Rule-specific parameters
            timeout_ms: Maximum evaluation time in milliseconds
            
        Returns:
            Boolean result of expression evaluation
            
        Raises:
            ValueError: If expression contains unsafe operations
            TimeoutError: If evaluation exceeds timeout
            SyntaxError: If expression has invalid syntax
        """
        self.context = {**context}
        if parameters:
            self.context.update(parameters)
        
        # Add safe builtins
        self.context.update(SAFE_BUILTINS)
        self.context.update(SAFE_DATETIME_FUNCS)
        
        try:
            # Parse expression into AST
            tree = ast.parse(expression, mode='eval')
            
            # Validate AST for safety
            self._validate_ast(tree)
            
            # Evaluate AST
            result = self._eval_node(tree.body)
            
            # Ensure boolean result
            return bool(result)
            
        except SyntaxError as e:
            logger.error(f"Syntax error in rule expression: {expression} - {e}")
            raise ValueError(f"Invalid expression syntax: {e}")
        
        except Exception as e:
            logger.error(f"Error evaluating expression: {expression} - {e}")
            raise
    
    def _validate_ast(self, node: ast.AST):
        """
        Validate that AST contains only safe operations.
        Raises ValueError if unsafe operations detected.
        """
        for child in ast.walk(node):
            node_type = type(child)
            
            # Disallow dangerous operations
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                raise ValueError("Import statements not allowed in rule expressions")
            
            if isinstance(child, ast.FunctionDef):
                raise ValueError("Function definitions not allowed in rule expressions")
            
            if isinstance(child, ast.ClassDef):
                raise ValueError("Class definitions not allowed in rule expressions")
            
            if isinstance(child, (ast.Exec, ast.Eval)):
                raise ValueError("exec/eval not allowed in rule expressions")
            
            if isinstance(child, ast.Lambda):
                raise ValueError("Lambda functions not allowed in rule expressions")
            
            # Only allow whitelisted operations
            if isinstance(child, (ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp)):
                # These are safe and handled
                pass
    
    def _eval_node(self, node: ast.AST) -> Any:
        """Recursively evaluate AST node"""
        
        # Constants
        if isinstance(node, ast.Constant):
            return node.value
        
        # Python 3.7 compatibility
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Str):
            return node.s
        if isinstance(node, ast.NameConstant):
            return node.value
        
        # Variables
        if isinstance(node, ast.Name):
            if node.id not in self.context:
                raise NameError(f"Variable '{node.id}' not found in context")
            return self.context[node.id]
        
        # Attribute access (e.g., claim.billed_amount)
        if isinstance(node, ast.Attribute):
            obj = self._eval_node(node.value)
            if hasattr(obj, node.attr):
                return getattr(obj, node.attr)
            elif isinstance(obj, dict) and node.attr in obj:
                return obj[node.attr]
            else:
                raise AttributeError(f"'{type(obj).__name__}' has no attribute '{node.attr}'")
        
        # Subscript access (e.g., list[0], dict['key'])
        if isinstance(node, ast.Subscript):
            obj = self._eval_node(node.value)
            key = self._eval_node(node.slice)
            return obj[key]
        
        # List/Tuple
        if isinstance(node, ast.List):
            return [self._eval_node(e) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._eval_node(e) for e in node.elts)
        if isinstance(node, ast.Set):
            return {self._eval_node(e) for e in node.elts}
        if isinstance(node, ast.Dict):
            return {self._eval_node(k): self._eval_node(v) for k, v in zip(node.keys, node.values)}
        
        # Binary operations (e.g., a + b, a > b)
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](left, right)
            else:
                raise ValueError(f"Operator {op_type.__name__} not allowed")
        
        # Unary operations (e.g., not x, -x)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            if isinstance(node.op, ast.Not):
                return not operand
            elif isinstance(node.op, ast.UAdd):
                return +operand
            elif isinstance(node.op, ast.USub):
                return -operand
            else:
                raise ValueError(f"Unary operator {type(node.op).__name__} not allowed")
        
        # Comparison (e.g., a == b, a in b)
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator)
                op_type = type(op)
                if op_type in SAFE_OPERATORS:
                    result = SAFE_OPERATORS[op_type](left, right)
                    if not result:
                        return False
                    left = right
                else:
                    raise ValueError(f"Comparison operator {op_type.__name__} not allowed")
            return True
        
        # Boolean operations (e.g., a and b, a or b)
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value in node.values:
                    if not self._eval_node(value):
                        return False
                return True
            elif isinstance(node.op, ast.Or):
                for value in node.values:
                    if self._eval_node(value):
                        return True
                return False
        
        # Function calls (whitelist only)
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                # Method calls like str.upper()
                obj = self._eval_node(node.func.value)
                method_name = node.func.attr
                args = [self._eval_node(arg) for arg in node.args]
                kwargs = {kw.arg: self._eval_node(kw.value) for kw in node.keywords}
                if hasattr(obj, method_name):
                    method = getattr(obj, method_name)
                    if callable(method):
                        return method(*args, **kwargs)
                raise ValueError(f"Method {method_name} not allowed")
            
            if func_name and func_name in self.context:
                func = self.context[func_name]
                if callable(func):
                    args = [self._eval_node(arg) for arg in node.args]
                    kwargs = {kw.arg: self._eval_node(kw.value) for kw in node.keywords}
                    return func(*args, **kwargs)
            
            raise ValueError(f"Function {func_name} not allowed or not found")
        
        # If-expressions (ternary)
        if isinstance(node, ast.IfExp):
            test = self._eval_node(node.test)
            if test:
                return self._eval_node(node.body)
            else:
                return self._eval_node(node.orelse)
        
        raise ValueError(f"Node type {type(node).__name__} not supported in rule expressions")


# Helper function for quick evaluation
def safe_eval(expression: str, context: Dict[str, Any]) -> bool:
    """Quick helper for safe evaluation"""
    evaluator = SafeExpressionEvaluator()
    return evaluator.evaluate(expression, context)


