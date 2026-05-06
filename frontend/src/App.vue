// 这是 App.vue 的完整代码，包含了之前讨论的所有功能点和修复措施
// 注意：请确保你已经在 src/api.ts 中正确实现了与后端 FastAPI 的接口交互函数，如 uploadWord、saveVocab、getVocabList、groupRoots、generateRootGraph、saveStudyRecord 和 getStudyRecords。
// 另外，确保你已经安装了 echarts 和相关的 Vue 依赖，并在 main.ts 中正确引入了 App.vue。
// 这个组件实现了一个完整的词汇背诵系统，包含书架管理、单词图谱展示、专注度追踪和学习报告等功能。

// 引入 Vue 相关函数和 ECharts库，以及我们定义的 API 交互函数
<script setup lang="ts">

// ref = 定义一个“会变的数据”（比如数字、文字、开关）
// computed = 根据现有数据自动计算新数据
// nextTick = 等页面更新完了再执行（比如等图表渲染好了再绑定事件）
// onMounted = 网页一打开就自动执行的函数
// onUnmounted = 网页关闭时执行
// reactive = 定义一个“对象/复杂数据”（比如单词列表、配置）
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue';

// 导入 ECharts → 画知识图谱的库（词根/单词关系图）
import * as echarts from 'echarts';

// 导入我们定义的 API 交互函数，负责和后端 FastAPI 通信
import { uploadWord, saveVocab, getVocabList, groupRoots, generateRootGraph, saveStudyRecord, getStudyRecords, generateTestDict, saveTestRecord, getTestRecords, getSimilarWords} from './api';

// 定义视图状态类型和当前视图变量
type ViewState = 'home' | 'upload' | 'recite-setup' | 'recite-learning' | 'report' | 'history' | 'test-setup' | 'test-learning' | 'test-report';

// 当前显示的视图，初始为主页
const currentView = ref<ViewState>('home');

// ================= 全局状态 =================

//// 单词本列表（从后端读取）
const vocabBooks = ref<any>({});

// 页面一打开就加载书架数据
onMounted(async () => {
  const res = await getVocabList();
  if (res.success) vocabBooks.value = res.data;
});

// 学习历史记录（从后端读取）
const studyHistory = ref<any[]>([]);

// 测试用的单词字典和测试记录
const testHistory = ref<any[]>([]);

/**
 * 在 goTo 函数里拦截 history 视图
 * goTo ：页面切换的总控函数  
 * 作用：专门用来切换页面（首页 / 上传 / 背诵 / 历史）
 *       切换前会自动刷新对应页面需要的数据（比如单词本、学习记录）
 *       是整个项目最核心的“页面导航器”
 * 
 * @param view  要切换到的目标页面（比如 'home' 首页 / 'upload' 上传页）
 * @param book  可选参数（可以传也可以不传），用于切换页面时自动选中某个单词本
 * 
 * ViewState 是自定义的类型，限定只能传：home / upload / recite-setup / recite-learning / report / history
 */
const goTo = async (view: ViewState, book?: string) => {
  if (view === 'upload' || view === 'recite-setup' || view === 'test-setup' || view === 'home') {
    const res = await getVocabList();
    if (res.success) vocabBooks.value = res.data;
  }
  if (view === 'history') {
    const res1 = await getStudyRecords();
    if (res1.success) studyHistory.value = res1.data;
    const res2 = await getTestRecords(); // >>> 并发获取测试记录 <<<
    if (res2.success) testHistory.value = res2.data;
  }
  if (book) selectedBook.value = book;
  currentView.value = view;
};

// ================= 1. 上传与书架 =================
const isDragging = ref(false);  // 控制拖拽时的样式变化
const uploadLoading = ref(false); // 控制上传解析过程中的加载动画
const uploadStatus = ref(''); // 显示上传解析的状态提示（成功/失败/错误信息）
const parsedMultiUnits = ref<any>({}); // 存储解析后的单词（每个单元的单词列表）
const uploadSummary = ref({ units: 0, words: 0 }); // 统计解析结果（单元数、单词数）
const bookNameInput = ref('');  // 存储用户输入的单词本名称，准备保存到书架

/**
 * 处理【拖拽文件放下】的事件
 * 当用户把文件拖到网页上并松开时，触发这个函数
 * @param e DragEvent = 浏览器自带的拖拽事件对象（包含拖拽的文件信息）
 */
const handleDrop = async (e: DragEvent) => { 
  // 阻止默认拖拽行为（比如打开文件）
  e.preventDefault(); 

  // 关闭拖拽高亮样式（用户已经松开鼠标，不拖了）
  isDragging.value = false;  
  
  // 判断：如果用户拖拽的文件存在
  // ? 是可选链操作符，意思是“如果有值才继续，没有就不执行”，防止报错
  if (e.dataTransfer?.files?.length){
    // 取出第一个文件，交给 processFile 函数处理（上传+解析）
    await processFile(e.dataTransfer.files[0]); 
  }
};

/**
 * 处理【点击选择文件】的事件
 * 当用户在弹出的文件夹窗口中选择文件后，触发这个函数
 * @param e Event = 浏览器自带的事件对象
 */
const handleFileSelect = async (e: Event) => {
  // 把事件目标转成“文件输入框”类型（固定写法，为了拿到文件）
  const target = e.target as HTMLInputElement;

  // 如果用户选择了文件
  if (target.files?.length){
    // 取出第一个文件，交给 processFile 函数处理（上传+解析）
    await processFile(target.files[0]);
  }
};

/**
 * 【核心函数】处理文件：校验格式 → 显示加载 → 上传后端 → 接收结果
 * @param file File = 用户选择/拖拽的文件对象
 */
const processFile = async (file: File) => {
  // 如果文件名不是以 .docx 结尾，说明格式不对，直接提示用户并返回（不继续执行后面的上传解析逻辑）
  if (!file.name.endsWith('.docx')) { uploadStatus.value = "仅支持 .docx"; return; }
  uploadLoading.value = true;
  uploadStatus.value = '正在提取图片并合并分析多个单元，请稍候...';

  // 上传前先清空之前的解析结果，避免旧数据干扰新上传的显示
  parsedMultiUnits.value = {};
  
  //调用 api.ts 里的 uploadWord，把文件传给后端解析，等待结果返回
  try {
    const res = await uploadWord(file);
    if (res.success) {
      parsedMultiUnits.value = res.data;
      uploadSummary.value = res.summary;
      bookNameInput.value = file.name.replace('.docx', '');
      uploadStatus.value = `解析成功！包含 ${res.summary.units} 个单元，共 ${res.summary.words} 个单词。`;
    } else uploadStatus.value = '解析失败: ' + res.error;
  } catch (e) { uploadStatus.value = '网络异常'; }
  finally { uploadLoading.value = false; }
};

/**
 * 【保存单词本】按钮点击事件
 * 把解析好的所有单元单词，批量保存到后端
 */
const handleSaveVocab = async () => {
  if (!bookNameInput.value) return alert("请输入词汇本名称");

  // ========== 循环保存所有单元 ==========
  // Object.entries 把解析好的多单元对象转成 [单元名, 单词数组] 遍历
  for (const [unit, words] of Object.entries(parsedMultiUnits.value)) {
    await saveVocab(bookNameInput.value, unit, words as string[]);
  }
  alert("整本词汇本保存成功！");
  goTo('upload'); // 刷新书架
  parsedMultiUnits.value = {};
};

// ================= 2. 背诵系统 (数据与状态) =================
const selectedBook = ref(''); // 存储用户选择的单词本名称，准备背诵
const selectedUnit = ref(''); // 存储用户选择的单元名称，准备背诵
const rootGroups = ref<any[]>([]); // 存储当前单元的词根分组信息 any[] 表示“数组”，里面放一组一组的词根+单词
const currentRootIdx = ref(0); // 存储当前正在展示的词根分组的索引（默认从第一组开始）
const graphLoading = ref(false); // 控制词根图谱加载状态（显示转圈圈），避免用户在加载时点击导致错误
const loadingMessage = ref(''); // 存储加载状态的提示信息（比如“加载中...”）
const activeNodeInfo = ref<any>(null); // 存储当前点击的词根节点的信息（词根、相关单词列表）
const currentUnitWords = ref<string[]>([]); // 存储当前单元的所有单词列表，用于计算背诵进度和完成度
const preloadedGraphs = ref<Record<string, any>>({}); // >>> 新增：前端预加载缓存池，键是词根，值是对应的图谱数据
let isPreloading = false; // >>> 新增：控制是否正在预加载图谱，避免重复加载

// 埋点跟踪变量
const visitedWords = ref<Set<string>>(new Set()); // 存储用户点击过的单词，Set 是一种特殊的数据结构，自动去重，适合存储唯一值
const isPaused = ref(false); // 控制是否暂停背诵（点击暂停按钮）
const totalTimeSeconds = ref(0); // 记录用户背诵的总秒数（单位：秒）
let timerInterval: any = null; // 记时器，用于记录用户背诵的总秒数
const wordTimeLog = ref<Record<string, number>>({}); // 记录每个单词的专注时长（单位：秒）
let lastClickTime = Date.now(); // 记录上一次点击单词的时间戳，用于计算停留时长
let currentTrackedWord = ''; // 记录当前正在计时的单词（如果用户点击了一个单词，就把它记录下来，直到点击下一个单词或切换词根才停止计时）

let myChart: echarts.ECharts | null = null; // >>> 新增：echarts 实例，用于绘制专注时长图表
const chartRef = ref<HTMLElement | null>(null); // >>> 新增：图表容器的引用，用于挂载 echarts 实例

// 计算属性：根据用户选择的单词本，动态计算出该书下有哪些单元可供选择
const availableUnits = computed(() => selectedBook.value ? Object.keys(vocabBooks.value[selectedBook.value]) :[]);

// 格式化时间显示（秒 → 分钟+秒）
const formatTime = (sec: number) => `${Math.floor(sec / 60)}分${sec % 60}秒`;

// 开始背诵，进入专注学习界面
const startReciting = async () => {
  // 安全校验：如果用户没有选择书本或单元，直接返回，不执行后续逻辑
  if (!selectedBook.value || !selectedUnit.value) return;
  goTo('recite-learning');

  // 初始化计时与记录
  currentUnitWords.value = vocabBooks.value[selectedBook.value][selectedUnit.value];
  visitedWords.value.clear();
  wordTimeLog.value = {};
  preloadedGraphs.value = {}; // >>> 新增：清空上一次的预加载缓存 <<<
  totalTimeSeconds.value = 0;

  // 初始化计时与记录
  currentUnitWords.value = vocabBooks.value[selectedBook.value][selectedUnit.value];
  visitedWords.value.clear();
  wordTimeLog.value = {};
  totalTimeSeconds.value = 0;
  isPaused.value = false;
  lastClickTime = Date.now();
  currentTrackedWord = '';
  startTimer();

  // 加载第一个词根的图谱
  graphLoading.value = true;
  loadingMessage.value = '加载中...';

  // 从后端获取当前单元的词根分组信息（每组包含一个词根和相关单词列表）
  const res = await groupRoots(currentUnitWords.value);
  loadingMessage.value = '加载中...';
  if (res.success && res.data.groups) {
    rootGroups.value = res.data.groups;
    currentRootIdx.value = 0;
    if (rootGroups.value.length > 0) await loadGraphForRoot(0);
  }
  graphLoading.value = false;
};

// 计时器控制
const startTimer = () => {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => { 
    // 逻辑：如果没有暂停，且图谱没有在加载（转圈圈），才计入总专注时长
    if (!isPaused.value && !graphLoading.value) {
      totalTimeSeconds.value++; 
    }
  }, 1000);
};

// 暂停/继续背诵
const togglePause = () => {
  isPaused.value = !isPaused.value;
  if (!isPaused.value) lastClickTime = Date.now(); // 恢复时重置间隔基准
};

// 计算上一个单词的停留时间
const recordWordTime = () => {
  if (currentTrackedWord && !isPaused.value) {
    const now = Date.now();
    const duration = Math.round((now - lastClickTime) / 1000);
    wordTimeLog.value[currentTrackedWord] = (wordTimeLog.value[currentTrackedWord] || 0) + duration;
    lastClickTime = now;
  }
};

// 切换词根 (上一组/下一组)
const changeRoot = async (offset: number) => {
  /**
  * 功能：切换词根分组（点击 上一组 / 下一组 时执行）
  * @param offset 偏移量：传 -1 表示上一组，传 1 表示下一组
  * 比如：changeRoot(-1) → 上一组；changeRoot(1) → 下一组
  */
  const newIdx = currentRootIdx.value + offset; // 计算新的索引
  if (newIdx >= 0 && newIdx < rootGroups.value.length) {
    recordWordTime(); // 离开当前词根时记录
    currentTrackedWord = ''; // 切换词根不记录为某个单词的专注
    currentRootIdx.value = newIdx;
    await loadGraphForRoot(newIdx);
  }
};

// >>> 新增：后台静默预加载接下来 5 个词根图谱 <<<
const preloadNextRoots = async (startIndex: number) => {
  if (isPreloading) return; // 互斥锁：防止多个后台任务并发
  isPreloading = true;
  try {
    const maxIdx = Math.min(startIndex + 5, rootGroups.value.length - 1);
    for (let i = startIndex + 1; i <= maxIdx; i++) {
      const group = rootGroups.value[i];
      if (!preloadedGraphs.value[group.root]) {
         const res = await generateRootGraph(group.root, group.words, selectedBook.value, selectedUnit.value);
         if (res.success) {
           preloadedGraphs.value[group.root] = res.data;
         }
      }
    }
  } finally {
    isPreloading = false;
  }
};

// >>> 修改：前端优先读取缓存的无缝加载逻辑 <<<
const loadGraphForRoot = async (idx: number) => {
  const group = rootGroups.value[idx];
  activeNodeInfo.value = null; // 切换时先清空右侧卡片

  const processAndRender = async (graphData: any) => {
  
    // >>> 新增：前端防崩溃校验，发现数据不对直接弹窗警告并停止渲染 <<<
    if (!graphData || !graphData.nodes || !Array.isArray(graphData.nodes)) {
      alert("AI 生成的图谱数据错乱，请点击【下一组】或重新生成！");
      return;
    }

    await nextTick();
    renderChart(graphData);
    // 默认在右侧展示该词根的详细释义 (查找 category: 0 的节点)
    const rootNode = graphData.nodes.find((n: any) => n.category === 0);
    if (rootNode) {
      activeNodeInfo.value = { isRoot: true, name: rootNode.name, ...rootNode.info };
    }
    lastClickTime = Date.now(); // 图谱加载完重新计时
  };

  // 1. 判断缓存池是否命中
  if (preloadedGraphs.value[group.root]) {
    await processAndRender(preloadedGraphs.value[group.root]);
  } else {
    // 2. 未命中则显示 Loading 并请求后端
    graphLoading.value = true;
    try {
      const res = await generateRootGraph(group.root, group.words, selectedBook.value, selectedUnit.value);
      if (res.success) {
        preloadedGraphs.value[group.root] = res.data; // 存入缓存
        await processAndRender(res.data);
      }
    } finally {
      graphLoading.value = false;
    }
  }

  // 3. 渲染完成后，触发后台静默预加载
  preloadNextRoots(idx);
};

// 渲染 ECharts 及颜色逻辑
const renderChart = (graphData: any) => {
  if (!chartRef.value) return;
  if (myChart) myChart.dispose();
  
  myChart = echarts.init(chartRef.value);
  
  // 动态计算节点颜色
  // 1. 将 const 改为 let，把它变成一个可变的内部状态变量
  let currentNodes = graphData.nodes.map((node: any) => {
    if (node.category === 1) { // 单词节点
      const isVisited = visitedWords.value.has(node.name);
      return {
        ...node,
        itemStyle: { color: isVisited ? '#10b981' : '#6366f1' }, 
        symbolSize: isVisited ? 20 : 25 
      };
    }
    return { ...node, itemStyle: { color: '#ef4444' } }; // 词根红色
  });

  const option = {
    tooltip: { trigger: 'item' },
    animationDurationUpdate: 300, 
    series:[{
      type: 'graph', layout: 'force',
      data: currentNodes, // 2. 这里使用刚才存下来的 currentNodes
      links: graphData.links,
      roam: true, label: { show: true, fontSize: 18, fontWeight: 'bold' }, // 字号在这里也修改了
      force: { repulsion: 400, edgeLength: 100 },
      lineStyle: { color: 'source', width: 2, curveness: 0.2 }
    }]
  };
  myChart.setOption(option);

  // 监听点击事件
  myChart.on('click', (params: any) => {
    if (isPaused.value) return; 

    recordWordTime(); 
    
    if (params.data.category === 1) { // 点击单词
      const word = params.data.name;
      visitedWords.value.add(word);
      currentTrackedWord = word;
      lastClickTime = Date.now();
      
      currentNodes = currentNodes.map((n: any) => {
        if (n.name === word && n.category === 1) return { ...n, itemStyle: { color: '#10b981' }, symbolSize: 20 };
        return n;
      });
      myChart!.setOption({ series:[{ data: currentNodes }] });

      // >>> 1. 先用原本的图谱数据更新右侧卡片（瞬间渲染） <<<
      activeNodeInfo.value = { isRoot: false, name: word, ...params.data.info, similarWords: null };
      speakWord(word); 
      checkCompletion();

      // >>> 2. 异步触发纯向量检索获取近义词，完全不卡顿主线程 <<<
      getSimilarWords(word).then(res => {
        if (res.success && activeNodeInfo.value && activeNodeInfo.value.name === word) {
          activeNodeInfo.value.similarWords = res.data; // 拿到结果后追加到卡片里
        }
      });
    } else { // 点击词根
      currentTrackedWord = '';
      lastClickTime = Date.now();
      activeNodeInfo.value = { isRoot: true, name: params.data.name, ...params.data.info };
    }
  });
};

// 检查是否完成背诵
const checkCompletion = () => {
  if (visitedWords.value.size >= currentUnitWords.value.length) {
    setTimeout(() => {
      if (confirm("当前单元所有单词已点亮！是否结束本次背诵并查看报告？")) {
        finishRecitation();
      }
    }, 500);
  }
};

const finishRecitation = async () => {
  recordWordTime();
  if (timerInterval) clearInterval(timerInterval);
  await saveStudyRecord(selectedBook.value, selectedUnit.value, totalTimeSeconds.value, wordTimeLog.value);
  goTo('report');
};

// ================= 语音发音 (Web Speech API) =================
const speakWord = (text: string) => {
  if (!window.speechSynthesis) return;
  // 取消当前正在读的内容
  window.speechSynthesis.cancel();
  
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'en-US'; // 纯正美音
  utterance.rate = 0.9;     // 语速稍微放慢一点点，适合背诵
  window.speechSynthesis.speak(utterance);
};

onUnmounted(() => { if (timerInterval) clearInterval(timerInterval); });

// ================= 3. SRS 智能测试引擎 =================
const testQueue = ref<string[]>([]);
const currentTestWord = ref('');
const testDict = ref<Record<string, any>>({});
const showTestAnswer = ref(false); // 控制是否展示释义
const testStats = ref({ known: 0, unknown: 0 }); // 统计一次过和错误的数量

// 启动测试
const startTesting = async () => {
  if (!selectedBook.value || !selectedUnit.value) return;
  goTo('test-learning');
  
  const words = vocabBooks.value[selectedBook.value][selectedUnit.value];
  testQueue.value = [...words]; // 将单词装入队列
  
  // 初始化计时与追踪
  wordTimeLog.value = {};
  totalTimeSeconds.value = 0;
  isPaused.value = false;
  testStats.value = { known: 0, unknown: 0 };
  
  graphLoading.value = true;
  loadingMessage.value = '正在提取单元专属词典，马上开始测试 (约5秒)...';
  
  try {
    const res = await generateTestDict(selectedBook.value, selectedUnit.value, words);
    if (res.success) {
      testDict.value = res.data;
      nextTestWord(); // 抽取第一个词
      startTimer();   // 复用之前的计时器
    } else alert("生成词典失败，请重试！");
  } catch (e) { alert("网络异常"); }
  finally { graphLoading.value = false; }
};

// 下一个单词的流转
const nextTestWord = () => {
  if (testQueue.value.length === 0) {
    finishTest();
    return;
  }
  currentTestWord.value = testQueue.value[0];
  showTestAnswer.value = false; // 隐藏释义
  lastClickTime = Date.now();
  speakWord(currentTestWord.value); // 自动发音
};

// 核心判断逻辑 (认识 / 不认识)
const handleTestAnswer = (know: boolean) => {
  if (isPaused.value) return;
  
  // 1. 记录耗时
  const timeSpent = Math.round((Date.now() - lastClickTime) / 1000);
  wordTimeLog.value[currentTestWord.value] = (wordTimeLog.value[currentTestWord.value] || 0) + timeSpent;
  
  // 2. 队列处理
  if (know) {
    testQueue.value.shift(); // 认识：移除出列
    if (!showTestAnswer.value) testStats.value.known++; // 首次点击算一次过
  } else {
    const word = testQueue.value.shift()!;
    testQueue.value.push(word); // 不认识：推入队尾，稍后再次出现
    if (!showTestAnswer.value) testStats.value.unknown++; // 记录不认识次数
  }
  
  // 3. 展开释义供用户复习
  showTestAnswer.value = true;
};

// 点击“下一个”按钮继续
const confirmNextTestWord = () => {
  if (testQueue.value.length === 0) finishTest();
  else nextTestWord();
};

const finishTest = async () => {
  if (timerInterval) clearInterval(timerInterval);
  await saveTestRecord(selectedBook.value, selectedUnit.value, totalTimeSeconds.value, wordTimeLog.value);
  goTo('test-report');
};

</script>

<template>
  <div class="min-h-screen bg-slate-50 text-gray-800 font-sans">
    <!-- 顶栏 -->
    <header class="bg-white shadow-sm px-6 py-4 flex justify-between items-center">
      <h1 class="text-xl font-black text-indigo-700 cursor-pointer" @click="goTo('home')">🧠 AI Vocab Agent</h1>
      <nav class="space-x-4">
        <button @click="goTo('upload')" class="text-sm font-medium text-gray-600 hover:text-indigo-600">书架与上传</button>
        <button @click="goTo('recite-setup')" class="text-sm font-medium text-gray-600 hover:text-indigo-600">开始背诵</button>
      </nav>
    </header>

    <main class="max-w-6xl mx-auto p-6 mt-4">
      
      <!-- ================= 视图 1：主页 ================= -->
      <div v-if="currentView === 'home'" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 pt-10">
        <!-- 1. 书架与上传 -->
        <div @click="goTo('upload')" class="bg-white p-6 rounded-2xl shadow hover:shadow-lg cursor-pointer transition border-t-4 border-blue-500 text-center flex flex-col items-center justify-center h-full">
          <div class="text-5xl mb-4">📂</div>
          <h2 class="text-xl font-bold mb-2">书架与资源上传</h2>
          <p class="text-xs text-gray-500">上传单词图片解析为多单元词库</p>
        </div>
        <!-- 2. 沉浸式背诵 -->
        <div @click="goTo('recite-setup')" class="bg-white p-6 rounded-2xl shadow hover:shadow-lg cursor-pointer transition border-t-4 border-indigo-500 text-center flex flex-col items-center justify-center h-full">
          <div class="text-5xl mb-4">📖</div>
          <h2 class="text-xl font-bold mb-2">沉浸式背诵</h2>
          <p class="text-xs text-gray-500">词根星状图与 RAG 语料扩展</p>
        </div>
        <!-- 3. SRS 智能测试 (新增) -->
        <div @click="goTo('test-setup')" class="bg-white p-6 rounded-2xl shadow hover:shadow-lg cursor-pointer transition border-t-4 border-orange-500 text-center flex flex-col items-center justify-center h-full">
          <div class="text-5xl mb-4">🎯</div>
          <h2 class="text-xl font-bold mb-2">SRS 智能测试</h2>
          <p class="text-xs text-gray-500">间隔重复错词复盘，动态记忆测试</p>
        </div>
        <!-- 4. 历史记录 -->
        <div @click="goTo('history')" class="bg-white p-6 rounded-2xl shadow hover:shadow-lg cursor-pointer transition border-t-4 border-green-500 text-center flex flex-col items-center justify-center h-full">
          <div class="text-5xl mb-4">📈</div>
          <h2 class="text-xl font-bold mb-2">学习数据中心</h2>
          <p class="text-xs text-gray-500">查看历史记录与单词掌握情况</p>
        </div>
      </div>

      <!-- ================= 视图 2：上传与书架 ================= -->
      <div v-if="currentView === 'upload'" class="space-y-8">
        <!-- 书架展示 -->
        <div class="bg-white p-6 rounded-2xl shadow-sm">
          <h2 class="text-xl font-bold mb-4 flex items-center">📚 我的词汇书架</h2>
          <div v-if="Object.keys(vocabBooks).length === 0" class="text-gray-400 py-4 text-center">书架空空如也，请先上传资源。</div>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div v-for="(units, book) in vocabBooks" :key="book" @click="goTo('recite-setup', book as string)"
                 class="p-4 bg-gradient-to-br from-indigo-50 to-blue-50 rounded-xl border border-indigo-100 cursor-pointer hover:shadow-md transition">
              <div class="text-3xl mb-2">📘</div>
              <h3 class="font-bold text-gray-800 truncate">{{ book }}</h3>
              <p class="text-xs text-gray-500 mt-1">包含 {{ Object.keys(units).length }} 个单元</p>
            </div>
          </div>
        </div>

        <!-- 拖拽上传 -->
        <div class="bg-white p-8 rounded-2xl shadow-sm">
          <h2 class="text-xl font-bold mb-4">上传新书本 (批量提取多单元)</h2>
          <div @dragover.prevent="isDragging=true" @dragleave.prevent="isDragging=false" @drop="handleDrop"
             :class="['flex justify-center px-6 pt-10 pb-12 border-2 border-dashed rounded-xl cursor-pointer transition', isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400']">
            <div class="text-center">
              <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
              <label class="mt-4 flex text-sm justify-center">
                <span class="text-indigo-600 font-medium">点击或拖拽 Word (docx) 到此处</span>
                <input type="file" class="sr-only" accept=".docx" @change="handleFileSelect">
              </label>
              <p class="text-xs text-gray-400 mt-1">系统将自动提取多张图片并划分为不同单元</p>
            </div>
          </div>
          
          <div v-if="uploadLoading" class="mt-4 text-center text-indigo-600 animate-pulse">{{ uploadStatus }}</div>
          <div v-else-if="uploadStatus" class="mt-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm text-center font-medium">{{ uploadStatus }}</div>

          <div v-if="Object.keys(parsedMultiUnits).length > 0" class="mt-6 border-t pt-6">
            <label class="block text-sm font-medium text-gray-700 mb-2">为该词汇本命名并保存全部单元</label>
            <div class="flex gap-4">
              <input v-model="bookNameInput" type="text" class="flex-1 border-gray-300 rounded-md border p-2 focus:ring-indigo-500" placeholder="如：考研核心词汇"/>
              <button @click="handleSaveVocab" class="px-6 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 font-bold">批量保存</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ================= 视图 3：配置背诵 ================= -->
      <div v-if="currentView === 'recite-setup'" class="bg-white p-8 rounded-2xl shadow-sm max-w-md mx-auto">
        <h2 class="text-2xl font-bold mb-6 text-center">🎯 开始背诵</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">选择词汇本</label>
            <select v-model="selectedBook" class="w-full border p-3 rounded-md bg-gray-50 focus:ring-indigo-500">
              <option disabled value="">请选择书架上的书</option>
              <option v-for="(_, book) in vocabBooks" :key="book" :value="book">{{ book }}</option>
            </select>
          </div>
          <div v-if="selectedBook">
            <label class="block text-sm font-medium text-gray-700 mb-1">选择章节单元</label>
            <select v-model="selectedUnit" class="w-full border p-3 rounded-md bg-gray-50 focus:ring-indigo-500">
              <option disabled value="">请选择单元</option>
              <option v-for="unit in availableUnits" :key="unit" :value="unit">{{ unit }}</option>
            </select>
          </div>
          <button @click="startReciting" :disabled="!selectedUnit" class="w-full bg-gradient-to-r from-indigo-500 to-purple-600 disabled:from-gray-300 disabled:to-gray-400 text-white py-3 rounded-md hover:shadow-lg transition font-bold mt-4">
            🚀 开启专注背诵模式
          </button>
        </div>
      </div>

      <!-- ================= 视图 4：沉浸式背诵主界面 ================= -->
      <div v-if="currentView === 'recite-learning'" class="space-y-4">
        
        <!-- 顶控栏 (定时器、进度、控制) -->
        <div class="bg-white p-4 rounded-xl shadow-sm flex flex-wrap justify-between items-center gap-4">
          <div class="flex items-center space-x-6">
            <div class="text-indigo-800 font-bold bg-indigo-50 px-4 py-2 rounded-lg">
              ⏱ 专注用时: <span class="font-mono text-xl">{{ formatTime(totalTimeSeconds) }}</span>
            </div>
            <div class="text-gray-600 font-medium">
              🎯 进度: <span class="text-green-600">{{ visitedWords.size }}</span> / {{ currentUnitWords.length }}
            </div>
          </div>
          <div class="space-x-3">
            <button @click="togglePause" :class="['px-4 py-2 font-bold rounded-lg transition', isPaused ? 'bg-orange-500 text-white animate-pulse' : 'bg-gray-100 text-gray-700 hover:bg-gray-200']">
              {{ isPaused ? '▶ 继续背诵' : '⏸ 暂停专注' }}
            </button>
            <button @click="finishRecitation" class="px-4 py-2 bg-red-100 text-red-600 font-bold rounded-lg hover:bg-red-200 transition">
              ⏹ 结束并看报告
            </button>
          </div>
        </div>

        <!-- 词根切换栏 -->
        <div class="flex items-center justify-between bg-white p-4 rounded-xl shadow-sm">
          <button @click="changeRoot(-1)" :disabled="currentRootIdx === 0" class="px-3 py-1 bg-gray-100 rounded disabled:opacity-30">◀ 上一组</button>
          <div class="font-bold text-indigo-700">当前词根：{{ rootGroups[currentRootIdx]?.root }}</div>
          <button @click="changeRoot(1)" :disabled="currentRootIdx === rootGroups.length - 1" class="px-3 py-1 bg-gray-100 rounded disabled:opacity-30">下一组 ▶</button>
        </div>

        <!-- 主体图谱与解析 -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 relative">
          <!-- 暂停遮罩 -->
          <div v-if="isPaused" class="absolute inset-0 z-50 bg-white/60 backdrop-blur-sm flex items-center justify-center rounded-xl">
            <div class="text-2xl font-black text-gray-600 tracking-widest shadow-sm bg-white p-6 rounded-2xl">已暂停休息 ☕</div>
          </div>

          <!-- 左侧：图谱 -->
          <div class="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 p-4 h-[550px] relative">
            <div v-if="graphLoading" class="absolute inset-0 z-10 bg-white/80 flex flex-col items-center justify-center rounded-xl">
              <div class="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
            </div>
            <div class="absolute top-4 left-4 text-xs text-gray-400 z-10 space-y-1">
              <div class="flex items-center"><span class="w-3 h-3 bg-red-500 rounded-full mr-2"></span>母词根</div>
              <div class="flex items-center"><span class="w-3 h-3 bg-indigo-500 rounded-full mr-2"></span>未背单词</div>
              <div class="flex items-center"><span class="w-3 h-3 bg-green-500 rounded-full mr-2"></span>已掌握</div>
            </div>
            <div ref="chartRef" class="w-full h-full"></div>
          </div>

          <!-- 右侧：动态卡片 -->
          <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 h-[550px] overflow-y-auto">
            <div v-if="activeNodeInfo" class="animate-fade-in-up">
              <div class="border-b pb-4 mb-4">
                <span :class="['px-2 py-1 text-xs font-bold rounded mb-2 inline-block', activeNodeInfo.isRoot ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700']">
                  {{ activeNodeInfo.isRoot ? '🔍 核心词根解析' : '✅ 单词详情' }}
                </span>
                <h2 class="text-3xl font-black text-gray-900">{{ activeNodeInfo.name }}</h2>
                <div v-if="!activeNodeInfo.isRoot" class="flex items-center gap-4 mt-1">
                  <button 
                    @click="speakWord(activeNodeInfo.name)" 
                    class="p-2 rounded-full bg-indigo-100 hover:bg-indigo-200 transition text-indigo-600"
                    title="发音">
                      🔊
                  </button>
                  <p class="text-lg text-gray-500 font-mono">{{ activeNodeInfo.phonetic || '' }}</p>           
                </div>
              </div>

              <div v-if="activeNodeInfo.isRoot" class="space-y-4">
                <div>
                  <h4 class="text-xs font-bold text-gray-400 uppercase mb-2">📜 词源深度解析 (Origin)</h4>
                  <p class="text-gray-700 leading-relaxed bg-red-50 border-l-4 border-red-400 p-3 rounded-r">
                    {{ activeNodeInfo.origin || '源自拉丁语或希腊语，承载核心含义...' }}
                  </p>
                </div>
                <div class="p-4 bg-gray-50 rounded text-sm text-gray-500">
                  💡 提示：点击左侧蓝色的卫星节点，可查看基于该词根派生的具体单词。
                </div>
              </div>

              <div v-else class="space-y-5">
                <div>
                  <h4 class="text-xs font-bold text-gray-400 uppercase mb-1">🎯 释义</h4>
                  <p class="text-lg font-bold text-gray-800 bg-indigo-50 inline-block px-3 py-1 rounded">{{ activeNodeInfo.definition }}</p>
                </div>
                <div>
                  <h4 class="text-xs font-bold text-gray-400 uppercase mb-1">🧠 记忆法</h4>
                  <p class="text-gray-700 leading-relaxed bg-orange-50 border-l-4 border-orange-400 p-3 rounded-r">
                    {{ activeNodeInfo.memory_trick }}
                  </p>
                </div>
                <div>
                  <h4 class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">🔗 语义向量雷达 (FAISS Retrieval)</h4>
                  
                  <!-- 加载状态 -->
                  <div v-if="!activeNodeInfo.similarWords" class="text-sm text-indigo-400 animate-pulse flex items-center">
                    <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-indigo-500" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                    正在计算多维语义空间距离...
                  </div>
                  
                  <!-- 结果展示 -->
                  <div v-else-if="activeNodeInfo.similarWords.length > 0" class="flex flex-wrap gap-2">
                    <span 
                      v-for="item in activeNodeInfo.similarWords" 
                      :key="item.word" 
                      class="px-3 py-1 rounded-lg text-sm font-bold bg-green-50 text-green-700 border border-green-300 shadow-sm"
                    >
                      🎯 {{ item.word }} 
                      <span class="text-xs font-normal ml-1 text-green-600">{{ item.definition }}</span>
                    </span>
                  </div>
                  <div v-else class="text-sm text-gray-400">词库中暂无相近词汇，继续上传新书本丰富词库吧！</div>
                </div>
                <div>
                  <h4 class="text-xs font-bold text-gray-400 uppercase mb-1">📖 外刊 RAG 例句</h4>
                  <p class="text-gray-600 italic leading-relaxed border-l-4 border-gray-300 pl-3">
                    "{{ activeNodeInfo.example }}"
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ================= 视图 5：背诵记录/报告 ================= -->
      <div v-if="currentView === 'report'" class="bg-white p-8 rounded-2xl shadow-sm max-w-3xl mx-auto">
        <h2 class="text-3xl font-black text-indigo-900 mb-6 text-center">🏆 本次背诵分析报告</h2>
        
        <div class="grid grid-cols-2 gap-4 mb-8">
          <div class="bg-indigo-50 p-6 rounded-xl text-center">
            <div class="text-sm text-indigo-600 font-bold mb-1">专注总时长</div>
            <div class="text-3xl font-black text-indigo-900">{{ formatTime(totalTimeSeconds) }}</div>
          </div>
          <div class="bg-green-50 p-6 rounded-xl text-center">
            <div class="text-sm text-green-600 font-bold mb-1">掌握单词数</div>
            <div class="text-3xl font-black text-green-900">{{ visitedWords.size }} / {{ currentUnitWords.length }}</div>
          </div>
        </div>

        <h3 class="text-lg font-bold border-b pb-2 mb-4">埋点追踪：各单词停留时长</h3>
        <div class="max-h-64 overflow-y-auto pr-2 space-y-2">
          <div v-for="(sec, word) in wordTimeLog" :key="word" class="flex justify-between items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100">
            <span class="font-bold text-gray-700">{{ word }}</span>
            <span class="text-sm font-medium text-gray-500">{{ sec }} 秒</span>
          </div>
          <div v-if="Object.keys(wordTimeLog).length === 0" class="text-center text-gray-400 py-4">无单词点击记录</div>
        </div>

        <div class="mt-8 flex justify-center gap-4">
          <button @click="goTo('home')" class="px-6 py-3 bg-gray-200 text-gray-700 rounded-lg font-bold hover:bg-gray-300">返回主页</button>
          <button @click="goTo('recite-setup')" class="px-6 py-3 bg-indigo-600 text-white rounded-lg font-bold hover:bg-indigo-700">继续背下一单元</button>
        </div>
      </div>

      <!-- ================= 视图 6：历史记录大厅 ================= -->
      <div v-if="currentView === 'history'" class="bg-white p-8 rounded-2xl shadow-sm max-w-4xl mx-auto">
        <h2 class="text-2xl font-bold mb-6 flex items-center justify-between">
          <span>📈 历史背诵记录</span>
          <button @click="goTo('home')" class="text-sm text-indigo-600 hover:underline">返回主页</button>
        </h2>
        
        <div v-if="studyHistory.length === 0" class="text-gray-400 text-center py-10">暂无背诵记录，快去背单词吧！</div>
        
        <div class="space-y-4">
          <div v-for="record in studyHistory" :key="record.id" class="border border-gray-200 p-5 rounded-xl hover:shadow-md transition">
            <div class="flex justify-between items-center border-b pb-2 mb-3">
              <h3 class="font-bold text-lg text-indigo-900">{{ record.book_name }} - {{ record.unit_name }}</h3>
              <span class="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-xs font-bold">总专注时长: {{ formatTime(record.total_time_seconds) }}</span>
            </div>
            <!-- 简单展示耗时最长的3个难点词 -->
            <div class="text-sm text-gray-600">
              <span class="font-bold text-gray-700">重点关注单词(耗时前三): </span>
              <span v-for="word in Object.entries(record.word_time_log || {}).sort((a,b)=> (b[1] as number)-(a[1] as number)).slice(0,3)" :key="word[0]" class="mr-3 bg-red-50 text-red-600 px-2 py-0.5 rounded">
                {{ word[0] }} ({{ word[1] }}s)
              </span>
            </div>
          </div>
        </div>
      </div>
      <!-- ================= 视图 7：配置测试 ================= -->
      <div v-if="currentView === 'test-setup'" class="bg-white p-8 rounded-2xl shadow-sm max-w-md mx-auto mt-10">
        <h2 class="text-2xl font-bold mb-6 text-center text-orange-600">🎯 配置智能测试</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">选择要测试的词汇本</label>
            <select v-model="selectedBook" class="w-full border p-3 rounded-md bg-gray-50 focus:ring-orange-500">
              <option disabled value="">请选择书架上的书</option>
              <option v-for="(_, book) in vocabBooks" :key="book" :value="book">{{ book }}</option>
            </select>
          </div>
          <div v-if="selectedBook">
            <label class="block text-sm font-medium text-gray-700 mb-1">选择单元</label>
            <select v-model="selectedUnit" class="w-full border p-3 rounded-md bg-gray-50 focus:ring-orange-500">
              <option disabled value="">请选择单元</option>
              <option v-for="unit in availableUnits" :key="unit" :value="unit">{{ unit }}</option>
            </select>
          </div>
          <button @click="startTesting" :disabled="!selectedUnit" class="w-full bg-gradient-to-r from-orange-400 to-red-500 disabled:from-gray-300 disabled:to-gray-400 text-white py-3 rounded-md hover:shadow-lg transition font-bold mt-4">
            进入测试模式
          </button>
        </div>
      </div>

      <!-- ================= 视图 8：测试主界面 (闪卡) ================= -->
      <div v-if="currentView === 'test-learning'" class="space-y-6 max-w-3xl mx-auto mt-6">
        
        <!-- 测试顶控栏 -->
        <div class="bg-white p-4 rounded-xl shadow-sm flex flex-wrap justify-between items-center gap-4 border-t-4 border-orange-500">
          <div class="flex items-center space-x-6">
            <div class="text-orange-800 font-bold bg-orange-50 px-4 py-2 rounded-lg">
              ⏱ 测验用时: <span class="font-mono text-xl">{{ formatTime(totalTimeSeconds) }}</span>
            </div>
            <div class="text-gray-600 font-medium bg-gray-50 px-4 py-2 rounded-lg">
              队列剩余: <span class="text-orange-600 font-black text-xl">{{ testQueue.length }}</span> 词
            </div>
          </div>
          <div class="space-x-3">
            <button @click="togglePause" :class="['px-4 py-2 font-bold rounded-lg transition', isPaused ? 'bg-orange-500 text-white animate-pulse' : 'bg-gray-100 text-gray-700 hover:bg-gray-200']">
              {{ isPaused ? '▶ 继续测试' : '⏸ 暂停' }}
            </button>
            <button @click="finishTest" class="px-4 py-2 bg-red-100 text-red-600 font-bold rounded-lg hover:bg-red-200 transition">
              ⏹ 提前交卷
            </button>
          </div>
        </div>

        <!-- 闪卡主体 -->
        <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-10 min-h-[450px] flex flex-col relative overflow-hidden">
          
          <!-- Loading 与暂停遮罩 -->
          <div v-if="graphLoading" class="absolute inset-0 z-20 bg-white/95 flex flex-col items-center justify-center">
            <div class="w-12 h-12 border-4 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
            <span class="mt-6 text-orange-700 font-bold text-lg animate-pulse">{{ loadingMessage }}</span>
          </div>
          <div v-if="isPaused" class="absolute inset-0 z-10 bg-white/60 backdrop-blur-sm flex items-center justify-center">
            <div class="text-2xl font-black text-gray-600 tracking-widest shadow-sm bg-white p-6 rounded-2xl">已暂停休息 ☕</div>
          </div>

          <!-- 单词展示区 -->
          <div class="flex-1 flex flex-col items-center justify-center text-center">
            <h1 class="text-6xl md:text-7xl font-black text-gray-800 tracking-tight cursor-pointer hover:text-indigo-600 transition-colors" @click="speakWord(currentTestWord)">
              {{ currentTestWord }}
            </h1>
            <p v-if="showTestAnswer && testDict[currentTestWord]?.phonetic" class="text-xl text-gray-400 font-mono mt-4">
              {{ testDict[currentTestWord]?.phonetic }}
            </p>
          </div>

          <!-- 底部交互区 (分两种状态) -->
          <div class="mt-8 border-t border-gray-100 pt-8">
            
            <!-- 状态 A：还没给出答案，显示认识/不认识按钮 -->
            <div v-if="!showTestAnswer" class="flex justify-center gap-6 md:gap-12">
              <button @click="handleTestAnswer(true)" class="flex-1 max-w-[200px] py-4 bg-green-50 text-green-600 border-2 border-green-500 rounded-2xl font-black text-xl hover:bg-green-500 hover:text-white transition-all transform hover:scale-105 shadow-sm">
                ✅ 认识
              </button>
              <button @click="handleTestAnswer(false)" class="flex-1 max-w-[200px] py-4 bg-red-50 text-red-600 border-2 border-red-500 rounded-2xl font-black text-xl hover:bg-red-500 hover:text-white transition-all transform hover:scale-105 shadow-sm">
                ❌ 不认识
              </button>
            </div>

            <!-- 状态 B：已经点击，显示释义与例句，并提供“下一个”按钮 -->
            <div v-else class="animate-fade-in-up">
              <div class="space-y-4 mb-8">
                <div>
                  <h4 class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">🎯 释义</h4>
                  <p class="text-xl font-bold text-gray-800 bg-orange-50 inline-block px-4 py-2 rounded-lg">
                    {{ testDict[currentTestWord]?.definition || '暂无释义' }}
                  </p>
                </div>
                <div v-if="testDict[currentTestWord]?.memory_trick">
                  <h4 class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">🧠 记忆法/词源</h4>
                  <p class="text-gray-700 bg-gray-50 border-l-4 border-gray-300 p-3 rounded-r text-sm">
                    {{ testDict[currentTestWord]?.memory_trick }}
                  </p>
                </div>
                <div v-if="testDict[currentTestWord]?.example">
                  <h4 class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">📖 例句</h4>
                  <p class="text-gray-600 italic border-l-4 border-indigo-300 pl-3">
                    "{{ testDict[currentTestWord]?.example }}"
                  </p>
                </div>
              </div>
              
              <button @click="confirmNextTestWord" class="w-full py-4 bg-gradient-to-r from-orange-500 to-red-500 text-white rounded-xl font-black text-xl hover:shadow-lg transition-all">
                下一个单词 👉
              </button>
            </div>
          </div>
          
        </div>
      </div>

      <!-- ================= 视图 9：测试复盘报告 ================= -->
      <div v-if="currentView === 'test-report'" class="bg-white p-8 rounded-2xl shadow-sm max-w-3xl mx-auto mt-10">
        <h2 class="text-3xl font-black text-orange-600 mb-6 text-center">🎯 本次测试复盘报告</h2>
        
        <div class="grid grid-cols-3 gap-4 mb-8">
          <div class="bg-gray-50 p-6 rounded-xl text-center border border-gray-100">
            <div class="text-sm text-gray-500 font-bold mb-1">测验总耗时</div>
            <div class="text-3xl font-black text-gray-800">{{ formatTime(totalTimeSeconds) }}</div>
          </div>
          <div class="bg-green-50 p-6 rounded-xl text-center border border-green-100">
            <div class="text-sm text-green-600 font-bold mb-1">一遍过 (熟练)</div>
            <div class="text-3xl font-black text-green-700">{{ testStats.known }}</div>
          </div>
          <div class="bg-red-50 p-6 rounded-xl text-center border border-red-100">
            <div class="text-sm text-red-600 font-bold mb-1">反复记 (生疏)</div>
            <div class="text-3xl font-black text-red-700">{{ testStats.unknown }}</div>
          </div>
        </div>

        <h3 class="text-lg font-bold border-b pb-2 mb-4">测试难点词排行 (耗时最长)</h3>
        <div class="max-h-64 overflow-y-auto pr-2 space-y-2">
          <!-- 按照耗时从大到小排序显示 -->
          <div v-for="[word, sec] in Object.entries(wordTimeLog).sort((a,b)=> b[1]-a[1])" :key="word" class="flex justify-between items-center p-3 bg-gray-50 rounded-lg hover:bg-orange-50">
            <div>
              <span class="font-bold text-gray-800 text-lg mr-3">{{ word }}</span>
              <span class="text-sm text-gray-500">{{ testDict[word]?.definition }}</span>
            </div>
            <span class="text-sm font-black text-orange-500 bg-orange-100 px-3 py-1 rounded-full">{{ sec }} 秒</span>
          </div>
        </div>

        <div class="mt-8 flex justify-center gap-4">
          <button @click="goTo('history')" class="px-6 py-3 bg-gray-200 text-gray-700 rounded-lg font-bold hover:bg-gray-300 transition">查看全局记录</button>
          <button @click="goTo('home')" class="px-6 py-3 bg-orange-500 text-white rounded-lg font-bold hover:bg-orange-600 transition shadow-md">返回首页</button>
        </div>
      </div>
    </main>
  </div>
</template>

<style>
.animate-fade-in-up { animation: fadeInUp 0.4s ease-out; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
</style>