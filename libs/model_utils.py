def normalize_model_name(model_name):
    """
    Normalize model name for litellm compatibility.
    Maps legacy model names to current names, adds provider prefixes where needed.
    """
    # Legacy mappings
    legacy_mappings = {
        "claude-2.1": "claude-sonnet-4-6",
        "claude-2": "claude-sonnet-4-6",
    }
    
    # Known Claude models that don't need anthropic prefix
    known_claude = ["claude-sonnet-4-6", "claude-opus-4-6"]
    
    # Apply legacy mapping
    model_name = legacy_mappings.get(model_name, model_name)
    
    if '/' in model_name:
        return model_name
    
    if 'claude' in model_name:
        if model_name in known_claude:
            return model_name
        else:
            return f'anthropic/{model_name}'
    
    if any(model_name.lower().startswith(prefix) for prefix in ['gpt', 'o1', 'o3', 'o4']):
        return model_name
    
    if 'deepseek' in model_name:
        return f'deepseek/{model_name}'
    
    if 'gemini' in model_name:
        return f'gemini/{model_name}'
    
    if 'groq' in model_name:
        return f'groq/{model_name}'
    
    # For other models (e.g., huggingface), return as is
    return model_name