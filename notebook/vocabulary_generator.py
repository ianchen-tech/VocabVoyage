# import os
import time
import json
# from openai import OpenAI
from vertexai.generative_models import GenerativeModel
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# OpenAI API金鑰
# client = OpenAI(
#     api_key = os.environ.get('OPENAI_API_KEY'),
# )

# 定義主題列表
topics = [
    # "Daily Life",
    # "Work & Career",
    # "Travel & Transportation",
    # "Food & Dining",
    # "Education & Learning",
    # "Technology & Digital",
    # "Health & Medical",
    # "Entertainment & Leisure",
    # "Environment & Nature",
    "Social Relationships"
]

# 用於儲存所有已生成的單字
generated_words = set()

def generate_vocabulary(topic):
    try:
        # 建立所有主題的字串，並標記當前主題
        all_topics_str = "\n".join([f"{'-> ' if t == topic else '   '}{t}" for t in topics])
        
        prompt = f"""I am creating vocabulary lists for the following topics:

{all_topics_str}

Currently generating words for: {topic}

Please generate 150 intermediate to upper-intermediate level English words or phrases specifically related to {topic}. Requirements:
1. Format: 'English word/phrase - Traditional Chinese translation (optional: word type)' on each new line
2. Words should be practical and commonly used
3. Include different word types (nouns, verbs, adjectives, phrases)
4. Make sure each word/phrase is:
   - Specifically relevant to the current topic "{topic}"
   - Not too general that it could appear in other topics
   - Unique and not repeated within this topic
5. For words that can be different parts of speech, indicate all possible uses
6. All Chinese translations must be in Traditional Chinese characters
7. Only provide the word list without any additional explanation or comments

Example format:
1. advocate - 提倡，倡導 (v.) / 擁護者，提倡者 (n.)
2. sustainable - 可持續的，永續的 (adj.)
3. ...
"""

        # response = client.chat.completions.create(
        #     model="gpt-4o",
        #     messages=[
        #         {"role": "system", "content": "You are a helpful English language teacher specializing in vocabulary. You understand the importance of generating topic-specific vocabulary that doesn't overlap with other topics."},
        #         {"role": "user", "content": prompt}
        #     ]
        # )
        # content = response.choices[0].message.content

        model = GenerativeModel('gemini-1.5-pro-001')
        response = model.generate_content(prompt)
        content = response.text
        
        # 提取新生成的單字（取英文部分）
        new_words = [line.split('-')[0].strip().lower() for line in content.split('\n') if '-' in line]
        
        # 檢查是否有重複的單字
        duplicates = set(new_words) & generated_words
        if duplicates:
            print(f"Warning: Found duplicate words in {topic}: {duplicates}")
        
        # 更新全局單字集
        generated_words.update(new_words)
        
        return content
        
    except Exception as e:
        print(f"Error generating vocabulary for {topic}: {str(e)}")
        return None

def save_to_file(topic, content):
    # 創建output資料夾（如果不存在）
    output_dir = Path("notebook/vocabulary_output")
    output_dir.mkdir(exist_ok=True)
    
    # 將主題名稱轉換為適合的檔案名稱
    filename = topic.lower().replace(" & ", "_").replace(" ", "_") + ".txt"
    file_path = output_dir / filename
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"Topic: {topic}\n")
            f.write(content)
        print(f"Successfully saved vocabulary for {topic}")
        # 儲存已生成的單字列表（用於除錯）
        debug_file = output_dir / "generated_words_list.json"
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump(list(generated_words), f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Error saving file for {topic}: {str(e)}")

def main():
    for topic in topics:
        print(f"Generating vocabulary for {topic}...")
        content = generate_vocabulary(topic)
        
        if content:
            save_to_file(topic, content)
            # 在每次請求之間暫停1秒，避免超過API速率限制
            time.sleep(1)
        else:
            print(f"Skipping {topic} due to generation error")
        
        # 顯示目前已生成的單字數量
        print(f"Total unique words/phrases generated so far: {len(generated_words)}")

if __name__ == "__main__":
    main()
