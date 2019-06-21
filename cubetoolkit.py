# encoding: utf-8

import os
import re
import io
import sys
import string
import random
import tarfile
import fnmatch
import operator
import mimetypes
import itertools
import subprocess

from datetime import datetime
from distutils.version import LooseVersion
from contextlib import contextmanager

import argh
import requests

from redbaron import RedBaron

INSTANCES_PATH = os.path.expanduser("~/etc/cubicweb.d/")


def _get_python_files(path="."):
    python_files = []

    all_hg_files = subprocess.check_output(
        "hg status -A", shell=True, cwd=path).decode().split("\n")
    tracked_files = [x.split(" ", 1)[1] for x in all_hg_files if x.startswith("C ")]

    tracked_files = filter(None, tracked_files)

    for file in tracked_files:
        file = os.path.join(path, file)
        if file.endswith(".py"):
            python_files.append(file)
        elif os.path.isdir(file):
            continue
        elif "." not in file:
            try:
                is_python_script = "python script" in subprocess.check_output(["file", file]).lower()
            except Exception as e:
                print("Warning: could launch the 'file' command on %s (to check if it's a python script) because of %s" % e)
            else:
                if is_python_script:
                    python_files.append(file)

    return python_files


@contextmanager
def cd(newdir):
    """ Custom change directory command. """
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def print_warning(msg):
    """ Custom print coloring printed message. """
    print('\x1b[1;33;40m %s \x1b[0m' % msg)


def _dtnm(path):
    """ Returns a list of folders to not move. """

    folders_not_to_move = []
    for root, dirs, files in os.walk(path):
        for d in ['bin', 'debian', 'test', '.hg', '.tox', 'cubicweb_*']:
            for folder in fnmatch.filter(dirs, d):
                folders_not_to_move.append(folder)
        break
    return folders_not_to_move


def _ftnm(path):
    """ Returns a list of files to not move. """

    files_not_to_move = []
    for root, dirs, files in os.walk(path):
        for f in ['setup.py', 'README', '*.ini', 'MANIFEST.in',
                  '*.txt', '*.spec', '.hgtags', '.hgrc', 'test*']:
            for filename in fnmatch.filter(files, f):
                files_not_to_move.append(filename)
        break
    return files_not_to_move


def create_cube_folder(path, cube_root, cube_folder):
    """ Creates the cube folder. """

    with cd(path):
        try:
            if not os.path.exists(cube_folder):
                os.makedirs(cube_folder)
                print_warning('Info: %s successfully created' % cube_folder)
                return cube_folder
            else:
                print_warning('Error: %s already exists.' % cube_folder)
        except OSError:
            print_warning('Error: Creating directory %s.' % cube_folder)


def update_pkginfo(pkginfo):
    """ Update __pkginfo__.py content. """

    # retrieve numversion, depends, recommends
    __pkginfo__ = {}
    with open(pkginfo, "r") as f:
        exec(f.read(), __pkginfo__)

    context = {
        'numversion': __pkginfo__['numversion'],
        'cubename': os.path.split(pkginfo)[0],
        'distname': 'cubicweb-' + os.path.split(pkginfo)[0],
        'license': __pkginfo__['license'],
        'author': __pkginfo__['author'],
        'author-email': __pkginfo__['author_email'],
        'shortdesc': __pkginfo__['description'],
        'dependencies': __pkginfo__['__depends__'],
    }

    if '__recommends__' in __pkginfo__:
        context['__recommends__'] = __pkginfo__['__recommends__']

    command = "hg rm %s" % pkginfo
    subprocess.Popen(command, shell=True).wait()

    url = "https://hg.logilab.org/master/cubicweb/raw-file/tip/cubicweb/skeleton/cubicweb_CUBENAME/__pkginfo__.py.tmpl"

    response = requests.get(url)
    with open(pkginfo, 'w') as out:
        template = response.content.decode()
        new_pkginfo = template % context
        new_pkginfo = new_pkginfo.split('\n')

        for l in new_pkginfo:
            if "numversion" in l:
                l = re.sub(r"^numversion ?= ?.*$", "numversion = %s" % (context['numversion'],), l)
            # if '>= ' in l: # not sure how to update cubicweb version to 3.24
            #     l = re.sub(r"'^.*cubicweb' ?: ?'>?= ?'\d{1}\.\d{1}\.\d{1}',?.*", "'cubicweb': '>= 3.24.0'", l)
            out.write(l + '\n')

    command = "hg add %s" % pkginfo
    subprocess.Popen(command, shell=True).wait()
    print_warning('Info: Successfully updated __pkginfo__.py.')


def move_cube_files(path, cube_root, cube_folder):
    """ Move cube files from root to cube folder. """

    ftnm = _ftnm(cube_root)
    dtnm = _dtnm(cube_root)
    cf = []

    for root, dirs, files in os.walk(path):
        for filename in files:
            if fnmatch.fnmatch(filename, '__pkginfo__.py'):
                update_pkginfo(os.path.join(path, filename))
            if filename not in ftnm:
                cf.append(filename)

        for dirname in dirs:
            if dirname not in dtnm:
                cf.append(dirname)
        break  # we just need level 1 walk

    with cd(path):
        for i in cf:
            command = "hg mv %s %s" % (i, cube_folder)
            subprocess.Popen(command, shell=True).wait()

    print_warning('Info: cube files successfully moved into %s' % cube_root)


def replace_cube_file(path, cube_root, filename):
    """ Delete & replace files that needs to be rewritten using the skeleton. """

    with cd(path):
        command = "hg rm %s" % filename
        subprocess.Popen(command, shell=True).wait()

        url = "https://hg.logilab.org/master/cubicweb/raw-file/tip/cubicweb/skeleton/%s.tmpl" % filename
        context = {'cubename': cube_root, 'distname': 'cubicweb-' + cube_root}
        response = requests.get(url)
        with open(filename, 'w') as out:
            template = response.content.decode()
            out.write(template % context)

            command = "hg add %s" % filename
            subprocess.Popen(command, shell=True).wait()
            print_warning('Info: %s successfully updated' % filename)


def remove_useless_files(cube_root):
    """ Remove all the files that are no more used. """

    with cd(cube_root):
        for filename in ['apycot.ini', 'pytestconf.py']:
            command = "hg rm %s" % filename
            subprocess.Popen(command, shell=True).wait()
            print_warning('Info: %s successfully removed' % filename)


def fix_unittest_import(path, filename):
    """ Make sure we use unittest from standard lib."""
    with cd(path):
        content = []
        with open(filename, 'r') as f:
            content = f.readlines()

        with open(filename, 'w') as f:
            for l in content:
                if "unittest_main" in l:
                    l = re.sub(r"^from logilab\.common\.testlib import unittest_main$", r"import unittest", l)
                    l = re.sub(r"^    from logilab\.common\.testlib import unittest_main$", r"    import unittest", l)
                    l = re.sub(r"^    unittest_main\(\)$", "    unittest.main()", l)
                f.write(l)


def fix_cube_import(cube_root, filename):
    """ Make sure we import cube using new layout."""
    with cd(cube_root):
        content = []
        with open(filename, 'r') as f:
            content = f.readlines()

        with open(filename, 'w') as f:
            for l in content:
                if "cubes." in l:
                    l = re.sub(r"", r"", l)
                    f.write(l)


def to_newstyle_cube(path):
    "Upgrade oldstyle CW cube to newstyle"
    path = os.path.realpath(os.path.expanduser(path))

    if not os.path.exists(path):
        print("Error: '%s' doesn't exist" % path)
        sys.exit(1)

    cube_root = os.path.basename(path)
    cube_folder = 'cubicweb_%s' % cube_root

    # setup.py and MANIFEST.in can just be replaced
    for i in ['setup.py', 'MANIFEST.in', 'tox.ini']:
        replace_cube_file(path, cube_root, i)

    create_cube_folder(path, cube_root, cube_folder)
    move_cube_files(path, cube_root, cube_folder)

    py_files = _get_python_files(path)
    # remove_useless_files

    for f in py_files:
        fix_unittest_import(path, f)
        # fix_cubes_import
        # automatically call autopep8?


def find_pkginfo(path):
    dirs = os.listdir(path)

    if "__pkginfo__.py" in dirs:
        return os.path.join(path, "__pkginfo__.py")

    cube_subdirs = [os.path.join(path, x) for x in dirs if os.path.isdir(x) and x.startswith("cubicweb_")]

    if not cube_subdirs:
        print("Couldn't find the __pkginfo__.py file :(")
        sys.exit(1)

    for subdir in cube_subdirs:
        if "__pkginfo__.py" in os.listdir(subdir):
            return os.path.join(subdir, "__pkginfo__.py")

    print("Couldn't find the __pkginfo__.py file :(")
    sys.exit(1)


def parse_pkginfo(path):
    red = RedBaron(open(path, "r").read())

    depends = red.find("assign", lambda x: x.target.value == "__depends__")

    if not depends:
        print("I couldn't find __depends__ in the __pkginfo__.py :(")
        sys.exit(1)

    assert depends.value.type == "dict"

    # oupsi I'm lazy, it's bad :(
    # XXX use to_python() somehow
    return eval(depends.value.dumps()), red, depends


def merge_depends_with_pypi_info(depends):
    new_depends = {}

    for key, value in depends.items():
        pkg_name = key.split("[", 1)[0]

        print("Get all releases of %s..." % pkg_name)
        response = requests.get("https://pypi.org/pypi/%s/json" % pkg_name, timeout=30)
        if response.status_code == 404:
            print("Warning: %s doesn't exist on pypi, skip it" % pkg_name)
            continue

        data = response.json()

        all_versions = []

        for key2, value2 in data["releases"].items():
            # sometime we don't have metadata information for a release :|
            all_versions.append(value2[0] if value2 else {})
            all_versions[-1]["version"] = key2

        new_depends[key] = {
            "pkg_name": pkg_name,
            "current_version_scheme": value,
            "all_versions": all_versions
        }

    return new_depends


def filter_pkg_that_can_be_upgraded(depends):
    no_upgrades = []
    new_depends = {}

    for key, value in depends.items():
        conditions = parse_conditions(value["current_version_scheme"])

        if conditions is None:
            print("No specified version for %s, drop it" % key)
            continue

        compatible_versions = value["all_versions"]

        for (op, version) in conditions:
            compatible_versions = [x for x in compatible_versions if op(LooseVersion(x["version"]), LooseVersion(version))]

        maximum_version = list(sorted(compatible_versions, key=lambda x: LooseVersion(x["version"])))[-1]
        all_versions_sorted = sorted(value["all_versions"], key=lambda x: LooseVersion(x["version"]))
        possible_upgrades = list(itertools.dropwhile(lambda x: LooseVersion(x["version"]) <= LooseVersion(maximum_version["version"]), all_versions_sorted))

        if possible_upgrades:
            new_depends[key] = value
            new_depends[key]["possible_upgrades"] = possible_upgrades
        else:
            no_upgrades.append(key)

    if no_upgrades:
        print("Skipped packages that don't need to be upgraded: %s" % (", ".join(no_upgrades)))

    if new_depends:
        print("")
        print("Packages that can upgrades with all those available verisons:")
        for key, value in new_depends.items():
            print("* %s (%s) to %s" % (key, value["current_version_scheme"], ", ".join(map(lambda x: x["version"], value["possible_upgrades"]))))

    return new_depends


def parse_conditions(conditions):
    string_to_operator = {
        "==": operator.eq,
        "<": operator.lt,
        "<=": operator.le,
        "!=": operator.ne,
        ">=": operator.ge,
        ">": operator.gt,
    }

    parsed_conditions = []

    if not conditions:
        return None

    for i in conditions.split(","):
        version_operator, version_number = re.match("(==|>=|<=|>|<) *([0-9.]*)", i.strip()).groups()

        parsed_conditions.append([
            string_to_operator[version_operator],
            version_number,
        ])

    return parsed_conditions


def try_to_upgrade_dependencies(test_command, depends, pkginfo_path, red, red_depends):
    def change_dependency_version_on_disk(entry, value):
        entry.value = ("'== %s'" % value).encode("Utf-8")

        dumps = red.dumps()
        with open(pkginfo_path, "w") as pkginfo_file:
            pkginfo_file.write(dumps)

    def hg_commit(key, before, after):
        commit_message = "[enh] upgrade %s from '%s' to '== %s'" % (key, before, after)
        hg_commit_command = "hg commit -m \"%s\"" % commit_message
        print(hg_commit_command)
        subprocess.check_call(hg_commit_command, shell=True)

        return commit_message

    def launch_test_command(test_command, depend_key, before, after):
        print("starting test process '%s'..." % test_command)
        log_file_name = "autoupgradedependencies/%s/upgrade_%s_from_%s_to_%s.log" % (session_start_time,
                                                                                     depend_key, before, after)
        log_file_name = log_file_name.replace(" ", "")

        directory = os.path.split(log_file_name)[0]

        log_file_name = os.path.realpath(log_file_name)

        if not os.path.exists(directory):
            os.makedirs(directory)

        print("logging command output in %s" % log_file_name)
        test_process = subprocess.Popen(test_command,
                                        shell=True,
                                        bufsize=0,
                                        stdout=open(log_file_name, "w"),
                                        stderr=subprocess.STDOUT)

        # will return return_code
        return test_process.wait(), log_file_name

    def change_cubes_import_if_needed(cube_name, version_metadata):
        if "url" not in version_metadata:
            print("Warning: there is no distributions files for %s version %s, I can't check if the cube format has changed" % (version_metadata["version"]))

        cube_name = cube_name.split("-")[1]

        url = version_metadata["url"]

        archive = tarfile.open(fileobj=requests.get(url, stream=True).raw, mode="r|*")

        directories = [x.name.split("/", 1)[1] for x in archive.getmembers() if x.isdir() and "/" in x.name]

        # this is still the old format
        if ("cubicweb_%s" % cube_name) not in directories:
            print("(cube %s is still in old format)" % cube_name)
            return

        pattern = "from cubes.%s" % cube_name

        # lazy way for now, should use redbaron
        for python_file in _get_python_files():
            with open(python_file, "r") as text:
                text = text.read()

                if pattern in text:
                    with open(python_file, "w") as to_modify:
                        print("* change import to new format for cube %s in %s" % (cube_name, python_file))
                        text = text.replace(pattern, "from cubicweb_%s" % cube_name)
                        to_modify.write(text)

    # start with cubes
    cubes = filter(lambda x: x[0].startswith("cubicweb-"), depends.items())
    not_cubes = filter(lambda x: not x[0].startswith("cubicweb-"), depends.items())

    session_start_time = datetime.now().strftime("%F-%X")

    summary = {
        "full_success": [],
        "partial_success": [],
        "total_failure": [],
        "commits": [],
    }

    for depend_key, depend_data in itertools.chain(cubes, not_cubes):
        is_a_cube = depend_key.startswith("cubicweb-")

        entry = red_depends.value.filter(lambda x: hasattr(x, "key") and x.key.to_python() == depend_key)[0]

        initial_value = entry.value.copy()

        max_possible_value = depend_data["possible_upgrades"][-1]["version"]

        print("")
        print("Upgrading %s to %s" % (depend_key, max_possible_value))
        change_dependency_version_on_disk(entry, max_possible_value)

        if is_a_cube:
            change_cubes_import_if_needed(depend_key, depend_data["possible_upgrades"][-1])

        pid, log_file_name = launch_test_command(test_command, depend_key, initial_value.to_python(), max_possible_value)
        if pid == 0:
            print("Success for upgrading %s to %s!" % (depend_key, max_possible_value))
            summary["commits"].append(hg_commit(depend_key, initial_value.to_python(), max_possible_value))

            summary["full_success"].append({
                "dependency": depend_key,
                "from": initial_value.to_python(),
                "to": max_possible_value,
                "log_file_name": log_file_name,
            })

        elif len(depend_data["possible_upgrades"]) > 1:
            print("Failure when upgrading %s to %s, switch to version per version strategy" % (depend_key, max_possible_value))

            subprocess.check_call("hg revert -a --no-backup", shell=True)

            previous_version = None
            previous_version_metadata = None

            for number, version_metadata in enumerate(depend_data["possible_upgrades"][:-1]):
                version = version_metadata["version"]

                print("")
                print("trying %s to %s" % (depend_key, version))
                change_dependency_version_on_disk(entry, version)

                if is_a_cube:
                    change_cubes_import_if_needed(depend_key, version_metadata)

                pid, log_file_name = launch_test_command(test_command, depend_key, initial_value.to_python(), version)
                if pid == 0:
                    print("Success on %s for version %s! Continue to next version" % (depend_key, version))
                    previous_version = version
                    previous_version_metadata = version_metadata
                elif previous_version:
                    print("Failure when upgrading %s to %s, %s is the maximum upgradable version" % (depend_key, version, previous_version))

                    change_dependency_version_on_disk(entry, previous_version)

                    if is_a_cube:
                        change_cubes_import_if_needed(depend_key, previous_version_metadata)

                    summary["commits"].append(hg_commit(depend_key, initial_value.to_python(), version))

                    summary["partial_success"].append({
                        "dependency": depend_key,
                        "from": initial_value.to_python(),
                        "to": version,
                        "log_file_name": log_file_name,
                        "possible_upgrades": depend_data["possible_upgrades"][number:],
                    })

                    break
                else:
                    print("Failure when upgrading %s to any version, it's not upgradable :(" % (depend_key))

                    entry.value = initial_value
                    subprocess.check_call("hg revert -a --no-backup", shell=True)

                    summary["total_failure"].append({
                        "dependency": depend_key,
                        "from": initial_value.to_python(),
                        "log_file_name": log_file_name,
                        "possible_upgrades": depend_data["possible_upgrades"],
                    })

                    break
            # we haven't break
            # yes this python syntaxe is horrible
            else:
                print("Actually it's the last compatible versions before the buggy %s" % max_possible_value)
                # should already be done
                # change_dependency_version_on_disk(entry, previous_version)

                summary["commits"].append(hg_commit(depend_key, initial_value.to_python(), version))

                summary["partial_success"].append({
                    "dependency": depend_key,
                    "from": initial_value.to_python(),
                    "to": version,
                    "log_file_name": log_file_name,
                    "possible_upgrades": depend_data["possible_upgrades"][-1:],
                })

        else:
            print("Failure when upgrading %s to %s, fail back to previous value :(" % (depend_key, max_possible_value))
            entry.value = initial_value

            subprocess.check_call("hg revert -a --no-backup", shell=True)

            summary["total_failure"].append({
                "dependency": depend_key,
                "from": initial_value.to_python(),
                "log_file_name": log_file_name,
                "possible_upgrades": [],
            })

    print("")
    print("Summary of execution")
    print("====================")

    if summary["full_success"]:
        print("")
        print("Successful upgrade to latest version:")

        for i in summary["full_success"]:
            print("* %s from '%s' to %s, log: %s" % (i["dependency"], i["from"], i["to"], i["log_file_name"]))

    if summary["partial_success"]:
        print("")
        print("Upgraded to a more up to date version but fail to upgrade to the latest one:")

        for i in summary["full_success"]:
            print("* %s from '%s' to %s, newest versions: %s, log: %s" % (i["dependency"],
                                                                          i["from"], i["to"],
                                                                          map(lambda x: x.vstring, i["possible_upgrades"]),
                                                                          i["log_file_name"]))

    if summary["total_failure"]:
        print("")
        print("Totally fail to upgrade to any version")

        for i in summary["total_failure"]:
            print("* %s, possible upgrades: %s, log: %s" % (i["dependency"], i["from"],
                                                            map(lambda x: x.vstring, i["possible_upgrades"]),
                                                            i["log_file_name"]))

    print("")
    if summary["commits"]:
        print("Generated commits:")
        for i in summary["commits"]:
            print("* %s" % i)
    else:
        print("Not commits.")

    print("")
    print("All log files are located in %s" % os.path.split(log_file_name)[0])


def autoupgradedependencies(test_command):
    if test_command.strip().startswith("tox") and "--recreate" not in test_command:
        print("WARNING: if you are using tox you very likely want to put '--recreate' in the command")

    if subprocess.check_output(["hg", "diff"]) != '':
        print("ERROR: according to 'hg diff' repository is not clean, abort")
        sys.exit(1)

    path = "."
    path = os.path.realpath(os.path.expanduser(path))

    pkginfo_path = find_pkginfo(path)
    print("Foudn __pkginfo__.py: %s" % pkginfo_path)

    depends, red, red_depends = parse_pkginfo(pkginfo_path)
    cubes = [x for x in depends if x.startswith("cubicweb-")]

    print("")

    if cubes:
        sys.stdout.write("Found cubes:\n* ")
        print("\n* ".join(cubes))
    else:
        print("This cube doesn't depends on other cubes")

    print("")

    depends = merge_depends_with_pypi_info(depends)

    print("")

    depends = filter_pkg_that_can_be_upgraded(depends)

    if not depends:
        print("")
        print("Nothing to do, everything is up to date")
        sys.exit(0)

    try_to_upgrade_dependencies(test_command, depends, pkginfo_path, red, red_depends)


def generate_secure_random():
    charset = string.digits + string.letters
    random_generator = random.SystemRandom()

    return "".join([random_generator.choice(charset) for _ in range(50)])


def list_instances():
    instances = []

    for directory in os.listdir(INSTANCES_PATH):
        full_path = os.path.join(INSTANCES_PATH, directory)

        if os.path.isdir(full_path):
            instances.append(directory)

    return instances


PYRAMID_INI_TEMPLATE = """\
[main]

cubicweb.session.secret = SECRET_1
cubicweb.auth.authtkt.session.secret = SECRET_2
cubicweb.auth.authtkt.persistent.secret = SECRET_3
cubicweb.auth.authtkt.session.secure = no
cubicweb.auth.authtkt.persistent.secure = no
"""


def generate_pyramid_ini(instance=None, force=False):
    pyramid_ini = (PYRAMID_INI_TEMPLATE.replace("SECRET_1", generate_secure_random())
                                       .replace("SECRET_2", generate_secure_random())
                                       .replace("SECRET_3", generate_secure_random()))
    if instance:
        all_instances = list_instances()

        if instance not in all_instances:
            print("ERROR: %s is not a valid instance name, available instances are: %s"
                  % (instance, ", ".join(all_instances)))
            sys.exit(1)

        pyramid_ini_path = os.path.join(INSTANCES_PATH, instance, "pyramid.ini")

        if not os.path.exists(pyramid_ini_path) or force:
            with open(pyramid_ini_path, "w") as f:
                f.write(pyramid_ini)
        else:
            print("ERROR: pyramid.ini file already exists at %s, use -f/--force if you want to overwrite it"
                  % pyramid_ini_path)

    else:
        print(pyramid_ini)


def generate_doc():
    if os.path.exists("doc"):
        print("'doc' dir already exist, abort")
        sys.exit(1)

    dirs = os.listdir(".")

    cube_subdirs = [os.path.join(".", x) for x in dirs if os.path.isdir(x)
                                                          and x.startswith("cubicweb_")
                                                          and "." not in x]

    if not cube_subdirs:
        print("Couldn't find the cube module :(")
        sys.exit(1)

    cube_subdir = cube_subdirs[0]
    cube_name = cube_subdir.split("_", 1)[1]

    doc_template_path = os.path.join(os.path.split(os.path.realpath(__file__))[0], "templates/doc/")

    os.makedirs("doc")
    os.makedirs("doc/_static")

    for i in os.listdir(doc_template_path):
        with open(os.path.join(doc_template_path, i), "r") as source:
            with open(os.path.join("doc", i), "w") as destination:
                destination.write(source.read().replace("CUBE_NAME", cube_name))

    subprocess.check_call(["sphinx-apidoc", cube_subdir, "-o", "doc"])

    print("Doc generate in 'doc' folder, do a 'pip install sphinx && pip install -e' in a virtualenv then 'make html' in the 'doc' folder and you'll have your doc built in doc/_build/html/index.html")
    print("If the __pkginfo__.py doesn't list all needed dependencies you might need to install more by hand.")
    print("Happy doc writting :)")


parser = argh.ArghParser()
parser.add_commands([generate_pyramid_ini, autoupgradedependencies, generate_doc, to_newstyle_cube])


def main():
    parser.dispatch()


if __name__ == '__main__':
    main()
