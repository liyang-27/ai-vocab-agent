import base64
import json
import requests
from docx import Document
from langchain_core.messages import HumanMessage 
from services.llm_service import llm_agent
import os
from dotenv import load_dotenv
load_dotenv()
from langchain_openai import ChatOpenAI  



# 加载环境变量
load_dotenv()

class VisionService:
    def __init__(self):
        # 独立初始化“阿里云百炼 Qwen-VL-OCR”作为视觉 Agent，通过 OpenAI 兼容接口调用
        self.vision_llm = ChatOpenAI(
            temperature=0.1, # 提取任务温度设低一点，保证 JSON 格式更稳定
            openai_api_key=os.getenv("ZHIPU_API_KEY"),
            openai_api_base=os.getenv("ZHIPU_API_BASE"),
            model_name=os.getenv("ZHIPU_MODEL_NAME", "glm-4v-plus"),
            max_tokens=1024
        )
    def extract_images_from_docx(self, file_path: str) -> list[str]:  #self代表当前实例对象, file_path 参数是一个字符串，表示 Word 文档的文件路径，返回值是一个字符串列表，每个字符串都是一个图片的 Base64 编码。
        """
        从 Word 文档中提取所有图片
        按 视觉从上到下 顺序返回
        """
        doc = Document(file_path) #使用 python-docx 库打开指定路径的 Word 文档，创建一个 Document 对象来操作文档内容。
        images_with_pos = []  # 存放 (top坐标, 图片二进制)

        # ------------------------------------------------------
        # 遍历 段落 中的 内联图片（正常排版的图片）
        # ------------------------------------------------------
        for paragraph in doc.paragraphs: #遍历文档中的每个段落，paragraphs 属性返回一个段落对象的列表，每个段落对象代表文档中的一个段落。
            for run in paragraph.runs: #遍历段落中的每个 run，runs 属性返回一个 run 对象的列表，每个 run 对象代表段落中的一段连续文本或图片等元素。
                if run.element.xpath('.//a:blip'): #如果 run 对象包含一个 a:blip 元素，说明这是一个图片元素。
                    """
                    在 Word （本质是 XML）里：
                        一段文字 = paragraph
                        一段相同格式的文字 = run
                        图片不是文字，但会被 “包裹” 在一个 run 里
                        <a:blip>是Office 官方标准 XML 标签，全称：
                        a:blip = Binary Large Image Property（二进制大图属性）
                        所以：图片 = 一个特殊的 run，里面包含 <a:blip>
                    """
                    blips = run.element.xpath('.//a:blip') #获取 run 对象中的所有 a:blip 元素标签，返回一个列表，可能有多个图片。
                    for blip in blips:
                        try:
                            embed_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed') 
                            # http是固定命名空间，从 a:blip 元素标签中获取 embed 属性的值，这个值是一个 ID，用于在文档的关系中找到对应的图片数据。
                            img_part = doc.part.related_parts[embed_id]    #根据 embed_id 从文档的相关部分中找到对应的图片数据部分，related_parts 是一个字典，键是 embed_id，值是包含图片数据的对象。
                            img_bytes = img_part.blob          #从图片数据部分获取图片的二进制数据，blob 属性包含了图片的原始二进制内容。
                            rank = len(images_with_pos)  # 当前已经提取的图片数量，作为这张图片的排名，因为我们是按顺序提取的，所以越早提取的图片排名越靠前。
                            images_with_pos.append((rank, img_bytes)) #将图片的排名和二进制数据作为一个元组添加到 images_with_pos 列表中
                        except:
                            continue
        # 转 Base64
        base64_images = []
        for rank, img_bytes in images_with_pos:
            base64_str = base64.b64encode(img_bytes).decode("utf-8")
            base64_images.append(base64_str)

        return base64_images

    def analyze_vocab_image(self, base64_image: str) -> str:
        """调用 Vision Agent 识别图片中的单词，并进行初步结构化"""
        prompt = """
        你是一个专业的 OCR 和数据清洗 Agent。
        这张图片里包含了一组英语单词。请你提取图片中的所有英语单词。
        请按照 JSON 格式输出，格式如下（不要输出任何其他的 markdown 符号）：
        {
            "unit": "Unit X",
            "words": ["abandon", "ability", ...]
        }
        如果没有明确的单元信息，unit 字段请默认填写 "Unit 1"。
        """
        
        # 构造多模态消息体 (OpenAI Vision 规范)
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                }
            ]
        )
        
        # 复用之前初始化的 LLM 服务
        response = self.vision_llm.invoke([message])
        return response.content

vision_agent = VisionService()