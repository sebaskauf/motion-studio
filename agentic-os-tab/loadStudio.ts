import { spawn } from "child_process";
import { existsSync, mkdirSync, openSync, readFileSync } from "fs";
import { get as httpGet } from "http";
import { homedir, platform } from "os";
import { join } from "path";

/**
 * STUDIO-Tab für Motion-Studio (eingebaut von motion-studio/agentic-os-tab/einbauen.py).
 * Startet das Dashboard des Nutzers (<HEIM>/dashboard/server.py, nur 127.0.0.1) und zeigt es als iframe.
 * HEIM = Installationsordner von Motion-Studio: Zeigerdatei ~/.motion-studio-heim, sonst <CLAUDE_CONFIG_DIR|~/.claude>/motion-studio.
 * Port und optionaler Adapter kommen aus <HEIM>/config.json („dashboard_port“, „dashboard_adapter“), Standard 8777.
 * Läuft auf macOS, Windows und Linux. Kennung im Bundle: motion-studio-tab (prüft einbauen.py).
 */
export const STUDIO_KENNUNG = "motion-studio-tab";
const IS_WIN = platform() === "win32";

function heim(): string {
	const zeiger = join(homedir(), ".motion-studio-heim");
	try {
		if (existsSync(zeiger)) {
			const p = readFileSync(zeiger, "utf-8").trim();
			if (p && existsSync(p)) return p;
		}
	} catch (_) {
		/* Zeiger unlesbar: Standard nehmen */
	}
	return join(process.env.CLAUDE_CONFIG_DIR ?? join(homedir(), ".claude"), "motion-studio");
}

function konfig(): { port: number; adapter?: string } {
	try {
		const d = JSON.parse(readFileSync(join(heim(), "config.json"), "utf-8")) as Record<string, unknown>;
		const port = Number(d["dashboard_port"] ?? 8777);
		const adapter = typeof d["dashboard_adapter"] === "string" ? (d["dashboard_adapter"] as string) : undefined;
		return { port: Number.isInteger(port) && port > 1024 && port < 65536 ? port : 8777, adapter };
	} catch (_) {
		return { port: 8777 };
	}
}

export const STUDIO_PORT = Number(process.env.AGENTIC_OS_STUDIO_PORT ?? konfig().port);

export function studioUrl(dark: boolean): string {
	return `http://127.0.0.1:${STUDIO_PORT}/?thema=${dark ? "dunkel" : "hell"}`;
}

/** Python: zuerst das venv von Motion-Studio, dann die üblichen Orte. Windows: Scripts\python.exe bzw. der py-Starter. */
function python(h: string): { cmd: string; pre: string[] } | undefined {
	const venv = join(h, IS_WIN ? ".venv/Scripts/python.exe" : ".venv/bin/python");
	if (existsSync(venv)) return { cmd: venv, pre: [] };
	const kandidaten = IS_WIN
		? [join(process.env.LOCALAPPDATA ?? "", "Programs/Python/Launcher/py.exe"), "C:/Windows/py.exe"]
		: ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"];
	const p = kandidaten.find((k) => k && existsSync(k));
	if (p !== undefined) return { cmd: p, pre: IS_WIN ? ["-3"] : [] };
	return IS_WIN ? { cmd: "python", pre: [] } : undefined;
}

/** Health-Check per Node-http (requestUrl erreicht 127.0.0.1 nicht zuverlässig). */
export function studioRunning(timeoutMs = 3000): Promise<boolean> {
	return new Promise((resolve) => {
		const req = httpGet({ host: "127.0.0.1", port: STUDIO_PORT, path: "/api/stand", timeout: timeoutMs }, (res) => {
			res.resume();
			resolve(res.statusCode === 200);
		});
		req.on("timeout", () => {
			req.destroy();
			resolve(false);
		});
		req.on("error", () => resolve(false));
	});
}

/** Startet den Dashboard-Server abgekoppelt (überlebt Obsidian), Ausgabe nach <HEIM>/dashboard.log. */
export function startStudio(): { ok: boolean; error?: string } {
	const h = heim();
	const server = join(h, "dashboard/server.py");
	if (!existsSync(server)) return { ok: false, error: `Motion-Studio fehlt (${server}). Erst den Setup-Prompt von Motion-Studio ausführen.` };
	const py = python(h);
	if (py === undefined) return { ok: false, error: "Python 3 nicht gefunden. Motion-Studio-Setup (ms check) prüfen." };
	const { adapter } = konfig();
	const args = [...py.pre, server, "--port", String(STUDIO_PORT)];
	if (adapter !== undefined && existsSync(adapter)) args.push("--adapter", adapter);
	try {
		mkdirSync(h, { recursive: true });
		const log = openSync(join(h, "dashboard.log"), "a");
		const child = spawn(py.cmd, args, {
			cwd: h,
			detached: true,
			windowsHide: true,
			stdio: ["ignore", log, log],
			env: { ...process.env, PYTHONIOENCODING: "utf-8" },
		});
		child.unref();
		return { ok: true };
	} catch (e) {
		return { ok: false, error: String(e) };
	}
}

export async function waitForStudio(timeoutMs = 15000): Promise<boolean> {
	const t0 = Date.now();
	while (Date.now() - t0 < timeoutMs) {
		if (await studioRunning()) return true;
		await new Promise<void>((r) => window.setTimeout(r, 500));
	}
	return false;
}

export function logPfad(): string {
	return join(heim(), "dashboard.log");
}
