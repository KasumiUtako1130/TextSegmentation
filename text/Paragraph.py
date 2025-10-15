import os
import json
import re
import docx
import requests
import pdfplumber
from typing import List, Tuple

from config import ROOT_DIR

IMGBB_API_KEY = "2a1aab4e3864f71e121b7a4a6e7d1879"

output_dir = ROOT_DIR / "output"
map_dir = output_dir / "maps"
map_dir.mkdir(parents=True, exist_ok=True)

IMAGE_MAP_PATH = output_dir / "image_map.json"


def clean_pagination(text: str) -> str:
    # 去掉页码形式：- 1 -、— 12 —、第3页、第3页/共10页
    text = re.sub(r'^\s*[-—]?\s*\d+\s*[-—]?\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*第\s*\d+\s*页(\s*/\s*共\s*\d+\s*页)?\s*$', '', text, flags=re.MULTILINE)

    text = text.replace('\xa0', ' ')  # 替换不可见空格
    text = re.sub(r'\n+', ' ', text)  # 合并多余换行
    text = re.sub(r'[ ]+', ' ', text)  # 合并多余空格
    return text.strip()


def looks_like_contract(text: str, min_clause_count=2) -> bool:
    pattern = re.compile(r'^\s*([一二三四五六七八九十]+、|\d+\.\s|\(\d+\))', re.MULTILINE)
    clauses = pattern.findall(text)
    return len(clauses) >= min_clause_count


def is_contract_or_legal_text(text: str) -> bool:
    keywords = ["合同", "示范文本", "协议"]
    if any(kw in text for kw in keywords):
        return True
    return looks_like_contract(text)


# 按标点符号划分句子，保留句子完整性，防止不同段落之间重复的部分会直接切断句子
def split_into_sentences(text: str) -> List[str]:
    parts = re.split(r'([。！？；.!?])', text)
    sents = []
    i = 0
    while i < len(parts):
        piece = parts[i].strip()
        punct = parts[i + 1] if i + 1 < len(parts) else ''
        if piece or punct:
            sents.append(piece + punct)
        i += 2
    # 处理极端情况（如果正则分割产生空结果）
    if not sents and text.strip():
        sents = [text.strip()]
    return sents


# 按段落切分
def split_paragraphs(text: str, chunk_size=5000, overlap=100) -> List[str]:
    # 保留原始换行用于定位（不要先把所有换行替换掉）
    text = text.replace("\r\n", "\n")

    # 如果是合同/条款类，按条款关键字切分；否则按空行切分
    raw_paragraphs = []
    if looks_like_contract(text):
        clause_pat = re.compile(
            r'(?:第\s*[一二三四五六七八九十百千壹贰叁肆伍陆柒捌玖拾\d]+(?:之[一二三四五六七八九十\d]+)?\s*[条章部分节行]|'  # 第几章
            r'条款\s*[一二三四五六七八九十\d]+|'  # 条款几
            r'[一二三四五六七八九十]+[、.：]|'  # 一、
            r'[（(]\s*(?:[一二三四五六七八九十百千\d]+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+)\s*[）)]|'  # (一)(1)(I)
            r'\d+\s*[、.：]|'  # 几、
            r'附\s*(?:录|件|则)\s*\d*'  # 附录几
            r')'
        )
        matches = list(clause_pat.finditer(text))
        if matches:
            first_start = matches[0].start()
            if first_start > 0:
                head = text[:first_start].strip()
                if head:
                    raw_paragraphs.append(head)
            for i, m in enumerate(matches):
                start = m.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                seg = text[start:end].strip()
                if seg:
                    raw_paragraphs.append(seg)
        else:
            raw_paragraphs = [p for p in re.split(r'\n', text) if p.strip()]
    else:
        raw_paragraphs = [p for p in re.split(r'\n', text) if p.strip()]

    # 清理每个段落并对过长段落按句子切分（并在必要时使用字符级 overlap 回退到句子边界）
    final_chunks: List[str] = []
    puncts = "。！？；.!?"

    for para in raw_paragraphs:
        para = clean_pagination(para)
        if not para:
            continue

        if len(para) <= chunk_size:
            final_chunks.append(para)
        else:
            # 按句子拆（保留标点）
            sentences = split_into_sentences(para)

            cur_chunk_sents: List[str] = []
            cur_len = 0
            for sent in sentences:
                # 如果下一个句子还能放下，直接加入当前 chunk
                if cur_len + len(sent) <= chunk_size:
                    cur_chunk_sents.append(sent)
                    cur_len += len(sent)
                else:
                    # 当前 chunk 满了，先把它写入 final_chunks
                    if cur_chunk_sents:
                        final_chunks.append("".join(cur_chunk_sents))

                    # 计算 overlap_text：从 previous chunk 的末尾取 overlap 个字符
                    if overlap > 0 and final_chunks:
                        prev_chunk_text = final_chunks[-1]
                        raw_start = max(0, len(prev_chunk_text) - overlap)

                        # 在 raw_start 之前寻找最后一个句子结束标点位置
                        last_pos = -1
                        for ch in puncts:
                            pos = prev_chunk_text.rfind(ch, 0, raw_start)
                            if pos > last_pos:
                                last_pos = pos

                        if last_pos == -1:
                            # 没找到标点，从头开始（保守策略）
                            start_pos = 0
                        else:
                            # 回退到标点后（即新句子的起始）
                            start_pos = last_pos + 1

                        overlap_text = prev_chunk_text[start_pos:]
                        # 将 overlap_text 再拆成完整句子（防止出现半句）
                        overlap_sents = split_into_sentences(overlap_text) if overlap_text.strip() else []
                        # 新的当前 chunk 以这些完整句子开头，再加上当前这个无法放下的句子
                        cur_chunk_sents = overlap_sents + [sent]
                    else:
                        # 不使用 overlap 或没有 previous chunk 时，直接从当前句子开始新 chunk
                        cur_chunk_sents = [sent]

                    cur_len = sum(len(x) for x in cur_chunk_sents)

            # 循环结束后，如果还有残留 chunk，把它写入
            if cur_chunk_sents:
                final_chunks.append("".join(cur_chunk_sents))

    return final_chunks

def merge_pdf_lines_to_paragraphs(text: str, min_line_length=20):
    # 将pdf的行重构成段落
    lines = text.split("\n")
    merged = []
    current_para = ""

    for line in lines:
        line = line.strip()
        if not line:
            # 空行表示段落结束
            if current_para:
                merged.append(current_para.strip())
                current_para = ""
            continue

        # 如果当前行像是标题或太短，直接断开
        if len(line) < min_line_length and not re.search(r'[。！？.!?]$', line):
            current_para += line + " "
            continue

        # 如果行末没有标点，说明是连贯句
        if not re.search(r'[。！？.!?]$', line):
            current_para += line + " "
        else:
            current_para += line
            merged.append(current_para.strip())
            current_para = ""

    if current_para:
        merged.append(current_para.strip())

    return "\n\n".join(merged)


def upload_to_imgbb(image_path: str, api_key: str = IMGBB_API_KEY) -> str:
    if not api_key:
        print("未配置api key")
        return image_path
    try:
        with open(image_path, 'rb') as file:
            response = requests.post(
                "https://api.imgbb.com/1/upload",
                params={"key": api_key},
                files={"image": file}
            )
        data = response.json()
        if data.get("success"):
            return data["data"]["url"]
        else:
            print("上传失败:", data)
            return image_path
    except Exception as e:
        print(f"上传异常:{e}")
        return image_path


# 文件读取
def extract_text_and_images_from_file(file_path: str, image_output_root: str = "../output/images") -> Tuple[str, dict]:
    base_name = os.path.basename(file_path)
    name = os.path.splitext(base_name)[0]
    image_output_dir = os.path.join(image_output_root, f"{name}image")
    ext = os.path.splitext(file_path)[1].lower()

    text_paragraphs = []
    image_map = {}
    image_counter = 1
    has_image = False

    if ext in [".docx", ".doc"]:
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            para_text = para.text.strip()
            # 检查 inline_shapes（Word 图片）
            for run in para.runs:
                if run._element.xpath('.//w:drawing'):
                    if not has_image:
                        os.makedirs(image_output_dir, exist_ok=True)
                        has_image = True
                    if image_counter <= len(doc.inline_shapes):
                        inline_shape = doc.inline_shapes[image_counter - 1]
                        r_id = inline_shape._inline.graphic.graphicData.pic.blipFill.blip.embed
                        image_part = doc.part.related_parts[r_id]
                        image_bytes = image_part.blob
                        image_name = f"image_{image_counter}.png"
                        image_path = os.path.join(image_output_dir, image_name)
                        with open(image_path, "wb") as f:
                            f.write(image_bytes)

                        image_url = upload_to_imgbb(image_path)

                        # 在文本中添加占位符
                        placeholder = f"[IMAGE_{image_counter}]"
                        para_text += " " + placeholder
                        image_map[placeholder] = image_url
                        image_counter += 1
            if para_text:
                text_paragraphs.append(para_text)
        text = "\n\n".join(text_paragraphs)

    elif ext in [".pdf"]:
        paragraphs = []
        with pdfplumber.open(file_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                repaired_text = merge_pdf_lines_to_paragraphs(page_text)
                paragraphs.append(repaired_text.strip())

                # 提取页面中的图片
                for img in page.images:
                    if not has_image:
                        os.makedirs(image_output_dir, exist_ok=True)
                        has_image = True
                    x0, top, x1, bottom = img["x0"], img["top"], img["x1"], img["bottom"]
                    cropped = page.within_bbox((x0, top, x1, bottom)).to_image(resolution=150)
                    image_name = f"image_{page_number}_{image_counter}.png"
                    image_path = os.path.join(image_output_dir, image_name)
                    cropped.save(image_path, format="PNG")
                    image_url = upload_to_imgbb(image_path)
                    placeholder = f"[IMAGE_{image_counter}]"
                    image_map[placeholder] = image_url
                    paragraphs.append(placeholder)
                    image_counter += 1

        text = "\n\n".join(paragraphs)

    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        raise ValueError(f"不支持的文件类型: {ext}")

    map_path = map_dir / f"{name}_image_map.json"
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(image_map, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存文件专属图片映射: {map_path}")
    return text, image_map


if __name__ == "__main__":
    test_files = [
        # "../data/test.txt ",
        # "../data/散文.docx",
        # "../data/散文2.docx",
        # "../data/散文3.docx",
        # "../data/散文4.docx",
        # "../data/散文6.docx",
        # "../data/常年法律顾问服务合同.docx",
        "../data/新疆维吾尔自治区中小学校校外供餐合同.pdf",
        # "../data/三国演义.txt"
        # "../data/罗兆燊 简历 (2).pdf"
    ]

    os.makedirs(output_dir, exist_ok=True)

    for file_path in test_files:
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            continue

        print(f"\n处理文件: {file_path}")
        text, image_map = extract_text_and_images_from_file(file_path)
        print("图片映射表：", image_map)

        chunks = split_paragraphs(text, chunk_size=2000)  # 每段最多2000字

        # 控制台输出
        for idx, chunk in enumerate(chunks, 1):
            print(f"Chunk {idx}:\t{chunk}")

        # 保存切分内容到同名txt中
        base_name = os.path.basename(file_path)
        name = os.path.splitext(base_name)[0]
        output_file = os.path.join(output_dir, f"{name}.txt")
        with open(output_file, "w", encoding="utf-8") as wf:
            for chunk in chunks:
                wf.write(chunk + "\n\n")  # 段落之间加空行

        print(f"已保存切分结果: {output_file}")
