import argparse
import os
import sys
import re
import subprocess
from shutil import which
from pathlib import Path
from urllib.request import urlopen, Request
from urllib import error
import json

import jdk  # requires install-jdk package

mvn_repo: str
homedir: Path

# https://www.zenrows.com/blog/urllib-headers
http_headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": "\"Google Chrome\";v=\"123\", \"Not:A-Brand\";v=\"8\", \"Chromium\";v=\"123\"",
    "Referer":"https://www.google.com/",
    "Sec-Ch-Ua-Platform": "\"Windows\"",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}


def initialize_paths():
    global mvn_repo, homedir
    homedir = Path.home()
    mvn_repo = os.path.join(homedir, '.m2', 'repository', 'org', 'antlr', 'antlr4')


def latest_version():
    request = Request(
        url="https://central.sonatype.com/solrsearch/select?q=a:antlr4-master+g:org.antlr",
        headers=http_headers,
    )
    try:
        with urlopen(request, timeout=10) as response:
            s = response.read().decode("UTF-8")
            searchResult = json.loads(s)['response']
            # searchResult = s.json()['response']
            antlr_info = searchResult['docs'][0]
            # print(json.dump(searchResult))
            latest = antlr_info['latestVersion']
            return latest
    except (error.URLError, error.HTTPError, TimeoutError):
        print("Could not get latest version number, attempting to fall back to latest downloaded version...")
        version_dirs = list(filter(lambda directory: re.match(r"[0-9]+\.[0-9]+\.[0-9]+", directory), os.listdir(mvn_repo)))
        version_dirs.sort(reverse=True)
        if len(version_dirs) == 0:
            raise FileNotFoundError("Could not find a previously downloaded antlr4 jar")
        else:
            latest_version_dir = version_dirs.pop()
            print(f"Found version '{latest_version_dir}', this version may be out of date")
            return latest_version_dir


def antlr4_jar(version):
    jar = os.path.join(mvn_repo, version, f'antlr4-{version}-complete.jar')
    if not os.path.exists(jar):
        return download_antlr4(jar, version)
    return jar


def download_antlr4(jar, version):
    s = None
    request = Request(
        url=f"https://repo1.maven.org/maven2/org/antlr/antlr4/{version}/antlr4-{version}-complete.jar",
        headers=http_headers,
    )
    try:
        with urlopen(request, timeout=60) as response:
            print(f"Downloading antlr4-{version}-complete.jar")
            os.makedirs(os.path.join(mvn_repo, version), exist_ok=True)
            s = response.read()
    except (error.URLError, error.HTTPError, TimeoutError):
        print(f"Could not find antlr4-{version}-complete.jar at maven.org")

    if s is None:
        return None
    with open(jar, "wb") as f:
        f.write(s)
    return jar


def find_bin_dir(install_dir):
    for root, dirs, files in os.walk(install_dir):
        if root.endswith("bin"):
            return root
    return None


def install_jre(java_version='11'):
    USER_DIR = os.path.expanduser("~")
    JRE_DIR = os.path.join(USER_DIR, ".jre")
    if os.path.exists(JRE_DIR):
        for f in os.listdir(JRE_DIR):
            if f.startswith(f"jdk-{java_version}"):
                install_dir = os.path.join(JRE_DIR, f)
                bindir = find_bin_dir(install_dir)
                java = os.path.join(bindir, 'java')
                return java

    r = input(f"ANTLR tool needs Java to run; install Java JRE 11 yes/no (default yes)? ")
    if r.strip().lower() not in {'yes', 'y', ''}:
        exit(1)
    install_dir = jdk.install(java_version, jre=True)
    print(f"Installed Java in {install_dir}; remove that dir to uninstall")
    bindir = find_bin_dir(install_dir)
    if bindir is None:
        print(f"Can't find bin/java in {install_dir}; installation failed")
        return None
    java = os.path.join(bindir, 'java')
    return java


def install_jre_and_antlr(version):
    jar = antlr4_jar(version)
    java = which("java")
    if java is None:
        java = install_jre()
    if jar is None or java is None:
        exit(1)
    CHECK_JRE_VERSION = False
    if CHECK_JRE_VERSION:
        p = subprocess.Popen([java, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        out = out.decode("UTF-8").split('\n')[0]
        print(f"Running {out}")
    return jar, java


def process_args():
    parser = argparse.ArgumentParser(
        add_help=False, usage="%(prog)s [-v VERSION] [%(prog)s options]"
    )
    # Note, that the space after `-v` is needed, so we don't pick up other arguments beginning with `v`, like `-visitor`
    parser.add_argument("-v ", dest="version", default=None)
    args, unparsed_args = parser.parse_known_args()

    return unparsed_args, (
            args.version or os.environ.get("ANTLR4_TOOLS_ANTLR_VERSION") or latest_version()
    )


def run_cli(entrypoint):
    initialize_paths()
    args, version = process_args()
    jar, java = install_jre_and_antlr(version)

    cp = subprocess.run([java, '-cp', jar, entrypoint] + args)
    sys.exit(cp.returncode)


def tool():
    """Entry point to run antlr4 tool itself"""
    run_cli('org.antlr.v4.Tool')


def interp():
    """Entry point to run antlr4 profiling using grammar and input file"""
    run_cli('org.antlr.v4.gui.Interpreter')


if __name__ == '__main__':
    interp()
