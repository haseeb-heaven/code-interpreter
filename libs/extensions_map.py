# Define a dictionary to map language name to file extension
extension_map = {
    ".python": ".py",
    ".javascript": ".js",
    ".java": ".java",
    ".c": ".c",
    ".c++": ".cpp",
    ".c#": ".cs",
    ".php": ".php",
    ".ruby": ".rb",
    ".go": ".go",
    ".swift": ".swift",
    ".kotlin": ".kt",
    ".rust": ".rs",
    ".dart": ".dart",
    ".r": ".r",
    ".typescript": ".ts",
    ".scala": ".scala",
    ".perl": ".pl",
    ".haskell": ".hs",
    ".lua": ".lua",
    ".julia": ".jl",
    ".elixir": ".ex",
    ".clojure": ".clj",
    ".erlang": ".erl",
    ".ocaml": ".ml",
}

streamlit_code_langs = {
    ".py": "python",
    ".js": "javascript",
    ".html": "html",
    ".css": "css",
    ".java": "java",
    ".cpp": "c++",
    ".cs": "csharp",
    ".r": "r",
    ".sql": "sql"
}

def get_streamlit_code_lang(language):
    # make language name small letters
    language = language.lower()
    # get file extension from ext_map
    file_extension = streamlit_code_langs.get(language)
    # return file extension
    #print(f"get_file_extesion: Language: {language} File Extension: {file_extension}")
    return file_extension
    
# Method to get file extension from language name
def get_file_extesion(language):
    # make language name small letters
    language = language.lower()
    # get file extension from ext_map
    file_extension = extension_map.get(language)
    # return file extension
    #print(f"get_file_extesion: Language: {language} File Extension: {file_extension}")
    return file_extension