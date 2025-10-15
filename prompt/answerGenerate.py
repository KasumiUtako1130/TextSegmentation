def get_answer_generation_prompt(text: str, question: str, image_map: dict = None) -> dict:
    system_content = (
        "你是一位专业的文本分析专家，擅长从复杂文本中提取准确答案。"
        "请严格根据提供的文本内容生成答案，严禁虚构"
    )
    # 如果有图片占位符，则附加图片说明
    image_text = ""
    if image_map:
        for ph, path in image_map.items():
            if ph in text.upper():
                image_text += f"{ph} 对应图片路径：{path}\n"

    user_content = f'''
请基于下面的文本段落，回答给定问题。

## 要求：
- 答案必须直接来自文本，不得胡编乱造
- 回答要准确，简洁，避免额外说明
- 如果文本中没有答案，请回答 ”无法在文本中找到答案“
- 输出答案时只写答案本身，不要加”答案：“或其他符号

## 文本段落：
{text}
{image_text}

## 问题：
{question}
'''
    return {"system": system_content.strip(), "user": user_content.strip()}
