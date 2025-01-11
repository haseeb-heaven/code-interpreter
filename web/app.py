from flask import Flask, render_template, request, jsonify
# fix the path for libs
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from libs.interpreter_lib import Interpreter
from libs.code_interpreter import CodeInterpreter
import os
import json
self.logger = Logger.initialize("logs/interpreter.log")
app = Flask(__name__)
interpreter = None

class InterpreterArgs:
    def __init__(self, model='code-llama', mode='code', lang='python', save_code=False, exec=False, display_code=True, file=None, history=False):
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
    return render_template('index.html')

@app.route('/get_models', methods=['GET'])
def get_models():
    try:
        models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'configs')
        models = []
        for file in os.listdir(models_dir):
            if file.endswith('.config'):
                models.append(file.replace('.config', ''))
        return jsonify({'models': models})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'})
            
        prompt = data.get('prompt')
        mode = data.get('mode', 'code')
        model = data.get('model', 'code-llama')
        language = data.get('language', 'python')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'})
        

        global interpreter
        if interpreter is None or interpreter.INTERPRETER_MODEL != model:
            args = InterpreterArgs(model=model,mode=mode, lang=language)
            interpreter = Interpreter(args)
        
        os_platform = interpreter.utility_manager.get_os_platform()
        os_name = os_platform[0]
        code_snippet: str = None
        
        # Seting the mode.
        if interpreter.SCRIPT_MODE:
            interpreter.INTERPRETER_MODE = 'script'
        elif interpreter.COMMAND_MODE:
            interpreter.INTERPRETER_MODE = 'command'
        elif interpreter.VISION_MODE:
            interpreter.INTERPRETER_MODE = 'vision'
        elif interpreter.CHAT_MODE:
            interpreter.INTERPRETER_MODE = 'chat'

        prompt = interpreter.get_mode_prompt(prompt, os_name)

        chat_history = []  # Empty chat history for now
        response = interpreter.generate_content(
            message=prompt,
            chat_history=chat_history
        )

        start_sep = str(interpreter.config_values.get('start_sep', '```'))
        end_sep = str(interpreter.config_values.get('end_sep', '```'))
        skip_first_line = interpreter.config_values.get('skip_first_line', 'False') == 'True'

        # Extract the code from the generated output.
        code_snippet = interpreter.code_interpreter.extract_code(response, start_sep, end_sep, skip_first_line)

        return jsonify({'response': code_snippet})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'})
            
        code = data.get('code')
        language = data.get('language', 'python')
        
        if not code:
            return jsonify({'error': 'No code provided'})
        
        code_interpreter = CodeInterpreter()
        result = code_interpreter.execute_code(code, language)
        
        if isinstance(result, tuple):
            output, error = result
            if error:
                return jsonify({'error': error})
            return jsonify({'result': output})
        
        return jsonify({'result': str(result)})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/fix', methods=['POST'])
def fix_code():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'})
            
        code = data.get('code')
        language = data.get('language', 'python')
        
        if not code:
            return jsonify({'error': 'No code provided'})
        
        code_interpreter = CodeInterpreter()
        fixed_code = code_interpreter.fix_code_errors(code, language)
        
        return jsonify({'fixed_code': fixed_code})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/save_code', methods=['POST'])
def save_code():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'})
            
        code = data.get('code')
        language = data.get('language', 'python')
        
        if not code:
            return jsonify({'error': 'No code provided'})
        
        # Save code to a file in the saved_code directory
        save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'saved_code')
        os.makedirs(save_dir, exist_ok=True)
        
        # Generate a unique filename with proper extension
        import datetime
        ext = '.py' if language == 'python' else '.js'
        filename = f"code_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        filepath = os.path.join(save_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(code)
        
        return jsonify({'result': f'Code saved to {filename}'})
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
