Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "python main.py", 0, False
WScript.Sleep 1000
WshShell.Run "http://localhost:8001/", 1, False
