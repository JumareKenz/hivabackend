import httpx

class LLMClient:
    def __init__(self, base_url="http://127.0.0.1:11434", model="llama3:latest"):
        self.base_url = base_url
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.0):
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        raw_responses = []
        response_text = ""
        with httpx.stream("POST", url, json=payload, timeout=None) as r:
            for line in r.iter_lines():
                if line:
                    data = httpx.Response(200, content=line).json()
                    raw_responses.append(data)
                    response_text += data.get("response", "")

        return {"answer": response_text, "raw": {"responses": raw_responses}}
