/**
 * Welcome to Cloudflare Workers! This is your first worker.
 *
 * - Run "npm run dev" in your terminal to start a development server
 * - Open a browser tab at http://localhost:8787/ to see your worker in action
 * - Run "npm run deploy" to publish your worker
 *
 * Learn more at https://developers.cloudflare.com/workers/
 */

const MAX_ITEMS = 200;
const TZ_CHICAGO = "America/Chicago";

const FEEDS = {
  movies: {
    kv: "FEED_MOVIES",
    title: "Movies",
    link: "https://example.com",
    description: "Private movies feed",
  },
  shows: {
    kv: "FEED_SHOWS",
    title: "Shows",
    link: "https://example.com",
    description: "Private shows feed",
  },
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const secret = env.PATH_SECRET;
    if (!secret) {
      return new Response("PATH_SECRET not configured", { status: 500 });
    }

    const prefix = `/f/${secret}/`;
    if (!url.pathname.startsWith(prefix)) {
      return new Response("Not found", { status: 404 });
    }

    const rest = url.pathname.slice(prefix.length);

    const feedMatch = rest.match(/^(movies|shows)\.xml$/);
    if (request.method === "GET" && feedMatch) {
      const cfg = FEEDS[feedMatch[1]];
      const kv = env[cfg.kv];
      if (!kv) return new Response(`${cfg.kv} not bound`, { status: 500 });
      return serveFeed(kv, cfg);
    }

    const addMatch = rest.match(/^(movies|shows)\/add$/);
    if (request.method === "POST" && addMatch) {
      const cfg = FEEDS[addMatch[1]];
      const kv = env[cfg.kv];
      if (!kv) return new Response(`${cfg.kv} not bound`, { status: 500 });
      return addItem(request, kv);
    }

    return new Response("Not found", { status: 404 });
  },
};

/**
 * Current instant as an ISO-8601 string in America/Chicago (with offset).
 * Example: 2026-09-04T15:34:11.867-05:00
 */
function chicagoNowISO(date = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: TZ_CHICAGO,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
      hourCycle: "h23",
    })
      .formatToParts(date)
      .filter((p) => p.type !== "literal")
      .map((p) => [p.type, p.value]),
  );

  // Offset = Chicago wall time interpreted as UTC minus the real instant.
  const asUTC = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second),
    Number(parts.fractionalSecond || 0),
  );
  const offsetMin = Math.round((asUTC - date.getTime()) / 60000);
  const sign = offsetMin >= 0 ? "+" : "-";
  const abs = Math.abs(offsetMin);
  const oh = String(Math.floor(abs / 60)).padStart(2, "0");
  const om = String(abs % 60).padStart(2, "0");

  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}.${parts.fractionalSecond || "000"}${sign}${oh}:${om}`;
}

async function loadItems(kv) {
  const items = [];
  let cursor;

  do {
    const page = await kv.list({ prefix: "item:", cursor });
    for (const key of page.keys) {
      const raw = await kv.get(key.name);
      if (!raw) continue;
      try {
        const data = JSON.parse(raw);
        items.push({
          id: key.name,
          title: data.title || "untitled",
          enclosure: data.enclosure || "",
          created: data.created || key.name.slice(5),
        });
      } catch {
        // skip bad values
      }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);

  items.sort((a, b) => String(b.created).localeCompare(String(a.created)));
  return items.slice(0, MAX_ITEMS);
}

async function serveFeed(kv, cfg) {
  const items = await loadItems(kv);
  const now = new Date().toUTCString();

  const body = [];
  for (const item of items) {
    const guid = await sha256Hex32(item.id + "|" + item.title);
    const pubDate = new Date(item.created || Date.now()).toUTCString();

    body.push(`    <item>
        <title><![CDATA[${cdata(item.title)}]]></title>
        <enclosure url="${esc(item.enclosure)}" length="0" type="application/x-bittorrent" />
        <guid isPermaLink="false">${esc(guid)}</guid>
        <pubDate>${pubDate}</pubDate>
    </item>`);
  }

  const xml = `<?xml version="1.0" encoding="utf-8"?><rss version="2.0">
	<channel>
		<title>${esc(cfg.title)}</title>
		<link><![CDATA[${cdata(cfg.link)}]]></link>
		<description><![CDATA[${cdata(cfg.description)}]]></description>
		<language>zh-cn</language>
		<pubDate>${now}</pubDate>
		<generator>RSS Generator</generator>
		<docs><![CDATA[http://www.rssboard.org/rss-specification]]></docs>
		<ttl>5</ttl>

${body.join("")}</channel></rss>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

async function addItem(request, kv) {
  let data;
  const ctype = request.headers.get("content-type") || "";

  if (ctype.includes("application/json")) {
    data = await request.json();
  } else {
    const form = await request.formData();
    data = Object.fromEntries(form.entries());
  }

  const title = String(data.title || "").trim();
  const enclosure = String(data.enclosure || "").trim();

  if (!title && !enclosure) {
    return Response.json({ error: "title or enclosure required" }, { status: 400 });
  }

  const created = chicagoNowISO();
  const key = `item:${created}:${crypto.randomUUID()}`;

  await kv.put(
    key,
    JSON.stringify({
      title: title || "untitled",
      enclosure,
      created,
    }),
  );

  return Response.json({ ok: true, id: key });
}

async function sha256Hex32(text) {
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(text),
  );
  return [...new Uint8Array(buf)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

function cdata(s) {
  return String(s).replaceAll("]]>", "]]]]><![CDATA[>");
}

function esc(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}
