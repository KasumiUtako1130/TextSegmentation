from text.Paragraph import split_paragraphs,extract_text_from_file
import os

if __name__ == "__main__":
    test_files = [
        # "data/test.txt",
        # "data/散文.docx",
        "data/常年法律顾问服务合同.docx",
    ]

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    for f in test_files:
        if not os.path.exists(f):
            print(f"⚠ 文件不存在: {f}")
            continue

        print(f"\n处理文件: {f}")
        text = extract_text_from_file(f)
        chunks = split_paragraphs(text, chunk_size=2000)  # 每段最多2000字

        # 控制台输出
        for idx, chunk in enumerate(chunks, 1):
            print(f"Chunk {idx}:\t{chunk}")