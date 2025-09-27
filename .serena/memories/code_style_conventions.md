# ASEOfSmartICE Code Style and Conventions

## File Organization
- **Descriptive naming** - Files use clear, descriptive names indicating functionality
- **Version comments** - File headers include version and purpose comments
- **Feature-based directories** - `test/` for testing scripts, `sub-stream/` for streaming features

## Python Conventions

### File Headers
All Python files include standardized headers:
```python
"""
File Description
Version: X.X
Purpose: Clear description of file purpose
Date: YYYY-MM-DD
"""
```

### Naming Conventions
- **snake_case** for variables, functions, and file names
- **UPPER_CASE** for constants (camera IPs, URLs)
- **Descriptive names** that clearly indicate purpose

### Code Structure
- **Global variables** clearly marked and documented
- **Threading** used for concurrent operations (video capture + web serving)
- **Error handling** with try/catch blocks for network operations
- **Logging** with emoji-enhanced print statements for visual clarity

### Comments and Documentation
- **Docstrings** for functions explaining purpose and parameters
- **Inline comments** for complex operations
- **Visual emoji indicators** in output (🎥, ✅, ❌, 🔍, etc.)

## Configuration Management
- **Hardcoded values** for camera IPs and credentials (test environment)
- **Global constants** at top of files for easy modification
- **Clear separation** between configuration and logic

## Error Handling Pattern
```python
try:
    # Network/camera operation
    operation()
except SpecificException:
    print("❌ Specific error message")
except Exception as e:
    print(f"❌ General error: {e}")
```