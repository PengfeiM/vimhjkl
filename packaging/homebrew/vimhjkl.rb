class Vimhjkl < Formula
  desc "Terminal trainer that drills advanced Vim techniques in real vim/nvim"
  homepage "https://github.com/S-Sigdel/vimhjkl"
  url "https://github.com/S-Sigdel/vimhjkl/archive/refs/tags/v0.2.0.tar.gz"
  sha256 "4fc539109894fd6d1b8c5b9616945389677d1154255071e377087b1d9dc4e45b"
  license "MIT"
  head "https://github.com/S-Sigdel/vimhjkl.git", branch: "master"

  depends_on "python@3.13"

  def install
    # vimhjkl is pure standard library with a __file__-relative data file
    # (vimhjkl/data/skills.json), so it needs no pip install, no build backend,
    # and no third-party packages. Drop the package under libexec and ship a
    # thin launcher that runs it with Homebrew's Python.
    libexec.install "src/vimhjkl"
    python = Formula["python@3.13"].opt_bin/"python3.13"
    (bin/"vimhjkl").write <<~SH
      #!/bin/bash
      export PYTHONPATH="#{libexec}${PYTHONPATH:+:$PYTHONPATH}"
      exec "#{python}" -m vimhjkl "$@"
    SH
    chmod 0755, bin/"vimhjkl"
  end

  def caveats
    <<~EOS
      Drills run inside a real editor — install one if you haven't:
        brew install neovim   # preferred
        brew install vim      # alternative
    EOS
  end

  test do
    # --list renders the curriculum without launching an editor.
    assert_match "curriculum", shell_output("#{bin}/vimhjkl --list")
  end
end
