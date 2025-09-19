def get_question_generation_prompt(paragraph: str, max_qs: int = 3) -> dict:
    system_content = (
        "你是一位专业的文本分析专家，擅长从复杂文本提取关键信息并生成高质量的问题（仅生成问题）。"
        "请严格根据文本内容生成问题，禁止虚构。"
    )

    user_content = f"""
请基于下面的文本段落生成最多 {max_qs} 个问题。
## 要求：
- 问题必须基于文本内容直接生成
- 问题应具有明确答案指向性,但不要给出答案
- 问题类型可以多样：事实型、推理型、填空型
- 禁止生成假设性、重复或相似问题
- 优先覆盖文本中的关键信息点
- 输出 JSON 格式如下,严格遵守：
["问题1","问题2","..."]

## 输出示例
["甲方通过什么方式将餐费支付到乙方账户？","学生的晚餐用餐标准包含哪些类型的菜品？"]

## 文本段落：
{paragraph}
"""
    return {"system": system_content.strip(), "user": user_content.strip()}