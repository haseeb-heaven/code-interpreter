from setuptools import setup, find_packages

setup(
    name="open-code-interpreter",
    version="0.1",
    packages=find_packages(),
    author="Haseeb Mir",
    author_email="haseebmir.hm@gmail.com",
    description="An innovative open-source Code Interpreter with (GPT,Gemini,PALM,LLaMa) models.",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/haseeb-heaven/open-code-interpreter",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)