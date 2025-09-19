import os
from openai import OpenAI
from pathlib import Path
from prompt.dataClean import get_data_clean_prompt

# api key
client = OpenAI(
    api_key="sk-0a396d2798444089ae902925f45c34ae",
    base_url="https://api.deepseek.com",
)
MODEL_NAME = "deepseek-chat"

# 输入输出目录
INPUT_DIR = Path("./output")
OUTPUT_DIR = Path("./cleaned")
OUTPUT_DIR.mkdir(exist_ok=True)

# 清洗数据
def clean_data(text: str, language: str = "zh", global_prompt: str = "", clean_prompt: str = "") -> str:
    prompt = get_data_clean_prompt(text, global_prompt, clean_prompt)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]}
            ],
            temperature=0,
            max_tokens=3000
        )
        cleaned_text = response.choices[0].message.content.strip()
        if not cleaned_text:
            print("清洗返回结果为空")
            return None
        return cleaned_text
    except Exception as e:
        print(f"清洗失败:{e}")
        return None

# 将切分好的段落取出来
def split_paragraphs(text: str, max_length: int = 2000) -> list:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    blocks = []
    current_block = ""
    for para in paragraphs:
        if len(current_block) + len(para) + 2 > max_length:
            if current_block:
                blocks.append(current_block.strip())
            current_block = para + "\n\n"
        else:
            current_block += para + "\n\n"
    if current_block:
        blocks.append(current_block.strip())
    return blocks

# 处理文件
def clean_file():
    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith(".txt"):
            continue
        input_path = os.path.join(INPUT_DIR, filename)
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"正在清洗文件：{filename}")
        paragraph_blocks = split_paragraphs(content, max_length=2000)
        cleaned_blocks = []

        for i, block in enumerate(paragraph_blocks):
            print(f"清洗段落块 {i + 1}/{len(paragraph_blocks)}: ")
            cleaned_block = clean_data(block)
            if cleaned_block:
                print(f"段落块 {i + 1} 清洗完成。")
                cleaned_blocks.append(cleaned_block)
            else:
                print(f"段落块 {i + 1}清洗失败，跳过。")

        if cleaned_blocks:
            output_path = OUTPUT_DIR / filename
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(cleaned_blocks))
            print(f"已保存清洗结果：{output_path}")
        else:
            print(f"{filename} 全部段落清洗失败，未保存文件。")


if __name__ == "__main__":
    clean_file()
