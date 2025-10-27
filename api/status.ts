import { kv } from "@vercel/kv";
import type { VercelRequest, VercelResponse } from "@vercel/node";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  try {
    const data = await kv.get<string>("macro:latest");
    if (!data) return res.status(404).json({ error: "No snapshot yet. Run /api/compute." });
    return res.status(200).setHeader("Cache-Control", "no-store").send(data);
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || "KV error" });
  }
}
