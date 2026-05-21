from openai import OpenAI

client = OpenAI(
    api_key="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"
)

response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "user", "content": "Say hello"}
    ],
    max_tokens=5
)

print(response.choices[0].message.content)