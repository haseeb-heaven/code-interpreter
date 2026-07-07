## 2024-05-24 - Windows Command Injection via shell=True
**Vulnerability:** Command injection vulnerability in Windows file launch using \`subprocess.call(['start', filename], shell=True)\`.
**Learning:** Because Windows filenames can legally contain shell metacharacters like \`&\` and \`^\`, an \`os.path.isfile()\` check is insufficient to prevent command injection if \`shell=True\` is used.
**Prevention:** Always prefer using \`os.startfile(filename)\` over \`subprocess.call\` with \`shell=True\` when launching or opening files on Windows.
