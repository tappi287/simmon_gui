# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['simmon_watcher.py'],
             pathex=['I:\\Nextcloud\\py\\simmon_gui'],
             binaries=[],
             datas=[],
             hiddenimports=['pkg_resources.py2_warn', 'win32timezone', 'sqlalchemy.ext.baked', ],
             hookspath=[],
             runtime_hooks=[],
             excludes=['tk', 'tkinter', 'lib2to3', ],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='simmon_watcher',
          icon='./ui/sw_icon.ico',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=['cprocessors.cp38*.pyd', 'cresultproxy.cp38*.pyd', 'cutils.cp38*.pyd', '_sqlite3.pyd'],
               name='simmon_watcher')
