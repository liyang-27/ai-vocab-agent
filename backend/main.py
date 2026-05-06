import os, json, re, shutil,hashlib 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from services.llm_service import llm_agent
from fastapi import UploadFile, File

from services.vision_service import vision_agent

from services.graph_rag_service import graph_rag_agent

load_dotenv()

# 创建 FastAPI 应用实例，设置 API 的标题和版本信息
app = FastAPI(title="AI Vocab Agent API", version="1.0.0")

# 配置 CORS 跨域（让前端能访问后端）

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
# 从环境变量中获取允许的 CORS 来源，默认是 http://localhost:5173（前端开发服务器地址），让这个地址可以访问后端 API。支持多个来源，使用逗号分隔。

# 添加 CORS 中间件，允许指定的来源访问 API，允许发送凭证（如 Cookie），允许所有 HTTP 方法和头部。这样前端就可以正常调用后端接口了，不会被浏览器的同源策略限制。
app.add_middleware(
    CORSMiddleware,            #FastAPI 官方提供的跨域中间件，用于解决浏览器跨域禁止访问问题
    allow_origins=["*"],     #允许的 CORS 来源列表，默认是 http://localhost:5173（前端开发服务器地址）
    allow_credentials=False,    #是否允许发送包含凭证的请求（如 Cookie、Authorization 头等），默认是 False
    allow_methods=["*"],      #允许的 HTTP 方法列表，使用 ["*"] 表示允许所有方法（GET、POST、PUT、DELETE 等）
    allow_headers=["*"],      #允许的 HTTP 头列表，使用 ["*"] 表示允许所有头（如 Content-Type、Authorization 等）
)

# ================= 数据库文件路径 =================
# 直接指定绝对物理路径，确保读取已有数据
#DATA_DIR = r"D:\My_Project\ai-vocab-agent\data"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)
# mkdir 会创建目录，exist_ok=True 表示如果目录已经存在则不抛出异常，这样第一次运行时会创建目录，后续运行时会直接使用这个目录，不会因为目录不存在而报错。

VOCAB_DB_PATH = os.path.join(DATA_DIR, "vocab_books.json")
CACHE_DB_PATH = os.path.join(DATA_DIR, "graph_cache.json")
RECORD_DB_PATH = os.path.join(DATA_DIR, "study_records.json")
GROUP_CACHE_PATH = os.path.join(DATA_DIR, "group_cache.json")
TEST_CACHE_PATH = os.path.join(DATA_DIR, "test_dict_cache.json")
TEST_RECORD_PATH = os.path.join(DATA_DIR, "test_records.json")

# 定义请求参数模型，用于接收前端发送的聊天消息
class ChatRequest(BaseModel):   
    # 定义一个字段 message，类型为 str，用于接收前端发送的聊天消息
    # 这是一个必填项，因为前端必须提供一个消息才能调用大模型接口
    message: str

# 定义接收前端请求数据结构，包含一个单词列表，用于生成 RAG 图谱数据
class GraphRequest(BaseModel):
    words: list[str]

# 定义请求参数模型，用于保存词汇本数据，包含书籍名称、单元名称和单词列表
class SaveVocabRequest(BaseModel):
    book_name: str
    unit_name: str
    words: list[str]

# 定义请求参数模型，用于生成单个词根的 RAG 图谱数据，包含词根名称、相关单词列表、书籍名称和单元名称（用于缓存键）
class RootGraphRequest(BaseModel):
    root_name: str
    words: list[str]
    book_name: str
    unit_name: str

# 定义请求参数模型，用于保存背诵记录与停留时长，前端会传入书籍名称、单元名称、总停留时间和每个单词的停留时间日志
class StudyRecord(BaseModel):
    book_name: str
    unit_name: str
    total_time_seconds: int
    word_time_log: dict

# 定义请求参数模型，用于生成测试词典，包含书籍名称、单元名称和单词列表
class TestDictRequest(BaseModel):
    book_name: str
    unit_name: str
    words: list[str]

# 定义请求参数模型，用于通过词向量（Embeddings）+ FAISS 实现毫秒级近义词召回，前端点击单词时触发全局向量检索
class SimilarWordRequest(BaseModel):
    word: str
# 从 JSON 文件加载数据，如果文件不存在则返回一个空字典
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# 将数据保存到 JSON 文件中，确保写入时使用 UTF-8 编码，并且格式化输出（indent=2）以便于阅读
def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 用于接收客户端上传的 Word 文档，提取其中的图片并调用 AI 进行解析，最终返回聚合后的单词数据结构
@app.post("/api/upload-word")
async def upload_word_document(file: UploadFile = File(...)):
    """接收前端上传的 Word 文件，提取所有图片并循环让 AI 解析聚合多单元单词"""
    # 接受参数名为 file 的上传文件，类型为 UploadFile，使用 File(...) 表示这是一个必填项
    try:
        # ========================= 实时日志：开始处理上传文件 =========================
        print("🔹 【后端进度】开始接收并处理上传的 Word 文件：", file.filename)

        # 1. 临时保存前端传来的文件
        # 使用f-string格式化字符串创建一个临时文件路径
        temp_file_path = f"temp_{file.filename}"

        # with 语句用于打开一个文件，并确保在使用完后正确关闭它
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print("🔹 【后端进度】文件已保存到临时路径：", temp_file_path)

        # 2. 提取 Word 中的图片 (Base64)
        print("🔹 【后端进度】开始从 Word 中提取图片...")
        images_base64 = vision_agent.extract_images_from_docx(temp_file_path)
        print("🔹 【后端进度】图片提取完成，共提取到图片数量：", len(images_base64))
        
        
        if not images_base64:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            print("🔴 【后端进度】Word 文档中没有找到任何图片，返回错误")
            return {"success": False, "error": "Word 文档中没有找到图片！"}
            
        # ============ 新增：聚合多个单元的数据 ============
        aggregated_data = {}
        total_words = 0
        
        # 3. 遍历所有的图片，而不是只处理下标 [17]
        print("🔹 【后端进度】开始循环解析所有图片...")
        for idx, b64_img in enumerate(images_base64):
            try:
                print(f"----------------------------------------------------")
                print(f"🔹 【后端进度】正在处理 第 {idx+1}/{len(images_base64)} 张图片")

                # 继续使用你验证过非常强大的 Vision 提取逻辑
                print(f"🔹 【后端进度】第 {idx+1} 张图片 → 调用AI视觉解析中...")
                ai_json_str = vision_agent.analyze_vocab_image(b64_img)
                print(f"🔹 【后端进度】第 {idx+1} 张图片 → AI返回成功，开始解析JSON")
                
                # 尝试解析 AI 返回的 JSON 字符串 (使用你原本的清理逻辑)
                clean_str = ai_json_str.replace("```json", "").replace("```", "").strip()
                parsed_data = json.loads(clean_str)
                print(f"🔹 【后端进度】第 {idx+1} 张图片 → JSON解析成功")
                
                # 提取 AI 识别出的单元名称和单词，若没有 unit 字段则兜底
                unit_name = parsed_data.get("unit", f"Unit {idx+1}")
                words = parsed_data.get("words",[])
                print(f"🔹 【后端进度】第 {idx+1} 张图片 → 识别单元：{unit_name}，识别单词数：{len(words)}")
                
                 # ===================== 重名 unit 自动编号（不合并） =====================
                base_unit = unit_name
                counter = 1
                # 如果重名，自动变成 Unit1(1)、Unit1(2)
                while unit_name in aggregated_data:
                    unit_name = f"{base_unit}({counter})"
                    counter += 1
                # ======================================================================

                # 把解析出来的单词加进去
                aggregated_data[unit_name] = []
                aggregated_data[unit_name].extend(words)
                # 对单元内的单词进行去重，防止 AI 提取出重复的词
                aggregated_data[unit_name] = list(set(aggregated_data[unit_name]))
                
                print(f"🟢 【后端进度】第 {idx+1} 张图片 → 处理完成！")

            except Exception as e:
                # 某一张图片解析失败不抛出整个异常，跳过它继续解析下一张
                print(f"🔴 【后端进度】第 {idx+1} 张图片解析失败: {str(e)}")
                continue
        
        print("🔹 【后端进度】所有图片循环处理完毕")

        # 4. 清理临时文件
        print("🔹 【后端进度】开始清理临时文件...")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print("🔹 【后端进度】临时文件已删除")
        
        # 5. 统计解析出来的总词数（前端展示需要）
        print("🔹 【后端进度】开始统计最终单词总数...")
        for u in aggregated_data:
            total_words += len(aggregated_data[u])
        print(f"🔹 【后端进度】最终统计：单元数={len(aggregated_data)}，总单词数={total_words}")
        
        # 返回满足最新前端要求的数据结构（包含 data 和 summary）
        print("🟢 【后端进度】全部流程执行成功，返回结果给前端！")
        return {
            "success": True, 
            "data": aggregated_data, 
            "summary": {"units": len(aggregated_data), "words": total_words},
            "message": "所有图片单词解析与聚合成功！"
        }
        
    except Exception as e:
        print("🔴 【后端进度】整体接口发生异常！错误信息：", str(e))
        if os.path.exists(f"temp_{file.filename}"):
            os.remove(f"temp_{file.filename}")
            print("🔴 【后端进度】异常情况下已清理临时文件")
        return {"success": False, "error": str(e)}

# 用于接收前端传入的单词数组，并生成基于 RAG 的知识图谱数据，这个接口是后续图谱生成的核心入口
@app.post("/api/generate-graph")
def generate_graph_endpoint(req: GraphRequest):
    """前端传入单词数组，后端生成基于 RAG 的知识图谱数据"""
    try:
        if not req.words:
            return {"success": False, "error": "单词列表不能为空"}
            
        graph_data = graph_rag_agent.generate_knowledge_graph(req.words)
        
        if "error" in graph_data:
            return {"success": False, "error": graph_data["error"]}
            
        return {"success": True, "data": graph_data}
    except Exception as e:
        return {"success": False, "error": str(e)}


    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 用于保存解析出的词汇到本地 JSON (模拟数据库)，前端会传入书籍名称、单元名称和单词列表
@app.post("/api/vocab/save")
def save_vocab(req: SaveVocabRequest):
    """保存解析出的词汇到本地 JSON (模拟数据库)"""
    db = load_json(VOCAB_DB_PATH)
    if req.book_name not in db:
        db[req.book_name] = {}
    db[req.book_name][req.unit_name] = req.words
    save_json(VOCAB_DB_PATH, db)
    return {"success": True, "message": "保存成功"}

# 用于获取所有词汇本及单元列表，返回一个包含书籍名称、单元名称和单词列表的嵌套数据结构
@app.get("/api/vocab/list")
def get_vocab_list():
    """获取所有词汇本及单元列表"""
    return {"success": True, "data": load_json(VOCAB_DB_PATH)}

# 用于接收前端传入的单词数组，并快速将单词按词根分组（第一步）
@app.post("/api/graph/group")
def group_roots(req: list[str]):
    """第一步：将单词按词根分组（引入哈希锁定缓存解决 AI 随机性导致的失效）"""
    try:
        # 将单词列表排序并拼接，生成唯一 MD5 哈希值作为缓存 Key
        words_str = ",".join(sorted(req))
        hash_key = hashlib.md5(words_str.encode('utf-8')).hexdigest()
        
        cache_db = load_json(GROUP_CACHE_PATH)
        
        # 如果这个单词列表曾经分过组，直接秒回历史分组，彻底锁定词根名称！
        if hash_key in cache_db:
            return {"success": True, "data": cache_db[hash_key]}
            
        # 如果是新单词列表，再调用大模型
        data = graph_rag_agent.group_words_by_root(req)
        cache_db[hash_key] = data
        save_json(GROUP_CACHE_PATH, cache_db)
        return {"success": True, "data": data}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
# 用于生成单个词根的详细 RAG 图谱数据，并带有缓存机制
@app.post("/api/graph/generate")
def generate_root_graph(req: RootGraphRequest):
    cache_db = load_json(CACHE_DB_PATH)
    cache_key = f"{req.book_name}_{req.unit_name}_{req.root_name}"
    
    # 优先读缓存
    if cache_key in cache_db:
        return {"success": True, "cached": True, "data": cache_db[cache_key]}
        
    try:
        data = graph_rag_agent.generate_single_root_graph(req.root_name, req.words)
        
        # >>> 修复核心漏洞：如果 AI 返回了报错，必须告诉前端 success=False，并拒绝缓存！ <<<
        if "error" in data:
            return {"success": False, "error": data["error"]}
            
        # 只有真正成功的图谱数据才存入缓存
        cache_db[cache_key] = data
        save_json(CACHE_DB_PATH, cache_db)
        
        return {"success": True, "cached": False, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 用于保存背诵记录与停留时长，前端会传入书籍名称、单元名称、总停留时间和每个单词的停留时间日志
@app.post("/api/record/save")
def save_study_record(req: StudyRecord):
    """保存背诵记录与停留时长"""
    db = load_json(RECORD_DB_PATH)
    # 生成唯一记录 ID
    record_id = f"{req.book_name}_{req.unit_name}_{len(db)}"
    db[record_id] = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    save_json(RECORD_DB_PATH, db)
    return {"success": True}

# 用于获取所有的背诵历史记录，返回一个列表，最新的记录在前面
@app.get("/api/record/list")
def get_study_records():
    """获取所有的背诵历史记录"""
    db = load_json(RECORD_DB_PATH)
    # 将字典转为列表并按时间/顺序倒序返回（最新的在前）
    records_list = [{"id": k, **v} for k, v in db.items()]
    records_list.reverse()
    return {"success": True, "data": records_list}

# 用于从 AI 返回的文本中提取 JSON 数据，增加了异常处理和日志输出，确保在解析失败时能得到清晰的错误信息
@app.post("/api/test/dictionary")
def generate_test_dictionary(req: TestDictRequest):
    """获取测试词典：优先从星状图缓存中‘偷取’数据，只有缺失的个别词才请求大模型"""
    try:
        cache_db = load_json(TEST_CACHE_PATH)
        cache_key = f"{req.book_name}_{req.unit_name}"
        
        # 1. 如果测试专用缓存已经齐了，直接 0 秒返回
        if cache_key in cache_db:
            return {"success": True, "data": cache_db[cache_key]}
            
        # 2. 从星状图缓存里“偷取”数据
        graph_cache_db = load_json(CACHE_DB_PATH)
        prefix = f"{req.book_name}_{req.unit_name}_"
        extracted_dict = {}
        
        for k, v in graph_cache_db.items():
            if k.startswith(prefix) and "nodes" in v:
                for node in v["nodes"]:
                    if node.get("category") == 1 and "info" in node:
                        # 确保提取时的单词没有多余空格
                        extracted_dict[node["name"].strip()] = node["info"]
                        
        # 3. 严格比对：到底还有哪些单词没有释义？
        missing_words =[w.strip() for w in req.words if w.strip() not in extracted_dict]
        
        # 如果全都有了，直接保存并返回
        if len(missing_words) == 0:
            cache_db[cache_key] = extracted_dict
            save_json(TEST_CACHE_PATH, cache_db)
            return {"success": True, "data": extracted_dict}
            
        # 4. 只有缺失的单词，才去请求大模型！防止一次性传几十个词导致卡死！
        print(f"\n⚠️ 测试字典缓存不全，准备调用大模型生成缺失的 {len(missing_words)} 个单词...")
        print(f"缺失名单: {missing_words}\n")
        
        data = graph_rag_agent.generate_test_dictionary(missing_words)
        
        if "error" not in data:
            # 将大模型刚生成的词和之前偷取出来的词合并在一起
            extracted_dict.update(data)
            cache_db[cache_key] = extracted_dict
            save_json(TEST_CACHE_PATH, cache_db)
            print("✅ 缺失词典生成完毕并合并成功！")
            return {"success": True, "data": extracted_dict}
            
        return {"success": False, "error": data["error"]}
        
    except Exception as e:
        print(f"❌ 测试词典生成发生代码错误: {str(e)}")
        return {"success": False, "error": str(e)}

# 用于保存测试记录与停留时长，前端会传入书籍名称、单元名称、总停留时间和每个单词的停留时间日志
@app.post("/api/record/test/save")
def save_test_record(req: StudyRecord): # 复用之前的结构体
    """保存测试记录与停留时长"""
    db = load_json(TEST_RECORD_PATH)
    record_id = f"TEST_{req.book_name}_{req.unit_name}_{len(db)}"
    db[record_id] = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    save_json(TEST_RECORD_PATH, db)
    return {"success": True}

# 用于获取所有的测试历史记录，返回一个列表，最新的记录在前面
@app.get("/api/record/test/list")
def get_test_records():
    """获取测试历史记录"""
    db = load_json(TEST_RECORD_PATH)
    records_list =[{"id": k, **v} for k, v in db.items()]
    records_list.reverse()
    return {"success": True, "data": records_list}

# 用于通过词向量（Embeddings）+ FAISS 实现毫秒级近义词召回，前端点击单词时触发全局向量检索
@app.post("/api/vocab/similar")
def get_similar_vocab(req: SimilarWordRequest):
    try:
        # 1. 扫描全书单词
        db = load_json(VOCAB_DB_PATH)
        all_book_words = set()
        for units in db.values():
            for words in units.values():
                for w in words: all_book_words.add(w.strip().lower())

        # 2. 调用【纯向量引擎】进行跨单元全书检索
        sim_words = graph_rag_agent.get_similar_words(req.word, list(all_book_words))
        
        # 3. 获取已有的中文释义映射
        graph_cache = load_json(CACHE_DB_PATH)
        test_cache = load_json(TEST_CACHE_PATH)
        global_word_map = {}
        
        def clean_def(d): 
            if not d: return "暂无"
            return str(d).split('；')[0].split(';')[0].split('，')[0].strip()

        for v in graph_cache.values():
            if "nodes" in v:
                for node in v["nodes"]:
                    if node.get("category") == 1:
                        global_word_map[node["name"].strip().lower()] = clean_def(node["info"].get("definition", ""))
        for v in test_cache.values():
            for w, info in v.items():
                if isinstance(info, dict):
                    global_word_map[w.strip().lower()] = clean_def(info.get("definition", ""))

        # 4. 组装结果与现场补全释义
        result_data =[]
        words_waiting_for_ai =[]

        for w in sim_words:
            if w in global_word_map:
                result_data.append({"word": w, "definition": global_word_map[w]})
            else:
                words_waiting_for_ai.append(w)

        # 5. 如果命中了“未背过的单元”里的单词，利用 AI 瞬间补全释义
        if words_waiting_for_ai:
            print(f"⌛ 正在为跨单元近义词 {words_waiting_for_ai} 补全释义...")
            temp_defs = graph_rag_agent.generate_test_dictionary(words_waiting_for_ai)
            
            for original_w in words_waiting_for_ai:
                info = None
                for k, v in temp_defs.items():
                    if k.strip().lower() == original_w:
                        info = v
                        break
                if info and isinstance(info, dict):
                    result_data.append({"word": original_w, "definition": clean_def(info.get("definition", "关联词汇"))})
                else:
                    result_data.append({"word": original_w, "definition": "词库已收录，暂无解析"})

        print(f"✅ 雷达最终下发数据: {result_data}")
        return {"success": True, "data": result_data}

    except Exception as e:
        print(f"❌ 相似词接口崩溃: {str(e)}")
        return {"success": False, "error": str(e)}
                                   
if __name__ == "__main__":
    import uvicorn

    # 启动 FastAPI 应用，监听在本地的 8000 端口，reload=False 表示不启用自动重载（适合生产环境）
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)