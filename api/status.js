import { kv } from "@vercel/kv";

export default async function handler(req, res) {
  try {
    const data = await kv.get("macro:latest");
    if (!data) return res.status(404).json({ error: "No snapshot yet. Run /api/compute." });
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).send(data);
  } catch (e) {
    return res.status(500).json({ error: e?.message || "KV error" });
  }
}
