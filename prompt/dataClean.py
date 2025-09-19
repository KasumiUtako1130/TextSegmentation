def get_data_clean_prompt(text: str, global_prompt: str = "", clean_prompt: str = "") -> dict:
    system_content = "你是一位专业的数据清洗专家，擅长识别和清理文本中的噪声、重复、错误等”脏数据“，提升数据准确性、一致性与可用性。"
    if global_prompt:
        system_content += f"在后续的任务中，你务必遵循这样的规则：{global_prompt}"

    user_content = f"""
请对以下文本进行严格的数据清洗（只清洗，不改写）：

{text}

要求：
- 只清洗文本，删除无意义符号、乱码、重复内容
- 修正格式、编码问题、标点错误、明显错别字和语法错误
- 保留原文意思和逻辑顺序，不添加任何原文中不存在的内容
- 不改写、不扩写、不生成新句子
- 输出纯净文本，不要解释、标记或附加任何信息
"""
    if clean_prompt:
        user_content += f"\n- 在清洗数据时，你务必遵循这样的规则：{clean_prompt}"

    return {"system": system_content.strip(), "user": user_content.strip()}
