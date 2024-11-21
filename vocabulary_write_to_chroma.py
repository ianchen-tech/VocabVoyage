from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
import os

def load_vocabulary_files():
    documents = []
    vocab_dir = "notebook/vocabulary_output"
    
    # 遍歷vocabulary_output目錄下的所有.txt文件
    for filename in os.listdir(vocab_dir):
        if filename.endswith(".txt"):
            file_path = os.path.join(vocab_dir, filename)
            
            # 讀取文件內容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 從文件名中提取主題（移除.txt後綴）
            topic = filename.replace('.txt', '')
            
            # 創建 Document 對象
            doc = Document(
                page_content=content,
                metadata={"topic": topic}
            )
            documents.append(doc)
    
    return documents

def main():
    # 載入詞彙文件
    documents = load_vocabulary_files()
    
    # 創建向量存儲
    vectorstore = Chroma.from_documents(
        documents=documents,
        collection_name="vocabulary_v1",
        embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        persist_directory="./chroma_db"
    )
    
    print(f"Successfully processed {len(documents)} vocabulary files")

if __name__ == "__main__":
    main()