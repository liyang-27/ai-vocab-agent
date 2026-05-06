import os
import json
import re
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from services.llm_service import llm_agent
from dotenv import load_dotenv

load_dotenv()

class GraphRAGService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv("ZHIPU_API_KEY"),
            openai_api_base=os.getenv("ZHIPU_API_BASE"),
            model="embedding-2"
        )
        self.mock_corpus =[
            "To abandon oneself to despair is to ruin the future.",
            "He has a remarkable ability to learn new languages quickly.",
            "The weather in the mountains can be quite abnormal this time of year.",
            "We must abolish the outdated regulations.",
            "The new system runs in absolute synchrony."
        ]
        self.vector_store = FAISS.from_texts(self.mock_corpus, self.embeddings)

    def extract_json(self, text: str):
        """增强版 JSON 提取，专治大模型各种乱加格式的毛病"""
        # 1. 暴力清除 Markdown 标签
        clean_text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(clean_text)
        except:
            pass
            
        # 2. 截取法：精准定位第一个 { 和最后一个 }，丢弃所有废话
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = text[start:end+1]
                return json.loads(json_str)
        except Exception as e:
            print(f"JSON 解析彻底失败: {e}\n原始返回文本: {text}")
            
        return None

    def group_words_by_root(self, words: list[str]) -> dict:
        """
        第一步：将单词按词根分组（优化 prompt 版）
        """
    # 构建示例（Few-shot）
        examples = """
        示例1：
        单词: ["dictionary", "predict", "contradict", "apple", "banana", "portable"]
        正确输出：
        {
            "groups": [
                {"root": "dict (说)", "words": ["dictionary", "predict", "contradict"]},
                {"root": "未知词根", "words": ["apple", "banana"]},
                {"root": "port (搬运)", "words": ["portable"]}
            ]
        }

        示例2：
        单词: ["tendency", "tentative", "attend", "extend"]
        正确输出：
        {
            "groups": [
                {"root": "tend/tens/tent (伸展,趋向)", "words": ["tendency", "tentative", "attend", "extend"]}
            ]
        }
        """
        
        prompt = f"""
        你是一个英语词源学专家。请按以下规则对给定的单词列表进行词根分组。

        【规则】
        1. 识别每个单词的核心词根（通常来自拉丁语或希腊语），忽略前缀和后缀。
        2. 同一词根的单词应归为一组。词根名称使用“英语词根 (中文含义)”的格式，例如 "dict (说)", "scrib (写)", "spect (看)"。
        3. 如果某个单词的词根不明显或过于特殊，归入 "未知词根" 组。
        4. 必须严格按照 JSON 格式输出，不要输出任何额外解释。
        5. 如果一组里只有一个单词，允许保留该组，也可以放入“未知词根”。

        {examples}

        现在请对以下单词进行分组：
        单词: {words}

        输出 JSON：
        """
        response = llm_agent.llm.invoke([HumanMessage(content=prompt)])
        result = self.extract_json(response.content)
        
        # 兜底：如果解析失败或没有 groups 字段，返回一个默认分组
        if not result or "groups" not in result:
            return {"groups": [{"root": "默认词根", "words": words}]}
        
        # 可选：合并相同词根的组（防止 LLM 输出多个同义词根但名称略有不同）
        merged = {}
        for g in result["groups"]:
            root = g["root"]
            # 简单归一化：去除括号内容和尾部空格
            base_root = root.split("(")[0].strip()
            merged.setdefault(base_root, []).extend(g["words"])
        final_groups = [{"root": k, "words": list(set(v))} for k, v in merged.items()]
        
        return {"groups": final_groups}

    def generate_single_root_graph(self, root_name: str, words: list[str]) -> dict:
        """第二步：仅对当前选中的【单个词根】进行详细 RAG 分析与图谱生成"""
        # RAG 检索
        context_sentences = set()
        for word in words:
            docs = self.vector_store.similarity_search(word, k=1)
            for doc in docs:
                context_sentences.add(doc.page_content)
        rag_context = "\n".join(context_sentences)
        
        prompt = f"""
        你是一个知识图谱构建专家。请针对词根【{root_name}】及其包含的单词 {words} 生成详细解析。
        参考例句语料：{rag_context}
        
        要求返回 JSON，包含 nodes 和 links：
        1. 必须包含一个 "词根节点" (category: 0)，其 info 需包含：
           - origin (词根来源/含义深度解析)
        2. 必须包含若干 "单词节点" (category: 1)，其 info 需包含：
           - definition (释义)
           - phonetic (音标)
           - memory_trick (记忆法)
           - example (为每个单词生成一个自然、地道的英文例句，不要重复使用相同例句，并给出一个中文翻译)
        
        输出示例：
        {{
            "nodes":[
                {{"id": "root_1", "name": "{root_name}", "category": 0, "symbolSize": 40, "info": {{"origin": "源自拉丁语，意为..."}}}},
                {{"id": "word_1", "name": "单词", "category": 1, "symbolSize": 20, "info": {{"definition": "...", "phonetic": "...", "memory_trick": "...", "example": "..."}}}}
            ],
            "links":[ {{"source": "root_1", "target": "word_1"}} ]
        }}
        """
        response = llm_agent.llm.invoke([SystemMessage(content="只输出合法JSON"), HumanMessage(content=prompt)])
        result = self.extract_json(response.content)
        return result if result else {"error": "生成图谱失败"}

    def generate_test_dictionary(self, words: list[str]) -> dict:
        """为测试模式批量生成单元词典（支持前端瞬间展示释义）"""
        prompt = f"""
        你是一个英语测试专家。请为以下单词生成简明词典。
        单词列表: {words}
        
        必须输出纯 JSON 格式，不要任何多余文字或 Markdown 标记：
        {{
            "单词1": {{"definition": "中文释义", "phonetic": "音标", "example": "英文例句"}},
            "单词2": {{"definition": "中文释义", "phonetic": "音标", "example": "英文例句"}}
        }}
        """
        response = llm_agent.llm.invoke([SystemMessage(content="只输出合法JSON"), HumanMessage(content=prompt)])
        result = self.extract_json(response.content)
        return result if result else {"error": "生成词典失败"}

    def get_similar_words(self, target_word: str, all_book_words: list[str], top_k=5) -> list[str]:
        """
        大厂级抗干扰方案：LLM 极速本体展开 (Ontology Expansion) + 全书精准碰撞
        彻底抛弃容易受 BPE 分词污染的纯向量模型。
        """
        import os, json
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        ROOT_DIR = os.path.dirname(BASE_DIR)
        CACHE_PATH = os.path.join(ROOT_DIR, "data", "synonym_agent_cache.json")

        target_word = target_word.strip().lower()
        # 将全书词库转为哈希集合，查找速度 O(1)
        all_book_words_lower = {w.strip().lower() for w in all_book_words if w.strip()}

        # 1. 读取 Agent 联想缓存（实现 0 延迟）
        cache = {}
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                try: cache = json.load(f)
                except: pass

        # 2. 获取近义词簇
        if target_word in cache:
            synonyms = cache[target_word]
        else:
            print(f"🧠 触发 Agent 极速联想 (耗时约1秒): [{target_word}] ...")
            # 极简 Prompt，要求大模型只吐出 5 个单词，不废话，速度极快
            prompt = f"Give 5 exact English synonyms for the word '{target_word}'. Output ONLY the words separated by commas."
            try:
                from langchain_core.messages import HumanMessage
                response = llm_agent.llm.invoke([HumanMessage(content=prompt)])
                # 清洗输出（去掉句号，按逗号分割）
                clean_text = response.content.replace('.', '').replace('\n', '')
                synonyms =[w.strip().lower() for w in clean_text.split(',') if w.strip()]
                
                # 存入缓存
                cache[target_word] = synonyms
                with open(CACHE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False)
                print(f"   -> Agent 提供内核词: {synonyms}")
            except Exception as e:
                print(f"❌ Agent 联想失败: {e}")
                synonyms =[]

        # 3. 核心碰撞：只从用户的书架里，挑出命中的近义词！
        final_hits =[]
        for syn in synonyms:
            if syn in all_book_words_lower and syn != target_word:
                final_hits.append(syn)

        print(f"--- 🎯 精准碰撞结果: {final_hits} ---")
        return final_hits[:top_k]
        
graph_rag_agent = GraphRAGService()