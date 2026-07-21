class Openagent < Formula
  desc "Open-source terminal agent — natural language to task execution"
  homepage "https://github.com/haseeb-heaven/open-agent"
  license "Apache-2.0"
  version "<VERSION>"

  on_macos do
    url "https://github.com/haseeb-heaven/open-agent/releases/download/v<VERSION>/openagent-macos-x64"
    sha256 "<SHA256_OF_MAC_BINARY>"
  end

  on_linux do
    url "https://github.com/haseeb-heaven/open-agent/releases/download/v<VERSION>/openagent-linux-x64"
    sha256 "<SHA256_OF_LINUX_BINARY>"
  end

  def install
    bin.install (OS.mac? ? "openagent-macos-x64" : "openagent-linux-x64") => "openagent"
  end

  test do
    system "#{bin}/openagent", "--version"
  end
end
