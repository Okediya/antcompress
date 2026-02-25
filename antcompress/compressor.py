from __future__ import annotations
import lzma
import struct
import tarfile
import os
import json
from io import BytesIO
from pathlib import Path

try:
    import tiktoken  # type: ignore
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

MAGIC = b'ANTv1'

DICTIONARIES = {
    "claude": {b"def ": b"d:", b"function ": b"f:", b"import ": b"i:", b"class ": b"c:",
               b"return ": b"r:", b"console.log": b"cl", b"print(": b"p(",
               b"async ": b"a:", b"await ": b"w:"},
    "gemini": {b"def ": b"d:", b"function ": b"f:", b"import ": b"i:", b"class ": b"c:"},
    "gpt": {b"def ": b"d:", b"function ": b"f:", b"import ": b"i:", b"class ": b"c:"},
    "grok": {b"def ": b"d:", b"function ": b"f:", b"import ": b"i:", b"class ": b"c:"},
    "any": {b"def ": b"d:", b"function ": b"f:", b"import ": b"i:", b"class ": b"c:"},
}

def pack_path(path: str) -> bytes:
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        def filter_func(ti):
            name = ti.name.lower()
            if any(x in name for x in [".git", "node_modules", "__pycache__", ".ant", ".ai.md", "build", ".dart_tool", "dist", "egg-info"]):
                return None
            return ti
        tar.add(path, arcname=os.path.basename(path.rstrip("/")), filter=filter_func)
    return buf.getvalue()

def ant_compress(data: bytes) -> bytes:
    compressed = data
    passes = 0
    while passes < 10:
        new_comp = lzma.compress(compressed, preset=lzma.PRESET_EXTREME | 9)
        if len(new_comp) > len(compressed) - 64:
            break
        compressed = new_comp
        passes += 1
    header = MAGIC + struct.pack("<Q", len(data)) + bytes([passes])
    return header + compressed

def ant_decompress(ant_data: bytes) -> bytes:
    if not ant_data.startswith(MAGIC):
        raise ValueError("❌ Not a valid .ant file")
    offset = len(MAGIC)
    orig_size = struct.unpack("<Q", ant_data[offset:offset+8])[0]
    passes = ant_data[offset+8]
    payload = ant_data[offset+9:]
    data = payload
    for _ in range(passes):
        data = lzma.decompress(data)
    if len(data) != orig_size:
        raise ValueError("❌ Corrupted data")
    return data

def apply_dictionary(data: bytes, model: str) -> bytes:
    dic = DICTIONARIES.get(model.lower(), DICTIONARIES["any"])
    for k, v in dic.items():
        data = data.replace(k, v)
    return data

def estimate_tokens(text: str) -> int:
    if TIKTOKEN_AVAILABLE:
        try:
            enc = tiktoken.encoding_for_model("gpt-4o")
            return len(enc.encode(text))
        except:
            pass
    return int(len(text.split()) * 1.35 + len(text) * 0.15)

def pack_ai_agent(folder: str, model: str = "claude", max_tokens: int | None = None, fmt: str = "json") -> dict | str:
    tar_bytes = pack_path(folder)
    files = {}
    with tarfile.open(fileobj=BytesIO(tar_bytes)) as tar:
        for member in tar.getmembers():
            if member.isfile():
                f = tar.extractfile(member)
                if f:
                    content = f.read().decode(errors="ignore")
                    files[member.name] = content

    for path in files:
        files[path] = apply_dictionary(files[path].encode(), model).decode(errors="ignore")

    if fmt == "json":
        result = {
            "repo_name": os.path.basename(folder.rstrip("/")),
            "model": model,
            "total_files": len(files),
            "estimated_tokens": 0,
            "files": [{"path": p, "content": c} for p, c in sorted(files.items())]
        }
        full_json = json.dumps(result, ensure_ascii=False)
        result["estimated_tokens"] = estimate_tokens(full_json)

        if max_tokens and result["estimated_tokens"] > max_tokens:
            sorted_files = sorted(result["files"], key=lambda x: len(x["content"]))
            while result["estimated_tokens"] > max_tokens and result["files"]:
                result["files"].pop(0)
                full_json = json.dumps(result, ensure_ascii=False)
                result["estimated_tokens"] = estimate_tokens(full_json)
        return result
    else:
        lines = [f"# Ant AI Export — {os.path.basename(folder)} (optimized for {model})"]
        for path, content in sorted(files.items()):
            ext = Path(path).suffix[1:] or "txt"
            lines.append(f"\n### {path}\n```{ext}\n{content}\n```\n")
        return "\n".join(lines)

def unpack_ai_text(ai_text: str) -> bytes:
    files = {}
    current_file = None
    current_content = []
    for line in ai_text.splitlines():
        if line.startswith("### ") and line.strip().endswith("```") is False:
            if current_file:
                files[current_file] = "\n".join(current_content)
            current_file = line[4:].strip()
            current_content = []
        elif current_file and line.strip() == "```":
            if current_content:
                files[current_file] = "\n".join(current_content)
                current_file = None
                current_content = []
        elif current_file:
            current_content.append(line)
    if current_file and current_content:
        files[current_file] = "\n".join(current_content)

    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for path, content in files.items():
            info = tarfile.TarInfo(name=path)
            data = content.encode()
            info.size = len(data)
            tar.addfile(info, BytesIO(data))
    return buf.getvalue()

def init_workspace(path: str) -> None:
    folder = Path(path).resolve()
    context_dir = folder / ".ant_context"
    context_dir.mkdir(exist_ok=True)
    
    print("🐜 Initializing Antcompress workspace...")
    
    ignored = {".git", "node_modules", "__pycache__", ".ant_context", "venv", "env", ".venv", "build", ".dart_tool", "dist", "egg-info", ".idea", ".vscode"}
    
    def is_ignored(p: Path) -> bool:
        for part in p.parts:
            if part in ignored or part.endswith(".egg-info"):
                return True
        return False

    print("📦 Replicating directory tree into .ant_context/ ...")
    count = 0
    for file_path in folder.rglob("*"):
        if file_path.is_file():
            rel_path = file_path.relative_to(folder)
            if is_ignored(rel_path):
                continue
            
            # Replicate the exact directory structure, append .ai.md to the filename
            out_file = context_dir / rel_path.with_name(rel_path.name + ".ai.md")
            out_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                compressed = apply_dictionary(content.encode("utf-8"), "any").decode("utf-8", errors="ignore")
                ext = file_path.suffix[1:] or "txt"
                md_content = f"### {rel_path}\n```{ext}\n{compressed}\n```\n"
                out_file.write_text(md_content, encoding="utf-8")
                count += 1
            except Exception:
                pass
                
    print(f"✅ Packed {count} files into individual AI contexts!")
    
    # Create IDE rules
    rule_content = """# Antcompress AI Agent Instructions

To save tokens massively, when you need to explore or read code in this repository, DO NOT read the raw source files directly. 
Instead, read the corresponding pre-packed Agent Mode files in the `.ant_context/` directory (e.g., read `.ant_context/src.ai.md` instead of the `src/` folder files).
If a directory's compressed file is outdated, run `ant pack-ai <directory>` to update it, or `ant pack-ai . --stdout` to view the whole repo.
"""
    
    try:
        (folder / ".cursorrules").write_text(rule_content, encoding="utf-8")
        (folder / ".windsurfrules").write_text(rule_content, encoding="utf-8")
        
        github_dir = folder / ".github"
        github_dir.mkdir(exist_ok=True)
        (github_dir / "copilot-instructions.md").write_text(rule_content, encoding="utf-8")
        
        agents_dir = folder / ".agents" / "workflows"
        agents_dir.mkdir(parents=True, exist_ok=True)
        workflow_content = f"---\ndescription: How to use Antcompress\n---\n{rule_content}"
        (agents_dir / "antcompress.md").write_text(workflow_content, encoding="utf-8")
    except Exception as e:
        print(f"⚠️ Could not create all IDE rule files: {e}")
    
    print(f"✅ Workspace initialized! IDE rules created and context saved to .ant_context/")