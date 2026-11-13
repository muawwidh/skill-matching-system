import { build } from "esbuild";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const temp = await mkdtemp(join(tmpdir(), "matching-ui-tests-"));
try {
  const file = join(temp, "tests.cjs");
  await build({ entryPoints: [fileURLToPath(new URL("./matching.test.tsx", import.meta.url))], outfile: file,
    bundle: true, platform: "node", format: "cjs", jsx: "automatic",
    define: { "import.meta.env.VITE_API_BASE_URL": '"http://mock.invalid"', "import.meta.url": JSON.stringify(new URL("./matching.test.tsx", import.meta.url).href) } });
  const result = spawnSync(process.execPath, ["--test", file], { stdio: "inherit" });
  process.exitCode = result.status ?? 1;
} finally { await rm(temp, { recursive: true, force: true }); }
