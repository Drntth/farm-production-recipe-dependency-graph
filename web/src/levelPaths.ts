// Static paths of the level pages, shared by both languages.
import type { GetStaticPaths } from "astro";
import { loadIndex } from "./data";

export const levelPaths: GetStaticPaths = () => {
  const levels = loadIndex().levels.map((row) => row.level);
  return levels.map((level, i) => ({
    params: { level: String(level) },
    props: { level, levels, prev: levels[i - 1], next: levels[i + 1] },
  }));
};

export interface LevelProps {
  level: number;
  levels: number[];
  prev?: number;
  next?: number;
}
