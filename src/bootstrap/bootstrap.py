# Copyright 2015-2016 The Rust Project Developers. See the COPYRIGHT
# file at the top-level directory of this distribution and at
# http://rust-lang.org/COPYRIGHT.
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import argparse
import contextlib
import os
import shutil
import subprocess
import sys
import tarfile

def get(url, path, verbose=False):
    print("downloading " + url)
    # see http://serverfault.com/questions/301128/how-to-download
    if sys.platform == 'win32':
        run(["PowerShell.exe", "/nologo", "-Command",
             "(New-Object System.Net.WebClient).DownloadFile('" + url +
                "', '" + path + "')"], verbose=verbose)
    else:
        run(["curl", "-o", path, url], verbose=verbose)

def unpack(tarball, dst, verbose=False, match=None):
    print("extracting " + tarball)
    fname = os.path.basename(tarball).replace(".tar.gz", "")
    with contextlib.closing(tarfile.open(tarball)) as tar:
        for p in tar.getnames():
            if "/" not in p:
                continue
            name = p.replace(fname + "/", "", 1)
            if match is not None and not name.startswith(match):
                continue
            name = name[len(match) + 1:]

            fp = os.path.join(dst, name)
            if verbose:
                print("  extracting " + p)
            tar.extract(p, dst)
            tp = os.path.join(dst, p)
            if os.path.isdir(tp) and os.path.exists(fp):
                continue
            shutil.move(tp, fp)
    shutil.rmtree(os.path.join(dst, fname))

def run(args, verbose=False):
    if verbose:
        print("running: " + ' '.join(args))
    sys.stdout.flush()
    # Use Popen here instead of call() as it apparently allows powershell on
    # Windows to not lock up waiting for input presumably.
    ret = subprocess.Popen(args)
    code = ret.wait()
    if code != 0:
        if not verbose:
            print("failed to run: " + ' '.join(args))
        raise RuntimeError("failed to run command")

class RustBuild:
    def download_rust_nightly(self):
        cache_dst = os.path.join(self.build_dir, "cache")
        rustc_cache = os.path.join(cache_dst, self.snap_rustc_date())
        cargo_cache = os.path.join(cache_dst, self.snap_cargo_date())
        if not os.path.exists(rustc_cache):
            os.makedirs(rustc_cache)
        if not os.path.exists(cargo_cache):
            os.makedirs(cargo_cache)

        if self.rustc().startswith(self.bin_root()) and \
           (not os.path.exists(self.rustc()) or self.rustc_out_of_date()):
            filename = "rust-std-nightly-" + self.build + ".tar.gz"
            url = "https://static.rust-lang.org/dist/" + self.snap_rustc_date()
            tarball = os.path.join(rustc_cache, filename)
            if not os.path.exists(tarball):
                get(url + "/" + filename, tarball, verbose=self.verbose)
            unpack(tarball, self.bin_root(),
                   match="rust-std-" + self.build,
                   verbose=self.verbose)

            filename = "rustc-nightly-" + self.build + ".tar.gz"
            url = "https://static.rust-lang.org/dist/" + self.snap_rustc_date()
            tarball = os.path.join(rustc_cache, filename)
            if not os.path.exists(tarball):
                get(url + "/" + filename, tarball, verbose=self.verbose)
            unpack(tarball, self.bin_root(), match="rustc", verbose=self.verbose)
            with open(self.rustc_stamp(), 'w') as f:
                f.write(self.snap_rustc_date())

        if self.cargo().startswith(self.bin_root()) and \
           (not os.path.exists(self.cargo()) or self.cargo_out_of_date()):
            filename = "cargo-nightly-" + self.build + ".tar.gz"
            url = "https://static.rust-lang.org/cargo-dist/" + self.snap_cargo_date()
            tarball = os.path.join(cargo_cache, filename)
            if not os.path.exists(tarball):
                get(url + "/" + filename, tarball, verbose=self.verbose)
            unpack(tarball, self.bin_root(), match="cargo", verbose=self.verbose)
            with open(self.cargo_stamp(), 'w') as f:
                f.write(self.snap_cargo_date())

    def snap_cargo_date(self):
        return self._cargo_date

    def snap_rustc_date(self):
        return self._rustc_date

    def rustc_stamp(self):
        return os.path.join(self.bin_root(), '.rustc-stamp')

    def cargo_stamp(self):
        return os.path.join(self.bin_root(), '.cargo-stamp')

    def rustc_out_of_date(self):
        if not os.path.exists(self.rustc_stamp()):
            return True
        with open(self.rustc_stamp(), 'r') as f:
            return self.snap_rustc_date() != f.read()

    def cargo_out_of_date(self):
        if not os.path.exists(self.cargo_stamp()):
            return True
        with open(self.cargo_stamp(), 'r') as f:
            return self.snap_cargo_date() != f.read()

    def bin_root(self):
        return os.path.join(self.build_dir, self.build, "stage0")

    def get_toml(self, key):
        for line in self.config_toml.splitlines():
            if line.startswith(key + ' ='):
                return self.get_string(line)
        return None

    def get_mk(self, key):
        for line in iter(self.config_mk.splitlines()):
            if line.startswith(key):
                return line[line.find(':=') + 2:].strip()
        return None

    def cargo(self):
        config = self.get_toml('cargo')
        if config:
            return config
        return os.path.join(self.bin_root(), "bin/cargo" + self.exe_suffix())

    def rustc(self):
        config = self.get_toml('rustc')
        if config:
            return config
        config = self.get_mk('CFG_LOCAL_RUST')
        if config:
            return config + '/bin/rustc' + self.exe_suffix()
        return os.path.join(self.bin_root(), "bin/rustc" + self.exe_suffix())

    def get_string(self, line):
        start = line.find('"')
        end = start + 1 + line[start+1:].find('"')
        return line[start+1:end]

    def exe_suffix(self):
        if sys.platform == 'win32':
            return '.exe'
        else:
            return ''

    def parse_nightly_dates(self):
        nightlies = os.path.join(self.rust_root, "src/nightlies.txt")
        with open(nightlies, 'r') as nightlies:
            rustc, cargo = nightlies.read().split("\n")[:2]
            assert rustc.startswith("rustc: ")
            assert cargo.startswith("cargo: ")
            self._rustc_date = rustc[len("rustc: "):]
            self._cargo_date = cargo[len("cargo: "):]

    def build_bootstrap(self):
        env = os.environ.copy()
        env["CARGO_TARGET_DIR"] = os.path.join(self.build_dir, "bootstrap")
        env["RUSTC"] = self.rustc()
        env["LD_LIBRARY_PATH"] = os.path.join(self.bin_root(), "lib")
        env["DYLD_LIBRARY_PATH"] = os.path.join(self.bin_root(), "lib")
        env["PATH"] = os.path.join(self.bin_root(), "bin") + \
                      os.pathsep + env["PATH"]
        self.run([self.cargo(), "build", "--manifest-path",
                  os.path.join(self.rust_root, "src/bootstrap/Cargo.toml")],
                 env)

    def run(self, args, env):
        proc = subprocess.Popen(args, env = env)
        ret = proc.wait()
        if ret != 0:
            sys.exit(ret)

    def build_triple(self):
        config = self.get_toml('build')
        if config:
            return config
        config = self.get_mk('CFG_BUILD')
        if config:
            return config
        try:
            ostype = subprocess.check_output(['uname', '-s']).strip()
            cputype = subprocess.check_output(['uname', '-m']).strip()
        except FileNotFoundError:
            if sys.platform == 'win32':
                return 'x86_64-pc-windows-msvc'
            else:
                raise

        # Darwin's `uname -s` lies and always returns i386. We have to use
        # sysctl instead.
        if ostype == 'Darwin' and cputype == 'i686':
            sysctl = subprocess.check_output(['sysctl', 'hw.optional.x86_64'])
            if sysctl.contains(': 1'):
                cputype = 'x86_64'

        # The goal here is to come up with the same triple as LLVM would,
        # at least for the subset of platforms we're willing to target.
        if ostype == 'Linux':
            ostype = 'unknown-linux-gnu'
        elif ostype == 'FreeBSD':
            ostype = 'unknown-freebsd'
        elif ostype == 'DragonFly':
            ostype = 'unknown-dragonfly'
        elif ostype == 'Bitrig':
            ostype = 'unknown-bitrig'
        elif ostype == 'OpenBSD':
            ostype = 'unknown-openbsd'
        elif ostype == 'NetBSD':
            ostype = 'unknown-netbsd'
        elif ostype == 'Darwin':
            ostype = 'apple-darwin'
        elif ostype.startswith('MINGW'):
            # msys' `uname` does not print gcc configuration, but prints msys
            # configuration. so we cannot believe `uname -m`:
            # msys1 is always i686 and msys2 is always x86_64.
            # instead, msys defines $MSYSTEM which is MINGW32 on i686 and
            # MINGW64 on x86_64.
            ostype = 'pc-windows-gnu'
            cputype = 'i686'
            if os.environ.get('MSYSTEM') == 'MINGW64':
                cputype = 'x86_64'
        elif ostype.startswith('MSYS'):
            ostype = 'pc-windows-gnu'
        elif ostype.startswith('CYGWIN_NT'):
            cputype = 'i686'
            if ostype.endswith('WOW64'):
                cputype = 'x86_64'
            ostype = 'pc-windows-gnu'
        else:
            raise ValueError("unknown OS type: " + ostype)

        if cputype in {'i386', 'i486', 'i686', 'i786', 'x86'}:
            cputype = 'i686'
        elif cputype in {'xscale', 'arm'}:
            cputype = 'arm'
        elif cputype == 'armv7l':
            cputype = 'arm'
            ostype += 'eabihf'
        elif cputype == 'aarch64':
            cputype = 'aarch64'
        elif cputype in {'powerpc', 'ppc', 'ppc64'}:
            cputype = 'powerpc'
        elif cputype in {'amd64', 'x86_64', 'x86-64', 'x64'}:
            cputype = 'x86_64'
        else:
            raise ValueError("unknown cpu type: " + cputype)

        return cputype + '-' + ostype

parser = argparse.ArgumentParser(description='Build rust')
parser.add_argument('--config')
parser.add_argument('-v', '--verbose', action='store_true')

args = [a for a in sys.argv if a != '-h']
args, _ = parser.parse_known_args(args)

# Configure initial bootstrap
rb = RustBuild()
rb.config_toml = ''
rb.config_mk = ''
rb.rust_root = os.path.abspath(os.path.join(__file__, '../../..'))
rb.build_dir = os.path.join(os.getcwd(), "build")
rb.verbose = args.verbose

try:
    with open(args.config or 'config.toml') as config:
        rb.config_toml = config.read()
except:
    pass
try:
    rb.config_mk = open('config.mk').read()
except:
    pass

# Fetch/build the bootstrap
rb.build = rb.build_triple()
rb.parse_nightly_dates()
rb.download_rust_nightly()
sys.stdout.flush()
rb.build_bootstrap()
sys.stdout.flush()

# Run the bootstrap
args = [os.path.join(rb.build_dir, "bootstrap/debug/bootstrap")]
args.extend(sys.argv[1:])
args.append('--src')
args.append(rb.rust_root)
args.append('--build')
args.append(rb.build)
env = os.environ.copy()
env["BOOTSTRAP_PARENT_ID"] = str(os.getpid())
rb.run(args, env)
