import re
import json

def clean_json_text(text: str) -> str:
    """清理 AI 回傳的 JSON 格式文字（移除 ```json ... ``` 標記）"""
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()

def parse_json_response(text: str):
    """嘗試將 AI 回傳文字清理並轉換為 Python dict"""
    cleaned = clean_json_text(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print("⚠️ JSON 解析錯誤：", e)
        print("原始內容：", cleaned[:300])
        return None

def clean_mermaid_code(code: str) -> str:
    """清理 Mermaid 語法區塊"""
    code = re.sub(r'^```[a-zA-Z0-9]*\s*', '', code.strip())
    code = re.sub(r'\s*```$', '', code.strip())
    return code.strip()

def clean_code_block(text: str) -> str:
    """清理任意語言的 Markdown 程式區塊"""
    text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text.strip())
    text = re.sub(r"```$", "", text)
    return text.strip()

def remove_all_comments(text: str) -> str:
    """移除多行、單行註解與空行"""
    code = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    code = re.sub(r"'''.*?'''", '', code, flags=re.DOTALL)
    code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)
    code = re.sub(r'(^|\s)#.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'(^|\s)//.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'\n{2,}', '\n', code)
    return code.strip()