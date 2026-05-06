import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# 加载环境变量
load_dotenv()

class LLMService:
    def __init__(self):
        # 统一使用 ChatOpenAI 接口，它能完美兼容所有支持 OpenAI 协议的国内大模型 API
        self.llm = ChatOpenAI(
            temperature=0.7,
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base=os.getenv("DEEPSEEK_API_BASE"),
            model_name=os.getenv("DEEPSEEK_MODEL_NAME", "gpt-3.5-turbo"),
            max_tokens=8192,   # 翻倍，足够放下77个单词完整图谱
            timeout=60         # 超时保护，再也不会卡死转圈
        )

    def test_connection(self, message: str) -> str:
        """测试大模型连通性"""
        messages =[
            SystemMessage(content="你是一个专业的英语私教Agent，你的任务是帮助用户高效背诵单词。"),
            HumanMessage(content=message)
        ]
        response = self.llm.invoke(messages)
        return response.content

# 实例化单例
llm_agent = LLMService()