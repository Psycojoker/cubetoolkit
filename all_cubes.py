import os
import argh
import requests
from subprocess import check_call
from bs4 import BeautifulSoup


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


parser = argh.ArghParser()
parser.add_commands([clone])


def main():
    parser.dispatch()


if __name__ == '__main__':
    main()
