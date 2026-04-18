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

    if (!ocrText) {
      return json({ error: "missing ocr_text" }, 400);
    }

    const prompt = `
你是一个生活文件解读助手。请根据用户提供的 OCR 文本，输出严格 JSON，不要输出 markdown，不要输出解释文字。

返回格式必须是：
{
  "success": true,
  "document_type": "字符串",
  "one_line_summary": "字符串",
  "key_points": ["字符串"],
  "key_info": [{"label":"字符串","value":"字符串"}],
  "next_steps": ["字符串"],
  "risks": ["字符串"]
}

要求：
1. 只返回合法 JSON
2. key_points、key_info、next_steps、risks 必须是数组
3. 如果信息不足，也要返回合理的空数组
4. document_type 尽量使用：租房合同、电费账单、医疗单据、学校通知、其他
5. 内容使用简体中文
`;

    const completion = await client.chat.completions.create({
      model: process.env.QWEN_MODEL || "qwen-plus",
      temperature: 0.2,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: prompt },
        { role: "user", content: `OCR 文本如下：\n${ocrText}` }
      ]
    });

    const raw = extractTextContent(completion.choices?.[0]?.message?.content);

    if (!raw) {
      return json({ error: "empty model response" }, 502);
    }

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return json(
        {
          error: "model returned invalid json",
          raw
        },
        502
      );
    }

    return json({
      success: Boolean(parsed.success ?? true),
      document_type: parsed.document_type ?? "其他",
      one_line_summary: parsed.one_line_summary ?? "",
      key_points: Array.isArray(parsed.key_points) ? parsed.key_points : [],
      key_info: Array.isArray(parsed.key_info) ? parsed.key_info : [],
      next_steps: Array.isArray(parsed.next_steps) ? parsed.next_steps : [],
      risks: Array.isArray(parsed.risks) ? parsed.risks : []
    });
  } catch (error) {
    return json(
      {
        error: "analyze_failed",
        message: error instanceof Error ? error.message : String(error)
      },
      500
    );
  }
}
