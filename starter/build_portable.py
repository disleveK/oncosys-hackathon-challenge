"""Embed the exact allowlisted starter dependencies; never package raw or judging files."""
import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import textwrap


HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "tcga_starter.ipynb"
DATA = HERE.parent / "data" / "tcga-brca"
FILES = ("fetch.py", "sources.csv", "sample_manifest.csv", "slide_manifest.csv")
MARKER = "cancer-ai-lab-portable-bootstrap"


def bootstrap():
    lines = [
        "# @title Prepare the pinned starter files",
        "# Bundled by starter/build_portable.py. No GitHub access is used at runtime.",
        "import base64, gzip, hashlib, pathlib, subprocess, sys, tempfile",
        "",
        "BUNDLE = {",
    ]
    for name in FILES:
        data = (DATA / name).read_bytes()
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as compressed:
            compressed.write(data)
        packed = base64.b64encode(buffer.getvalue()).decode("ascii")
        lines += [f"    {name!r}: ({hashlib.sha256(data).hexdigest()!r},", "        ("]
        lines += [f"            {chunk!r}" for chunk in textwrap.wrap(packed, 96)]
        lines += ["        ),", "    ),"]
    lines += [
        "}",
        "",
        "# Use only the embedded, hash-checked files, even if run from a checkout.",
        "_starter_workspace = tempfile.TemporaryDirectory(prefix='cancer-ai-lab-')",
        "DATA = pathlib.Path(_starter_workspace.name)",
        "for name, (expected_hash, packed) in BUNDLE.items():",
        "    data = gzip.decompress(base64.b64decode(packed, validate=True))",
        "    if hashlib.sha256(data).hexdigest() != expected_hash:",
        "        raise ValueError(f'Starter file checksum mismatch: {name}. Download a fresh copy.')",
        "    (DATA / name).write_bytes(data)",
        "del BUNDLE",
        "subprocess.run([sys.executable, str(DATA / 'fetch.py'), '--no-rna'], check=True)",
        "print('Verified the bundled starter files and the required Xena tables.')",
    ]
    return "\n".join(lines).splitlines(keepends=True)


def render(existing):
    notebook = json.loads(existing)
    code = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    first = code[0]
    source = "".join(first["source"])
    if first.get("metadata", {}).get("portable_id") != MARKER and "data/tcga-brca/fetch.py" not in source:
        raise ValueError("Unexpected first code cell; refusing to replace it.")
    first["source"] = bootstrap()
    first["metadata"] = {"portable_id": MARKER, "cellView": "form"}
    for cell in code:
        cell["execution_count"] = None
        cell["outputs"] = []
    updates = {
        "## 1 · Get the data": (
            "## 1 · Get the data\n"
            "This notebook works from a single downloaded file. The first cell verifies its bundled helpers "
            "and manifests, then fetches and checks the required TCGA-BRCA tables directly from UCSC Xena. "
            "It does not fetch from GitHub. In Colab use **File → Upload notebook**, then **Run all**."
        ),
        "## 5 · Look at the tissue": (
            "## 5 · Find the matching tissue slide\n"
            "The output lists the pathology slide and its NCI Imaging Data Commons link. "
            "The external viewer may be unavailable; if it does not open, use the displayed slide ID "
            "and type as your evidence pointer and continue the exercise."
        ),
    }
    for cell in notebook["cells"]:
        if cell["cell_type"] != "markdown":
            continue
        text = "".join(cell["source"])
        for prefix, replacement in updates.items():
            if text.startswith(prefix):
                cell["source"] = replacement.splitlines(keepends=True)
    return json.dumps(notebook, ensure_ascii=False, indent=1) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the generated notebook is stale")
    args = parser.parse_args()
    old = NOTEBOOK.read_text(encoding="utf-8")
    new = render(old)
    if args.check:
        if old != new:
            parser.exit(1, "Portable starter is stale. Run python starter/build_portable.py.\n")
        print("Portable starter is current.")
    else:
        NOTEBOOK.write_text(new, encoding="utf-8")
        print(f"Generated {NOTEBOOK.name}: {len(new.encode('utf-8')):,} bytes")


if __name__ == "__main__":
    main()
