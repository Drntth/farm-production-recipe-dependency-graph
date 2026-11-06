// The layout SVG of a level, drawn by the Python core, served as a static file.
import type { APIRoute, GetStaticPaths } from "astro";
import { loadIndex, loadLevelSvg } from "../../data";

export const getStaticPaths: GetStaticPaths = () =>
  loadIndex().levels.map((row) => ({ params: { level: String(row.level) } }));

export const GET: APIRoute = ({ params }) =>
  new Response(loadLevelSvg(Number(params.level)), {
    headers: { "Content-Type": "image/svg+xml" },
  });
