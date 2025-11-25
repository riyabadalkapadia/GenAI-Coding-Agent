# app.py (or streamlit_app.py)
# Streamlit UI for GenAI Coding Agent with file downloads + clear output folder
import os
import sys
import io
import shutil
import zipfile
import traceback
import mimetypes
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Ensure root + agent package are discoverable no matter how the app is launched
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Your internals
from agent.graph import agent
from agent.tools import init_project_root

# Load environment (.env should contain GROQ_API_KEY)
load_dotenv()

# Initialize output directory
try:
    init_project_root()
except Exception:
    pass

GENERATED_DIR = Path(SCRIPT_DIR) / "generated_project"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# --------------- Streamlit Page Setup ---------------
st.set_page_config(page_title="GenAI Coding Agent", page_icon="🤖", layout="wide")

st.markdown(
    """
    <h1 style='text-align:center;'>🤖 GenAI Coding Agent</h1>
    <p style='text-align:center;'>Build code projects from natural language prompts — download files, or zip them all.</p>
    """,
    unsafe_allow_html=True
)

# --------------- Helper Functions ---------------
def collect_files(root: Path):
    """Return a list of files (Path) under root, recursively, sorted."""
    if not root.exists():
        return []
    return sorted([p for p in root.rglob("*") if p.is_file()])

def guess_language_for_code(path: Path) -> str:
    """Return a code language string for st.code based on file suffix."""
    ext = path.suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".md": "markdown",
        ".sh": "bash",
        ".bat": "batch",
        ".sql": "sql",
        ".xml": "xml",
        ".csv": "csv",
        ".txt": "text",
    }.get(ext, "")

def is_text_like(path: Path) -> bool:
    """Heuristic: treat common code/docs as text; otherwise use mimetypes."""
    if path.suffix.lower() in {
        ".py",".js",".ts",".html",".css",".json",".yml",".yaml",
        ".md",".txt",".csv",".xml",".sql",".ini",".toml"
    }:
        return True
    mime, _ = mimetypes.guess_type(str(path))
    if mime and (mime.startswith("text/") or "json" in mime or "xml" in mime):
        return True
    return False

def make_project_zip_bytes(files):
    """Create a zip (in-memory) of all files under generated_project."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            rel = f.relative_to(GENERATED_DIR)
            zf.write(f, arcname=str(rel))
    buf.seek(0)
    return buf

def clear_generated_dir():
    """Delete and recreate generated_project directory."""
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR, ignore_errors=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# --------------- Sidebar: Actions ---------------
with st.sidebar:
    st.header("Project Actions")
    st.write(f"Output folder: `{GENERATED_DIR}`")

    with st.form("clear_form", clear_on_submit=True):
        st.markdown("🧹 **Clear generated_project** (deletes previous run files)")
        confirm = st.checkbox("I understand this will permanently delete current files.")
        do_clear = st.form_submit_button("Delete Now")
        if do_clear:
            if confirm:
                try:
                    clear_generated_dir()
                    st.success("Cleared `generated_project/`.")
                except Exception as e:
                    st.error(f"Failed to clear: {e}")
            else:
                st.warning("Please confirm the checkbox before deletion.")

    # Show quick file count
    current_files = collect_files(GENERATED_DIR)
    st.markdown(f"**Files in project:** {len(current_files)}")

# --------------- Main: Prompt Form ---------------
with st.form(key="prompt_form"):
    user_prompt = st.text_area(
        "💡 Describe what you want to build:",
        placeholder="Example: Build a modern To-Do app using HTML, CSS, and JavaScript with localStorage.",
        height=150,
    )
    recursion_limit = st.slider("🔁 Recursion Limit", 1, 50, 25, step=1)
    submit = st.form_submit_button("🚀 Generate Project")

# --------------- Run Agent ---------------
if submit:
    if not user_prompt.strip():
        st.error("❌ Please provide a project description first.")
        st.stop()

    st.info("⚙️ Running the GenAI Coding Agent. Please wait...")
    try:
        result = agent.invoke(
            {"user_prompt": user_prompt},
            {"recursion_limit": int(recursion_limit)},
        )
        st.success("✅ Generation Complete!")

        # Display raw agent result (often logs or textual summary)
        st.subheader("🧩 Agent Output")
        if result is None:
            st.warning("ℹ️ No output received from the agent.")
        elif isinstance(result, str):
            st.text_area("Output", value=result, height=350)
        elif hasattr(result, "content"):
            st.text_area("Output", value=str(result.content), height=350)
        elif isinstance(result, dict) and "content" in result:
            st.text_area("Output", value=str(result["content"]), height=350)
        else:
            st.text_area("Output", value=str(result), height=350)

    except Exception as e:
        st.error(f"❌ Error occurred: {e}")
        with st.expander("Show full traceback"):
            st.code(traceback.format_exc())

# --------------- Generated Files Browser ---------------
st.markdown("---")
st.header("📁 Generated Files")

files = collect_files(GENERATED_DIR)
if not files:
    st.info("No files found in `generated_project/` yet. Generate a project to see files here.")
else:
    # Zip download (all files) — give it a unique key
    zip_buf = make_project_zip_bytes(files)
    st.download_button(
        "⬇️ Download Entire Project (.zip)",
        data=zip_buf,
        file_name="generated_project.zip",
        mime="application/zip",
        key="download_zip_all_files",   # UNIQUE KEY
    )

    # Group files by type for quick filtering
    groups = {"HTML/CSS/JS": [], "Python": [], "Other": []}
    for f in files:
        ext = f.suffix.lower()
        if ext in {".html", ".css", ".js"}:
            groups["HTML/CSS/JS"].append(f)
        elif ext == ".py":
            groups["Python"].append(f)
        else:
            groups["Other"].append(f)

    tabs = st.tabs(["All", "HTML/CSS/JS", "Python", "Other"])

    def render_file_list(target_files, container, key_prefix: str):
        for f in target_files:
            rel = f.relative_to(GENERATED_DIR)
            with container.expander(f"📄 {rel}", expanded=False):
                # Read file bytes
                try:
                    data = f.read_bytes()
                except Exception as e:
                    st.error(f"Unable to read: {e}")
                    continue

                # Unique key per file per tab
                unique_key = f"dl-{key_prefix}-{rel.as_posix()}"

                st.download_button(
                    label=f"⬇️ Download {rel.name}",
                    data=data,
                    file_name=str(rel),
                    mime=mimetypes.guess_type(str(f))[0] or "application/octet-stream",
                    use_container_width=True,
                    key=unique_key,  # <-- UNIQUE KEY HERE
                )

                # Preview text-like files inline
                if is_text_like(f):
                    try:
                        text = data.decode("utf-8", errors="replace")
                        st.code(text, language=guess_language_for_code(f))
                    except Exception as e:
                        st.warning(f"Preview unavailable: {e}")
                else:
                    st.caption("Binary file (preview disabled).")

    # Render in each tab with distinct key_prefix values
    with tabs[0]:
        render_file_list(files, st, key_prefix="tab-all")
    with tabs[1]:
        render_file_list(groups["HTML/CSS/JS"], st, key_prefix="tab-web")
    with tabs[2]:
        render_file_list(groups["Python"], st, key_prefix="tab-py")
    with tabs[3]:
        render_file_list(groups["Other"], st, key_prefix="tab-other")
