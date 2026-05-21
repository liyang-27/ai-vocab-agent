import axios from 'axios';

// 创建 axios 实例，指向 FastAPI 的运行地址
const apiClient = axios.create({
  //baseURL: 'http://127.0.0.1:8000',
  // 改成你的 cpolar 后端地址
  baseURL: 'http://41265f78.r9.vip.cpolar.cn',

  headers: {
    'Content-Type': 'application/json',
  },
});

export const testLLM = async (message: string) => {
  const response = await apiClient.post('/api/test-llm', { message });
  return response.data;
};
// 上传 Word 文档的函数，接收一个 File 对象作为参数
export const uploadWord = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);

  // 发送 multipart/form-data 请求
  const response = await apiClient.post('/api/upload-word', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
};

// 生成知识图谱的函数，接收一个单词数组作为参数
export const generateGraph = async (words: string[]) => {
  const response = await apiClient.post('/api/generate-graph', { words });
  return response.data;
};

// 保存单词表的函数，接收书籍名称、单元名称和单词数组作为参数
export const saveVocab = async (book_name: string, unit_name: string, words: string[]) => {
  const res = await apiClient.post('/api/vocab/save', { book_name, unit_name, words });
  return res.data;
};

// 获取单词表的函数，接收书籍名称和单元名称作为参数
export const getVocabList = async () => {
  const res = await apiClient.get('/api/vocab/list');
  return res.data;
};

// 获取单词表的函数，接收书籍名称和单元名称作为参数
export const groupRoots = async (words: string[]) => {
  const res = await apiClient.post('/api/graph/group', words);
  return res.data;
};

// 生成根词图谱的函数，接收根词名称、单词数组、书籍名称和单元名称作为参数
export const generateRootGraph = async (root_name: string, words: string[], book_name: string, unit_name: string) => {
  const res = await apiClient.post('/api/graph/generate', { root_name, words, book_name, unit_name });
  return res.data;
};

// 保存学习记录的函数，接收书籍名称、单元名称、总学习时间和单词时间日志作为参数
export const saveStudyRecord = async (book_name: string, unit_name: string, total_time_seconds: number, word_time_log: Record<string, number>) => {
  const res = await apiClient.post('/api/record/save', { book_name, unit_name, total_time_seconds, word_time_log });
  return res.data;
};

// 获取学习记录的函数，不需要参数
export const getStudyRecords = async () => {
  const res = await apiClient.get('/api/record/list');
  return res.data;
};

// 生成测试词典的函数，接收书籍名称、单元名称和单词数组作为参数
export const generateTestDict = async (book_name: string, unit_name: string, words: string[]) => {
  const res = await apiClient.post('/api/test/dictionary', { book_name, unit_name, words });
  return res.data;
};

// 保存测试记录的函数，接收书籍名称、单元名称、总测试时间和单词时间日志作为参数
export const saveTestRecord = async (book_name: string, unit_name: string, total_time_seconds: number, word_time_log: Record<string, number>) => {
  const res = await apiClient.post('/api/record/test/save', { book_name, unit_name, total_time_seconds, word_time_log });
  return res.data;
};

// 获取测试记录的函数，不需要参数
export const getTestRecords = async () => {
  const res = await apiClient.get('/api/record/test/list');
  return res.data;
};

// 获取近义词的函数，接收一个单词作为参数
export const getSimilarWords = async (word: string) => {
  const res = await apiClient.post('/api/vocab/similar', { word });
  return res.data;
};

// 生成测试故事的函数，接收一个单词数组作为参数
export const generateTestStory = async (words: string[]) => {
  const res = await apiClient.post('/api/test/generate-story', words);
  return res.data;
};