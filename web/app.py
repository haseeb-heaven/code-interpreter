import os
import sys
import platform
import json

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from libs.interpreter_lib import Interpreter
from libs.code_interpreter import CodeInterpreter
from libs.package_manager import PackageManager
import argparse

app = Flask(__name__)

class WebArgs:
    def __init__(self):
        self.exec = False
        self.save_code = False
        self.mode = 'code'
        self.model = 'code-llama'
        self.lang = 'python'
        self.display_code = True
        self.history = False
        self.file = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_models', methods=['GET'])
def get_models():
    try:
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'configs')
        models = []
        for file in os.listdir(config_dir):
            if file.endswith('.config'):
                models.append(file.replace('.config', ''))
        return jsonify({'models': models})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        mode = data.get('mode', 'code')
        model = data.get('model', 'code-llama')
        lang = data.get('language', 'python')
        
        args = WebArgs()
        args.mode = mode
        args.model = model
        args.lang = lang
        
        interpreter = Interpreter(args)
        chat_history = []
        
        # Get the prompt based on mode
        generated_text = interpreter.get_prompt(prompt, chat_history)
        
        # Extract code from the generated text
        code_interpreter = CodeInterpreter()
        code = code_interpreter.extract_code(generated_text, start_sep='```', end_sep='```', skip_first_line=True)
        
        if code is None:
            return jsonify({'error': 'Failed to generate code'}), 500
            
        return jsonify({'response': code})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.get_json()
        code = data.get('code')
        
        if not code:
            return jsonify({'error': 'No code provided'})
        
        code_interpreter = CodeInterpreter()
        result = code_interpreter.execute_code(code, platform.system().lower())
        
        if result[1]:  # If there are errors
            return jsonify({'error': result[1]}), 500
            
        return jsonify({'result': result[0] if result[0] else 'Code executed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/fix', methods=['POST'])
def fix_code():
    try:
        data = request.get_json()
        code = data.get('code')
        
        if not code:
            return jsonify({'error': 'No code provided'})
        
        code_interpreter = CodeInterpreter()
        fixed_code = code_interpreter.fix_code_errors(code)
        
        return jsonify({'fixed_code': fixed_code})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/install_package', methods=['POST'])
def install_package():
    try:
        data = request.get_json()
        package = data.get('package')
        
        if not package:
            return jsonify({'error': 'Package name is required'}), 400
            
        package_manager = PackageManager()
        result = package_manager.install_package(package)
        
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/save_code', methods=['POST'])
def save_code():
    try:
        data = request.get_json()
        code = data.get('code')
        
        if not code:
            return jsonify({'error': 'No code provided'})
        
        # Save code to a file in the saved_code directory
        save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'saved_code')
        os.makedirs(save_dir, exist_ok=True)
        
        # Generate a unique filename
        import datetime
        filename = f"code_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        filepath = os.path.join(save_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(code)
        
        return jsonify({'result': f'Code saved to {filename}'})
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
