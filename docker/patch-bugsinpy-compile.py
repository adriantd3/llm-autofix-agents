"""Patch bugsinpy-compile to batch pip installs instead of one-per-package.

Original: xargs -I {} pip install {} (92 processes, ~5 min)
Patched:  pip install -r <file>      (1 process,  ~30 s with cache)
"""
import pathlib

compile_script = pathlib.Path("/opt/bugsinpy/framework/bin/bugsinpy-compile")
src = compile_script.read_text()

old = (
    "sed -e '/^\\s*#.*$/d' -e '/^\\s*$/d' $work_dir/bugsinpy_requirements.txt"
    " | xargs -I {} pip install {}"
)
# --no-deps skips inter-package dependency resolution, which would fail on
# the intentionally-conflicting pinned versions in bugsinpy requirements files.
# All required packages are explicitly listed, so deps are already covered.
new = "pip install --no-deps -r $work_dir/bugsinpy_requirements.txt"

patched = src.replace(old, new)
assert patched != src, "Pattern not found in bugsinpy-compile — patch failed"
compile_script.write_text(patched)
print(f"Patched {src.count(old)} occurrence(s) in bugsinpy-compile")
