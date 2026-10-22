import * as React from "react";
import { useEffect, useState } from "react";
import { STUDIO_KENNUNG, STUDIO_PORT, logPfad, startStudio, studioRunning, studioUrl, waitForStudio } from "./loadStudio";

type Phase = { kind: "checking" } | { kind: "starting" } | { kind: "running" } | { kind: "error"; error: string };

/**
 * STUDIO-Tab (Motion-Studio): bettet das Dashboard als iframe ein, startet den Server bei Bedarf selbst
 * und startet ihn neu, wenn er stirbt. Nutzt nur die CSS-Klassen des CUTTER-Tabs (gibt es ab v0.2.0),
 * darum kein styles.css-Eingriff. Neu laden und Server-Neustart hat die Seite selbst im Menü „⋯“.
 */
export function StudioView(): JSX.Element {
	const [phase, setPhase] = useState<Phase>({ kind: "checking" });
	const dark = document.body.classList.contains("theme-dark");

	const ensure = async (): Promise<void> => {
		if (await studioRunning()) {
			setPhase({ kind: "running" });
			return;
		}
		setPhase({ kind: "starting" });
		const r = startStudio();
		if (!r.ok) {
			setPhase({ kind: "error", error: r.error ?? "Start fehlgeschlagen" });
			return;
		}
		if (await waitForStudio()) setPhase({ kind: "running" });
		else setPhase({ kind: "error", error: `Das Studio antwortet nicht. Log: ${logPfad()}` });
	};

	useEffect(() => {
		void ensure();
	}, []);

	// Selbstheilung: zweiter Blick nach 2,5 s, damit ein Neustart aus der Seite nicht als Ausfall zählt
	useEffect(() => {
		if (phase.kind !== "running") return;
		const id = window.setInterval(() => {
			void (async () => {
				if (await studioRunning(4000)) return;
				await new Promise<void>((r) => window.setTimeout(r, 2500));
				if (!(await studioRunning(4000))) setPhase({ kind: "checking" });
			})();
		}, 15000);
		return () => window.clearInterval(id);
	}, [phase.kind]);

	useEffect(() => {
		if (phase.kind === "checking") void ensure();
	}, [phase.kind]);

	return (
		<div className="cutter-view" data-kennung={STUDIO_KENNUNG}>
			<div className="cutter-main">
				{phase.kind === "checking" && <div className="cutter-msg mono">prüfe studio…</div>}
				{phase.kind === "starting" && <div className="cutter-msg mono">starte studio · 127.0.0.1:{STUDIO_PORT}…</div>}
				{phase.kind === "error" && (
					<div className="cutter-launcher">
						<div className="cutter-error mono">{phase.error}</div>
						<button className="cutter-btn" onClick={() => void ensure()}>
							NEU VERSUCHEN
						</button>
					</div>
				)}
				{phase.kind === "running" && <iframe className="cutter-frame" src={studioUrl(dark)} title="Studio" />}
			</div>
		</div>
	);
}
