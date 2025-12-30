# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# List of data files to bundle (Source, Destination)
added_files = [
    ('templates', 'templates'),
    ('config.ini', '.'),
    ('vendedores_contato.csv', '.'),
    ('data', 'data'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'pandas', 
        'streamlit', 
        'plotly', 
        'matplotlib', 
        'sqlite_utils',
        'win32clipboard',
        'PIL'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RankingVendedores',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['templates/logo_empresa.png'] if os.path.exists('templates/logo_empresa.png') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RankingVendedoresBot',
)
