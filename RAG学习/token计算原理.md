## 大模型 Token 计算原理、文本长度限制与超长文本处理方案（面试深度版）

在日常使用大模型 API 或本地部署时，Token 是最核心的计量单位。理解其原理和限制，是高效、稳定、低成本使用大模型的基础。

---

### 一、Token 的定义与分词原理

**Token**：大模型处理文本的最小语义单元。可以是一个完整的单词、一个单词的一部分、一个标点符号，甚至是一个字符（中文常见）。

> 模型并不直接认识字符，而是将输入文本切分成一串 Token ID（整数索引），然后映射为向量进行运算。

#### 1. 主流分词算法

| 算法 | 原理 | 代表模型 |
|------|------|----------|
| **BPE** (Byte Pair Encoding) | 从字符级开始，统计最频繁的相邻对，逐步合并为新的 subword token。支持任意未知词分解为子词。 | GPT 系列、RoBERTa |
| **WordPiece** | 类似 BPE，但合并时选择使训练数据似然增加最大的 pair（基于概率）。 | BERT、DistilBERT |
| **Unigram** | 从一个大的词表开始，逐步删除使损失最小的 token，保留最优子集。 | T5、XLNet |
| **SentencePiece** | 将输入视为 Unicode 字符序列（含空格），不依赖预分词，适合多语言。 | Llama、Mistral、Qwen |

#### 2. 不同模型的分词器差异（面试常见陷阱）

| 模型族 | 分词器 | 中文字符占比 | 特点 |
|--------|--------|--------------|------|
| GPT-4 (GPT-4o) | cl100k_base (BPE) | 约 1 token/汉字 | 中文长文本 token 消耗大 |
| Llama 3 | tiktoken + BPE | 约 0.6-0.8 token/汉字 | 对中文效率优于 GPT |
| Qwen (通义千问) | QwenTokenizer (BPE) | 约 0.7 token/汉字 | 针对中文优化 |
| Claude 3 | 未公开 BPE | 约 0.8 token/汉字 | – |

**注意**：相同的文本，不同分词器得到的 token 数量可能相差 20% 甚至更多。例如 “你好世界”：
- GPT-4：4 个汉字 ≈ 4 token
- Llama 3：约 3 token

#### 3. Token 计算原理举例（BPE）

以 `"I love you"` 为例（GPT-4 cl100k_base）：

1. 初始字符序列: `I` (空格) `l` `o` `v` `e` (空格) `y` `o` `u`
2. 查词表，最长的匹配：`"I"` token_id=40, `" love"` (含前导空格) token_id=1386, `" you"` token_id=764。
3. 最终 3 个 token。

对于未知词 `"chatgpt"`：
- 拆分为 `"chat"` + `"g"` + `"pt"` 或 `"ch"` + `"atgpt"`，取决于词表。

**面试点**：BPE 可以处理任何未知词（OOV），不会出现 `<UNK>`，这是它优于传统词级分词的地方。

---

### 二、Token 数量的计算方法

#### 1. 在线工具
- **OpenAI Tokenizer**：https://platform.openai.com/tokenizer
- **Anthropic Tokenizer**：仅限内部使用，但可用第三方镜像。

#### 2. 编程方式

**使用 tiktoken (OpenAI 官方)**
```python
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 分词器
text = "你好世界, this is a test."
tokens = enc.encode(text)
print(len(tokens))  # 输出 token 数量
print([enc.decode([t]) for t in tokens])   # 查看每个 token
```

**使用 transformers (HuggingFace)**
```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3-8B")
text = "Hello, how are you?"
tokens = tokenizer.encode(text)
print(len(tokens))
```

**注意**：`len(text)` 字符数 ≠ token 数。英文通常 1 token ≈ 0.75 单词，中文 1 汉字 ≈ 0.7~1 token。

#### 3. API 计费中的 Token 计算
- **OpenAI**：输入 token + 输出 token 分别计费。长上下文模型（如 GPT-4 Turbo）输入更贵，输出便宜。
- **提示词复用**：多轮对话时，每次请求需重新发送完整对话历史（包括系统提示），每次都会计算 token。

**优化技巧**：对频繁使用的系统提示，可以使用 **缓存前缀**（某些 API 支持）或手动压缩历史。

---

### 三、文本长度限制

#### 1. 为什么会有限制？

- **显存限制**：Transformer 自注意力需要存储 `n × n` 的注意力矩阵（尽管有 FlashAttention 优化，KV 缓存仍然与 n 成正比）。
- **计算复杂度**：O(n²) 的时间复杂度使得超长文本推理延迟线性增长（实际是平方增长）。
- **位置编码范围**：训练时的最大长度限制了位置编码（如 RoPE）能有效外推的范围。
- **工程实践**：API 服务商为了保证延迟和成本，会设定硬上限。

#### 2. 常见模型的长度限制（2025 年）

| 模型 | 最大 token 数（推理） | 备注 |
|------|----------------------|------|
| GPT-4o | 128K | 支持输出 16K |
| GPT-4 Turbo | 128K | 输入 128K，输出 4K-16K |
| GPT-3.5 Turbo | 16K | 部分版本 4K |
| Claude 3.5 Sonnet | 200K | 输出最多 4K |
| Gemini 1.5 Pro | 1M | 输出受限（8K） |
| Llama 3 8B/70B | 8K（原生），可扩至 32K | 通过 RoPE 外推 |
| Qwen 2.5 7B/72B | 128K | – |
| Mistral 7B v0.3 | 32K（滑动窗口） | 有效窗口约 32K |

**面试问题**：“为什么 GPT-4 输入可以 128K，输出却限制 4K？”  
→ 输出长度受限于推理时的 KV 缓存增长。生成每个 token 都要缓存该 token 的 KV，输出很长时，缓存膨胀。同时，避免用户滥用生成极长的胡说八道内容，平衡质量与成本。

#### 3. 超过限制会发生什么？
- **本地模型**：直接报错 `IndexError` 或 `CUDA out of memory`。
- **API 调用**：返回 `400 Bad Request` 错误，如 `"This model's maximum context length is 4096 tokens..."`。

---

### 四、超长文本处理方案（面试核心）

当单段文本超过模型上下文窗口时，不能直接输入，需要采用各种策略“压缩”或“拆分”文本。

#### 方案 1：简单截断（Truncation）

**策略**：
- 保留开头（对于摘要任务，信息常在开头）。
- 保留结尾（对于问答，答案可能在后半部分）。
- 保留开头 + 结尾（中间截断，加提示 “... [中间省略] ...”）。

**适用场景**：对长文本末尾部分依赖少，且可容忍信息丢失。

**代码示例**（截断到前 2000 token）：
```python
tokens = tokenizer.encode(long_text)
truncated_tokens = tokens[:2000]
truncated_text = tokenizer.decode(truncated_tokens)
```

#### 方案 2：滑动窗口（Sliding Window）

**原理**：将长文本分成多个重叠的块（chunk），分别输入模型获得中间结果，再合并。

**应用示例**：超长文档摘要
```python
chunk_size = 2000  # token
overlap = 200
chunks = [text[i:i+chunk_size] for i in range(0, len(tokens), chunk_size - overlap)]
summaries = [model.summarize(chunk) for chunk in chunks]
final_summary = model.summarize(" ".join(summaries))
```

**优点**：保留全貌。**缺点**：需要多次调用，成本高，且可能丢失跨块依赖。

#### 方案 3：MapReduce 方式

**原理**：将长文本拆分为块，每个块独立“回答”一个子问题，然后将所有块的答案合并成最终答案。

**典型场景**：长文档问答
```python
questions = ["文中提到了哪些技术？", "作者的主要观点是什么？"]
per_chunk_answers = []
for chunk in chunks:
    ans = model.answer(question, context=chunk)
    per_chunk_answers.append(ans)
final_answer = model.synthesize(per_chunk_answers)  # 合并答案
```

**优化**：可以用 **递归式 MapReduce**，先合并相邻 chunk 的答案，再逐渐缩小。

#### 方案 4：摘要与压缩（Summarization + Compression）

- **递归摘要**：先对每个小块生成摘要，然后将摘要拼接成新文本，再摘要，直到适合窗口。
- **提取式压缩**：使用 TF-IDF、TextRank 或小模型抽取关键句子，丢弃冗余。
- **LLMLingua**：使用小语言模型对提示词进行压缩，保留语义信息。

**示例**：500 页技术手册 → 先按页摘要 → 再摘要章节 → 最终 2000 token。

#### 方案 5：检索增强生成（RAG）

**核心思想**：不把整个长文本给模型，而是先用检索器（向量数据库 + 嵌入模型）找到与问题最相关的 3-10 个片段，只将这些片段放入上下文。

**优点**：
- 完美解决超长文本问题。
- 可同时处理海量文档（企业知识库）。
- 每个请求成本低。

**缺点**：
- 需要外部索引和质量好的嵌入模型。
- 可能遗漏未检索到的相关信息（召回率问题）。

**典型流程**：
```
用户问题 → 嵌入向量 → 向量数据库检索 → 返回 top-k 片段 → 拼接成提示 → LLM 生成答案
```

#### 方案 6：长上下文模型 + 位置外推

如果无法避免全文本输入，可以选择支持更长窗口的模型（如 Gemini 1.5 Pro 1M），并使用 **位置编码插值** 技术扩展本地模型。

**示例**：将 Llama 3（原生 8K）扩展到 32K：
```bash
# 使用 YaRN 或 NTK-aware 插值，仅需几百步微调
# 或用 transformers 的 scaling_factor 参数
model.config.rope_scaling = {"type": "linear", "factor": 4.0}
```

但注意：即使窗口大了，仍存在“迷失在中间”问题，超长文本中间的信息召回率可能很低。

#### 方案 7：外部记忆机制（MemGPT）

**原理**：模仿操作系统虚拟内存，将长文本分成“分页”，只保留当前需要的部分在上下文窗口（主存），将历史或未来的部分存储在外部向量库（磁盘），需要时动态加载。

**代表性项目**：MemGPT（https://github.com/cpacker/MemGPT）

**工作流**：
1. 模型对话时，将对话历史定期“归档”到外部存储。
2. 当模型发现需要回忆之前信息时，通过“函数调用”从外部检索并加载回窗口。
3. 窗口始终保持固定大小（如 8K）。

**优点**：理论上可处理无限长对话或文档。**缺点**：实现复杂，需要模型具有工具调用能力。

#### 方案 8：文本分片 + 并行处理（针对批任务）

对于离线分析（如整本书的情感分析），可以将书分成段落，每段独立分析，最后聚合统计。

**示例**：统计长文本中某个词汇的频率：
```python
from concurrent.futures import ThreadPoolExecutor

def count_word_in_chunk(chunk):
    return chunk.lower().count("target_word")

chunks = split_text_into_chunks(long_text, chunk_size=1000)
with ThreadPoolExecutor(max_workers=10) as executor:
    counts = executor.map(count_word_in_chunk, chunks)
total = sum(counts)
```

### 五、不同场景的推荐方案（决策表）

| 场景 | 推荐方案 | 理由 |
|------|----------|------|
| 单个极长文档（>200K）的摘要 | 递归摘要 | 保证全局连贯性 |
| 长文档问答（有具体问题） | RAG + 检索 | 最经济、准确率高 |
| 实时对话（无限轮次） | 滑动窗口 + 历史摘要 | 平衡记忆与成本 |
| 代码仓库分析 | 仓库级 RAG + 依赖图 | 只加载相关文件 |
| 法律合同全文审查 | 长上下文模型（如 200K）+ 重排序 | 要求不遗漏任何条款 |
| 低成本、低延迟要求 | 截断（保开头结尾） | 简单快速 |

---

### 六、面试常见问题与回答

#### Q1：什么是 Token？为什么不用字符或单词作为单位？

> “Token 是模型处理的最小单元，通常为 subword。单词数量太多（几十万），会面临 OOV 问题；字符序列太长，效率低。Subword 折中：常见词用单个 token，罕见词拆成更小的子词，既能覆盖任意文本，又不会使序列过长。”

#### Q2：如何估算一段文本的 Token 数？

> “英文：文本字符数 ÷ 4 约等于 token 数（因为一个 token 平均 4 字符）。中文：一个汉字约等于 0.7~1 token，具体取决于模型。精确计数需用 `tiktoken` 或对应分词器。”

#### Q3：假设你要实现一个处理 100 万字小说的 QA 系统，但模型上下文只有 8K，你会怎么做？

> “我会用 RAG 方案：先将小说分成 500 字左右的小块，用嵌入模型建立向量索引。用户提问后，检索最相关的 3-5 个块，将块内容拼接后发送给模型。如果模型需要跨章节推理（如角色关系），我会在检索时加入元数据过滤（如限定章节），或者提前用模型抽取整本书的角色关系图存入知识图谱。”

#### Q4：长文本截断时，保留开头和结尾一定比保留随机部分好吗？

> “不一定。对于故事类文本，结尾常包含高潮；对于技术文档，答案可能在中间。更好的做法是根据任务动态决定：摘要任务保留开头；开放式问答用 RAG；如果无法预判，可以多次截断不同位置并投票。”

#### Q5：滑动窗口与 RAG 有什么区别？各自优缺点？

> “滑动窗口是按顺序分割，且每个窗口都输入模型，适合需要全局视角（如摘要）。缺点：调用次数多、成本高。RAG 是按语义检索，只挑选相关窗口，适合问答。缺点：召回不全可能导致信息丢失。两者可以结合：先用 RAG 找出可能相关的窗口，再对窗口内进行滑动窗口分析。”

#### Q6：有没有可能让模型在有上下文窗口限制的情况下，处理无限长的文本？

> “理论上，通过外部记忆（如 MemGPT）可以做到，但实际效果受限于模型对记忆的访问能力。如果模型不能主动调用外部记忆，就会‘忘事’。另一种思路是使用状态空间模型（如 Mamba），其计算复杂度线性，理论上可处理无限长，但目前尚未广泛应用。”

---

### 七、总结速记表

| 概念 | 核心要点 |
|------|----------|
| **Token 定义** | 模型处理的最小单元，subword 级别 |
| **主流分词** | BPE（GPT）, WordPiece（BERT）, SentencePiece（Llama） |
| **Token 估算** | 英文：字符数/4；中文：1 汉字 ≈ 0.7-1 token |
| **长度限制原因** | 显存（O(n²) / KV 缓存）、位置编码、服务商成本 |
| **超长文本处理** | 截断、滑动窗口、MapReduce、递归摘要、RAG、MemGPT |
| **最佳实践** | 问答用 RAG，摘要用递归摘要，实时对话用滑动窗口+摘要 |

掌握以上内容，面试中关于 Token 和长度限制的问题可以做到既有深度又有实操方案。