CubeToolkit
===========

CubeToolkit is a CLI toolkit to help with the development of
[CubicWeb](https://www.cubicweb.org/)'s cubes. The idea is to put mostly all
tools and scripts in the same place.

Installation
============

    pip install --user cubetoolkit

Available tools
===============

generate-pyramid-ini
--------------------

This tool generates the needed `pyramid.ini` file for instances using secure random generated secrets.

Usage:

    # this will print the generated file on the standard output
    cubetoolkit generate-pyramid-ini

    # this will put the file in the instance folder if not present
    cubetoolkit generate-pyramid-ini --instance instanceName
    # or
    cubetoolkit generate-pyramid-ini -i instanceName

    # this will in addition overwrite an existing pyramid.ini file
    cubetoolkit generate-pyramid-ini --instance instanceName -f

autoupgradedependencies
-----------------------

This tool is meant to upgrades the dependencies of a CubicWeb cube by parsing
its `__pkginfo__.py` and trying to upgrade each of its dependencies one by one
and running tests in the middle.

The algorithm is the following one:

* find `__pkginfo__.py` either in the root of the project or in `cubicweb_{project_name}`
* parse it, extract the values of `__depends__`
* merge those informations with pypi's one
* only keep the packages that can be upgraded
* for all upgradables cubes:
    * try to upgrade to the latest version
    * check if the cube has changed to a new-style cube
    * if so update the imports
    * run tests (a command provided by the user)
        * if the tests successed, commit
        * else, redo the previous step but next upgradable version by next upgradable version until you find the first buggy one, in the case the previous one is the good one, commit it
* redo the same operations for dependencies that aren't cube without the upgrade part
* display of summary of what has been done and which upgrades failed and point to their tests logs
* exit

Usage:

In the folder where the `.hg` is in a classic cube.

    cubetoolkit autoupgradedependencies "test command"

Examples:

    cubetoolkit autoupgradedependencies "tox -e py27 --recreate"
    cubetoolkit autoupgradedependencies "py.test tests"

generate-doc
------------

This tool will generate a base documentation for a cube using `sphinx-apidoc`
to expose the module content in the doc.

Only works for new-style cube.

Usage:

    # in the same directory that the cubicweb_$cube directory
    cubetoolkit generate-doc

to-newstyle-cube
----------------

This tool by nsukami will do /most/ of the work to migrate a cube in the
oldstyle format to the new one.

Usage:

    cubetoolkit to-newstyle-cube /path/to/cube
