import os
import json
from config import ROOT_DIR
from openai import OpenAI
from prompt.answerGenerate import get_answer_generation_prompt

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(
    api_key=deepseek_api_key,
    base_url="https://api.deepseek.com",
)
MODEL_NAME = "deepseek-chat"

QUESTION_DIR = ROOT_DIR / "question"
ANSWER_DIR = ROOT_DIR / "answer"
ANSWER_DIR.mkdir(exist_ok=True)


def generate_answer(paragraph: str, question: str, image_map: dict = None) -> str:
    prompt = get_answer_generation_prompt(paragraph, question, image_map)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]}
            ],
            temperature=0.2,
            max_tokens=3000
        )
        content = response.choices[0].message.content.strip()
        return content
    except Exception as e:
        print(f"生成答案失败：{e}")
        return "生成失败"


def process_qa_files():
    for filename in os.listdir(QUESTION_DIR):
        if not filename.endswith(".json"):
            continue

        input_path = QUESTION_DIR / filename
        output_path = ANSWER_DIR / filename

        with open(input_path, "r", encoding="utf-8") as f:
            qa_list = json.load(f)

        result = []
        print(f"处理文件：{filename},共{len(qa_list)}个问题")

        for i, item in enumerate(qa_list, start=1):
            question = item.get("question", "")
            paragraph = item.get("context", "")
            image_urls = item.get("images", [])
            print(f"生成答案{i}/{len(qa_list)}...")

            # 检查是否包含图片占位符
            if "[IMAGE_" in paragraph or "[IMAGE_" in question:
                # 找到占位符对应的图片 URL
                answer_found = False
                for idx, url in enumerate(image_urls, start=1):
                    placeholder = f"[IMAGE_{idx}]"
                    if placeholder in paragraph or placeholder in question:
                        answer = url  # 直接返回图片链接
                        answer_found = True
                        break
                if not answer_found:
                    answer = "无法在文本中找到答案"
            else:
                # 正常文本生成答案
                answer = generate_answer(paragraph, question)

            result.append({
                "context": paragraph,
                "question": question,
                "answer": answer,
                "images": image_urls
            })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"已保存答案文件:{output_path}")


if __name__ == "__main__":
    process_qa_files()
