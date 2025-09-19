import re
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pandas as pd
import tiktoken
import os
import docx
import pdfplumber
import json

enc = tiktoken.get_encoding("cl100k_base")
CUSTOM_SPLIT_SIGN = "\n\n---\n\n"


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


# 清理chunks中的噪音
def clean_chunk(text: str) -> str:
    # 去掉页码形式：- 1 -、— 12 —、第3页、第3页/共10页
    text = re.sub(r'^\s*[-—]?\s*\d+\s*[-—]?\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*第\s*\d+\s*页(\s*/\s*共\s*\d+\s*页)?\s*$', '', text, flags=re.MULTILINE)

    text = text.replace('\xa0', ' ')  # 不间断空格换成普通空格
    text = re.sub(r'\n+', ' ', text)  # 所有换行变成空格
    text = re.sub(r'[ ]+', ' ', text)  # 多空格合并
    return text.strip()


# 普通文本切分
def split_common_text(text, chunk_size=500, chunk_overlap=50):
    # 定义切分器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " "]  # 中文常见标点优先
    )

    # 切分文本
    chunks = text_splitter.split_text(text)

    # 防止上一个chunk中句末的标点符号跑到下一个chunk开头
    fixed_chunks = []
    for idx, chunk in enumerate(chunks):
        chunk = clean_chunk(chunk)
        if idx == 0:
            fixed_chunks.append((idx + 1, chunk))
            continue

        while chunk and chunk[0] in "。！？；，.,":
            fixed_chunks[-1] = (fixed_chunks[-1][0], fixed_chunks[-1][1] + chunk[0])
            chunk = chunk[1:].strip()

        fixed_chunks.append((idx + 1, chunk))
    final_chunks = [c[1] if isinstance(c, tuple) else c for c in fixed_chunks]
    return final_chunks


# 合同类文本切分
def split_contract_text(text: str, chunk_size=500, chunk_overlap=50):
    # 按条款编号拆分
    pattern = re.compile(r'(?=\n?[一二三四五六七八九十]+、|\n?\d+\.\s|\n?\(\d+\))')
    raw_chunks = pattern.split(text)
    raw_chunks = [c.strip() for c in raw_chunks if c.strip()]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " "]
    )

    final_chunks = []
    for idx, chunk in enumerate(raw_chunks):
        internal_chunks = splitter.split_text(chunk)
        for ic in internal_chunks:
            ic = clean_chunk(ic)
            if final_chunks:
                while ic and ic[0] in "。！？；，.,":
                    final_chunks[-1] += ic[0]
                    ic = ic[1:].strip()
            if ic:
                final_chunks.append(ic)

    output_chunks = [c for idx, c in enumerate(final_chunks)]
    return output_chunks


# 判断是否近似于合同、法律类文本
def looks_like_contract(text: str, min_clause_count=2) -> bool:
    pattern = re.compile(r'^\s*([一二三四五六七八九十]+、|\d+\.\s|\(\d+\))', re.MULTILINE)
    clauses = pattern.findall(text)
    return len(clauses) >= min_clause_count


# 判断是否合同类文本
def is_contract_or_legal_text(text: str) -> bool:
    keywords = ["合同", "示范文本", "协议"]
    if any(kw in text for kw in keywords):
        return True
    return looks_like_contract(text)


# 按 y 坐标合并 PDF 文字块为行
def merge_words_by_lines(words, column_threshold=5):
    lines_dict = {}
    for w in words:
        y = round(w['top'] / column_threshold) * column_threshold
        lines_dict.setdefault(y, []).append((w['x0'], w['text']))
    sorted_lines = []
    for y in sorted(lines_dict.keys()):
        line_words = sorted(lines_dict[y], key=lambda x: x[0])
        line_text = " ".join([w[1] for w in line_words])
        sorted_lines.append(line_text)
    return sorted_lines


# 判断罗马数字
def is_numbering(text: str) -> bool:
    """判断文本是否是纯数字编号或罗马数字编号"""
    text = text.strip()
    if re.fullmatch(r"\d+", text):  # 纯数字
        return True
    if re.fullmatch(r"[IVXLCDMⅰ-ⅻⅬⅭⅮⅯ]+", text, flags=re.IGNORECASE):  # 罗马数字
        return True
    return False


# 切分pdf普通文本
def extract_pdf_chunks(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    chunks = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    row_text = " | ".join([str(c) for c in row if c])
                    if row_text.strip():
                        chunks.append(clean_chunk(row_text))

            words = page.extract_words()
            if words:
                lines = merge_words_by_lines(words)

                merged_lines = []
                buffer = ""
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # 如果当前行是数字/罗马数字 → 拼接到下一行
                    if is_numbering(line):  # 直接拼上，不另起chunk
                        continue

                    # 如果上一行没有标点结束，拼接
                    if buffer and not buffer.endswith(("。", "！", "？", "；", ":", ".")):
                        buffer += line
                    else:
                        if buffer:
                            merged_lines.append(buffer)
                        buffer = line
                if buffer:
                    merged_lines.append(buffer)

                # token 切分
                for line in merged_lines:
                    tokens = count_tokens(line)
                    if tokens <= chunk_size:
                        clean_line = clean_chunk(line).strip()
                        if clean_line and not re.fullmatch(r"[。！？；,.、…·]+", clean_line):
                            chunks.append(clean_line)
                    else:
                        sep = ["。", ".", "?", "？", "!", "！", ";", "；"]
                        temp = [line]
                        for s in sep:
                            temp2 = []
                            for t in temp:
                                if count_tokens(t) > chunk_size:
                                    # 切分时，排除编号
                                    parts = [p for p in t.split(s) if p.strip() and not is_numbering(p)]
                                    temp2.extend(parts)
                                else:
                                    temp2.append(t)
                            temp = temp2
                        for t in temp:
                            t = clean_chunk(t).strip()
                            if t and not re.fullmatch(r"[。！？；,.、…·]+", t):
                                chunks.append(t)
    return chunks


# excel按行切分
def excel_to_chunks_auto(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50):
    # 先尝试用 header=0 读取
    df = pd.read_excel(file_path, header=0, dtype=str)

    # 简单判断是否有列头：第一行全是字符串，则认为有列头
    first_row_all_str = all(isinstance(val, str) for val in df.iloc[0])

    if not first_row_all_str:
        # 没有列头，重新读取
        df = pd.read_excel(file_path, header=None, dtype=str)

    all_chunks = []
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # 第一列作为行头
    first_col_name = df.columns[0]

    for idx, row in df.iterrows():
        row_header = str(row[first_col_name])
        row_values = "\t".join([str(row[col]) for col in df.columns[1:]])
        row_text = f"{row_header}：{row_values}"
        row_text = clean_chunk(row_text)

        if len(row_text) <= chunk_size:
            all_chunks.append(row_text)
        else:
            all_chunks.extend(splitter.split_text(row_text))

    return all_chunks


# 读取文件的原始文本
def extract_text_from_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if ext in [".docx", ".doc"]:
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
    elif ext in [".txt"]:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    elif ext in [".xlsx", ".xls", ".pdf"]:
        return None
    else:
        raise ValueError(f"不支持的文件类型: {ext}")
    return clean_chunk(text)


# 按文件类型调用切分函数
def split_file_to_chunks(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".xlsx", ".xls"]:
        return excel_to_chunks_auto(file_path)
    if ext in [".pdf"]:
        return extract_pdf_chunks(file_path, chunk_size, chunk_overlap)
    else:
        text = extract_text_from_file(file_path)
        if not text:
            return []
        if ext in [".docx", ".doc"] and is_contract_or_legal_text(text):
            return split_contract_text(text, chunk_size, chunk_overlap)
            # 其他文本
        return split_common_text(text, chunk_size, chunk_overlap)


if __name__ == "__main__":
    test_files = [
        # "../data/綜合能力評估開考報名表.pdf",
        # "../data/test.txt",
        # "../data/新建 XLSX 工作表.xlsx",
        # "../data/Day21 表格数据格式.xlsx",
        # "../data/Day04 排序.xlsx",
        "../data/散文.docx",
        # "../data/《委托合同（示范文本）》（GF—2025—1001）.docx",
        # "../data/北京市机动车驾驶培训服务合同（示范文本）.docx",
        # "../data/北京市科技类校外培训服务合同（示范文本）（试行）.docx",
        # "../data/民事起诉状.docx",
        # "../data/常年法律顾问服务合同.docx",
        # "../data/《委托合同（示范文本）》（GF—2025—1001）.pdf",
        # "../data/新疆维吾尔自治区中小学校校外供餐合同.pdf"
    ]

    output_dir = "../output"
    os.makedirs(output_dir, exist_ok=True)

    for f in test_files:
        if not os.path.exists(f):
            continue
        print(f"处理文件: {f}")
        chunks = split_file_to_chunks(f, chunk_size=200, chunk_overlap=20)
        for idx, chunk in enumerate(chunks):
            print(f"Chunk {idx + 1}:\t", chunk)
        print("=" * 60)

        # 保存切分内容到同名txt中
        base_name = os.path.basename(f)
        name = os.path.splitext(base_name)[0]
        output_file = os.path.join(output_dir, f"{name}_chunks.txt")

        with open(output_file, "w", encoding="utf-8") as wf:
            for chunk in chunks:
                chunk = chunk.replace("\n", " ").strip()
                if chunk:
                    wf.write(chunk + "\n")

        print(f"已保存txt文件：{output_file}")
