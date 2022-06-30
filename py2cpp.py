import ast
import sys
import json

includes = []
content = []
last_class = None
classes = []
last_func = None
defined_vars = {}

file_in = sys.argv[1]
file_out = file_in.replace(".py", ".cpp")

with open(file_in) as file:
    in_content = file.read()

module = ast.parse(in_content)
print(ast.dump(module, indent=4))

def add_content(text, indent=4):
    content.append(" " * indent + text)

def add_include(module):
    text = f"#include <{module}>"
    if text not in includes:
        includes.append(text)

def py_type_to_cpp_type(name: ast.Name):
    if name == None:
        return "void"
    if type(name) == ast.Attribute:
        return attribute_to_str(name)
    if name.id == 'str':
        add_include("string")
        return "std::string"
    return name.id

def handle_class(classDef, indent=0):
    global last_class
    global last_func
    print(f"class {classDef.name}")
    last_class = classDef.name
    last_func = None
    classes.append(classDef.name)
    add_content(f"class {classDef.name} {'{'}", indent=indent)
    add_content("public:", indent=indent)
    handle_body(classDef.body, indent=indent+4)
    add_content("};", indent=indent)

def handle_func(functionDef, indent=0):
    global last_func
    print(f"func {functionDef.name}")
    args = []
    for arg in functionDef.args.args:
        if arg.arg == 'self': continue
        args.append(f"{py_type_to_cpp_type(arg.annotation)} {arg.arg}")
    if functionDef.name == "__init__":
        print(f"  constructor for class {last_class}")
        add_content(f"{last_class}({', '.join(args)}) {'{'}")
    else:
        last_func = functionDef.name
        add_content(f"{'void' if functionDef.returns is None else py_type_to_cpp_type(functionDef.returns)} {functionDef.name}({', '.join(args)}) {'{'}", indent=indent)
    handle_body(functionDef.body, indent=indent+4)
    add_content("}", indent=indent)

def handle_print(args):
    add_include("iostream")
    return "std::cout << " + ' << " " << '.join(args) + ' << "\\n"'

def attribute_to_str(attribute):
    is_ptr = False
    value = attribute.value.id
    if value == 'self':
        value = 'this'
        is_ptr = True
    return f"{value}{'->' if is_ptr else '.'}{attribute.attr}"

def constant_to_str(constant):
    return json.dumps(constant.value)

def call_to_str(call):
    func = ""
    if type(call.func) == ast.Attribute:
        func = attribute_to_str(call.func)
    if type(call.func) == ast.Name:
        func = call.func.id
    args = []
    for arg in call.args:
        args.append(node_to_str(arg))
    if func == "print": # simulate a print with cout
        return handle_print(args)
    return f"{func}({', '.join(args)})"

def handle_assign(assign, indent=0):
    for target in assign.targets:
        left_hand = node_to_str(target)
        if last_func is not None:
            if last_func not in defined_vars:
                defined_vars[last_func] = []
            if left_hand not in defined_vars[last_func]:
                if type(assign.value) == ast.Call: # assume this is a constructor
                    left_hand = f"{assign.value.func.id} {left_hand}"
        value = node_to_str(assign.value)
        add_content(f"{left_hand} = {value};", indent=indent)

def handle_if(ifStmt, indent=0):
    global last_func
    if type(ifStmt.test.left) == ast.Name:
        if ifStmt.test.left.id == "__name__" and ifStmt.test.comparators[0].value == "__main__":
            # main func
            print("if statement interpreted as main func")
            last_func = "main"
            add_content("int main() {", indent=indent)
            handle_body(ifStmt.body, indent=indent+4)
            add_content("return 0;", indent=indent+4)
            add_content("}", indent=indent)
            return
    print("dont know how to parse ifs yet")

def handle_expr(expr, indent=0):
    if type(expr.value) == ast.Call:
        add_content(f"{call_to_str(expr.value)};", indent=indent)

def handle_return(ret, indent=0):
    cpp_ret = node_to_str(ret.value)
    add_content(f"return {cpp_ret};", indent=indent)

def node_to_str(node):
    if type(node) == ast.Constant:
        return constant_to_str(node)
    if type(node) == ast.Name:
        return node.id
    if type(node) == ast.Call:
        return call_to_str(node)
    if type(node) == ast.Attribute:
        return attribute_to_str(node)
    if type(node) == ast.BinOp:
        return binop_to_str(node)
    return "unknown node", node

def op_to_str(op):
    match type(op):
        case ast.Add: return "+"
        case _: print("unknown op", op)

def binop_to_str(binop):
    left = node_to_str(binop.left)
    right = node_to_str(binop.right)
    op = op_to_str(binop.op)
    return f"{left} {op} {right}"

def handle_raise(raiseObj, indent=0):
    add_content(f"throw {constant_to_str(raiseObj.exc.args[0])};", indent=indent)

def handle_body(body, indent=0):
    for obj in body:
        match type(obj):
            case ast.ClassDef:
                handle_class(obj, indent=indent)
            case ast.FunctionDef:
                handle_func(obj, indent=indent)
            case ast.Assign:
                handle_assign(obj, indent=indent)
            case ast.AnnAssign:
                add_content(f"{py_type_to_cpp_type(obj.annotation)} {obj.target.id};", indent=indent)
            case ast.If:
                handle_if(obj, indent=indent)
            case ast.Expr:
                handle_expr(obj, indent=indent)
            case ast.Return:
                handle_return(obj, indent=indent)
            case ast.Raise:
                handle_raise(obj, indent=indent)
            case _:
                print("unknown", obj)

handle_body(module.body)

with open(file_out, "w+") as file:
    file.write("\n".join([*includes, *content]))