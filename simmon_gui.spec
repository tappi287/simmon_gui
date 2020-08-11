# -*- mode: python ; coding: utf-8 -*-
from shared_modules.globals import APP_NAME

block_cipher = None

simmon_files = [('license.txt', '.'),
                ('README.md', '.'),
                ('ui/*.py', 'ui'),
                ('ui/*.ui', 'ui'),
                ('ui/*.qrc', 'ui'),
                ('ui/*.html', 'ui'),
                ('migrate/*.*', 'migrate'),
                ('migrate/versions/*.*', 'migrate/versions'),
                ('alembic.ini', '.'),
                ('userdata/*.json', 'userdata'),
                ]

local_hooks = ['hooks']

a = Analysis(['simmon.py'],
             pathex=['I:\\Nextcloud\\py\\simmon_gui'],
             binaries=[],
             datas=simmon_files,
             hiddenimports=['pkg_resources.py2_warn', 'win32timezone', 'sqlalchemy.ext.baked'],
             hookspath=local_hooks,
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
          name=APP_NAME,
          icon='./ui/sm_icon.ico',
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
               upx=False,
               upx_exclude=['cprocessors.cp38*.pyd', 'cresultproxy.cp38*.pyd', 'cutils.cp38*.pyd', '_sqlite3.pyd',
                            'shiboken*.dll', 'python*.dll'],
               name=APP_NAME)
