"""    Creates python resource file for PyQt5 with pyrcc5"""import sysfrom pathlib import Pathfrom shlex import split as shell_syntaxfrom subprocess import runscripts_dir = Path(sys.executable).parent  # eg. C:/Python/Scriptspyside_rcc_path = scripts_dir / 'pyside2-rcc.exe'args = pyside_rcc_path.as_posix() + r" -no-compress -o gui_resource.py res.qrc"print(shell_syntax(args))run(shell_syntax(args), shell=True)sys.exit()