import logging
from flask import Flask, render_template, request, jsonify, send_from_directory
# fix the path for libs
import sys
import os
import platform
import base64
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from libs.interpreter_lib import Interpreter
from libs.code_interpreter import CodeInterpreter
from libs.logger import Logger

# Initialize logger
logger = Logger.initialize("logs/interpreter.log")

app = Flask(__name__)
interpreter = None

class InterpreterArgs:
    def __init__(self, model='code-llama', mode='code', lang='python', save_code=False, exec=True, display_code=True, file=None, history=False):
        self.model = model
        self.mode = mode
        self.lang = lang
        self.save_code = save_code
        self.exec = exec
        self.display_code = display_code
        self.file = file
        self.history = history

@app.route('/')
def index():
    logger.info("GUI: Loading index page")
    return render_template('index.html')

@app.route('/get_models', methods=['GET'])
def get_models():
    try:
        logger.info("GUI: Getting available models")
        models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'configs')
        models = []
        for file in os.listdir(models_dir):
            if file.endswith('.config'):
                models.append(file.replace('.config', ''))
        logger.info(f"GUI: Found models: {models}")
        return jsonify({'models': models})
    except Exception as error:
        logger.error(f"GUI: Error getting models: {str(error)}")
        return jsonify({'error': str(error)})

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json()
        logger.info(f"GUI: Received generate request with data: {data}")
        
        if not data:
            logger.error("GUI: No data provided in generate request")
            return jsonify({'error': 'No data provided'})
            
        prompt = data.get('prompt')
        mode = data.get('mode', 'code')
        model = data.get('model', 'code-llama')
        language = data.get('language', 'python')
        
        if not prompt:
            logger.error("GUI: No prompt provided in generate request")
            return jsonify({'error': 'Prompt is required'})
        
        logger.info(f"GUI: Generating code with mode={mode}, model={model}, language={language}")

        global interpreter
        if interpreter is None or interpreter.INTERPRETER_MODEL != model:
            logger.info(f"GUI: Initializing new interpreter with model={model}")
            args = InterpreterArgs(model=model, mode=mode, lang=language)
            interpreter = Interpreter(args)
        
        os_platform = interpreter.utility_manager.get_os_platform()
        os_name = os_platform[0]
        code_snippet = None

        prompt = interpreter.get_mode_prompt(prompt, os_name)
        logger.info("GUI: Generated mode-specific prompt")

        chat_history = []
        response = interpreter.generate_content(
            message=prompt,
            chat_history=chat_history
        )
        logger.info("GUI: Generated content from interpreter")

        start_sep = str(interpreter.config_values.get('start_sep', '```'))
        end_sep = str(interpreter.config_values.get('end_sep', '```'))
        skip_first_line = interpreter.config_values.get('skip_first_line', 'False') == 'True'

        logger.info(f"GUI: Mode: {interpreter.INTERPRETER_MODE} \
            Start separator: {start_sep}, End separator: {end_sep}, Skip first line: {skip_first_line}")

        # Extract the code from the generated output
        code_snippet = interpreter.code_interpreter.extract_code(response, start_sep, end_sep, skip_first_line)
        logger.info("GUI: Extracted code snippet from response")

        return jsonify({'response': code_snippet})
    except Exception as error:
        logger.error(f"GUI: Error in generate endpoint: {str(error)}")
        return jsonify({'error': str(error)})

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.get_json()
        logger.info(f"GUI: Received execute request with data: {data}")
        
        if not data:
            logger.error("GUI: No data provided in execute request")
            return jsonify({'error': 'No data provided'})
            
        code = data.get('code')
        mode = data.get('mode', 'code')
        model = data.get('model', 'code-llama')
        language = data.get('language', 'python')
        execute = data.get('execute', True)
        
        if not code:
            logger.error("GUI: No code provided in execute request")
            return jsonify({'error': 'No code provided'})
        
        logger.info(f"GUI: Executing code with mode={mode}, model={model}, language={language}, execute={execute}")

        global interpreter
        if interpreter is None or interpreter.INTERPRETER_MODEL != model:
            logger.info(f"GUI: Initializing new interpreter with model={model}")
            args = InterpreterArgs(model=model, mode=mode, lang=language, exec=execute)
            interpreter = Interpreter(args)

        interpreter.initialize_mode()
        logger.info("GUI: Initialized interpreter mode")

        os_platform = interpreter.utility_manager.get_os_platform()
        os_name = os_platform[0]
        
        if execute:
            result = interpreter.execute_code(extracted_code=code, os_name=os_name)
            logger.info("GUI: Executed code with interpreter")
            
            if isinstance(result, tuple):
                output, error = result
                if error:
                    logger.error(f"GUI: Error executing code: {error}")
                    return jsonify({'error': error})
                logger.info(f"GUI: Code execution successful, output length: {len(output) if output else 0}")
                
                # Check for special outputs
                special_outputs = []
                output_dir = os.path.join(os.getcwd(), 'output')
                
                # Check for generated files
                if os.path.exists(os.path.join(output_dir, 'graph.png')):
                    special_outputs.append({
                        'type': 'image',
                        'url': '/output/graph.png',
                        'title': 'Graph'
                    })
                    
                if os.path.exists(os.path.join(output_dir, 'chart.png')):
                    special_outputs.append({
                        'type': 'image', 
                        'url': '/output/chart.png',
                        'title': 'Chart'
                    })
                    
                if os.path.exists(os.path.join(output_dir, 'table.html')):
                    with open(os.path.join(output_dir, 'table.html'), 'r') as f:
                        special_outputs.append({
                            'type': 'html',
                            'content': f.read(),
                            'title': 'Table'
                        })
                
                return jsonify({
                    'result': output,
                    'special_outputs': special_outputs
                })
            
            logger.info("GUI: Code execution successful")
            return jsonify({'result': str(result)})
        else:
            logger.info("GUI: Code execution skipped as per request")
            return jsonify({'result': 'Code execution skipped'})
    except Exception as error:
        logger.error(f"GUI: Error in execute endpoint: {str(error)}")
        return jsonify({'error': str(error)})

@app.route('/fix', methods=['POST'])
def fix_code():
    try:
        data = request.get_json()
        logger.info(f"GUI: Received fix request with data: {data}")
        
        if not data:
            logger.error("GUI: No data provided in fix request")
            return jsonify({'error': 'No data provided'})
            
        code:str = data.get('code')
        model: str = data.get('model', 'code-llama')
        mode: str = data.get('mode', 'code')
        language: str = data.get('language', 'python')
        
        if not code:
            logger.error("GUI: No code provided in fix request")
            return jsonify({'error': 'No code provided'})
        
        global interpreter
        if interpreter is None or interpreter.INTERPRETER_MODEL != model:
            logger.info(f"GUI: Initializing new interpreter with model={model}")
            args = InterpreterArgs(model=model, mode=mode, lang=language)
            interpreter = Interpreter(args)

        os_platform = interpreter.utility_manager.get_os_platform()
        os_name = os_platform[0]

        code_output, code_error = interpreter.execute_code(code, os_name)

        if not code_error:
            logger.error("GUI: No error found in code")
            return jsonify({'error': 'No error found in code'})
        
        start_sep = str(interpreter.config_values.get('start_sep', '```'))
        end_sep = str(interpreter.config_values.get('end_sep', '```'))
        skip_first_line = interpreter.config_values.get('skip_first_line', 'False') == 'True'

        fix_prompt = f"Fix the errors in {interpreter.INTERPRETER_LANGUAGE} language.\nCode is \n'{code_output}'\nAnd Error is \n'{code_error}'\n"
        f"give me output only in code and no other text or explanation. And comment in code where you fixed the error.\n"
        
        # Start the LLM Request.
        logger.info(f"Fix Prompt: {fix_prompt}")
        generated_output = interpreter.generate_content(fix_prompt, interpreter.history, config_values=interpreter.config_values, image_file=None)

        # Extract the code from the generated output.
        logger.info(f"Generated output type {type(generated_output)}")
        fixed_code = interpreter.code_interpreter.extract_code(generated_output, start_sep, end_sep, skip_first_line)
        
        logger.info("GUI: Fixed code errors")
        
        return jsonify({'fixed_code': fixed_code})
    except Exception as error:
        logger.error(f"GUI: Error in fix endpoint: {str(error)}")
        return jsonify({'error': str(error)})

@app.route('/save_code', methods=['POST'])
def save_code():
    try:
        data = request.get_json()
        logger.info(f"GUI: Received save request with data: {data}")
        
        if not data:
            logger.error("GUI: No data provided in save request")
            return jsonify({'error': 'No data provided'})
            
        code = data.get('code')
        mode = data.get('mode', 'code')
        language = data.get('language', 'python')
        
        if not code:
            logger.error("GUI: No code provided in save request")
            return jsonify({'error': 'No code provided'})
        
        # Get OS platform
        os_name = platform.system().lower()
        logger.info(f"GUI: Detected OS: {os_name}")
        
        # Define extensions based on mode and OS
        extensions = {
            "script": {
                "darwin": ".applescript",
                "linux": ".sh",
                "windows": ".bat"
            },
            "command": {
                "darwin": ".sh",
                "linux": ".sh",
                "windows": ".bat"
            },
            "code": lambda lang: '.py' if lang == 'python' else '.js'
        }
        
        # Get the appropriate extension
        if mode.lower() in extensions:
            if mode.lower() == "code":
                file_extension = extensions["code"](language)
            else:
                file_extension = extensions[mode.lower()].get(os_name, '.sh')
            logger.info(f"GUI: Using file extension: {file_extension}")
        else:
            error_msg = f"Unsupported mode type: {mode}"
            logger.error(f"GUI: {error_msg}")
            raise ValueError(error_msg)
            
        # Create output directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"GUI: Using output directory: {output_dir}")
        
        # Generate filename with timestamp
        import time
        filename = f"{mode}_{time.strftime('%Y_%m_%d-%H_%M_%S', time.localtime())}{file_extension}"
        filepath = os.path.join(output_dir, filename)
        logger.info(f"GUI: Saving code to: {filepath}")
        
        # Save the code
        with open(filepath, 'w') as f:
            f.write(code)
        
        logger.info(f"GUI: Code saved successfully to {filename}")
        return jsonify({'result': f'Code saved to {filename}'})
    except Exception as error:
        logger.error(f"GUI: Error in save endpoint: {str(error)}")
        return jsonify({'error': str(error)})

@app.route('/install', methods=['POST'])
def install_package():
    try:
        data = request.get_json()
        logger.info(f"GUI: Received install request with data: {data}")
        
        if not data:
            logger.error("GUI: No data provided in install request")
            return jsonify({'error': 'No data provided'})
            
        package_name = data.get('package')
        mode = data.get('mode', 'code')
        model = data.get('model', 'code-llama')
        language = data.get('language', 'python')
        
        if not package_name:
            logger.error("GUI: No package name provided in install request")
            return jsonify({'error': 'Package name is required'})
        
        logger.info(f"GUI: Installing package {package_name} with mode={mode}, model={model}, language={language}")

        global interpreter
        if interpreter is None or interpreter.INTERPRETER_MODEL != model:
            logger.info(f"GUI: Initializing new interpreter with model={model}")
            args = InterpreterArgs(model=model, mode=mode, lang=language)
            interpreter = Interpreter(args)
        
        # Skip system modules check
        system_modules = interpreter.package_manager.get_system_modules()
        if package_name in system_modules:
            logger.error(f"GUI: Package {package_name} is a system module")
            return jsonify({'error': f"Package {package_name} is a system module"})
            
        # Install the package
        interpreter.package_manager.install_package(package_name, language)
        logger.info(f"GUI: Package {package_name} installed successfully")
        
        return jsonify({'result': f'Package {package_name} installed successfully'})
    except Exception as error:
        logger.error(f"GUI: Error in install endpoint: {str(error)}")
        return jsonify({'error': str(error)})

@app.route('/output/<path:filename>')
def serve_output(filename):
    return send_from_directory('output', filename)

if __name__ == '__main__':
    try:
        # Run app without debug mode to avoid signal handler issues
        app.run(host='0.0.0.0', port=8080)
    except ValueError as error:
        if "signal only works" in str(error):
            # Run without signal handlers if we get signal error
            logger.warning("Running without signal handlers due to threading restrictions")
            app.run(host='0.0.0.0', port=8080, use_reloader=False)
        else:
            raise
    except Exception as error:
        logger.error(f"Error starting Flask app: {error}")
        raise
