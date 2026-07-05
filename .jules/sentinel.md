## 2024-05-30 - Command Injection in Windows File Launch
**Vulnerability:** \`subprocess.call(['start', filename], shell=True)\` was used to open files on Windows, allowing arbitrary command execution if the filename contained shell metacharacters like \`&\` or \`^\`.
**Learning:** \`os.path.isfile()\` verification is insufficient to prevent command injection because Windows filenames can legally contain shell metacharacters.
**Prevention:** Use \`os.startfile()\` which executes the file natively without invoking \`cmd.exe\`.
