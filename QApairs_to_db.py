import sqlite3
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

os.makedirs("db", exist_ok=True)
db_path = "db/qa_data.db"

model = SentenceTransformer("models/all-MiniLM-L6-v2")

def encode_text(text: str):
    embedding = model.encode(text)
    return embedding.tolist()

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS qa_pairs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        context TEXT,
        question TEXT,
        answer TEXT,
        embedding TEXT,
        UNIQUE(context, question)
    )               
    """)
    conn.commit()
    return conn

def import_json(json_path):
    conn = init_db()
    cursor = conn.cursor()

    with open(json_path,"r",encoding="utf-8") as f:
        qa_list = json.load(f)

    inserted,skipped = 0,0

    for item in qa_list:
        context = item.get("context","")
        question = item.get("question","")
        answer = item.get("answer","")

        text_to_encode = context + " " + question
        embedding = encode_text(text_to_encode)
        embedding_str = json.dumps(embedding)

        try:
            cursor.execute(
                "INSERT OR IGNORE INTO qa_pairs(context, question, answer, embedding) VALUES (?, ?, ?, ?)",
                (context, question, answer, embedding_str)
            )
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"插入出错： {e}")

    conn.commit()
    conn.close()
    print(f"已成功导入 {inserted} 条数据,跳过{skipped}条重复数据，到数据库 {db_path}")

def search_similar(query: str, top_k: int = 5):
    """基于向量相似度搜索"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, context, question, answer, embedding FROM qa_pairs")
    rows = cursor.fetchall()
    conn.close()

    query_vec = np.array(encode_text(query))
    results = []

    for row in rows:
        emb = np.array(json.loads(row[4]))
        score = np.dot(query_vec, emb) / (np.linalg.norm(query_vec) * np.linalg.norm(emb))
        results.append((row[0], row[1], row[2], row[3], score))

    results.sort(key=lambda x: x[4], reverse=True)
    return results[:top_k]

if __name__ == "__main__":
    import_json("answer/新疆维吾尔自治区中小学校校外供餐合同.json")

    query = "该合同示范文本由新疆维吾尔自治区哪个部门制定？"
    results = search_similar(query, top_k=3)
    for r in results:
        print(f"\n[相似度: {r[4]:.4f}]")
        print(f"Context: {r[1]}")
        print(f"Q: {r[2]}")
        print(f"A: {r[3]}")