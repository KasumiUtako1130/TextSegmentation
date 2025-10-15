import os
import re
import json
from config import ROOT_DIR
from openai import OpenAI
from prompt.questionGenerate import get_question_generation_prompt
from clean import clean_file, clean_data

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(
    api_key=deepseek_api_key,
    base_url="https://api.deepseek.com",
)
MODEL_NAME = "deepseek-chat"

CLEAN_DIR = ROOT_DIR / "cleaned"
QUESTION_DIR = ROOT_DIR / "question"
IMAGE_MAP_PATH = ROOT_DIR / "output"/"maps"

QUESTION_DIR.mkdir(exist_ok=True)
IMAGE_MAP_PATH.mkdir(exist_ok=True)


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

        map_path = IMAGE_MAP_PATH / f"{filename.replace('.txt','_image_map.json')}"
        if map_path.exists():
            with open(map_path, "r", encoding="utf-8") as f:
                image_map = json.load(f)
            print(f"已加载图片映射文件：{map_path}")
        else:
            image_map = {}
            print(f"未找到图片映射文件: {map_path}")

        with open(input_path, "r", encoding="utf-8") as f:
            paragraphs = [p.strip() for p in f.read().split("\n\n") if p.strip()]

        merged_paragraphs = merge_paragraphs(paragraphs, min_length=100, max_length=300)

        qa_list = []

        print(f"处理文件：{filename}，共 {len(merged_paragraphs)} 段")
        for i, para in enumerate(merged_paragraphs, start=1):
            print(f"生成 {i}/{len(merged_paragraphs)} 问题...")
            questions = generate_questions(para)

            # 找出当前段落出现的图片占位符
            images_in_para = []
            for placeholder, url in image_map.items():
                if placeholder.upper() in para.upper():
                    images_in_para.append(url)

            for q in questions:
                if isinstance(q, dict) and "question" in q:
                    # 清洗question
                    cleaned_q = clean_data(q["question"])
                    question_text = cleaned_q if cleaned_q else q["question"]

                    placeholders_in_question = re.findall(r"\[IMAGE_\d+\]", question_text.upper())
                    urls_for_question = [image_map.get(ph, "") for ph in placeholders_in_question]

                    qa_list.append({
                        "context": para,
                        "question": question_text,
                        "images": urls_for_question,
                    })
                elif isinstance(q, str):
                    placeholders_in_question = re.findall(r"\[IMAGE_\d+\]", q.upper())
                    urls_for_question = [image_map.get(ph, "") for ph in placeholders_in_question]

                    qa_list.append({
                        "context": para,
                        "question": q,
                        "images": urls_for_question,
                    })
        # 输出 JSON
        output_path = QUESTION_DIR / f"{filename.replace('.txt', '.json')}"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(qa_list, f, ensure_ascii=False, indent=2)
        print(f"已保存问题文件：{output_path}")


if __name__ == "__main__":
    process_clean_files()
