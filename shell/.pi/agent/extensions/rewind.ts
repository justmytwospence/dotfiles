/**
 * Rewind: restore files alongside conversation rewinds (/tree and /fork),
 * like Claude Code's /rewind or OpenCode's /undo.
 *
 * - When a user message is submitted, the working tree (tracked + untracked,
 *   minus ignored files) is snapshotted as a git tree object via a temporary
 *   index. HEAD, the real index, and the stash are never touched.
 * - When the agent run ends, the final state is snapshotted too.
 * - Snapshots are persisted as `rewind-checkpoint` custom entries, so they
 *   survive restarts. Tree objects are unreferenced; git keeps them for
 *   gc.pruneExpire (2 weeks by default).
 * - On /tree or /fork to a checkpointed entry, offers to restore files.
 *   Only differing files are rewritten; files created since are deleted.
 * - /rewind-undo restores the state saved just before the last restore.
 *
 * Only active in git repos and in interactive sessions (set
 * PI_REWIND_ALWAYS=1 to snapshot in non-interactive modes too).
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn } from "node:child_process";
import { copyFileSync, existsSync, mkdtempSync, rmdirSync, rmSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";

const ENTRY_TYPE = "rewind-checkpoint";

type Kind = "pre" | "post";
interface Checkpoint {
	entryId: string;
	kind: Kind;
	root: string;
	tree: string;
}

interface GitResult {
	code: number;
	stdout: string;
	stderr: string;
}

function git(cwd: string, args: string[], opts: { env?: Record<string, string>; input?: string } = {}): Promise<GitResult> {
	return new Promise((done) => {
		const child = spawn("git", args, {
			cwd,
			env: { ...process.env, GIT_OPTIONAL_LOCKS: "0", ...opts.env },
			stdio: ["pipe", "pipe", "pipe"],
		});
		let stdout = "";
		let stderr = "";
		child.stdout.on("data", (d) => (stdout += d));
		child.stderr.on("data", (d) => (stderr += d));
		child.on("error", (e) => done({ code: -1, stdout, stderr: String(e) }));
		child.on("close", (code) => done({ code: code ?? -1, stdout, stderr }));
		child.stdin.end(opts.input ?? "");
	});
}

async function repoRoot(cwd: string): Promise<string | undefined> {
	const r = await git(cwd, ["rev-parse", "--show-toplevel"]);
	return r.code === 0 ? r.stdout.trim() : undefined;
}

async function withTempIndex<T>(fn: (index: string) => Promise<T>): Promise<T> {
	const dir = mkdtempSync(join(tmpdir(), "pi-rewind-"));
	try {
		return await fn(join(dir, "index"));
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
}

/** Hash the working tree (respecting .gitignore) into a tree object. */
async function snapshot(root: string): Promise<string | undefined> {
	return withTempIndex(async (index) => {
		// Seed from the real index so unchanged files are not rehashed.
		const p = await git(root, ["rev-parse", "--git-path", "index"]);
		if (p.code === 0) {
			const real = resolve(root, p.stdout.trim());
			if (existsSync(real)) copyFileSync(real, index);
		}
		const env = { GIT_INDEX_FILE: index };
		if ((await git(root, ["add", "-A", "--", "."], { env })).code !== 0) return undefined;
		const w = await git(root, ["write-tree"], { env });
		return w.code === 0 ? w.stdout.trim() : undefined;
	});
}

interface Diff {
	remove: string[]; // present now, absent in target
	write: string[]; // absent or different now
}

async function diffTrees(root: string, target: string, current: string): Promise<Diff | undefined> {
	const r = await git(root, ["diff-tree", "-r", "-z", "--no-renames", "--name-status", target, current]);
	if (r.code !== 0) return undefined;
	const parts = r.stdout.split("\0").filter((s) => s.length > 0);
	const diff: Diff = { remove: [], write: [] };
	for (let i = 0; i + 1 < parts.length; i += 2) {
		const status = parts[i];
		const path = parts[i + 1];
		if (status === "A") diff.remove.push(path);
		else diff.write.push(path);
	}
	return diff;
}

async function applyTree(root: string, target: string, diff: Diff): Promise<string | undefined> {
	for (const rel of diff.remove) {
		const abs = join(root, rel);
		try {
			unlinkSync(abs);
		} catch {
			continue;
		}
		// Prune directories left empty.
		for (let dir = dirname(abs); dir.startsWith(root + "/") && dir !== root; dir = dirname(dir)) {
			try {
				rmdirSync(dir);
			} catch {
				break;
			}
		}
	}
	if (diff.write.length === 0) return undefined;
	return withTempIndex(async (index) => {
		const env = { GIT_INDEX_FILE: index };
		const rt = await git(root, ["read-tree", target], { env });
		if (rt.code !== 0) return rt.stderr.trim() || "git read-tree failed";
		const co = await git(root, ["checkout-index", "-f", "-z", "--stdin"], { env, input: diff.write.join("\0") });
		return co.code === 0 ? undefined : co.stderr.trim() || "git checkout-index failed";
	});
}

export default function (pi: ExtensionAPI) {
	const always = process.env.PI_REWIND_ALWAYS === "1";
	let root: string | undefined;
	let rootResolved = false;
	let pending: { message: unknown; timestamp: unknown; tree: string }[] = [];
	let lastUndo: { root: string; tree: string } | undefined;

	async function getRoot(cwd: string) {
		if (!rootResolved) {
			root = await repoRoot(cwd);
			rootResolved = true;
		}
		return root;
	}

	function checkpoints(ctx: any): Map<string, Checkpoint> {
		const map = new Map<string, Checkpoint>();
		for (const e of ctx.sessionManager.getEntries()) {
			if (e.type !== "custom" || e.customType !== ENTRY_TYPE) continue;
			for (const c of (e.data?.checkpoints ?? []) as Checkpoint[]) map.set(`${c.kind}:${c.entryId}`, c);
		}
		return map;
	}

	/** Find the checkpoint matching the file state at a conversation point. */
	function lookup(ctx: any, entryId: string, preferPre: boolean): Checkpoint | undefined {
		const map = checkpoints(ctx);
		let entry = ctx.sessionManager.getEntry(entryId);
		// Skip non-message entries (labels, summaries, our own checkpoints).
		while (entry && entry.type !== "message") entry = entry.parentId ? ctx.sessionManager.getEntry(entry.parentId) : undefined;
		if (!entry) return undefined;
		if (preferPre && entry.message?.role === "user") return map.get(`pre:${entry.id}`);
		return map.get(`post:${entry.id}`);
	}

	async function offerRestore(ctx: any, cp: Checkpoint | undefined) {
		if (!cp || !ctx.hasUI) return;
		if (!existsSync(cp.root)) return;
		if ((await git(cp.root, ["cat-file", "-e", `${cp.tree}^{tree}`])).code !== 0) {
			ctx.ui.notify("Rewind: file checkpoint was garbage-collected; files not restored", "warning");
			return;
		}
		const current = await snapshot(cp.root);
		if (!current || current === cp.tree) return;
		const diff = await diffTrees(cp.root, cp.tree, current);
		if (!diff) return;
		const n = diff.remove.length + diff.write.length;
		if (n === 0) return;
		const choice = await ctx.ui.select(`Restore files to this point? (${n} file${n === 1 ? "" : "s"} differ)`, [
			"Restore files",
			"Keep current files",
		]);
		if (choice !== "Restore files") return;
		const err = await applyTree(cp.root, cp.tree, diff);
		lastUndo = { root: cp.root, tree: current };
		if (err) ctx.ui.notify(`Rewind: restore incomplete: ${err}`, "error");
		else ctx.ui.notify(`Rewind: restored ${n} file${n === 1 ? "" : "s"} (/rewind-undo to revert)`, "info");
	}

	pi.on("session_start", () => {
		rootResolved = false;
		pending = [];
	});

	// Snapshot before the agent acts on each user message (prompts and queued messages).
	pi.on("message_end", async (event, ctx) => {
		if (event.message.role !== "user" || (!ctx.hasUI && !always)) return;
		const r = await getRoot(ctx.cwd);
		if (!r) return;
		const tree = await snapshot(r);
		if (tree) pending.push({ message: event.message, timestamp: (event.message as any).timestamp, tree });
	});

	pi.on("agent_end", async (_event, ctx) => {
		if (!ctx.hasUI && !always) return;
		const r = await getRoot(ctx.cwd);
		if (!r) return;
		const branch = ctx.sessionManager.getBranch();
		const found: Checkpoint[] = [];
		for (const p of pending) {
			const entry = [...branch]
				.reverse()
				.find((e: any) => e.type === "message" && e.message?.role === "user" && (e.message === p.message || e.message?.timestamp === p.timestamp));
			if (entry) found.push({ entryId: entry.id, kind: "pre", root: r, tree: p.tree });
		}
		pending = [];
		const leaf = ctx.sessionManager.getLeafEntry();
		if (leaf?.type === "message") {
			const tree = await snapshot(r);
			if (tree) found.push({ entryId: leaf.id, kind: "post", root: r, tree });
		}
		if (found.length > 0) pi.appendEntry(ENTRY_TYPE, { checkpoints: found });
	});

	pi.on("session_before_tree", async (event, ctx) => {
		await offerRestore(ctx, lookup(ctx, event.preparation.targetId, true));
	});

	pi.on("session_before_fork", async (event, ctx) => {
		await offerRestore(ctx, lookup(ctx, event.entryId, event.position === "before"));
	});

	pi.registerCommand("rewind-undo", {
		description: "Revert the last file restore made by /tree or /fork",
		handler: async (_args, ctx) => {
			if (!lastUndo) {
				ctx.ui.notify("Rewind: nothing to undo", "warning");
				return;
			}
			const { root: r, tree } = lastUndo;
			const current = await snapshot(r);
			const diff = current ? await diffTrees(r, tree, current) : undefined;
			if (!current || !diff) {
				ctx.ui.notify("Rewind: could not compute undo", "error");
				return;
			}
			const err = await applyTree(r, tree, diff);
			lastUndo = { root: r, tree: current };
			if (err) ctx.ui.notify(`Rewind: undo incomplete: ${err}`, "error");
			else ctx.ui.notify(`Rewind: reverted ${diff.remove.length + diff.write.length} file(s)`, "info");
		},
	});
}
