import os
import sys
import argh
import requests
import decorator

from subprocess import check_call

from bs4 import BeautifulSoup

from cubetoolkit import functions as ctk_functions


CUBE_LIST_URL = "https://www.cubicweb.org/project?__fromnavigation=1&__force_display=1&vid=sameetypelist"
HG_CLONE_PATTERN = "hg clone http://hg.logilab.org/review/cubes/%s %s"

SPECIAL_CASES_CUBE_URL = {
    "linked-data-browser": "hg clone https://bitbucket.org/laurentw/logilab-cubicweb-client linked-data-browser",
    "mercurial-server": "hg clone http://hg.logilab.org/review/cubes/mercurial_server/ mercurial-server",
}

CUBES_SKIP = (
    'jsonschema', 'legacyui', 'aggregator', 'stdlib', 'imagesearch',
    'bookreader', 'externalauth', 'sitemaps', 'meeting'
)

# update
# shell
# all other commands of cubtk


def list_cube():
    soup = BeautifulSoup(requests.get(CUBE_LIST_URL).content, features="html.parser")

    cubes = []

    for i in soup.find("div", id="contentmain").ul("li", recursive=False):
        if not i.h3.text.startswith("cubicweb-"):
            continue

        cube = i.h3.text.split('-', 1)[1]

        if cube in CUBES_SKIP:
            continue

        cubes.append(cube)

    return cubes


def clone():
    cubes = list_cube()

    for cube in cubes:
        if os.path.exists(cube):
            print("Skip %s, already cloned" % cube)
            continue

        if cube in SPECIAL_CASES_CUBE_URL:
            clone_command = SPECIAL_CASES_CUBE_URL[cube]
        else:
            clone_command = HG_CLONE_PATTERN % (cube, cube)

        print("Clone %s cube" % cube)
        check_call(clone_command, shell=True)


@argh.named("exec")
def exec_command(command):
    cubes = list_cube()
    pwd = os.path.realpath(os.path.curdir)

    cubes_in_dir = any([os.path.exists(os.path.join(pwd, cube)) for cube in cubes])

    if not cubes_in_dir:
        print("Error: no cubes in current dirs")
        print("Download them using 'all-cubes clone'")
        sys.exit(1)

    for cube in cubes:
        path = os.path.join(pwd, cube)

        if not os.path.exists(path):
            print("Warning: cube '%s' dir isn't present, skip it" % cube)
            continue

        print("Run '%s' in %s cube" % (command, cube))
        print("======================================")
        check_call(command, cwd=path, shell=True)
        print("")
        print("")


def _wrap(function, *args, **kwargs):
    cubes = list_cube()
    pwd = os.path.realpath(os.path.curdir)

    cubes_in_dir = any([os.path.exists(os.path.join(pwd, cube)) for cube in cubes])

    if not cubes_in_dir:
        print("Error: no cubes in current dirs")
        print("Download them using 'all-cubes clone'")
        sys.exit(1)

    for cube in cubes:
        path = os.path.join(pwd, cube)

        if not os.path.exists(path):
            print("Warning: cube '%s' dir isn't present, skip it" % cube)
            continue

        os.chdir(path)

        print("Process cube '%s'" % (cube))
        print("=======================")
        function(*args, **kwargs)
        print("")
        print("")


def on_all_cubes(function):
    return decorator.decorate(function, _wrap)


functions = [clone, exec_command]

for function in ctk_functions:
    function_name = function.__name__

    wrapped_function = on_all_cubes(function)
    wrapped_function = argh.named(function_name.replace("_", "-"))(wrapped_function)

    functions.append(wrapped_function)

parser = argh.ArghParser()
parser.add_commands(functions)


def main():
    parser.dispatch()


if __name__ == '__main__':
    main()
