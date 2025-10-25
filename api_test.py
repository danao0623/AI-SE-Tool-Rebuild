import requests, json
from api.api_sys import API_URL, HEADERS

data = {
    "contents": [
        {"parts": [{"text": "你好，幫我回覆一句：Gemini API 測試成功"}]}
    ]
}

response = requests.post(API_URL, headers=HEADERS, data=json.dumps(data))

print("狀態碼:", response.status_code)
print("回傳內容:")
print(response.text)