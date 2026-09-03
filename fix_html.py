import os
import re
import textwrap

def dedent_st_markdown(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # If the file doesn't use st.markdown with triple quotes, skip
    if 'st.markdown(' not in content:
        return

    # Add import textwrap if not present
    if 'import textwrap' not in content:
        content = content.replace('import streamlit as st', 'import streamlit as st\nimport textwrap')

    # Regex to find st.markdown(f\"\"\" ... \"\"\", unsafe_allow_html=True)
    # We will just write a custom replacer
    
    # Actually, a simpler way is just to replace \n followed by spaces with \n inside the specific st.markdown calls
    # Or just use Python's ast to parse and modify? No, too complex.
    
    # A safer approach for the specific files we know are affected:
    # blade_theme.py and app.py
    
    # Let's just find `    <div` and replace with `<div` and so on, but only for lines starting with whitespace + <
    # Wait, in markdown, ANY line starting with 4+ spaces is a code block. So we just need to remove leading spaces from lines inside strings.
    
    # Let's process line by line, if we are inside a triple quote string, strip leading whitespace (except for specific formatting if needed).
    
    pass

if __name__ == '__main__':
    for root, _, files in os.walk('frontend'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # We can just replace all instances of `    <` with `<` and `        <` with `<` etc.
                # Since HTML tags should ideally not be indented in Streamlit markdown.
                new_content = re.sub(r'\n[ \t]+<', '\n<', content)
                
                # Also fix lines that are part of the HTML but might not start with `<` like `{cards}`
                new_content = re.sub(r'\n[ \t]+{', '\n{', new_content)
                new_content = re.sub(r'\n[ \t]+}', '\n}', new_content)
                new_content = re.sub(r'\n[ \t]+-', '\n-', new_content) # for markdown lists in simulation_lab.py
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Fixed {filepath}")
