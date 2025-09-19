from openai import OpenAI

client = OpenAI(
    api_key="sk-0a396d2798444089ae902925f45c34ae",
    base_url="https://api.deepseek.com",
)
text = '''我喜欢看书.'''

prompt = f'''
你是一个语言专家，擅长中文文本改写。
请将下面这句话改写成三种不同的表达方式，意思保持不变，每个句子独占一行:

{text}
'''

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role":"system","content":"你是一个语言专家，擅长中文文本改写。"},
        {"role":"user",  "content":prompt}
    ],
    temperature = 0.7,
    max_tokens=200
)

output = response.choices[0].message.content
augmented_texts = [line.strip() for line in output.split("\n") if line.strip()]

print("原始文本：", text)
print("增强文本：")
for t in augmented_texts:
    print("-", t)