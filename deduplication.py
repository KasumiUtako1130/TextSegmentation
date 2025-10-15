import os
import json
import numpy as np
import sqlite3
from sentence_transformers import SentenceTransformer

# 加载本地模型
model = SentenceTransformer("./models/all-MiniLM-L6-v2")

# 数据库连接
conn = sqlite3.connect("./db/contracts.db")
cursor = conn.cursor()

# 建表
cursor.execute("""
               CREATE TABLE IF NOT EXISTS qa_pairs
               (
                   id
                   INTEGER
                   PRIMARY
                   KEY
                   AUTOINCREMENT,
                   context
                   TEXT,
                   question
                   TEXT,
                   answer
                   TEXT,
                   emb_context
                   TEXT,
                   emb_question
                   TEXT,
                   emb_answer
                   TEXT
               )
               """)
conn.commit()


# 相似度计算
def cosine_similarity(vec1, vec2):
    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


# 合并相似QA对
def insert_or_merge(context, question, answer, threshold_total=0.95, threshold_question=0.9):
    emb_context = model.encode(context)
    emb_question = model.encode(question)
    emb_answer = model.encode(answer)

    cursor.execute("SELECT id, context, question, answer, emb_context, emb_question, emb_answer FROM qa_pairs")
    rows = cursor.fetchall()
    for row in rows:
        row_id, old_ctx, old_que, old_ans, e_ctx_str, e_que_str, e_ans_str = row
        if not all([e_ctx_str, e_que_str, e_ans_str]):
            continue
        e_ctx = np.array(json.loads(e_ctx_str))
        e_que = np.array(json.loads(e_que_str))
        e_ans = np.array(json.loads(e_ans_str))

        sim_ctx = cosine_similarity(emb_context, e_ctx)
        sim_que = cosine_similarity(emb_question, e_que)
        sim_ans = cosine_similarity(emb_answer, e_ans)
        sim_total = 0.5 * sim_ctx + 0.3 * sim_que + 0.2 * sim_ans

        # 判断是否相似
        if sim_total > threshold_total and sim_que > threshold_question:
            print(f"🔁 检测到相似问答（context相似度 {sim_ctx:.2f}，question相似度 {sim_que:.2f}）: {question[:20]}...")

            # 保留旧内容 + 添加新差异部分
            merged_ctx = old_ctx
            merged_ans = old_ans

            # 仅在新文本中有独特内容时才合并，防止冗余
            if context not in old_ctx:
                merged_ctx += "\n" + context
            if answer not in old_ans:
                merged_ans += "\n" + answer

            cursor.execute("""
                           UPDATE qa_pairs
                           SET context=?,
                               answer=?,
                               emb_context=?,
                               emb_question=?,
                               emb_answer=?
                           WHERE id = ?
                           """, (
                               merged_ctx,
                               merged_ans,
                               json.dumps(model.encode(merged_ctx).tolist()),
                               json.dumps(model.encode(question).tolist()),
                               json.dumps(model.encode(merged_ans).tolist()),
                               row_id
                           ))
            conn.commit()
            print(f"✅ 已合并到已有问答：{old_que[:20]}...")
            return True

        # 如果没有相似问答，则直接插入新数据
        cursor.execute("""
                       INSERT INTO qa_pairs (context, question, answer, emb_context, emb_question, emb_answer)
                       VALUES (?, ?, ?, ?, ?, ?)
                       """, (
                           context, question, answer,
                           json.dumps(emb_context.tolist()),
                           json.dumps(emb_question.tolist()),
                           json.dumps(emb_answer.tolist())
                       ))
        conn.commit()
        print(f"🆕 已插入新问答: {question[:20]}...")
        return True


# 遍历 answer 文件夹
folder_path = "./answer"
for filename in os.listdir(folder_path):
    if filename.endswith(".json"):
        file_path = os.path.join(folder_path, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            context = item.get("context", "")
            question = item.get("question", "")
            answer = item.get("answer", "")
            insert_or_merge(context, question, answer)

print("所有问答对已处理完成！")
