from flask import Flask, request, jsonify
import sys
import io
import time
import ast
import inspect
from contextlib import redirect_stdout, redirect_stderr
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=['http://localhost:3000', 'https://fantastic-code.vercel.app'])

def normalize_list_str(s):
    """Normalize list string representation by removing spaces and standardizing boolean values."""
    # First normalize spaces and quotes
    s = s.replace(' ', '').replace("'", '"')
    
    # Convert JavaScript/lowercase booleans to Python booleans
    s = s.replace('true', 'True').replace('false', 'False')
    
    return s

def parse_input(input_str):
    """Safely parse the input string containing arbitrary arguments."""
    if not input_str.strip():  # Handle empty input
        return []
        
    try:
        # Convert the string to a valid Python literal
        input_str = f"[{input_str}]"  # Wrap in brackets to make it a valid list
        parsed = ast.literal_eval(input_str)
        
        # If parsed is not a list/tuple, wrap it in a list
        if not isinstance(parsed, (list, tuple)):
            return [parsed]
            
        # If it's a single item in a list that's itself a list/tuple, unwrap it
        if len(parsed) == 1 and isinstance(parsed[0], (list, tuple)):
            return list(parsed[0])
            
        return list(parsed)
    except Exception as e:
        raise ValueError(f"Failed to parse input: {str(e)}")

def execute_code(code, test_cases, func):
    def custom_print(*args, sep=' ', end='\n'):
        """Custom print function to capture printed outputs."""
        print(*args, sep=sep, end=end)
    
    def run_test_case(test_input, output, global_env, func_obj):
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = {
            "stdout": [],
            "yourOutput": None,
            "output": output,
            "stderr": "",
            "error": None,
            "status": "failed"  # Default status
        }

        try:
            # Parse test input
            args = parse_input(test_input)
            
            # Get function signature
            sig = inspect.signature(func_obj)
            param_count = len(sig.parameters)
            
            # Validate argument count if function expects specific number of arguments
            if param_count != len(args) and param_count != 0:
                raise ValueError(f"Function expects {param_count} arguments but got {len(args)}")

            # Execute the main function with test inputs
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result_value = func_obj(*args) if args else func_obj()

            # Get prints from function execution
            function_prints = stdout.getvalue().strip().split('\n') if stdout.getvalue().strip() else []
            
            # Store all prints in stdout
            result["stdout"] = function_prints if function_prints else [""]
            
            # Store function return value separately
            result["yourOutput"] = str(result_value) if result_value is not None else "None"
            result["stderr"] = stderr.getvalue()
            
            # Set status based on output comparison using normalized strings
            if normalize_list_str(result["yourOutput"].strip()) == normalize_list_str(str(output).strip()):
                result["status"] = "passed"
                return result, 1  # Return 1 for passed test
            return result, 0  # Return 0 for failed test

        except Exception as e:
            result["error"] = str(e)
            result["stdout"] = [""]
            result["yourOutput"] = "None"
            return result, 0  # Return 0 for failed test

    if isinstance(__builtins__, dict):
        builtins_dict = __builtins__
    else:  # It's a module
        builtins_dict = vars(__builtins__)
    global_env = {
        "__builtins__": {k: builtins_dict[k] for k in [
            'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
            'chr', 'complex', 'dict', 'divmod', 'enumerate', 'filter', 'float',
            'format', 'frozenset', 'hash', 'hex', 'int', 'isinstance', 'issubclass',
            'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'oct', 'ord',
            'pow', 'range', 'repr', 'reversed', 'round', 'set', 'slice',
            'sorted', 'str', 'sum', 'tuple', 'type', 'zip'
        ]},
        'print': custom_print  # Override print
    }

    # First execute the code to define all functions
    try:
        exec(code, global_env)
        func_obj = global_env.get(func)
        if not func_obj:
            raise NameError(f"Function '{func}' not found in the code")
        if not callable(func_obj):
            raise TypeError(f"'{func}' is not a callable function")
    except Exception as e:
        # If there's an error in function definition, return error for all test cases
        results = [{"error": str(e), "stdout": [""], "yourOutput": "None", 
                   "output": test_case["output"], "stderr": "",
                   "status": "failed"} for test_case in test_cases]
        return results, 0

    # Then run each test case using the same global environment
    results = []
    passed_count = 0
    for test_case in test_cases:
        input_data = test_case['input']
        output = test_case['output']
        result, is_passed = run_test_case(input_data, output, global_env, func_obj)
        results.append(result)
        passed_count += is_passed

    return results, passed_count

@app.route('/python', methods=['POST'])
def execute_python():
    data = request.json
    print(data)
    code = data.get('code', '')
    test_cases = data.get('testCases', [])
    action = data.get('action', 'submit')
    func = data.get('func', '')

    if not code:
        return jsonify({"error": "No code provided"}), 400
    
    start_time = time.time()
    results, passed_test_cases = execute_code(code, test_cases, func)
    end_time = time.time()
    
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    # Check if any test case has an error
    has_error = any(result["error"] is not None for result in results)
    total_test_cases = len(results)

    # Determine status
    if has_error:
        status = "Runtime Error"
    else:
        status = "Accepted" if passed_test_cases == total_test_cases else "Wrong Answer"

    return jsonify({
        "status": status,
        "passedTestCases": passed_test_cases,
        "totalTestCases": total_test_cases,
        "output": results,
        "version": python_version,
        "runtime": round((end_time - start_time) * 1000)
    })

@app.route('/')
def home():
    return "Welcome to the Python Execution API!"

if __name__ == '__main__':
    app.run(debug=True)