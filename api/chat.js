import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.DASHSCOPE_API_KEY,
  baseURL:
    process.env.DASHSCOPE_BASE_URL ||
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
});

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" }
  });
}

function extractTextContent(content) {
  if (!content) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map(item => {
        if (typeof item === "string") return item;
        if (item?.type === "text") return item.text || "";
        return "";
      })
      .join("\n")
      .trim();
  }
  return "";
}

export async function POST(request) {
  try {
    const body = await request.json();
    const ocrText = body?.ocr_text?.trim();
    const question = body?.question?.trim();
    const history = Array.isArray(body?.history) ? body.history : [];

    if (!ocrText) {
      return json({ error: "missing ocr_text" }, 400);
    }

    if (!question) {
      return json({ error: "missing question" }, 400);
    }

    const messages = [
      {
        role: "system",
        content:
          "你是一个生活文件解读助手。基于 OCR 文本和已有对话，用简体中文给出清晰、可靠、简洁的回答。不要编造未出现的信息。"
      },
      {
        role: "user",
        content: `这是文件 OCR 原文：\n${ocrText}`
      },
      ...history
        .filter(item => item?.role && item?.content)
        .map(item => ({
          role: item.role === "assistant" ? "assistant" : "user",
          content: String(item.content)
        })),
      {
        role: "user",
        content: question
      }
    ];

    const completion = await client.chat.completions.create({
      model: process.env.QWEN_MODEL || "qwen-plus",
      temperature: 0.3,
      messages
    });

    const answer = extractTextContent(completion.choices?.[0]?.message?.content);

    if (!answer) {
      return json({ error: "empty model response" }, 502);
    }

    return json({ answer });
  } catch (error) {
    return json(
      {
        error: "chat_failed",
        message: error instanceof Error ? error.message : String(error)
      },
      500
    );
  }
}
