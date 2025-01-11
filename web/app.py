import os
import sys
import platform

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from libs.interpreter_lib import Interpreter
from libs.code_interpreter import CodeInterpreter
from libs.package_manager import PackageManager
import argparse
import json

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

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt')
    mode = data.get('mode', 'code')
    model = data.get('model', 'code-llama')
    lang = data.get('language', 'python')
    
    args = WebArgs()
    args.mode = mode
    args.model = model
    args.lang = lang
    
    interpreter = Interpreter(args)
    # Initialize empty chat history
    chat_history = []
    response = interpreter.get_prompt(prompt, chat_history)
    
    return jsonify({'response': response})

@app.route('/execute', methods=['POST'])
def execute():
    data = request.json
    code = data.get('code')
    
    args = WebArgs()
    args.exec = True
    
    interpreter = Interpreter(args)
    code_interpreter = CodeInterpreter()
    result = code_interpreter.execute_code(code, platform.system().lower())
    
    return jsonify({'result': result})

@app.route('/fix', methods=['POST'])
def fix_code():
    data = request.json
    code = data.get('code')
    
    args = WebArgs()
    interpreter = Interpreter(args)
    code_interpreter = CodeInterpreter()
    fixed_code = code_interpreter.fix_code_errors(code)
    
    return jsonify({'fixed_code': fixed_code})

@app.route('/install_package', methods=['POST'])
def install_package():
    data = request.json
    package = data.get('package')
    
    args = WebArgs()
    package_manager = PackageManager()
    result = package_manager.install_package(package)
    
    return jsonify({'result': result})

@app.route('/save_code', methods=['POST'])
def save_code():
    data = request.json
    code = data.get('code')
    
    args = WebArgs()
    code_interpreter = CodeInterpreter()
    result = code_interpreter.save_code(code)
    
    return jsonify({'result': result})

if __name__ == '__main__':
    app.run(debug=True)
