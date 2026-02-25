import argparse
import sys
import json
import tarfile
from io import BytesIO
from pathlib import Path
from .compressor import (
    ant_compress, ant_decompress, pack_path,
    pack_ai_agent, unpack_ai_text, init_workspace
)

def main():
    parser = argparse.ArgumentParser(
        prog="ant",
        description="🐜 Ant v0.4.0 — Compressor + Agent Mode (70–90% token savings)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # compress
    comp = subparsers.add_parser("compress", help="Compress folder/file")
    comp.add_argument("path", type=Path)

    # decompress
    decomp = subparsers.add_parser("decompress", help="Decompress .ant")
    decomp.add_argument("path", type=Path)

    # pack-ai (Agent Mode)
    pack = subparsers.add_parser("pack-ai", help="Agent Mode — tiny context for IDEs/phones")
    pack.add_argument("path", type=Path)
    pack.add_argument("--format", choices=["json", "md"], default="json")
    pack.add_argument("--model", choices=["claude", "gemini", "gpt", "grok", "any"], default="claude")
    pack.add_argument("--max-tokens", type=int)
    pack.add_argument("--stdout", action="store_true")

    # unpack-ai
    unpack = subparsers.add_parser("unpack-ai", help="Turn AI-edited .md back into .ant")
    unpack.add_argument("path", type=Path)
    
    # init
    init_cmd = subparsers.add_parser("init", help="Initialize workspace with IDE rules and compressed context (.ant_context)")
    init_cmd.add_argument("path", nargs="?", type=Path, default=Path("."))

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "compress":
        data = pack_path(str(args.path)) if args.path.is_dir() else args.path.read_bytes()
        compressed = ant_compress(data)
        out = args.path.absolute().with_suffix(".ant")
        out.write_bytes(compressed)
        print(f"✅ {len(data):,} → {len(compressed):,} bytes ({(1-len(compressed)/len(data))*100:.1f}% saved)")

    elif args.command == "decompress":
        with open(args.path, "rb") as f:
            data = ant_decompress(f.read())
        if tarfile.is_tarfile(BytesIO(data)):
            out = args.path.with_suffix("")
            out.mkdir(exist_ok=True)
            with tarfile.open(fileobj=BytesIO(data)) as tar:
                tar.extractall(out)
            print(f"✅ Folder restored to {out}/")
        else:
            args.path.with_suffix("").write_bytes(data)
            print(f"✅ File restored")

    elif args.command == "pack-ai":
        if not args.path.is_dir():
            print("❌ pack-ai needs a folder")
            sys.exit(1)
        result = pack_ai_agent(str(args.path), args.model, args.max_tokens, args.format)
        if args.stdout:
            if args.format == "json":
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(result)
            return
        suffix = ".json" if args.format == "json" else ".ai.md"
        out = args.path.with_suffix(suffix)
        with open(out, "w", encoding="utf-8") as f:
            if args.format == "json":
                json.dump(result, f, indent=2, ensure_ascii=False)
            else:
                f.write(result)
        tokens = result.get("estimated_tokens", "unknown") if isinstance(result, dict) else "unknown"
        print(f"✅ Agent-ready! ~{tokens} tokens → {out}")

    elif args.command == "unpack-ai":
        with open(args.path, "r", encoding="utf-8") as f:
            text = f.read()
        tar_data = unpack_ai_text(text)
        compressed = ant_compress(tar_data)
        out = Path("updated-" + str(args.path).replace(".ai.md", "").replace(".md", "") + ".ant")
        out.write_bytes(compressed)
        print(f"✅ New compressed .ant created: {out}")
        
    elif args.command == "init":
        init_workspace(str(args.path))

if __name__ == "__main__":
    main()