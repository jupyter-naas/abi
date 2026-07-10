# PyInstaller spec for ABI Desktop.
# Build with: pyinstaller abi-desktop.spec  (see build.md for the full recipe)

from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs

app_dir = Path(SPECPATH)  # noqa: F821

a = Analysis(  # noqa: F821
    [str(app_dir / "run.py")],
    pathex=[str(app_dir.parent)],
    binaries=collect_dynamic_libs("pyoxigraph"),
    datas=[
        (str(app_dir / "gui" / "web"), "desktop/gui/web"),
        (str(app_dir / "assets"), "desktop/assets"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "python_multipart",
        "multipart",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "numpy", "pandas", "matplotlib", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="abi-desktop",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="abi-desktop",
)

app = BUNDLE(  # noqa: F821
    coll,
    name="ABI Desktop.app",
    icon=str(app_dir / "assets" / "abi-desktop.icns"),
    bundle_identifier="ai.naas.abi.desktop",
    info_plist={
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
    },
)
