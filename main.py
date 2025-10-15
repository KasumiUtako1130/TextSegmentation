import os
import json
from clean import clean_file, clean_data
from question import merge_paragraphs, generate_questions
from answer import generate_answer
from config import ROOT_DIR
from openai import OpenAI

client = OpenAI(
    api_key="sk-0a396d2798444089ae902925f45c34ae",
    base_url="https://api.deepseek.com"
)
MODEL_NAME = "deepseek-chat"

RAW_DIR = ROOT_DIR / "output"
CLEAN_DIR = ROOT_DIR / "cleaned"
QUESTION_DIR = ROOT_DIR / "question"
ANSWER_DIR = ROOT_DIR / "answer"
CLEAN_DIR.mkdir(exist_ok=True)
QUESTION_DIR.mkdir(exist_ok=True)
ANSWER_DIR.mkdir(exist_ok=True)


def main_pineline():
    print("1.清洗原始文件")
    clean_file()

    print("2.生成问题")
    for filename in os.listdir(CLEAN_DIR):
        if not filename.endswith(".txt"):
            continue
        input_path = CLEAN_DIR / filename
        with open(input_path, "r", encoding="utf-8") as f:
            paragraphs = [p.strip() for p in f.read().split("\n\n") if p.strip()]

        merged_paragraphs = merge_paragraphs(paragraphs, min_length=100, max_length=300)

        question_list = []

        print(f"处理文件：{filename},共{len(merged_paragraphs)}段")
        for i, para in enumerate(merged_paragraphs, start=1):
            print(f"生成段落 {i}/{len(merged_paragraphs)} 问题...")
            questions = generate_questions(para)

            for q in questions:
                if isinstance(q, dict) and "question" in q:
                    cleaned_q = clean_data(q["question"])
                    question_list.append({
                        "context": para,
                        "question": cleaned_q if cleaned_q else q["question"]
                    })
                elif isinstance(q, str):
                    question_list.append({
                        "context": para,
                        "question": q
                    })
        # 输出 JSON
        output_path = QUESTION_DIR / f"{filename.replace('.txt', '.json')}"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(question_list, f, ensure_ascii=False, indent=2)
        print(f"已保存问题文件：{output_path}")

    print("3.生成答案")
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
            questions = item.get("question", "")
            paragraphs = item.get("context", "")
            print(f"生成答案{i}/{len(qa_list)}...")

            answers = generate_answer(paragraphs, questions)
            result.append({
                "context": paragraphs,
                "question": questions,
                "answer": answers
            })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"已保存答案文件：{output_path}")


if __name__ == "__main__":
    main_pineline()
