from langchain.text_splitter import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
import re
import os
import docx


CUSTOM_SPLIT_SIGN = "===SPLIT==="

def is_markdown_table(text: str) -> bool:
    """判断是不是 markdown 表格"""
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return False
    return "|" in lines[0] and re.match(r'^\s*\|?[-:\s]+\|[-:\s]+', lines[1]) is not None

def split_markdown_table(text: str, chunk_size: int = 500) -> list[str]:
    """表格切分：尽量带表头，按行拆"""
    lines = text.strip().splitlines()
    header = lines[0] + "\n" + lines[1]  # 表头+分隔线
    rows = lines[2:]

    chunks, current = [], []
    for row in rows:
        current.append(row)
        # 控制 chunk 大小（这里简化用行数）
        if len(current) >= chunk_size // 50:
            chunks.append(header + "\n" + "\n".join(current))
            current = []
    if current:
        chunks.append(header + "\n" + "\n".join(current))
    return chunks

def split_common_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """普通文本切分：优先按层级分隔符，再用长度兜底"""
    separators = ["\n## ", "\n# ", "\n\n", ".", "。", "?", "？", "!", "！"]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        keep_separator=True
    )
    return splitter.split_text(text)

def split_text2chunks(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """模仿 FastGPT 的文档切分"""
    chunks = []
    # Step1: 按自定义分隔符切
    segments = text.split(CUSTOM_SPLIT_SIGN)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        # Step2: 判断是否表格
        if is_markdown_table(seg):
            chunks.extend(split_markdown_table(seg, chunk_size))
        else:
            # Step3: 普通文本
            chunks.extend(split_common_text(seg, chunk_size, chunk_overlap))

    # Step4: 去重（简单版）
    seen, deduped = set(), []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


def read_file(file_path: str) -> str:
    """根据文件类型读取文本内容"""
    ext = os.path.splitext(file_path)[-1].lower()
    text = ""

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

    elif ext == ".pdf":
        reader = PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() or ""

    elif ext == ".docx":
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"

    else:
        raise ValueError(f"暂不支持的文件类型: {ext}")

    return text

def process_file(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """入口：读取 + 切分"""
    text = read_file(file_path)
    return split_text2chunks(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


# ================= 测试入口 =================
if __name__ == "__main__":
    file_path = "example.txt"  # 用户上传的文件路径
    chunks = process_file(file_path, chunk_size=100, chunk_overlap=20)

    for i, c in enumerate(chunks, 1):
        print(f"Chunk {i}:\n{c}\n{'-'*40}")