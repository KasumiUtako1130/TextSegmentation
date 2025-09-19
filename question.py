import os
import json
from pathlib import Path
from openai import OpenAI
from prompt.questionGenerate import get_question_generation_prompt
from clean import clean_file, clean_data

client = OpenAI(
    api_key="sk-0a396d2798444089ae902925f45c34ae",
    base_url="https://api.deepseek.com",
)
MODEL_NAME = "deepseek-chat"

CLEAN_DIR = Path("./cleaned")
QA_DIR = Path("./QA")
QA_DIR.mkdir(exist_ok=True)


# 合并段落
def merge_paragraphs(paragraphs, min_length=100, max_length=300):
    merged_paragraphs = []
    buffer = ""
    for para in paragraphs:
        if len(buffer) + len(para) < max_length:
            buffer += " " + para if buffer else para

            if len(buffer) >= min_length:
                merged_paragraphs.append(buffer.strip())
                buffer = ""
        else:
            if buffer:
                merged_paragraphs.append(buffer.strip())
            buffer = para
    if buffer:
        merged_paragraphs.append(buffer.strip())
    return merged_paragraphs


# 生成问题
def generate_questions(paragraph: str, max_qs: int = 3):
    prompt = get_question_generation_prompt(paragraph, max_qs)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        content = response.choices[0].message.content.strip()
        # 尝试解析 JSON
        try:
            qa_pairs = json.loads(content)
            return qa_pairs
        except json.JSONDecodeError:
            print("生成的内容不是标准 JSON，返回原始文本")
            return [{"question_answer_text": content}]
    except Exception as e:
        print(f"生成失败: {e}")
        return []


# 处理文件
def process_clean_files():
    for filename in os.listdir(CLEAN_DIR):
        if not filename.endswith(".txt"):
            continue
        input_path = CLEAN_DIR / filename
        with open(input_path, "r", encoding="utf-8") as f:
            paragraphs = [p.strip() for p in f.read().split("\n\n") if p.strip()]

        merged_paragraphs = merge_paragraphs(paragraphs, min_length=100, max_length=300)

        qa_list = []

        print(f"处理文件：{filename}，共 {len(merged_paragraphs)} 段")
        for i, para in enumerate(merged_paragraphs, start=1):
            print(f"生成段落 {i}/{len(merged_paragraphs)} 问题...")
            questions = generate_questions(para)

            for q in questions:
                if isinstance(q, dict) and "question" in q:
                    cleaned_q = clean_data(q["question"])
                    qa_list.append({
                        "context": para,
                        "question": cleaned_q if cleaned_q else q["question"]
                    })
                elif isinstance(q, str):
                    qa_list.append({
                        "context": para,
                        "question": q
                    })
        # 输出 JSON
        output_path = QA_DIR / f"{filename.replace('.txt', '.json')}"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(qa_list, f, ensure_ascii=False, indent=2)
        print(f"已保存问答文件：{output_path}")


if __name__ == "__main__":
    process_clean_files()
